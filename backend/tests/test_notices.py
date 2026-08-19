"""Tests tableau d'affichage virtuel (Art. L.414-16).

Matrice des droits :
- LECTURE : tout membre de l'org (employés compris).
- ÉCRITURE : admin, bureau, délégué sécurité/santé, délégué égalité.
- ÉDITION/SUPPRESSION : auteur ou bureau ; isolation entre organisations.
"""

from app.core.database import SessionLocal
from app.models import User
from tests.helpers import fetch_captcha


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


def _create_user(db, email: str, org_id: int, **kwargs):
    from tests.helpers import create_user
    return create_user(db, email, "test123456", org_id, **kwargs)


# ── Lecture ─────────────────────────────────────────────────────────

def test_notices_readable_by_any_member(client, org_with_users):
    r = client.get("/api/notices", headers=_h(org_with_users["sophie_token"]))
    assert r.status_code == 200 and r.json() == []
    r2 = client.get("/api/notices", headers=_h(org_with_users["tom_token"]))
    assert r2.status_code == 200


def test_notices_readable_by_plain_employee(client, org_with_users):
    db = SessionLocal()
    _create_user(db, "employe@test.lu", org_with_users["org_id"],
                 delegue_status="employe", role="member")
    db.close()
    tok = _login(client, "employe@test.lu")
    r = client.get("/api/notices", headers=_h(tok))
    assert r.status_code == 200


# ── Écriture (qui peut afficher — miroir de L.414-16) ───────────────

def test_notices_post_forbidden_for_plain_member(client, org_with_users):
    r = client.post("/api/notices", json={
        "title": "Spam", "body": "Pas autorisé",
    }, headers=_h(org_with_users["tom_token"]))
    assert r.status_code == 403


def test_notices_post_allowed_admin_and_bureau(client, org_with_users):
    r = client.post("/api/notices", json={
        "title": "Réunion", "body": "Prochaine réunion le 5 septembre.",
    }, headers=_h(org_with_users["sophie_token"]))
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["title"] == "Réunion"
    assert data["pinned"] is False
    assert data["created_by_name"] == "Sophie Muller"

    # marc est secrétaire (bureau) → autorisé aussi
    r2 = client.post("/api/notices", json={
        "title": "Formation", "body": "Inscriptions ouvertes.",
    }, headers=_h(org_with_users["marc_token"]))
    assert r2.status_code == 201


def test_notices_post_allowed_designated_delegates(client, org_with_users):
    db = SessionLocal()
    _create_user(db, "secu@test.lu", org_with_users["org_id"],
                 delegue_status="employe", is_delegue_securite_sante=True)
    _create_user(db, "egal@test.lu", org_with_users["org_id"],
                 delegue_status="titulaire", is_delegue_egalite=True)
    db.close()

    tok_secu = _login(client, "secu@test.lu")
    r = client.post("/api/notices", json={
        "title": "Contrôle sécurité", "body": "Tournée hebdomadaire.",
    }, headers=_h(tok_secu))
    assert r.status_code == 201, r.text

    tok_egal = _login(client, "egal@test.lu")
    r2 = client.post("/api/notices", json={
        "title": "Égalité", "body": "Réunion des délégués égalité.",
    }, headers=_h(tok_egal))
    assert r2.status_code == 201, r2.text


def test_notices_pinned_ordered_first(client, org_with_users):
    client.post("/api/notices", json={"title": "Normal", "body": "x"},
                headers=_h(org_with_users["sophie_token"]))
    client.post("/api/notices", json={"title": "Important", "body": "y", "pinned": True},
                headers=_h(org_with_users["sophie_token"]))
    r = client.get("/api/notices", headers=_h(org_with_users["tom_token"]))
    titles = [n["title"] for n in r.json()]
    assert titles[0] == "Important"


# ── Édition / suppression ───────────────────────────────────────────

def test_notices_edit_delete_author_or_bureau(client, org_with_users):
    # marc (secrétaire) publie
    r = client.post("/api/notices", json={"title": "A", "body": "b"},
                    headers=_h(org_with_users["marc_token"]))
    post_id = r.json()["id"]

    # tom (membre simple) ne peut pas modifier la publication de marc
    r = client.put(f"/api/notices/{post_id}", json={"title": "Hack"},
                   headers=_h(org_with_users["tom_token"]))
    assert r.status_code == 403

    # l'auteur peut modifier
    r = client.put(f"/api/notices/{post_id}", json={"title": "A2", "pinned": True},
                   headers=_h(org_with_users["marc_token"]))
    assert r.status_code == 200
    assert r.json()["title"] == "A2" and r.json()["pinned"] is True

    # le bureau (sophie) peut modifier la publication de marc
    r = client.put(f"/api/notices/{post_id}", json={"body": "b2"},
                   headers=_h(org_with_users["sophie_token"]))
    assert r.status_code == 200
    assert r.json()["body"] == "b2"

    # tom ne peut pas supprimer ; l'auteur oui
    assert client.delete(f"/api/notices/{post_id}", headers=_h(org_with_users["tom_token"])).status_code == 403
    assert client.delete(f"/api/notices/{post_id}", headers=_h(org_with_users["marc_token"])).status_code == 204
    assert client.get("/api/notices", headers=_h(org_with_users["sophie_token"])).json() == []


# ── Isolation entre organisations ───────────────────────────────────

def test_notices_org_isolation(client, org_with_users):
    client.post("/api/notices", json={"title": "Interne", "body": "secret"},
                headers=_h(org_with_users["sophie_token"]))

    # L'autre org ne voit rien et ne peut pas toucher aux affiches
    r = client.get("/api/notices", headers=_h(org_with_users["other_token"]))
    assert r.status_code == 200 and r.json() == []

    db = SessionLocal()
    from app.models import NoticePost
    post = db.query(NoticePost).first()
    post_id = post.id
    db.close()
    r2 = client.delete(f"/api/notices/{post_id}", headers=_h(org_with_users["other_token"]))
    assert r2.status_code == 404
    r3 = client.put(f"/api/notices/{post_id}", json={"title": "X"},
                    headers=_h(org_with_users["other_token"]))
    assert r3.status_code == 404


def test_notices_validation(client, org_with_users):
    r = client.post("/api/notices", json={"title": "", "body": "x"},
                    headers=_h(org_with_users["sophie_token"]))
    assert r.status_code == 422
    r2 = client.post("/api/notices", json={"title": "T", "body": ""},
                     headers=_h(org_with_users["sophie_token"]))
    assert r2.status_code == 422
