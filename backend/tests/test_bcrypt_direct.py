"""Tests bcrypt direct (passlib retiré) + garde de troncature 72 octets."""

import bcrypt
import pytest

from app.core.security import hash_password, verify_password
from tests.helpers import fetch_captcha


# ── hash_password / verify_password ───────────────────────────────

def test_hash_verify_roundtrip():
    hashed = hash_password("mon-mot-de-passe-123")
    assert hashed.startswith("$2b$")
    assert verify_password("mon-mot-de-passe-123", hashed) is True


def test_verify_wrong_password():
    hashed = hash_password("bon-mot-de-passe")
    assert verify_password("mauvais-mot-de-passe", hashed) is False


def test_verify_malformed_hash_returns_false():
    assert verify_password("x", "pas-un-hash-bcrypt") is False


def test_passlib_format_hash_still_verifies():
    """Les hash existants (format $2b$, identique à passlib) restent valides."""
    legacy = bcrypt.hashpw(b"demo123456", bcrypt.gensalt()).decode("utf-8")
    assert verify_password("demo123456", legacy) is True


def test_bcrypt_truncation_is_rejected_by_schema():
    """Un mot de passe > 72 octets est refusé à la validation (jamais tronqué)."""
    from app.schemas.auth import RegisterRequest, BCRYPT_MAX_BYTES

    long_pwd = "a" * (BCRYPT_MAX_BYTES + 1)
    with pytest.raises(ValueError, match="72 octets"):
        RegisterRequest(
            email="x@y.lu", password=long_pwd, first_name="X", last_name="Y",
            invitation_code="ABCDEFGH", captcha_id="c", captcha_answer="1",
        )


# ── Via l'API ─────────────────────────────────────────────────────

def test_change_password_rejects_over_72_bytes(client, org_with_users):
    tok = org_with_users["sophie_token"]
    r = client.put(
        "/api/auth/password",
        json={"old_password": "test123456", "new_password": "b" * 73},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 400
    assert "72 octets" in r.json()["detail"]


def test_change_password_accepts_exactly_72_bytes(client, org_with_users):
    tok = org_with_users["sophie_token"]
    r = client.put(
        "/api/auth/password",
        json={"old_password": "test123456", "new_password": "c" * 72},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200, r.text
    # remise de l'état d'origine pour les autres tests
    r2 = client.put(
        "/api/auth/password",
        json={"old_password": "c" * 72, "new_password": "test123456"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r2.status_code == 200
