import base64
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User
from app.models.minute import Minute, MinuteSection, MinuteStatus, SectionVisibility
from app.models.meeting import Meeting
from app.schemas.minute import (
    MinuteResponse, CreateMinuteRequest, UpdateSectionsRequest,
    SectionSchema, PreviewSectionSchema, DirectionPreviewResponse,
)

router = APIRouter(tags=["minutes"])

BUREAU_ROLES = {"president", "vice_president", "secretaire"}


def _section_to_dict(s: MinuteSection) -> dict:
    return {
        "id": s.id,
        "position": s.position,
        "title": s.title,
        "visibility": s.visibility.value if s.visibility else "interne",
        "content": base64.b64encode(s.content).decode("ascii") if s.content else "",
    }


def _minute_to_response(m: Minute) -> dict:
    return {
        "id": m.id,
        "meeting_id": m.meeting_id,
        "status": m.status.value if m.status else "brouillon",
        "is_encrypted": m.is_encrypted,
        "created_by_id": m.created_by_id,
        "created_by_name": m.created_by.full_name if m.created_by else None,
        "validated_by_id": m.validated_by_id,
        "validated_by_name": m.validated_by.full_name if m.validated_by else None,
        "validated_at": m.validated_at,
        "created_at": m.created_at,
        "updated_at": m.updated_at,
        "sections": [_section_to_dict(s) for s in (m.sections or [])],
    }


def _projection_fingerprint(sections: list) -> list[tuple[int, str, bytes]]:
    """Représentation canonique de la version direction : liste ordonnée de
    (position renumérotée, title, content_bytes) pour les sections partagées.
    Utilisée à la fois par direction_preview (projection) et update_sections
    (comparaison avant/après) pour garantir qu'elles ne peuvent pas diverger."""
    partage = [s for s in sections if s.visibility == SectionVisibility.partage]
    return [(i, s.title, s.content) for i, s in enumerate(partage)]


# ── POST /api/meetings/{meeting_id}/minutes ────────────────────────


@router.post("/api/meetings/{meeting_id}/minutes", response_model=MinuteResponse, status_code=status.HTTP_201_CREATED)
def create_minute(
    meeting_id: int,
    body: CreateMinuteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Cloisonnement : vérifier que la réunion appartient à l'organisation de l'utilisateur
    meeting = (
        db.query(Meeting)
        .filter(Meeting.id == meeting_id, Meeting.organization_id == current_user.organization_id)
        .first()
    )
    if not meeting:
        raise HTTPException(status_code=404, detail="Réunion non trouvée")

    # Une réunion a au plus un PV
    existing = db.query(Minute).filter(Minute.meeting_id == meeting_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Un PV existe déjà pour cette réunion")

    minute = Minute(
        meeting_id=meeting_id,
        organization_id=current_user.organization_id,
        created_by_id=current_user.id,
    )
    db.add(minute)
    db.flush()

    for i, sec in enumerate(body.sections):
        content_bytes = base64.b64decode(sec.content) if sec.content else b""
        db.add(MinuteSection(
            minute_id=minute.id,
            position=sec.position if sec.position is not None else i,
            title=sec.title,
            visibility=SectionVisibility(sec.visibility) if sec.visibility else SectionVisibility.interne,
            content=content_bytes,
        ))

    db.commit()
    db.refresh(minute)
    return _minute_to_response(minute)


# ── GET /api/meetings/{meeting_id}/minute ──────────────────────────


@router.get("/api/meetings/{meeting_id}/minute", response_model=MinuteResponse)
def get_meeting_minute(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Récupère le PV associé à une réunion, ou 404 s'il n'existe pas."""
    meeting = (
        db.query(Meeting)
        .filter(Meeting.id == meeting_id, Meeting.organization_id == current_user.organization_id)
        .first()
    )
    if not meeting:
        raise HTTPException(status_code=404, detail="Réunion non trouvée")

    minute = db.query(Minute).filter(Minute.meeting_id == meeting_id).first()
    if not minute:
        raise HTTPException(status_code=404, detail="Aucun PV pour cette réunion")
    return _minute_to_response(minute)


# ── GET /api/minutes/{id} ──────────────────────────────────────────


@router.get("/api/minutes/{minute_id}", response_model=MinuteResponse)
def get_minute(
    minute_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    minute = (
        db.query(Minute)
        .filter(Minute.id == minute_id, Minute.organization_id == current_user.organization_id)
        .first()
    )
    if not minute:
        raise HTTPException(status_code=404, detail="PV non trouvé")
    return _minute_to_response(minute)


# ── PUT /api/minutes/{id}/sections ─────────────────────────────────


@router.put("/api/minutes/{minute_id}/sections", response_model=MinuteResponse)
def update_sections(
    minute_id: int,
    body: UpdateSectionsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    minute = (
        db.query(Minute)
        .filter(Minute.id == minute_id, Minute.organization_id == current_user.organization_id)
        .first()
    )
    if not minute:
        raise HTTPException(status_code=404, detail="PV non trouvé")

    # Empreinte de la projection direction AVANT modification
    old_fingerprint = _projection_fingerprint(list(minute.sections or []))

    # Supprimer les anciennes sections
    for s in list(minute.sections or []):
        db.delete(s)
    db.flush()

    # Insérer les nouvelles sections (elles n'ont pas encore d'id)
    for i, sec in enumerate(body.sections):
        vis = SectionVisibility(sec.visibility) if sec.visibility else SectionVisibility.interne
        content_bytes = base64.b64decode(sec.content) if sec.content else b""
        db.add(MinuteSection(
            minute_id=minute.id,
            position=sec.position if sec.position is not None else i,
            title=sec.title,
            visibility=vis,
            content=content_bytes,
        ))
    db.flush()

    # Empreinte de la projection direction APRÈS modification
    new_sections = (
        db.query(MinuteSection)
        .filter(MinuteSection.minute_id == minute.id)
        .all()
    )
    new_fingerprint = _projection_fingerprint(new_sections)

    # Si le PV était validé et que la version direction a changé, repasser en brouillon
    if minute.status == MinuteStatus.valide and old_fingerprint != new_fingerprint:
        minute.status = MinuteStatus.brouillon
        minute.validated_by_id = None
        minute.validated_at = None

    db.commit()
    db.refresh(minute)
    return _minute_to_response(minute)


# ── POST /api/minutes/{id}/validate ────────────────────────────────


@router.post("/api/minutes/{minute_id}/validate")
def validate_minute(
    minute_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    minute = (
        db.query(Minute)
        .filter(Minute.id == minute_id, Minute.organization_id == current_user.organization_id)
        .first()
    )
    if not minute:
        raise HTTPException(status_code=404, detail="PV non trouvé")

    # Le validateur doit être membre du bureau
    if current_user.delegue_role.value not in BUREAU_ROLES:
        raise HTTPException(status_code=403, detail="Seuls les membres du bureau (président, vice-président, secrétaire) peuvent valider un PV")

    # Le validateur doit être différent du rédacteur
    if current_user.id == minute.created_by_id:
        raise HTTPException(status_code=403, detail="Le rédacteur du PV ne peut pas valider son propre PV. La validation doit être effectuée par un autre membre du bureau.")

    minute.status = MinuteStatus.valide
    minute.validated_by_id = current_user.id
    minute.validated_at = datetime.now(timezone.utc)
    db.commit()

    return {"status": "ok", "message": "PV validé"}


# ── GET /api/minutes/{id}/direction-preview ────────────────────────


@router.get("/api/minutes/{minute_id}/direction-preview", response_model=DirectionPreviewResponse)
def direction_preview(
    minute_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    minute = (
        db.query(Minute)
        .filter(Minute.id == minute_id, Minute.organization_id == current_user.organization_id)
        .first()
    )
    if not minute:
        raise HTTPException(status_code=404, detail="PV non trouvé")

    # Projection via la même fonction que celle utilisée pour la comparaison
    # avant/après dans update_sections — garantit l'absence de divergence.
    fingerprint = _projection_fingerprint(list(minute.sections or []))

    preview_sections = []
    for pos, title, content_bytes in fingerprint:
        preview_sections.append({
            "position": pos,
            "title": title,
            "content": base64.b64encode(content_bytes).decode("ascii") if content_bytes else "",
        })

    return {
        "minute_id": minute.id,
        "meeting_title": minute.meeting.title if minute.meeting else None,
        "validated_by_name": minute.validated_by.full_name if minute.validated_by else None,
        "validated_at": minute.validated_at,
        "sections": preview_sections,
        "generated_at": datetime.now(timezone.utc),
    }
