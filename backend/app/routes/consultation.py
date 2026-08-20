from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_module
from app.models import User
from app.models.email import EmailConfig
from app.models.consultation import (
    Consultation, ConsultationStatus, ConsultationCategory, DEFAULT_RESPONSE_DAYS,
)
from app.schemas.consultation import (
    ConsultationCreate, ConsultationUpdate, ConsultationResponse, ConsultationStats,
)
from app.services.email_service import queue_email, CATEGORY_LABELS_FR

router = APIRouter(prefix="/api/consultations", tags=["consultations"], dependencies=[Depends(require_module("consultations"))])

BUREAU_ROLES = {"president", "vice_president", "secretaire"}


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=422, detail="Date invalide (format ISO attendu)")


def _to_response(c: Consultation) -> dict:
    return {
        "id": c.id,
        "title": c.title,
        "category": c.category.value if c.category else ConsultationCategory.autre.value,
        "description": c.description,
        "status": c.status.value if c.status else ConsultationStatus.requested.value,
        "requested_at": c.requested_at.isoformat() if c.requested_at else None,
        "response_due": c.response_due.isoformat() if c.response_due else None,
        "direction_responded_at": c.direction_responded_at.isoformat() if c.direction_responded_at else None,
        "direction_response": c.direction_response,
        "created_by_name": c.created_by.full_name if c.created_by else None,
    }


@router.get("", response_model=list[ConsultationResponse])
def list_consultations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Toutes les consultations de l'organisation (visibles par les membres)."""
    rows = (
        db.query(Consultation)
        .filter(Consultation.organization_id == current_user.organization_id)
        .order_by(Consultation.requested_at.desc())
        .all()
    )
    return [_to_response(c) for c in rows]


@router.get("/stats", response_model=ConsultationStats)
def consultation_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Consultation)
        .filter(Consultation.organization_id == current_user.organization_id)
        .all()
    )
    now = datetime.utcnow()
    total = len(rows)
    pending = sum(1 for c in rows if c.status == ConsultationStatus.requested)
    overdue = sum(
        1 for c in rows
        if c.status == ConsultationStatus.requested
        and c.response_due is not None
        and c.response_due < now
    )
    received = sum(1 for c in rows if c.status == ConsultationStatus.response_received)
    closed = sum(1 for c in rows if c.status == ConsultationStatus.closed)
    return {"total": total, "pending": pending, "overdue": overdue, "received": received, "closed": closed}


@router.post("", response_model=ConsultationResponse, status_code=201)
def create_consultation(
    body: ConsultationCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Créer une consultation (réservé au bureau). Notifie la direction."""
    if current_user.delegue_role.value not in BUREAU_ROLES and current_user.role.value != "admin":
        raise HTTPException(
            status_code=403,
            detail="Seuls les membres du bureau peuvent créer une consultation",
        )

    due = _parse_dt(body.response_due)
    if due is None:
        days = DEFAULT_RESPONSE_DAYS.get(body.category)
        if days:
            due = datetime.utcnow() + timedelta(days=days)

    c = Consultation(
        organization_id=current_user.organization_id,
        created_by_id=current_user.id,
        title=body.title,
        category=body.category,
        description=body.description,
        response_due=due,
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    # Notification à la direction (réutilise l'outbox email existante)
    config = db.query(EmailConfig).filter(
        EmailConfig.organization_id == current_user.organization_id
    ).first()
    if config and config.enabled and config.direction_email:
        queue_email(
            db=db,
            org_id=current_user.organization_id,
            event_type="consultation_created",
            recipient_name="Direction",
            recipient_email=config.direction_email,
            lang="fr",
            ctx={
                "consultation_id": c.id,
                "title": c.title,
                "category": CATEGORY_LABELS_FR.get(c.category.value, c.category.value),
                "description": c.description or "",
                "response_due": due.isoformat() if due else None,
            },
        )
    return _to_response(c)


@router.patch("/{consultation_id}", response_model=ConsultationResponse)
def update_consultation(
    consultation_id: int,
    body: ConsultationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mettre à jour (bureau) : réponse de la direction, statut, échéance."""
    if current_user.delegue_role.value not in BUREAU_ROLES and current_user.role.value != "admin":
        raise HTTPException(
            status_code=403,
            detail="Seuls les membres du bureau peuvent mettre à jour une consultation",
        )

    c = (
        db.query(Consultation)
        .filter(
            Consultation.id == consultation_id,
            Consultation.organization_id == current_user.organization_id,
        )
        .first()
    )
    if not c:
        raise HTTPException(status_code=404, detail="Consultation non trouvée")

    if body.title is not None:
        c.title = body.title
    if body.category is not None:
        c.category = body.category
    if body.description is not None:
        c.description = body.description
    if body.response_due is not None:
        c.response_due = _parse_dt(body.response_due)
    if body.status is not None:
        new_status = ConsultationStatus(body.status)
        if new_status == ConsultationStatus.response_received:
            # Réponse motivée requise (L.414-1 : consultation = échange + réponse motivée)
            if not body.direction_response and not c.direction_response:
                raise HTTPException(
                    status_code=422,
                    detail="Une réponse motivée de l'employeur est requise pour clôturer la consultation",
                )
            c.direction_responded_at = datetime.utcnow()
        c.status = new_status
    if body.direction_response is not None:
        c.direction_response = body.direction_response

    db.commit()
    db.refresh(c)
    return _to_response(c)


@router.delete("/{consultation_id}", status_code=204)
def delete_consultation(
    consultation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Supprimer une consultation en attente (bureau uniquement)."""
    if current_user.delegue_role.value not in BUREAU_ROLES and current_user.role.value != "admin":
        raise HTTPException(
            status_code=403,
            detail="Seuls les membres du bureau peuvent supprimer une consultation",
        )
    c = (
        db.query(Consultation)
        .filter(
            Consultation.id == consultation_id,
            Consultation.organization_id == current_user.organization_id,
        )
        .first()
    )
    if not c:
        raise HTTPException(status_code=404, detail="Consultation non trouvée")
    if c.status == ConsultationStatus.closed:
        raise HTTPException(status_code=400, detail="Une consultation clôturée ne peut pas être supprimée")
    db.delete(c)
    db.commit()
