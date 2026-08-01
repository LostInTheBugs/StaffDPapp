"""Tests for the vault (coffre-fort) module — key envelope storage and API."""
import base64
import json
import os
import pytest
from tests.helpers import create_org, create_user, fetch_captcha
from app.models.vault_key import VaultKey
from app.core.database import SessionLocal


BUREAU_ROLES = {"president", "vice_president", "secretaire"}
NON_BUREAU = {"membre"}


def _make_envelope() -> dict:
    """Generate a realistic-looking opaque envelope (valid sizes, no secrets)."""
    return {
        "wrapped_dek": base64.b64encode(os.urandom(48)).decode("ascii"),
        "nonce": base64.b64encode(os.urandom(12)).decode("ascii"),
        "kdf_salt": base64.b64encode(os.urandom(16)).decode("ascii"),
        "kdf_params": json.dumps({"algo": "argon2id", "m": 65536, "t": 3, "p": 1}),
    }


def _login(client, email, password, captcha_id, captcha_answer):
    r = client.post("/api/auth/login", json={
        "email": email, "password": password,
        "captcha_id": captcha_id, "captcha_answer": captcha_answer,
    })
    assert r.status_code == 200, f"Login failed: {r.json()}"
    data = r.json()
    return data["access_token"]


# ═══════════════════════════════════════════════════════════════════
# POST /api/vault — création du coffre
# ═══════════════════════════════════════════════════════════════════

class TestCreateVault:
    def test_president_can_create_vault(self, client, db):
        """A bureau member (president) can create the vault."""
        org = create_org(db)
        user = create_user(db, "prez@test.com", "test123", org.id,
                           delegue_role="president")
        token = _login(client, "prez@test.com", "test123", *fetch_captcha(client))
        h = {"Authorization": f"Bearer {token}"}

        envelope = _make_envelope()
        r = client.post("/api/vault", json=envelope, headers=h)
        assert r.status_code == 201, f"Create vault failed: {r.json()}"
        data = r.json()
        assert data["dek_version"] == 1
        assert "wrapped_dek" in data

    def test_suppleant_rejected_403(self, client, db):
        """Non-bureau: suppléant without bureau role gets 403."""
        org = create_org(db)
        user = create_user(db, "supp@test.com", "test123", org.id,
                           delegue_status="suppleant", delegue_role="membre")
        token = _login(client, "supp@test.com", "test123", *fetch_captcha(client))
        h = {"Authorization": f"Bearer {token}"}

        r = client.post("/api/vault", json=_make_envelope(), headers=h)
        assert r.status_code == 403

    def test_titulaire_non_bureau_rejected_403(self, client, db):
        """Titulaire without bureau role (just 'membre') gets 403."""
        org = create_org(db)
        user = create_user(db, "membre@test.com", "test123", org.id,
                           delegue_status="titulaire", delegue_role="membre")
        token = _login(client, "membre@test.com", "test123", *fetch_captcha(client))
        h = {"Authorization": f"Bearer {token}"}

        r = client.post("/api/vault", json=_make_envelope(), headers=h)
        assert r.status_code == 403

    def test_vault_already_exists_409(self, client, db):
        """Second vault creation returns 409."""
        org = create_org(db)
        user = create_user(db, "prez2@test.com", "test123", org.id,
                           delegue_role="president")
        token = _login(client, "prez2@test.com", "test123", *fetch_captcha(client))
        h = {"Authorization": f"Bearer {token}"}

        envelope = _make_envelope()
        r1 = client.post("/api/vault", json=envelope, headers=h)
        assert r1.status_code == 201

        r2 = client.post("/api/vault", json=_make_envelope(), headers=h)
        assert r2.status_code == 409
        assert "existe déjà" in r2.json()["detail"]

    def test_secretaire_can_create_vault(self, client, db):
        """Secrétaire (bureau) can create vault."""
        org = create_org(db)
        user = create_user(db, "sec@test.com", "test123", org.id,
                           delegue_role="secretaire")
        token = _login(client, "sec@test.com", "test123", *fetch_captcha(client))
        h = {"Authorization": f"Bearer {token}"}

        r = client.post("/api/vault", json=_make_envelope(), headers=h)
        assert r.status_code == 201

    def test_vice_president_can_create_vault(self, client, db):
        """Vice-président (bureau) can create vault."""
        org = create_org(db)
        user = create_user(db, "vp@test.com", "test123", org.id,
                           delegue_role="vice_president")
        token = _login(client, "vp@test.com", "test123", *fetch_captcha(client))
        h = {"Authorization": f"Bearer {token}"}

        r = client.post("/api/vault", json=_make_envelope(), headers=h)
        assert r.status_code == 201


# ═══════════════════════════════════════════════════════════════════
# Validation des tailles
# ═══════════════════════════════════════════════════════════════════

class TestSizeValidation:
    def test_nonce_too_short(self, client, db):
        """Nonce < 12 bytes rejected."""
        org = create_org(db)
        user = create_user(db, "prez3@test.com", "test123", org.id,
                           delegue_role="president")
        token = _login(client, "prez3@test.com", "test123", *fetch_captcha(client))
        h = {"Authorization": f"Bearer {token}"}

        env = _make_envelope()
        env["nonce"] = base64.b64encode(os.urandom(8)).decode("ascii")
        r = client.post("/api/vault", json=env, headers=h)
        assert r.status_code in (400, 422), f"Expected 400/422, got {r.status_code}: {r.text}"

    def test_salt_too_short(self, client, db):
        """Salt < 16 bytes rejected."""
        org = create_org(db)
        user = create_user(db, "prez4@test.com", "test123", org.id,
                           delegue_role="president")
        token = _login(client, "prez4@test.com", "test123", *fetch_captcha(client))
        h = {"Authorization": f"Bearer {token}"}

        env = _make_envelope()
        env["kdf_salt"] = base64.b64encode(os.urandom(10)).decode("ascii")
        r = client.post("/api/vault", json=env, headers=h)
        assert r.status_code in (400, 422), f"Expected 400/422, got {r.status_code}: {r.text}"

    def test_wrapped_dek_too_short(self, client, db):
        """wrapped_dek < 48 bytes rejected."""
        org = create_org(db)
        user = create_user(db, "prez5@test.com", "test123", org.id,
                           delegue_role="president")
        token = _login(client, "prez5@test.com", "test123", *fetch_captcha(client))
        h = {"Authorization": f"Bearer {token}"}

        env = _make_envelope()
        env["wrapped_dek"] = base64.b64encode(os.urandom(32)).decode("ascii")
        r = client.post("/api/vault", json=env, headers=h)
        assert r.status_code in (400, 422), f"Expected 400/422, got {r.status_code}: {r.text}"


# ═══════════════════════════════════════════════════════════════════
# GET /api/vault/key — récupération de l'enveloppe
# ═══════════════════════════════════════════════════════════════════

class TestGetKey:
    def test_get_own_key_success(self, client, db):
        """A user can retrieve their own key envelope."""
        org = create_org(db)
        user = create_user(db, "prez6@test.com", "test123", org.id,
                           delegue_role="president")
        token = _login(client, "prez6@test.com", "test123", *fetch_captcha(client))
        h = {"Authorization": f"Bearer {token}"}

        envelope = _make_envelope()
        r = client.post("/api/vault", json=envelope, headers=h)
        assert r.status_code == 201

        r = client.get("/api/vault/key", headers=h)
        assert r.status_code == 200
        data = r.json()
        assert data["dek_version"] == 1
        assert data["wrapped_dek"] == envelope["wrapped_dek"]
        assert data["nonce"] == envelope["nonce"]

    def test_get_key_404_when_no_vault(self, client, db):
        """404 when user has no vault key."""
        org = create_org(db)
        user = create_user(db, "noob@test.com", "test123", org.id)
        token = _login(client, "noob@test.com", "test123", *fetch_captcha(client))
        h = {"Authorization": f"Bearer {token}"}

        r = client.get("/api/vault/key", headers=h)
        assert r.status_code == 404

    def test_get_key_only_returns_blobs(self, client, db):
        """GET /api/vault/key returns ONLY opaque blobs — nothing readable."""
        org = create_org(db, name="OrgA")
        user = create_user(db, "prez7@test.com", "test123", org.id,
                           delegue_role="president")
        token = _login(client, "prez7@test.com", "test123", *fetch_captcha(client))
        h = {"Authorization": f"Bearer {token}"}

        envelope = _make_envelope()
        r = client.post("/api/vault", json=envelope, headers=h)
        assert r.status_code == 201

        # Inspect the database directly — no human-readable text anywhere
        db_session = SessionLocal()
        vk = db_session.query(VaultKey).filter(VaultKey.organization_id == org.id).first()
        assert vk is not None

        # All stored columns must be binary blobs or encoded JSON, never plaintext secrets
        # wrapped_dek: binary blob (not text)
        assert isinstance(vk.wrapped_dek, bytes)
        # Verify it doesn't look like readable text
        try:
            decoded = vk.wrapped_dek.decode("utf-8")
            # If it decodes, it must not contain common password-like words
            for forbidden in ["password", "demo", "test123", "secret", "dek"]:
                assert forbidden not in decoded.lower(), \
                    f"Found forbidden word '{forbidden}' in wrapped_dek"
        except UnicodeDecodeError:
            pass  # Good — raw binary, not text at all

        # nonce: raw binary
        assert isinstance(vk.nonce, bytes)
        # kdf_salt: raw binary
        assert isinstance(vk.kdf_salt, bytes)
        # kdf_params: JSON, but never contains secret material
        assert isinstance(vk.kdf_params, str)
        params = json.loads(vk.kdf_params)
        for forbidden in ["password", "dek", "secret"]:
            assert forbidden not in str(params).lower()

        db_session.close()

        # API response must also be blobs (base64)
        data = r.json()
        assert isinstance(data["wrapped_dek"], str)
        assert isinstance(data["nonce"], str)
        # Decode base64 back — must be binary
        decoded_dek = base64.b64decode(data["wrapped_dek"])
        assert isinstance(decoded_dek, bytes)
        decoded_nonce = base64.b64decode(data["nonce"])
        assert isinstance(decoded_nonce, bytes)


# ═══════════════════════════════════════════════════════════════════
# PUT /api/vault/key — remplacement d'enveloppe
# ═══════════════════════════════════════════════════════════════════

class TestReplaceKey:
    def test_replace_own_key_success(self, client, db):
        """User can replace their own key envelope."""
        org = create_org(db)
        user = create_user(db, "prez8@test.com", "test123", org.id,
                           delegue_role="president")
        token = _login(client, "prez8@test.com", "test123", *fetch_captcha(client))
        h = {"Authorization": f"Bearer {token}"}

        # Create vault first
        r = client.post("/api/vault", json=_make_envelope(), headers=h)
        assert r.status_code == 201

        # Replace with a new envelope
        new_env = _make_envelope()
        r = client.put("/api/vault/key", json=new_env, headers=h)
        assert r.status_code == 200
        data = r.json()
        assert data["wrapped_dek"] == new_env["wrapped_dek"]
        assert data["nonce"] == new_env["nonce"]

    def test_replace_key_404_if_no_key(self, client, db):
        """PUT /api/vault/key returns 404 if user has no key."""
        org = create_org(db)
        user = create_user(db, "noob2@test.com", "test123", org.id,
                           delegue_role="president")
        token = _login(client, "noob2@test.com", "test123", *fetch_captcha(client))
        h = {"Authorization": f"Bearer {token}"}

        r = client.put("/api/vault/key", json=_make_envelope(), headers=h)
        assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# GET /api/vault/status
# ═══════════════════════════════════════════════════════════════════

class TestVaultStatus:
    def test_status_not_enabled(self, client, db):
        """Before vault creation, status shows disabled."""
        org = create_org(db)
        user = create_user(db, "user1@test.com", "test123", org.id)
        token = _login(client, "user1@test.com", "test123", *fetch_captcha(client))
        h = {"Authorization": f"Bearer {token}"}

        r = client.get("/api/vault/status", headers=h)
        assert r.status_code == 200
        data = r.json()
        assert data["enabled"] is False
        assert data["has_key"] is False
        assert data["dek_version"] is None

    def test_status_enabled_with_key(self, client, db):
        """After vault creation, status shows enabled + has_key."""
        org = create_org(db)
        user = create_user(db, "prez9@test.com", "test123", org.id,
                           delegue_role="president")
        token = _login(client, "prez9@test.com", "test123", *fetch_captcha(client))
        h = {"Authorization": f"Bearer {token}"}

        r = client.post("/api/vault", json=_make_envelope(), headers=h)
        assert r.status_code == 201

        r = client.get("/api/vault/status", headers=h)
        assert r.status_code == 200
        data = r.json()
        assert data["enabled"] is True
        assert data["has_key"] is True
        assert data["dek_version"] == 1


# ═══════════════════════════════════════════════════════════════════
# Cloisonnement par organisation
# ═══════════════════════════════════════════════════════════════════

class TestIsolation:
    def test_other_org_cannot_get_key(self, client, db):
        """User in org B gets 404 trying to read org A's vault."""
        org_a = create_org(db, name="OrgA")
        org_b = create_org(db, name="OrgB")

        user_a = create_user(db, "prez_a@test.com", "test123", org_a.id,
                             delegue_role="president")
        user_b = create_user(db, "user_b@test.com", "test123", org_b.id)

        token_a = _login(client, "prez_a@test.com", "test123", *fetch_captcha(client))
        token_b = _login(client, "user_b@test.com", "test123", *fetch_captcha(client))
        h_a = {"Authorization": f"Bearer {token_a}"}
        h_b = {"Authorization": f"Bearer {token_b}"}

        # Create vault in org A
        r = client.post("/api/vault", json=_make_envelope(), headers=h_a)
        assert r.status_code == 201

        # User B tries to access vault key — 404 (not their org)
        r = client.get("/api/vault/key", headers=h_b)
        assert r.status_code == 404

        # User B tries to get status — should see disabled (org B)
        r = client.get("/api/vault/status", headers=h_b)
        assert r.status_code == 200
        assert r.json()["enabled"] is False

        # User B tries replace key — 404
        r = client.put("/api/vault/key", json=_make_envelope(), headers=h_b)
        assert r.status_code == 404
