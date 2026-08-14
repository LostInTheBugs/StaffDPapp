"""Routes for delegate activities (activités des délégués désignés).

Access rules:
- READ (GET): every member of the organization sees the activities
- WRITE (POST): the designated delegate themself (their own user_id) or
  any bureau member (admin / president / vice-president / secretary) —
  target must be currently designated for the requested domain
- DELETE: the author or a bureau member
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.delegate_activity import DelegateActivity
from app.models.user import User
from app.schemas.delegate_activity import (
    DelegateActivityCreate,
    DelegateActivityResponse,
    DOMAIN_CATEGORIES,
)

router = APIRouter(tags=["delegate-activities"])

DOMAIN_LABELS = {"securite_sante": "is_delegue_securite_sante", "egalite": "is_delegue_egalite"}


def _is_bureau(user: User) -> bool:
    return user.role == "admin" or user.delegue_role.value in ("president", "vice_president", "secretaire")


def _is_designated(user: User, domain: str) -> bool:
    flag = DOMAIN_LABELS.get(domain)
    return bool(flag and getattr(user, flag))


def _to_response(a: DelegateActivity, name: str) -> DelegateActivityResponse:
    return DelegateActivityResponse(
        id=a.id,
        user_id=a.user_id,
        name=name,
        domain=a.domain,
        category=a.category,
        description=a.description,
        date=a.activity_date,
        created_by_id=a.created_by_id,
        created_at=a.created_at,
    )


@router.get("/api/delegate-activities", response_model=list[DelegateActivityResponse])
def list_activities(
    year: int | None = Query(None, ge=2000, le=2100),
    user_id: int | None = Query(None, gt=0),
    domain: str | None = Query(None, pattern="^(securite_sante|egalite)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(DelegateActivity).filter(
        DelegateActivity.organization_id == current_user.organization_id
    )
    if year:
        start = datetime(year, 1, 1, tzinfo=timezone.utc)
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        q = q.filter(DelegateActivity.activity_date >= start,
                     DelegateActivity.activity_date < end)
    if user_id:
        q = q.filter(DelegateActivity.user_id == user_id)
    if domain:
        q = q.filter(DelegateActivity.domain == domain)
    q = q.order_by(DelegateActivity.activity_date.desc(), DelegateActivity.id.desc())

    users = {u.id: u for u in db.query(User).filter(
        User.organization_id == current_user.organization_id
    ).all()}
    return [
        _to_response(a, f"{users[a.user_id].first_name} {users[a.user_id].last_name}"
                      if a.user_id in users else f"#{a.user_id}")
        for a in q.all()
    ]


@router.post("/api/delegate-activities", response_model=DelegateActivityResponse, status_code=201)
def create_activity(
    body: DelegateActivityCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = db.query(User).filter(
        User.id == body.user_id,
        User.organization_id == current_user.organization_id,
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="Membre introuvable dans la délégation")
    if not _is_designated(target, body.domain):
        raise HTTPException(status_code=400, detail="Ce membre n'est pas délégué désigné pour ce domaine")

    is_self = body.user_id == current_user.id and _is_designated(current_user, body.domain)
    if not is_self and not _is_bureau(current_user):
        raise HTTPException(status_code=403, detail="Réservé au délégué désigné ou au bureau")

    a = DelegateActivity(
        organization_id=current_user.organization_id,
        user_id=body.user_id,
        domain=body.domain,
        category=body.category,
        description=body.description.strip(),
        activity_date=body.date,
        created_by_id=current_user.id,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return _to_response(a, f"{target.first_name} {target.last_name}")


@router.delete("/api/delegate-activities/{activity_id}", status_code=204)
def delete_activity(
    activity_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    a = db.query(DelegateActivity).filter(
        DelegateActivity.id == activity_id,
        DelegateActivity.organization_id == current_user.organization_id,
    ).first()
    if not a:
        raise HTTPException(status_code=404, detail="Activité introuvable")
    if a.created_by_id != current_user.id and not _is_bureau(current_user):
        raise HTTPException(status_code=403, detail="Seul l'auteur ou le bureau peut supprimer")
    db.delete(a)
    db.commit()
