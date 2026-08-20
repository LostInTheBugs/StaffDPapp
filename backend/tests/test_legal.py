"""Tests congé-formation (L.415-9), registre sécurité/santé (L.414-14), protection (L.415-10)."""

from datetime import date, datetime, timedelta

from app.core.database import SessionLocal
from app.models import Organization, User, SafetyRegisterEntry
from app.models.time_entry import TimeEntry
from tests.helpers import fetch_captcha


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def _join(client, email, code, first, last, password="test123456"):
    """Rejoint une organisation avec un code d'invitation (retourne le token)."""
    cid, ans = fetch_captcha(client)
    r = client.post("/api/join", json={
        "email": email, "password": password,
        "first_name": first, "last_name": last,
        "invitation_code": code,
        "captcha_id": cid, "captcha_answer": ans,
    })
    assert r.status_code == 201, f"join failed: {r.text}"
    return r.json()["access_token"]


def test_formation_overview_entitlements(client, org_with_users):
    oid = org_with_users["org_id"]
    # ajoute un suppléant pour vérifier la règle « moitié »
    from tests.helpers import create_invitation
    from app.models.user import User
    db = SessionLocal()
    sophie = db.query(User).filter(User.email == "sophie@testpv.lu").first()
    create_invitation(db, "emma@testpv.lu", oid, sophie.id, "EMMA123",
                      delegue_status="suppleant", delegue_role="membre")
    db.close()
    _join(client, "emma@testpv.lu", "EMMA123", "Emma", "Dubois")
    r = client.get("/api/formation/overview", headers=_h(org_with_users["sophie_token"]))
    assert r.status_code == 200
    data = r.json()
    assert data["year"] == datetime.utcnow().year
    members = {m["full_name"]: m for m in data["members"]}
    # org 120 salariés → 2 semaines = 80 h ; suppléants → moitié = 40 h
    assert members["Sophie Muller"]["entitlement_hours"] == 80
    assert members["Emma Dubois"]["entitlement_hours"] == 40
    assert members["Emma Dubois"]["delegue_status"] == "suppleant"


def test_formation_primo_bonus(client, org_with_users):
    # Pierre (employé) n'a pas droit ; on passe un titulaire en primo-élu
    db = SessionLocal()
    u = db.query(User).filter(User.organization_id == org_with_users["org_id"],
                              User.delegue_status == "titulaire").first()
    uid = u.id
    db.close()
    r = client.put(f"/api/formation/primo/{uid}", json={"is_first_mandate": True},
                   headers=_h(org_with_users["sophie_token"]))
    assert r.status_code == 200
    assert r.json()["is_first_mandate"] is True
    data = client.get("/api/formation/overview", headers=_h(org_with_users["sophie_token"])).json()
    m = next(x for x in data["members"] if x["user_id"] == uid)
    assert m["entitlement_hours"] == 96  # 80 + 16
    # un employé ne peut pas modifier
    r2 = client.put(f"/api/formation/primo/{uid}", json={"is_first_mandate": False},
                    headers=_h(org_with_users["tom_token"]))
    assert r2.status_code == 403


def test_formation_used_hours(client, org_with_users):
    from app.models.user import User
    db = SessionLocal()
    u = db.query(User).filter(User.organization_id == org_with_users["org_id"],
                              User.delegue_status == "titulaire").first()
    uid = u.id
    db.add(TimeEntry(user_id=uid, date=datetime.utcnow(),
                     hours=10.0, category="formation", description="Cours sécurité"))
    db.commit()
    db.close()
    data = client.get("/api/formation/overview", headers=_h(org_with_users["sophie_token"])).json()
    m = next(x for x in data["members"] if x["user_id"] == uid)
    assert m["used_hours"] == 10.0
    assert m["remaining_hours"] == 70.0


def test_register_create_and_permissions(client, org_with_users):
    # membre non-désigné (tom) ne peut pas écrire
    r = client.post("/api/safety-register", json={
        "entry_date": "2026-08-19", "location": "Atelier 2",
        "description": "Fuite d'eau au plafond"}, headers=_h(org_with_users["tom_token"]))
    assert r.status_code == 403
    # le bureau (marc, secrétaire) peut écrire
    r = client.post("/api/safety-register", json={
        "entry_date": "2026-08-19", "location": "Atelier 2",
        "description": "Fuite d'eau au plafond"}, headers=_h(org_with_users["marc_token"]))
    assert r.status_code == 200, r.text
    eid = r.json()["id"]
    # lecture par tous
    r = client.get("/api/safety-register", headers=_h(org_with_users["tom_token"]))
    assert r.status_code == 200
    entries = r.json()
    assert any(e["id"] == eid and e["status"] == "pending" for e in entries)
    # contreseing par le bureau
    r = client.post(f"/api/safety-register/{eid}/countersign",
                    json={"chef_service_name": "M. Kirch"}, headers=_h(org_with_users["sophie_token"]))
    assert r.status_code == 200
    assert r.json()["status"] == "countersigned"
    # un simple membre ne peut pas contresigner (le chef de service signe, le bureau constate)
    r = client.post(f"/api/safety-register/{eid}/countersign",
                    json={"chef_service_name": "M. Kirch"}, headers=_h(org_with_users["tom_token"]))
    assert r.status_code == 403
    # suppression par l'auteur
    r = client.delete(f"/api/safety-register/{eid}", headers=_h(org_with_users["marc_token"]))
    assert r.status_code == 200
    entries = client.get("/api/safety-register", headers=_h(org_with_users["sophie_token"])).json()
    assert not any(e["id"] == eid for e in entries)


def test_protection_members_and_candidates(client, org_with_users):
    db = SessionLocal()
    org = db.query(Organization).get(org_with_users["org_id"])
    org.mandate_end_date = datetime.utcnow() + timedelta(days=60)
    db.commit()
    db.close()
    r = client.get("/api/protection", headers=_h(org_with_users["sophie_token"]))
    assert r.status_code == 200
    data = r.json()
    members = [p for p in data["people"] if p["kind"] == "member"]
    assert members
    # tous les titulaires/suppléants protégés jusqu'à fin de mandat + 6 mois
    for m in members:
        assert m["status"] == "protected"
        assert m["protected_until"] is not None
    # pas de candidats (aucune élection clôturée) → seuls les membres
    assert not any(p["kind"] == "candidate" for p in data["people"])
