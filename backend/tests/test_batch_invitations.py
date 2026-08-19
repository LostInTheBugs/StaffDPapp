"""Tests invitation en masse + retrait de membre (chantier 2026-08-19).

Couvre :
- POST /api/invitations/batch : admin-only, création employé non-élu,
  doublons (lot / compte existant / invitation en attente), lignes invalides
  partielles, plafond de lot, compatibilité du hash allégé.
- Règle assouplie : un salarié non-élu peut être invité SANS désignation.
- DELETE /api/organization/members/{id} : admin-only, suppression douce,
  login bloqué, gardes (soi-même, autre org).
"""

import pytest

from app.core.database import SessionLocal
from app.core.security import verify_invitation_code
from app.models import Invitation, User
from tests.helpers import fetch_captcha, create_invitation


def _login(client, email: str, password: str = "test123456") -> str:
    cid, ans = fetch_captcha(client)
    r = client.post("/api/auth/login", json={
        "email": email, "password": password,
        "captcha_id": cid, "captcha_answer": ans,
    })
    assert r.status_code == 200, f"Login {email} failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Invitation en masse ─────────────────────────────────────────────

def test_batch_member_forbidden(client, org_with_users):
    r = client.post("/api/invitations/batch", json={
        "invitations": [{"email": "x@test.lu", "first_name": "X", "last_name": "Y"}],
    }, headers=_h(org_with_users["marc_token"]))
    assert r.status_code == 403


def test_batch_creates_plain_employee_invitations(client, org_with_users):
    r = client.post("/api/invitations/batch", json={
        "invitations": [
            {"email": "alice@test.lu", "first_name": "Alice", "last_name": "Martin"},
            {"email": "bob@test.lu", "first_name": "Bob", "last_name": "Dupont"},
        ],
    }, headers=_h(org_with_users["sophie_token"]))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["created"] == 2
    assert data["skipped"] == 0 and data["failed"] == 0
    created = [res for res in data["results"] if res["status"] == "created"]
    assert len(created) == 2
    for res in created:
        inv = res["invitation"]
        assert inv["delegue_status"] == "employe"
        assert inv["delegue_role"] == "membre"
        assert len(inv["code"]) == 26
        assert inv["is_delegue_securite_sante"] is False
        # Le code (hash allégé) reste vérifiable avec le hasher par défaut
        db = SessionLocal()
        row = db.query(Invitation).filter(Invitation.email == res["email"]).first()
        assert row is not None
        assert row.expires_at is not None  # 30 jours
        assert verify_invitation_code(inv["code"], row.code_hash)
        db.close()


def test_batch_skips_existing_user_and_pending_invite(client, org_with_users):
    # tom@testpv.lu est déjà membre ; on crée une invitation en attente pour carol
    db = SessionLocal()
    sophie = db.query(User).filter(User.email == "sophie@testpv.lu").first()
    create_invitation(db, "carol@test.lu", org_with_users["org_id"],
                      sophie.id, code="CAROL123")
    db.close()

    r = client.post("/api/invitations/batch", json={
        "invitations": [
            {"email": "tom@testpv.lu", "first_name": "Tom", "last_name": "Wagner"},
            {"email": "carol@test.lu", "first_name": "Carol", "last_name": "Leroy"},
        ],
    }, headers=_h(org_with_users["sophie_token"]))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["created"] == 0
    assert data["skipped"] == 2
    statuses = {res["email"]: res["status"] for res in data["results"]}
    assert statuses["tom@testpv.lu"] == "duplicate"
    assert statuses["carol@test.lu"] == "duplicate"


def test_batch_partial_invalid_line(client, org_with_users):
    r = client.post("/api/invitations/batch", json={
        "invitations": [
            {"email": "not-an-email", "first_name": "X", "last_name": "Y"},
            {"email": "valid@test.lu", "first_name": "Val", "last_name": "Ide"},
        ],
    }, headers=_h(org_with_users["sophie_token"]))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["created"] == 1
    assert data["failed"] == 1
    bad = [res for res in data["results"] if res["status"] == "invalid"]
    assert bad and bad[0]["email"] == "not-an-email"
    assert bad[0]["message"]


def test_batch_dedup_within_batch(client, org_with_users):
    r = client.post("/api/invitations/batch", json={
        "invitations": [
            {"email": "dup@test.lu", "first_name": "D", "last_name": "U"},
            {"email": "dup@test.lu", "first_name": "D", "last_name": "U"},
        ],
    }, headers=_h(org_with_users["sophie_token"]))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["created"] == 1
    assert data["skipped"] == 1


def test_batch_too_many_lines(client, org_with_users):
    invites = [
        {"email": f"user{i}@test.lu", "first_name": "F", "last_name": "L"}
        for i in range(201)
    ]
    r = client.post("/api/invitations/batch", json={"invitations": invites},
                    headers=_h(org_with_users["sophie_token"]))
    assert r.status_code == 422


def test_plain_employee_single_invite_relaxed(client, org_with_users):
    """Règle assouplie : employé non-élu sans désignation → autorisé."""
    r = client.post("/api/invitations", json={
        "email": "simple@test.lu", "first_name": "Simple", "last_name": "Employe",
        "delegue_status": "employe", "delegue_role": "membre",
    }, headers=_h(org_with_users["sophie_token"]))
    assert r.status_code == 201, r.text


def test_employe_still_no_bureau_function(client, org_with_users):
    """La règle « non-élu → pas de fonction au bureau » reste en place."""
    r = client.post("/api/invitations", json={
        "email": "bureau@test.lu", "first_name": "B", "last_name": "U",
        "delegue_status": "employe", "delegue_role": "president",
    }, headers=_h(org_with_users["sophie_token"]))
    assert r.status_code == 400


# ── Retrait de membre ───────────────────────────────────────────────

def test_remove_member_admin_only(client, org_with_users):
    r = client.delete("/api/organization/members/1", headers=_h(org_with_users["marc_token"]))
    assert r.status_code == 403


def test_remove_member_flow(client, org_with_users):
    # tom est membre ; sophie (admin) le retire
    db = SessionLocal()
    tom = db.query(User).filter(User.email == "tom@testpv.lu").first()
    tom_id = tom.id
    db.close()

    r = client.delete(f"/api/organization/members/{tom_id}", headers=_h(org_with_users["sophie_token"]))
    assert r.status_code == 200
    assert r.json()["removed"] is True

    # Login bloqué (compte désactivé → 403 « Compte désactivé », par design)
    cid, ans = fetch_captcha(client)
    r2 = client.post("/api/auth/login", json={
        "email": "tom@testpv.lu", "password": "test123456",
        "captcha_id": cid, "captcha_answer": ans,
    })
    assert r2.status_code == 403

    # Disparu de la liste des membres
    r3 = client.get("/api/organization/members", headers=_h(org_with_users["sophie_token"]))
    emails = [m["email"] for m in r3.json()]
    assert "tom@testpv.lu" not in emails
    assert "sophie@testpv.lu" in emails

    # Idempotence : deuxième retrait → removed False
    r4 = client.delete(f"/api/organization/members/{tom_id}", headers=_h(org_with_users["sophie_token"]))
    assert r4.status_code == 200
    assert r4.json()["removed"] is False


def test_remove_member_self_blocked(client, org_with_users):
    db = SessionLocal()
    sophie = db.query(User).filter(User.email == "sophie@testpv.lu").first()
    sophie_id = sophie.id
    db.close()
    r = client.delete(f"/api/organization/members/{sophie_id}", headers=_h(org_with_users["sophie_token"]))
    assert r.status_code == 400


def test_remove_member_other_org_404(client, org_with_users):
    db = SessionLocal()
    other = db.query(User).filter(User.email == "other@other.lu").first()
    other_id = other.id
    db.close()
    r = client.delete(f"/api/organization/members/{other_id}", headers=_h(org_with_users["sophie_token"]))
    assert r.status_code == 404
