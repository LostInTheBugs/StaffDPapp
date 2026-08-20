"""Chantier C — congé-formation (L.415-9), registre sécurité/santé (L.414-14),
périodes protégées (L.415-10/11)."""

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_module
from app.models import User, Organization, SafetyRegisterEntry
from app.models.election import Election, ElectionStatus
from app.models.time_entry import TimeEntry

router = APIRouter(prefix="/api", tags=["legal"], dependencies=[Depends(require_module("legal"))])

WORK_HOURS_PER_WEEK = 40  # base conventionnelle : 1 semaine = 40 h
PRIMO_BONUS_HOURS = 16  # L.415-9(3) : +16 h pour les primo-élus


def formation_entitlement_hours(org: Organization, user: User) -> int:
    """Droit de congé-formation (L.415-9) en heures, par membre.

    15-49 salariés : 1 semaine par mandat · 50-150 : 2 semaines par mandat
    · >150 : 1 semaine par an. Primo-élus : +16 h. Suppléants : moitié.
    """
    n = org.employee_count or 0
    if n <= 49:
        base = WORK_HOURS_PER_WEEK
    elif n <= 150:
        base = 2 * WORK_HOURS_PER_WEEK
    else:
        base = WORK_HOURS_PER_WEEK  # par année
    if user.delegue_status and user.delegue_status.value == "suppleant":
        base //= 2
    if user.is_first_mandate:
        base += PRIMO_BONUS_HOURS
    return base


def _is_bureau(user: User) -> bool:
    # même prédicat que le tableau d'affichage : admin ou président/vice-président/secrétaire
    return user.role == "admin" or (
        user.delegue_role is not None and user.delegue_role.value in ("president", "vice_president", "secretaire")
    )


def _is_secu_or_bureau(user: User) -> bool:
    return _is_bureau(user) or bool(user.is_delegue_securite_sante)


# ---------------------------------------------------------------- formation


class PrimoUpdate(BaseModel):
    is_first_mandate: bool


@router.get("/formation/overview")
def formation_overview(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    if not org:
        raise HTTPException(404, "Organisation non trouvée")
    members = db.query(User).filter(
        User.organization_id == org.id, User.is_active == True  # noqa: E712
    ).all()
    year = datetime.utcnow().year
    out = []
    for u in members:
        used = db.query(TimeEntry).filter(
            TimeEntry.user_id == u.id,
            TimeEntry.category == "formation",
            TimeEntry.date >= date(year, 1, 1),
            TimeEntry.date <= date(year, 12, 31),
        ).all()
        used_h = sum((t.hours or 0) for t in used)
        ent = formation_entitlement_hours(org, u)
        out.append({
            "user_id": u.id,
            "full_name": u.full_name,
            "delegue_status": u.delegue_status.value if u.delegue_status else "employe",
            "is_first_mandate": bool(u.is_first_mandate),
            "entitlement_hours": ent,
            "used_hours": round(used_h, 1),
            "remaining_hours": round(max(ent - used_h, 0), 1),
        })
    return {"year": year, "members": sorted(out, key=lambda x: x["full_name"])}


@router.put("/formation/primo/{user_id}")
def set_primo(user_id: int, body: PrimoUpdate,
              current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not _is_bureau(current_user):
        raise HTTPException(403, "Réservé au bureau")
    u = db.query(User).filter(User.id == user_id, User.organization_id == current_user.organization_id).first()
    if not u:
        raise HTTPException(404, "Membre non trouvé")
    u.is_first_mandate = body.is_first_mandate
    db.commit()
    return {"ok": True, "is_first_mandate": bool(u.is_first_mandate)}


# ------------------------------------------------------- registre sécurité/santé


class RegisterEntryCreate(BaseModel):
    entry_date: str = Field(min_length=8)
    location: str = Field(default="", max_length=200)
    description: str = Field(min_length=3, max_length=5000)


class RegisterCountersign(BaseModel):
    chef_service_name: str = Field(min_length=2, max_length=200)


@router.get("/safety-register")
def list_register(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    entries = db.query(SafetyRegisterEntry).filter(
        SafetyRegisterEntry.organization_id == current_user.organization_id
    ).order_by(SafetyRegisterEntry.entry_date.desc(), SafetyRegisterEntry.id.desc()).all()
    return [{
        "id": e.id,
        "entry_date": e.entry_date.isoformat(),
        "location": e.location or "",
        "description": e.description,
        "status": e.status,
        "chef_service_name": e.chef_service_name or "",
        "countersigned_at": e.countersigned_at.isoformat() if e.countersigned_at else None,
        "delegate_name": e.delegate.full_name if e.delegate else "",
        "created_by_name": e.created_by.full_name if e.created_by else "",
        "can_countersign": _is_bureau(current_user),
        "can_delete": _is_bureau(current_user) or e.created_by_id == current_user.id,
    } for e in entries]


@router.post("/safety-register")
def create_register_entry(body: RegisterEntryCreate,
                          current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not _is_secu_or_bureau(current_user):
        raise HTTPException(403, "Réservé au délégué sécurité/santé et au bureau")
    try:
        d = date.fromisoformat(body.entry_date)
    except ValueError:
        raise HTTPException(422, "Date invalide")
    e = SafetyRegisterEntry(
        organization_id=current_user.organization_id,
        delegate_id=current_user.id,
        entry_date=d,
        location=body.location.strip(),
        description=body.description.strip(),
        status="pending",
        created_by_id=current_user.id,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return {"id": e.id, "status": "pending"}


@router.post("/safety-register/{entry_id}/countersign")
def countersign_entry(entry_id: int, body: RegisterCountersign,
                      current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not _is_bureau(current_user):
        raise HTTPException(403, "Le contreseing est enregistré par le bureau")
    e = db.query(SafetyRegisterEntry).filter(
        SafetyRegisterEntry.id == entry_id,
        SafetyRegisterEntry.organization_id == current_user.organization_id,
    ).first()
    if not e:
        raise HTTPException(404, "Entrée non trouvée")
    e.status = "countersigned"
    e.chef_service_name = body.chef_service_name.strip()
    e.countersigned_at = datetime.utcnow()
    db.commit()
    return {"id": e.id, "status": "countersigned"}


@router.delete("/safety-register/{entry_id}")
def delete_register_entry(entry_id: int,
                          current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    e = db.query(SafetyRegisterEntry).filter(
        SafetyRegisterEntry.id == entry_id,
        SafetyRegisterEntry.organization_id == current_user.organization_id,
    ).first()
    if not e:
        raise HTTPException(404, "Entrée non trouvée")
    if not (_is_bureau(current_user) or e.created_by_id == current_user.id):
        raise HTTPException(403, "Seul l'auteur ou le bureau peut supprimer")
    db.delete(e)
    db.commit()
    return {"ok": True}


# ----------------------------------------------------------- protection L.415-10


@router.get("/protection")
def protection_overview(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    if not org:
        raise HTTPException(404, "Organisation non trouvée")
    today = date.today()
    people = []

    # Membres : protection = mandat (en cours) + 6 mois après la fin
    members = db.query(User).filter(
        User.organization_id == org.id, User.is_active == True,  # noqa: E712
        User.delegue_status.in_(["titulaire", "suppleant"]),
    ).all()
    for u in members:
        end = org.mandate_end_date
        if end:
            end = end.date() if isinstance(end, datetime) else end
            protected_until = end + timedelta(days=182)  # +6 mois (mois civils approximés)
            days_left = (protected_until - today).days
            status = "protected" if days_left >= 0 else "expired"
        else:
            protected_until, days_left, status = None, None, "unknown"
        people.append({
            "kind": "member",
            "name": u.full_name,
            "role": u.delegue_status.value,
            "protected_until": protected_until.isoformat() if protected_until else None,
            "days_left": days_left,
            "status": status,
        })

    # Candidats aux élections : protection 3 mois après le scrutin (L.415-10)
    elections = db.query(Election).filter(
        Election.organization_id == org.id,
        Election.status == ElectionStatus.closed.value,
        Election.election_date.isnot(None),
    ).all()
    seen = set()
    for el in elections:
        ed = el.election_date
        ed = ed.date() if isinstance(ed, datetime) else ed
        protected_until = ed + timedelta(days=92)  # +3 mois
        days_left = (protected_until - today).days
        for c in el.candidates:
            key = c.full_name.lower()
            if key in seen:
                continue
            seen.add(key)
            people.append({
                "kind": "candidate",
                "name": c.full_name,
                "role": "candidat",
                "election": el.title,
                "protected_until": protected_until.isoformat(),
                "days_left": days_left,
                "status": "protected" if days_left >= 0 else "expired",
            })
    return {"today": today.isoformat(), "people": sorted(people, key=lambda p: (p["name"].lower()))}
