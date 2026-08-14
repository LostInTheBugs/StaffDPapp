from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User, WorkforceStat
from app.schemas.workforce_stat import (
    WorkforceStatCreate, WorkforceStatUpdate, WorkforceStatRead,
)

router = APIRouter(prefix="/api/workforce-stats", tags=["workforce-stats"])

BUREAU_ROLES = {"president", "vice_president", "secretaire"}


def _is_bureau(user: User) -> bool:
    return user.role.value == "admin" or (
        user.delegue_role is not None and user.delegue_role.value in BUREAU_ROLES
    )


def _to_response(s: WorkforceStat) -> dict:
    return {
        "id": s.id,
        "organization_id": s.organization_id,
        "semester": s.semester,
        "male_count": s.male_count,
        "female_count": s.female_count,
        "total": (s.male_count or 0) + (s.female_count or 0),
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@router.get("", response_model=list[WorkforceStatRead])
def list_workforce_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Statistiques semestrielles de l'effectif (L.414-3) — visibles par les membres."""
    rows = (
        db.query(WorkforceStat)
        .filter(WorkforceStat.organization_id == current_user.organization_id)
        .order_by(WorkforceStat.semester.desc())
        .all()
    )
    return [_to_response(s) for s in rows]


@router.get("/latest", response_model=WorkforceStatRead | None)
def latest_workforce_stat(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Dernier semestre publié (pour le tableau de bord)."""
    row = (
        db.query(WorkforceStat)
        .filter(WorkforceStat.organization_id == current_user.organization_id)
        .order_by(WorkforceStat.semester.desc())
        .first()
    )
    return _to_response(row) if row else None


@router.post("", response_model=WorkforceStatRead, status_code=201)
def create_workforce_stat(
    payload: WorkforceStatCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Créer un rapport semestriel (bureau uniquement)."""
    if not _is_bureau(current_user):
        raise HTTPException(status_code=403, detail="Réservé au bureau de la délégation")

    existing = (
        db.query(WorkforceStat)
        .filter(
            WorkforceStat.organization_id == current_user.organization_id,
            WorkforceStat.semester == payload.semester,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Ce semestre existe déjà — modifiez-le")

    row = WorkforceStat(
        organization_id=current_user.organization_id,
        semester=payload.semester,
        male_count=payload.male_count,
        female_count=payload.female_count,
        created_by=current_user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_response(row)


@router.put("/{stat_id}", response_model=WorkforceStatRead)
def update_workforce_stat(
    stat_id: int,
    payload: WorkforceStatUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Modifier un rapport semestriel (bureau uniquement)."""
    if not _is_bureau(current_user):
        raise HTTPException(status_code=403, detail="Réservé au bureau de la délégation")

    row = (
        db.query(WorkforceStat)
        .filter(
            WorkforceStat.id == stat_id,
            WorkforceStat.organization_id == current_user.organization_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Rapport introuvable")

    if payload.male_count is not None:
        row.male_count = payload.male_count
    if payload.female_count is not None:
        row.female_count = payload.female_count
    db.commit()
    db.refresh(row)
    return _to_response(row)


@router.delete("/{stat_id}", status_code=204)
def delete_workforce_stat(
    stat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Supprimer un rapport semestriel (bureau uniquement)."""
    if not _is_bureau(current_user):
        raise HTTPException(status_code=403, detail="Réservé au bureau de la délégation")

    row = (
        db.query(WorkforceStat)
        .filter(
            WorkforceStat.id == stat_id,
            WorkforceStat.organization_id == current_user.organization_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Rapport introuvable")

    db.delete(row)
    db.commit()
