"""Tests cockpit de conformité légale (L.415-6/7, L.414-3/5/14/15/16, L.416-1, L.413-2)."""

from datetime import datetime, timedelta

from app.core.database import SessionLocal
from app.models import Organization, ComplianceEvent


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


# ── Lecture ─────────────────────────────────────────────────────────

def test_overview_readable_by_member_and_employee(client, org_with_users):
    r = client.get("/api/compliance/overview", headers=_h(org_with_users["tom_token"]))
    assert r.status_code == 200
    keys = [i["key"] for i in r.json()["items"]]
    for expected in ("meetings", "plenary", "workforce", "consultations", "minutes",
                     "designations", "names", "elections", "eco", "notices"):
        assert expected in keys, keys
    # Statuses valides
    for i in r.json()["items"]:
        assert i["status"] in ("ok", "warn", "due", "na", "info")
    # Aucun événement → plénière due, meetings due
    by_key = {i["key"]: i for i in r.json()["items"]}
    assert by_key["plenary"]["status"] == "due"
    assert by_key["meetings"]["status"] in ("due", "warn")


def test_overview_employee_readable(client, org_with_users):
    from tests.helpers import create_user
    from tests.helpers import fetch_captcha
    db = SessionLocal()
    create_user(db, "employe2@test.lu", "test123456", org_with_users["org_id"],
                delegue_status="employe", role="member")
    db.close()
    cid, ans = fetch_captcha(client)
    r = client.post("/api/auth/login", json={
        "email": "employe2@test.lu", "password": "test123456",
        "captcha_id": cid, "captcha_answer": ans,
    })
    assert r.status_code == 200
    r2 = client.get("/api/compliance/overview", headers=_h(r.json()["access_token"]))
    assert r2.status_code == 200


# ── Événements ──────────────────────────────────────────────────────

def test_events_bureau_only(client, org_with_users):
    # membre simple → 403
    r = client.post("/api/compliance/events", json={"event_type": "plenary_assembly"},
                    headers=_h(org_with_users["tom_token"]))
    assert r.status_code == 403
    # bureau (marc = secrétaire) → 201
    r = client.post("/api/compliance/events", json={
        "event_type": "plenary_assembly", "notes": "Assemblée annuelle",
    }, headers=_h(org_with_users["marc_token"]))
    assert r.status_code == 201, r.text
    assert r.json()["created_by_name"] == "Marc Weber"
    # statut bascule due → ok
    r2 = client.get("/api/compliance/overview", headers=_h(org_with_users["sophie_token"]))
    by_key = {i["key"]: i for i in r2.json()["items"]}
    assert by_key["plenary"]["status"] == "ok", by_key["plenary"]
    # type invalide → 422
    r3 = client.post("/api/compliance/events", json={"event_type": "foo"},
                     headers=_h(org_with_users["sophie_token"]))
    assert r3.status_code == 422
    # date invalide → 422
    r4 = client.post("/api/compliance/events", json={"event_type": "plenary_assembly", "event_date": "pas-une-date"},
                     headers=_h(org_with_users["sophie_token"]))
    assert r4.status_code == 422


def test_events_delete_author_or_bureau(client, org_with_users):
    r = client.post("/api/compliance/events", json={"event_type": "names_communication"},
                    headers=_h(org_with_users["marc_token"]))
    ev_id = r.json()["id"]
    # tom ne peut pas supprimer
    assert client.delete(f"/api/compliance/events/{ev_id}", headers=_h(org_with_users["tom_token"])).status_code == 403
    # le bureau peut
    assert client.delete(f"/api/compliance/events/{ev_id}", headers=_h(org_with_users["sophie_token"])).status_code == 204
    assert client.delete(f"/api/compliance/events/{ev_id}", headers=_h(org_with_users["sophie_token"])).status_code == 404


def test_events_org_isolation(client, org_with_users):
    r = client.post("/api/compliance/events", json={"event_type": "plenary_assembly"},
                    headers=_h(org_with_users["sophie_token"]))
    ev_id = r.json()["id"]
    # autre org : ne voit rien et ne supprime pas
    r2 = client.get("/api/compliance/overview", headers=_h(org_with_users["other_token"]))
    assert r2.json()["events"] == []
    assert client.delete(f"/api/compliance/events/{ev_id}", headers=_h(org_with_users["other_token"])).status_code == 404


# ── Statuts spécifiques ─────────────────────────────────────────────

def test_eco_report_status_by_headcount(client, org_with_users):
    # org par défaut <150 → na
    r = client.get("/api/compliance/overview", headers=_h(org_with_users["sophie_token"]))
    eco = {i["key"]: i for i in r.json()["items"]}["eco"]
    assert eco["status"] == "na"

    # passage ≥150 → due, puis ok avec 2 événements de l'année
    db = SessionLocal()
    org = db.query(Organization).get(org_with_users["org_id"])
    org.employee_count = 200
    db.commit()
    db.close()
    r = client.get("/api/compliance/overview", headers=_h(org_with_users["sophie_token"]))
    assert {i["key"]: i for i in r.json()["items"]}["eco"]["status"] == "due"
    for _ in range(2):
        client.post("/api/compliance/events", json={
            "event_type": "eco_financial_report",
            "event_date": datetime.now().strftime("%Y-%m-%d"),
        }, headers=_h(org_with_users["sophie_token"]))
    r = client.get("/api/compliance/overview", headers=_h(org_with_users["sophie_token"]))
    assert {i["key"]: i for i in r.json()["items"]}["eco"]["status"] == "ok"

    # événement de l'année dernière ne compte pas
    db = SessionLocal()
    org = db.query(Organization).get(org_with_users["org_id"])
    org.employee_count = 15
    db.commit()
    db.close()
    db = SessionLocal()
    old = ComplianceEvent(
        organization_id=org_with_users["org_id"], event_type="eco_financial_report",
        event_date=datetime.now() - timedelta(days=400), created_by_id=org_with_users.get("sophie_id", 1),
    )
    db.add(old)
    db.commit()
    db.close()
    r = client.get("/api/compliance/overview", headers=_h(org_with_users["sophie_token"]))
    assert {i["key"]: i for i in r.json()["items"]}["eco"]["status"] == "na"
