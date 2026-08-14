"""Tests for the vault recovery-key feature (recovery envelope)."""

import base64
import json
import os

from tests.test_vault import _make_envelope, _login


def _create_vault(client, token):
    h = {"Authorization": f"Bearer {token}"}
    r = client.post("/api/vault", headers=h, json=_make_envelope())
    assert r.status_code == 201, r.json()
    return r.json()


class TestRecoveryKey:
    def test_put_recovery_key_success(self, client, db, org_with_users):
        t = org_with_users
        h = {"Authorization": f"Bearer {t['sophie_token']}"}
        _create_vault(client, t["sophie_token"])

        env = _make_envelope()
        env["kdf_params"] = json.dumps({"algo": "pbkdf2", "iterations": 210000, "hash": "SHA-256"})
        r = client.put("/api/vault/recovery-key", headers=h, json=env)
        assert r.status_code == 200, r.json()
        assert r.json()["recovery_enabled"] is True

        # La clé de récupération elle-même n'est JAMAIS stockée
        from app.models.vault_key import VaultKey
        vk = db.query(VaultKey).filter(VaultKey.organization_id == t["org_id"]).first()
        assert vk.recovery_wrapped_dek is not None
        assert vk.recovery_kdf_params is not None
        assert "X7K2" not in json.dumps(vk.recovery_kdf_params or "")
        # KDF params = pbkdf2 (pas argon2)
        params = json.loads(vk.recovery_kdf_params)
        assert params["algo"] == "pbkdf2"

    def test_status_reports_recovery_enabled(self, client, org_with_users):
        t = org_with_users
        h = {"Authorization": f"Bearer {t['sophie_token']}"}
        _create_vault(client, t["sophie_token"])

        r = client.get("/api/vault/status", headers=h)
        assert r.json()["recovery_enabled"] is False

        client.put("/api/vault/recovery-key", headers=h, json=_make_envelope())
        r = client.get("/api/vault/status", headers=h)
        assert r.json()["recovery_enabled"] is True

    def test_put_rejected_for_non_bureau(self, client, org_with_users):
        t = org_with_users
        _create_vault(client, t["sophie_token"])
        h = {"Authorization": f"Bearer {t['tom_token']}"}
        r = client.put("/api/vault/recovery-key", headers=h, json=_make_envelope())
        assert r.status_code == 403

    def test_put_404_without_vault(self, client, org_with_users):
        t = org_with_users
        h = {"Authorization": f"Bearer {t['sophie_token']}"}
        r = client.put("/api/vault/recovery-key", headers=h, json=_make_envelope())
        assert r.status_code == 404

    def test_put_guards_sizes(self, client, org_with_users):
        t = org_with_users
        h = {"Authorization": f"Bearer {t['sophie_token']}"}
        _create_vault(client, t["sophie_token"])

        bad = _make_envelope()
        bad["nonce"] = base64.b64encode(os.urandom(8)).decode("ascii")
        assert client.put("/api/vault/recovery-key", headers=h, json=bad).status_code == 400

        bad = _make_envelope()
        bad["kdf_salt"] = base64.b64encode(os.urandom(8)).decode("ascii")
        assert client.put("/api/vault/recovery-key", headers=h, json=bad).status_code == 400

        bad = _make_envelope()
        bad["wrapped_dek"] = base64.b64encode(os.urandom(16)).decode("ascii")
        assert client.put("/api/vault/recovery-key", headers=h, json=bad).status_code == 400

    def test_put_ignores_unknown_secret_fields(self, client, org_with_users):
        """Un champ secret en clair (nommé recovery_key) est ignoré par le schéma,
        jamais accepté ni stocké — l'enveloppe reste la seule source."""
        t = org_with_users
        h = {"Authorization": f"Bearer {t['sophie_token']}"}
        _create_vault(client, t["sophie_token"])

        env = _make_envelope()
        env["recovery_key"] = "X7K2-9M4P-Q8RT-3V2N"  # champ inconnu → ignoré
        r = client.put("/api/vault/recovery-key", headers=h, json=env)
        assert r.status_code == 200
        assert "recovery_key" not in r.json()

    def test_replace_invalidates_previous(self, client, db, org_with_users):
        """Remplacer l'enveloppe = la clé précédente ne fonctionne plus."""
        t = org_with_users
        h = {"Authorization": f"Bearer {t['sophie_token']}"}
        _create_vault(client, t["sophie_token"])
        client.put("/api/vault/recovery-key", headers=h, json=_make_envelope())

        # Remplacer par une nouvelle enveloppe (valeurs différentes)
        client.put("/api/vault/recovery-key", headers=h, json=_make_envelope())
        from app.models.vault_key import VaultKey
        vk = db.query(VaultKey).filter(VaultKey.organization_id == t["org_id"]).first()
        assert vk.recovery_wrapped_dek is not None
        r = client.get("/api/vault/status", headers=h)
        assert r.json()["recovery_enabled"] is True

    def test_delete_revokes(self, client, db, org_with_users):
        t = org_with_users
        h = {"Authorization": f"Bearer {t['sophie_token']}"}
        _create_vault(client, t["sophie_token"])
        client.put("/api/vault/recovery-key", headers=h, json=_make_envelope())

        r = client.delete("/api/vault/recovery-key", headers=h)
        assert r.status_code == 200
        assert r.json()["recovery_enabled"] is False

        from app.models.vault_key import VaultKey
        vk = db.query(VaultKey).filter(VaultKey.organization_id == t["org_id"]).first()
        assert vk.recovery_wrapped_dek is None
        assert vk.recovery_nonce is None

    def test_delete_rejected_for_non_bureau(self, client, org_with_users):
        t = org_with_users
        _create_vault(client, t["sophie_token"])
        client.put("/api/vault/recovery-key", headers={"Authorization": f"Bearer {t['sophie_token']}"}, json=_make_envelope())
        r = client.delete("/api/vault/recovery-key", headers={"Authorization": f"Bearer {t['tom_token']}"})
        assert r.status_code == 403
