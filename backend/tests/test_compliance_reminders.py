"""Tests rappels légaux quotidiens (chantier D) — scan idempotent, règles L.415-6/7, L.414-3/5, L.413-2."""

from datetime import date, datetime, timedelta

from app.core.database import SessionLocal
from app.models import Organization, User, EmailConfig, EmailOutbox
from app.models.workforce_stat import WorkforceStat
from app.services.email_service import scan_compliance_reminders


def _enable_emails(org_id: int) -> None:
    db = SessionLocal()
    db.add(EmailConfig(organization_id=org_id, enabled=True, transport_mode="eml",
                       from_name="Test", from_email="dp@test.lu"))
    db.commit()
    db.close()


def _bureau_count(org_id: int) -> int:
    db = SessionLocal()
    n = db.query(User).filter(
        User.organization_id == org_id, User.is_active == True,  # noqa: E712
        (User.role == "admin") | (User.delegue_role.in_(["president", "vice_president", "secretaire"])),
    ).count()
    db.close()
    return n


def _outbox_count(org_id: int, event_type: str) -> int:
    db = SessionLocal()
    n = db.query(EmailOutbox).filter(
        EmailOutbox.organization_id == org_id,
        EmailOutbox.event_type == event_type,
    ).count()
    db.close()
    return n


def test_scan_skips_other_days(client, org_with_users):
    _enable_emails(org_with_users["org_id"])
    db = SessionLocal()
    n = scan_compliance_reminders(db, today=date(2026, 8, 10))  # pas 1er ni 15
    db.close()
    assert n == 0


def test_scan_meetings_reminder_october(client, org_with_users):
    oid = org_with_users["org_id"]
    _enable_emails(oid)
    bureau = _bureau_count(oid)
    db = SessionLocal()
    # 15 octobre, aucune réunion cette année → rappel réunions
    # (4 règles actives en octobre sans données : réunions L.415-6, plénière
    #  L.415-7, stats S2 2025 et S1 2026 L.414-3 → n = 4 × bureau)
    n = scan_compliance_reminders(db, today=date(2026, 10, 15))
    db.close()
    assert n == 4 * bureau, f"attend {4 * bureau} emails (4 règles × {bureau} bureau), reçu {n}"
    # le rappel réunions est bien dans l'outbox
    db = SessionLocal()
    rows = db.query(EmailOutbox).filter(
        EmailOutbox.organization_id == oid,
        EmailOutbox.event_type == "compliance_reminder",
    ).all()
    db.close()
    assert any("L.415-6" in (r.payload or {}).get("label", "") for r in rows)
    # idempotent : un second passage n'ajoute rien
    db = SessionLocal()
    n2 = scan_compliance_reminders(db, today=date(2026, 10, 15))
    db.close()
    assert n2 == 0
    assert _outbox_count(oid, "compliance_reminder") == 4 * bureau


def test_scan_stats_reminder_january(client, org_with_users):
    oid = org_with_users["org_id"]
    _enable_emails(oid)
    bureau = _bureau_count(oid)
    db = SessionLocal()
    # 1er janvier : aucune règle active (fenêtres octobre-décembre et 15 janvier)
    n = scan_compliance_reminders(db, today=date(2026, 1, 1))
    db.close()
    assert n == 0
    # 15 janvier : S2 de l'année précédente absent → 1 règle × bureau
    db = SessionLocal()
    n = scan_compliance_reminders(db, today=date(2026, 1, 15))
    db.close()
    assert n == bureau
    # après enregistrement des stats S2 2025, plus de rappel pour ce motif
    db = SessionLocal()
    db.add(WorkforceStat(organization_id=oid, semester="2025-2", male_count=50, female_count=50))
    db.commit()
    db.close()
    db = SessionLocal()
    n2 = scan_compliance_reminders(db, today=date(2026, 1, 15))
    db.close()
    assert n2 == 0


def test_scan_renewal_window(client, org_with_users):
    oid = org_with_users["org_id"]
    _enable_emails(oid)
    bureau = _bureau_count(oid)
    db = SessionLocal()
    org = db.get(Organization, oid)
    org.mandate_end_date = datetime(2026, 3, 15)
    db.commit()
    # 1er mars 2026 dans la fenêtre, pas d'élection clôturée → rappel (réunions non concernées, stats S2 2025 ? mars > 15 jan → oui)
    n = scan_compliance_reminders(db, today=date(2026, 3, 1))
    db.close()
    assert n >= bureau  # au moins le rappel élections (et éventuellement stats)
    assert _outbox_count(oid, "compliance_reminder") >= bureau


def test_scan_eco_reports_large_org(client, org_with_users):
    oid = org_with_users["org_id"]
    _enable_emails(oid)
    db = SessionLocal()
    org = db.get(Organization, oid)
    org.employee_count = 200
    db.commit()
    n = scan_compliance_reminders(db, today=date(2026, 11, 1))
    db.close()
    assert n >= _bureau_count(oid)
