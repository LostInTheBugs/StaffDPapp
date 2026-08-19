"""Cockpit de conformité légale — synthèse des obligations de la délégation.

Agrège l'état des obligations du Code du travail (Livre IV) à partir des
données existantes de l'app + les événements suivis dans compliance_events.

Statuts : ok (à jour) / warn (partiel ou échéance proche) / due (à faire ou
en retard) / na (non applicable) / info (informatif).
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import (
    User, Organization, Consultation, Minute, WorkforceStat,
    NoticePost, ComplianceEvent,
)
from app.models.meeting import Meeting
from app.schemas.compliance import (
    ComplianceEventCreate, ComplianceEventResponse, ComplianceItem,
    ComplianceOverview,
)

router = APIRouter(prefix="/api", tags=["compliance"])

# Jours ouvrables de retard toléré pour la plénière (L.415-7 : 1x/an)
PLENARY_MONTHS = 14  # tolérance de 2 mois après l'année


def _is_bureau(user: User) -> bool:
    return user.role == "admin" or user.delegue_role.value in ("president", "vice_president", "secretaire")


def _now():
    return datetime.now()


@router.get("/compliance/overview", response_model=ComplianceOverview)
def compliance_overview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    now = _now()
    year = now.year
    items = []

    def item(key, title, legal_ref, status, detail):
        items.append(ComplianceItem(key=key, title=title, legal_ref=legal_ref, status=status, detail=detail))

    # 1. Réunions annuelles (L.415-6)
    total_meetings = db.query(Meeting).filter(
        Meeting.organization_id == org.id,
        Meeting.status != "cancelled",
    ).count()
    with_direction = db.query(Meeting).filter(
        Meeting.organization_id == org.id,
        Meeting.status != "cancelled",
        Meeting.direction_invited == True,  # noqa: E712
    ).count()
    if total_meetings >= 6 and with_direction >= 3:
        st, detail = "ok", f"{total_meetings}/6 dont {with_direction} avec la direction"
    elif total_meetings >= 3:
        st, detail = "warn", f"{total_meetings}/6 dont {with_direction} avec la direction"
    else:
        st, detail = "due", f"{total_meetings}/6 dont {with_direction} avec la direction"
    item("meetings", "Réunions annuelles", "L.415-6 · L.416-3", st, detail)

    # 2. Assemblée plénière annuelle (L.415-7)
    plenary = db.query(ComplianceEvent).filter(
        ComplianceEvent.organization_id == org.id,
        ComplianceEvent.event_type == "plenary_assembly",
    ).order_by(ComplianceEvent.event_date.desc()).first()
    if plenary and (now - plenary.event_date).days < 365:
        item("plenary", "Assemblée plénière annuelle", "L.415-7", "ok",
             f"Tenue le {plenary.event_date.strftime('%d/%m/%Y')}")
    elif plenary:
        item("plenary", "Assemblée plénière annuelle", "L.415-7", "due",
             f"Dernière le {plenary.event_date.strftime('%d/%m/%Y')} — plus d'un an")
    else:
        item("plenary", "Assemblée plénière annuelle", "L.415-7", "due",
             "Aucune assemblée plénière enregistrée (1x/an, convoquée par le président)")

    # 3. Statistiques semestrielles (L.414-3)
    latest_ws = db.query(WorkforceStat).filter(
        WorkforceStat.organization_id == org.id,
    ).order_by(WorkforceStat.semester.desc()).first()
    current_semester = f"{year}-{1 if now.month <= 6 else 2}"
    if latest_ws and latest_ws.semester >= current_semester:
        item("workforce", "Statistiques semestrielles effectif", "L.414-3", "ok",
             f"Semestre {latest_ws.semester} reçu")
    elif latest_ws:
        item("workforce", "Statistiques semestrielles effectif", "L.414-3", "warn",
             f"Dernier : {latest_ws.semester} — le semestre {current_semester} est attendu")
    else:
        item("workforce", "Statistiques semestrielles effectif", "L.414-3", "due",
             "Aucune statistique semestrielle enregistrée")

    # 4. Consultations (L.414-3) — réponses motivées sous 2 mois
    from app.models.consultation import ConsultationStatus
    overdue = db.query(Consultation).filter(
        Consultation.organization_id == org.id,
        Consultation.status == ConsultationStatus.requested,
        Consultation.response_due < now,
    ).count()
    open_c = db.query(Consultation).filter(
        Consultation.organization_id == org.id,
        Consultation.status == ConsultationStatus.requested,
    ).count()
    if overdue > 0:
        item("consultations", "Consultations en cours", "L.414-3", "due",
             f"{overdue} échéance(s) dépassée(s) sur {open_c} en attente")
    elif open_c > 0:
        item("consultations", "Consultations en cours", "L.414-3", "ok",
             f"{open_c} en attente, aucune échéance dépassée")
    else:
        item("consultations", "Consultations en cours", "L.414-3", "info",
             "Aucune consultation en cours")

    # 5. PV validés (L.416-5)
    validated = db.query(Minute).filter(
        Minute.organization_id == org.id,
        Minute.status == "valide",
    ).count()
    if validated > 0:
        item("minutes", "PV validés et approuvés", "L.416-5", "ok",
             f"{validated} PV validé(s)")
    elif total_meetings > 0:
        item("minutes", "PV validés et approuvés", "L.416-5", "warn",
             f"{total_meetings} réunion(s) mais aucun PV validé")
    else:
        item("minutes", "PV validés et approuvés", "L.416-5", "info",
             "Aucun PV pour le moment")

    # 6. Désignations spéciales (L.414-14 / L.414-15)
    secu = db.query(User).filter(
        User.organization_id == org.id, User.is_active == True,  # noqa: E712
        User.is_delegue_securite_sante == True,  # noqa: E712
    ).first()
    egal = db.query(User).filter(
        User.organization_id == org.id, User.is_active == True,  # noqa: E712
        User.is_delegue_egalite == True,  # noqa: E712
    ).first()
    if secu and egal:
        item("designations", "Délégués désignés", "L.414-14 · L.414-15", "ok",
             f"🛡️ {secu.first_name} {secu.last_name} · ⚖️ {egal.first_name} {egal.last_name}")
    elif secu or egal:
        item("designations", "Délégués désignés", "L.414-14 · L.414-15", "warn",
             f"🛡️ {'oui' if secu else '⚠️ manquant'} · ⚖️ {'oui' if egal else '⚠️ manquant'}")
    else:
        item("designations", "Délégués désignés", "L.414-14 · L.414-15", "due",
             "Aucun délégué désigné (sécurité/santé ni égalité)")

    # 7. Communication du bureau au chef d'entreprise (L.416-1, 3 jours)
    names = db.query(ComplianceEvent).filter(
        ComplianceEvent.organization_id == org.id,
        ComplianceEvent.event_type == "names_communication",
    ).order_by(ComplianceEvent.event_date.desc()).first()
    if names:
        item("names", "Bureau communiqué au chef d'entreprise", "L.416-1", "ok",
             f"Le {names.event_date.strftime('%d/%m/%Y')}")
    else:
        item("names", "Bureau communiqué au chef d'entreprise", "L.416-1", "due",
             "À faire sous 3 jours après la réunion constituante")

    # 8. Renouvellement des élections (L.413-2, fenêtre 1er fév – 31 mars)
    if org.mandate_end_date:
        me = org.mandate_end_date
        win_start = datetime(me.year, 2, 1)
        win_end = datetime(me.year, 3, 31, 23, 59, 59)
        if win_start <= now <= win_end:
            item("elections", "Renouvellement de la délégation", "L.413-2", "due",
                 "Fenêtre légale OUVERTE (1er février – 31 mars) — élections à organiser")
        elif now < win_start:
            item("elections", "Renouvellement de la délégation", "L.413-2", "info",
                 f"Fenêtre légale : {win_start.strftime('%d/%m/%Y')} – {win_end.strftime('%d/%m/%Y')}")
        else:
            item("elections", "Renouvellement de la délégation", "L.413-2", "due",
                 f"Fenêtre légale dépassée ({win_start.strftime('%d/%m/%Y')} – {win_end.strftime('%d/%m/%Y')})")
    else:
        item("elections", "Renouvellement de la délégation", "L.413-2", "info",
             "Date de fin de mandat non renseignée (Mon organisation)")

    # 9. Rapport écrit éco-financier (L.414-5, ≥150 salariés)
    if org.employee_count and org.employee_count >= 150:
        eco = db.query(ComplianceEvent).filter(
            ComplianceEvent.organization_id == org.id,
            ComplianceEvent.event_type == "eco_financial_report",
            ComplianceEvent.event_date >= datetime(year, 1, 1),
        ).count()
        if eco >= 2:
            item("eco", "Rapports éco-financiers reçus", "L.414-5", "ok", f"{eco}/2 cette année")
        elif eco == 1:
            item("eco", "Rapports éco-financiers reçus", "L.414-5", "warn", "1/2 cette année")
        else:
            item("eco", "Rapports éco-financiers reçus", "L.414-5", "due",
                 "0/2 — l'employeur doit fournir un rapport écrit ≥2x/an")
    else:
        item("eco", "Rapports éco-financiers", "L.414-5", "na",
             "Non applicable (<150 salariés)")

    # 10. Tableau d'affichage (L.414-16)
    notices = db.query(NoticePost).filter(NoticePost.organization_id == org.id).count()
    if notices > 0:
        item("notices", "Tableau d'affichage actif", "L.414-16", "ok",
             f"{notices} affiche(s) publiée(s)")
    else:
        item("notices", "Tableau d'affichage actif", "L.414-16", "info",
             "Aucune affiche publiée")

    # Événements (historique)
    events = db.query(ComplianceEvent).filter(
        ComplianceEvent.organization_id == org.id,
    ).order_by(ComplianceEvent.event_date.desc()).limit(50).all()
    event_responses = []
    for ev in events:
        name = f"{ev.created_by.first_name} {ev.created_by.last_name}".strip() if ev.created_by else None
        event_responses.append(ComplianceEventResponse(
            id=ev.id,
            event_type=ev.event_type,
            event_date=ev.event_date.isoformat() if ev.event_date else None,
            notes=ev.notes,
            created_by_name=name,
            created_at=ev.created_at.isoformat() if ev.created_at else None,
        ))

    return ComplianceOverview(
        items=items,
        events=event_responses,
        generated_at=now.isoformat(),
    )


@router.post("/compliance/events", response_model=ComplianceEventResponse, status_code=201)
def create_compliance_event(
    body: ComplianceEventCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _is_bureau(current_user):
        raise HTTPException(status_code=403, detail="Réservé au bureau de la délégation")
    try:
        event_date = datetime.fromisoformat(body.event_date) if body.event_date else _now()
    except ValueError:
        raise HTTPException(status_code=422, detail="Date invalide")
    ev = ComplianceEvent(
        organization_id=current_user.organization_id,
        event_type=body.event_type,
        event_date=event_date,
        notes=body.notes,
        created_by_id=current_user.id,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ComplianceEventResponse(
        id=ev.id,
        event_type=ev.event_type,
        event_date=ev.event_date.isoformat() if ev.event_date else None,
        notes=ev.notes,
        created_by_name=f"{current_user.first_name} {current_user.last_name}".strip(),
        created_at=ev.created_at.isoformat() if ev.created_at else None,
    )


@router.delete("/compliance/events/{event_id}", status_code=204)
def delete_compliance_event(
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ev = db.query(ComplianceEvent).filter(
        ComplianceEvent.id == event_id,
        ComplianceEvent.organization_id == current_user.organization_id,
    ).first()
    if ev is None:
        raise HTTPException(status_code=404, detail="Événement introuvable")
    if ev.created_by_id != current_user.id and not _is_bureau(current_user):
        raise HTTPException(status_code=403, detail="Seul l'auteur ou le bureau peut supprimer")
    db.delete(ev)
    db.commit()
    return None
