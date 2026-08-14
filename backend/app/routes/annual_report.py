"""Annual activity report (rapport d'activité annuel de la délégation).

Aggregates the delegation's activity over one year for the PDF report:
- workforce statistics by sex (Art. L.414-3) for the year's semesters
- hours tracked by the delegation (Art. L.415-5), totals by category
- meetings (total, with direction) and consultations (L.414-3)
- designated delegates (sécurité/santé L.414-14, égalité L.414-15):
  their declared hours + legal reference credits

Bureau/admin only — read endpoint, no schema change.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.organization import Organization
from app.models.user import User
from app.models.time_entry import TimeEntry
from app.models.workforce_stat import WorkforceStat
from app.models.meeting import Meeting
from app.models.consultation import Consultation

router = APIRouter(tags=["stats"])


def _is_bureau(user: User) -> bool:
    return user.role == "admin" or user.delegue_role.value in ("president", "vice_president", "secretaire")


def _year_range(year: int):
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    return start, end


def equality_monthly_credit(n: int) -> int:
    """Art. L.414-15 — extra monthly time credit for the equality delegate."""
    if n <= 25:
        return 4
    if n <= 50:
        return 6
    if n <= 75:
        return 8
    if n <= 150:
        return 10
    return 16  # 4h/semaine (barème hebdomadaire, ≈ 16h/mois)


@router.get("/api/stats/annual-report")
def annual_report(
    year: int = Query(..., ge=2000, le=2100, description="Année civile (AAAA)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _is_bureau(current_user):
        raise HTTPException(status_code=403, detail="Réservé au bureau de la délégation")

    org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organisation introuvable")

    start, end = _year_range(year)

    # ── Effectif par sexe (L.414-3) ────────────────────────────────
    workforce = db.query(WorkforceStat).filter(
        WorkforceStat.organization_id == org.id,
        WorkforceStat.semester.like(f"{year}-%"),
    ).order_by(WorkforceStat.semester.asc()).all()

    # ── Heures (L.415-5) ───────────────────────────────────────────
    hours_rows = db.query(
        TimeEntry.user_id,
        func.coalesce(func.sum(TimeEntry.hours), 0.0),
    ).filter(
        TimeEntry.user_id.in_(
            db.query(User.id).filter(User.organization_id == org.id)
        ),
        TimeEntry.date >= start,
        TimeEntry.date < end,
    ).group_by(TimeEntry.user_id).all()

    user_ids = [r[0] for r in hours_rows]
    users_by_id = {
        u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()
    } if user_ids else {}

    hours_by_user = []
    for uid, total in hours_rows:
        u = users_by_id.get(uid)
        if not u:
            continue
        hours_by_user.append({
            "user_id": uid,
            "name": f"{u.first_name} {u.last_name}",
            "email": u.email,
            "delegue_status": u.delegue_status.value,
            "total_hours": round(float(total), 2),
        })
    hours_by_user.sort(key=lambda x: -x["total_hours"])

    hours_by_category = dict(
        db.query(TimeEntry.category, func.coalesce(func.sum(TimeEntry.hours), 0.0))
        .filter(
            TimeEntry.user_id.in_(db.query(User.id).filter(User.organization_id == org.id)),
            TimeEntry.date >= start,
            TimeEntry.date < end,
        )
        .group_by(TimeEntry.category)
        .all()
    )
    total_hours = round(float(sum(hours_by_category.values())), 2)
    hours_by_category = {k: round(float(v), 2) for k, v in hours_by_category.items()}

    # ── Réunions ───────────────────────────────────────────────────
    meetings_total = db.query(func.count(Meeting.id)).filter(
        Meeting.organization_id == org.id,
        Meeting.date >= start,
        Meeting.date < end,
    ).scalar() or 0
    meetings_with_direction = db.query(func.count(Meeting.id)).filter(
        Meeting.organization_id == org.id,
        Meeting.date >= start,
        Meeting.date < end,
        Meeting.direction_invited == True,  # noqa: E712
    ).scalar() or 0

    # ── Consultations (L.414-3) ────────────────────────────────────
    consultations_total = db.query(func.count(Consultation.id)).filter(
        Consultation.organization_id == org.id,
        Consultation.requested_at >= start,
        Consultation.requested_at < end,
    ).scalar() or 0
    consultations_answered = db.query(func.count(Consultation.id)).filter(
        Consultation.organization_id == org.id,
        Consultation.requested_at >= start,
        Consultation.requested_at < end,
        Consultation.direction_response != None,  # noqa: E711
    ).scalar() or 0

    # ── Délégués désignés (L.414-14 / L.414-15) ─────────────────────
    designates = []
    delegates = db.query(User).filter(
        User.organization_id == org.id,
        (User.is_delegue_securite_sante == True) | (User.is_delegue_egalite == True),  # noqa: E712
    ).all()
    for d in delegates:
        hours = db.query(func.coalesce(func.sum(TimeEntry.hours), 0.0)).filter(
            TimeEntry.user_id == d.id,
            TimeEntry.date >= start,
            TimeEntry.date < end,
        ).scalar() or 0.0
        by_cat = dict(
            db.query(TimeEntry.category, func.coalesce(func.sum(TimeEntry.hours), 0.0))
            .filter(TimeEntry.user_id == d.id, TimeEntry.date >= start, TimeEntry.date < end)
            .group_by(TimeEntry.category)
            .all()
        )
        roles = []
        if d.is_delegue_securite_sante:
            roles.append("securite_sante")
        if d.is_delegue_egalite:
            roles.append("egalite")
        designates.append({
            "user_id": d.id,
            "name": f"{d.first_name} {d.last_name}",
            "email": d.email,
            "delegue_status": d.delegue_status.value,
            "roles": roles,
            "total_hours": round(float(hours), 2),
            "hours_by_category": {k: round(float(v), 2) for k, v in by_cat.items()},
        })

    weekly_credit = org.weekly_credit_hours
    return {
        "year": year,
        "organization": {
            "name": org.name,
            "company": org.company_name,
            "employee_count": org.employee_count,
            "weekly_credit_hours": weekly_credit,
            "equality_monthly_credit": equality_monthly_credit(org.employee_count),
        },
        "workforce": [
            {"semester": w.semester, "male_count": w.male_count,
             "female_count": w.female_count, "total": w.male_count + w.female_count}
            for w in workforce
        ],
        "hours": {
            "total": total_hours,
            "by_category": hours_by_category,
            "by_user": hours_by_user,
        },
        "meetings": {"total": meetings_total, "with_direction": meetings_with_direction},
        "consultations": {"total": consultations_total, "answered": consultations_answered},
        "designates": designates,
    }
