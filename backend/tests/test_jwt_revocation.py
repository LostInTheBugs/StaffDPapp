"""Tests de la révocation JWT (jti + token_version, ANALYSE-2026-08-24 §7).

Fixture org_with_users : sophie (admin, id=1), marc (id=2), tom (id=3),
other (autre org, id=4) — emails @testpv.lu, mot de passe test123456.
"""

from app.core.security import create_access_token, decode_access_token
from tests.helpers import fetch_captcha


def _login(client, email: str, password: str = "test123456") -> str:
    cid, ans = fetch_captcha(client)
    r = client.post("/api/auth/login", json={
        "email": email, "password": password,
        "captcha_id": cid, "captcha_answer": ans,
    })
    assert r.status_code == 200, f"Login {email} failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


# ── jti présent dans les jetons ───────────────────────────────────

def test_token_carries_jti_and_ver(client, org_with_users):
    tok = _login(client, "sophie@testpv.lu")
    payload = decode_access_token(tok)
    assert payload is not None
    assert payload.get("jti")  # identifiant unique de jeton
    assert payload.get("ver") == 0


# ── Logout ciblé (jti) ────────────────────────────────────────────

def test_logout_revokes_current_token(client, org_with_users):
    tok = _login(client, "tom@testpv.lu")
    r = client.post("/api/auth/logout", headers=_h(tok))
    assert r.status_code == 204
    # le jeton révoqué est refusé
    r2 = client.get("/api/meetings", headers=_h(tok))
    assert r2.status_code == 401
    assert "révoqué" in r2.json()["detail"]
    # un nouveau login fonctionne toujours
    tok2 = _login(client, "tom@testpv.lu")
    assert client.get("/api/meetings", headers=_h(tok2)).status_code == 200


def test_logout_is_idempotent(client, org_with_users):
    tok = _login(client, "tom@testpv.lu")
    assert client.post("/api/auth/logout", headers=_h(tok)).status_code == 204
    assert client.post("/api/auth/logout", headers=_h(tok)).status_code == 204


# ── Révocation globale d'un utilisateur (admin) ───────────────────

def test_revoke_user_kills_all_tokens(client, org_with_users):
    # deux jetons simultanés pour le même compte (tom = id 3)
    tok_a = _login(client, "tom@testpv.lu")
    tok_b = _login(client, "tom@testpv.lu")
    assert client.get("/api/meetings", headers=_h(tok_a)).status_code == 200

    r = client.post("/api/auth/revoke-user/3", headers=_h(org_with_users["sophie_token"]))
    assert r.status_code == 200, r.text
    assert client.get("/api/meetings", headers=_h(tok_a)).status_code == 401
    assert client.get("/api/meetings", headers=_h(tok_b)).status_code == 401
    # le compte peut se reconnecter (nouveau token ver=1)
    tok_c = _login(client, "tom@testpv.lu")
    assert client.get("/api/meetings", headers=_h(tok_c)).status_code == 200


def test_revoke_user_admin_only(client, org_with_users):
    r = client.post("/api/auth/revoke-user/3", headers=_h(org_with_users["tom_token"]))
    assert r.status_code == 403


def test_revoke_user_cross_org_404(client, org_with_users):
    r = client.post("/api/auth/revoke-user/9999", headers=_h(org_with_users["sophie_token"]))
    assert r.status_code == 404


# ── Retrait de membre → jeton mort immédiatement ──────────────────

def test_remove_member_revokes_tokens(client, org_with_users):
    # tom = id 3 (titulaire, non admin — retirable par sophie)
    tok = _login(client, "tom@testpv.lu")
    assert client.get("/api/meetings", headers=_h(tok)).status_code == 200
    r = client.delete("/api/organization/members/3", headers=_h(org_with_users["sophie_token"]))
    assert r.status_code == 200 and r.json()["removed"] is True
    # compte désactivé → 403 (is_active vérifié AVANT la révocation) ;
    # token_version incrémenté = seconde ligne de défense
    r2 = client.get("/api/meetings", headers=_h(tok))
    assert r2.status_code in (401, 403)


# ── Jetons émis avant la fonctionnalité (sans ver) ────────────────

def test_legacy_token_without_ver_dies_after_revocation(client, org_with_users):
    """Un jeton sans claim `ver` est traité comme ver=0 : après une
    révocation (ver=1), il est refusé — comportement voulu."""
    legacy = create_access_token(data={"sub": "3", "org_id": org_with_users["org_id"], "typ": "access"})
    r = client.get("/api/meetings", headers=_h(legacy))
    assert r.status_code == 200  # ver=0 == token_version=0 → valide
    client.post("/api/auth/revoke-user/3", headers=_h(org_with_users["sophie_token"]))
    r2 = client.get("/api/meetings", headers=_h(legacy))
    assert r2.status_code == 401
