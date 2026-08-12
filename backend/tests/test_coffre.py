"""
Tests for invitation code hardening (Crockford 26 chars, Argon2id hashing)
and vault envelope exchange.
"""
import base64
import json
import os
import pytest
from tests.helpers import create_org, create_user, create_invitation, fetch_captcha
from app.core.security import (
    generate_invitation_code, normalize_invitation_code,
    hash_invitation_code, verify_invitation_code,
)
from app.models import Invitation, VaultKey
from app.core.database import SessionLocal


def _login(client, email, password, captcha_id, captcha_answer):
    r = client.post("/api/auth/login", json={
        "email": email, "password": password,
        "captcha_id": captcha_id, "captcha_answer": captcha_answer,
    })
    assert r.status_code == 200, f"Login failed: {r.json()}"
    return r.json()["access_token"]


# ═══════════════════════════════════════════════════════════════════
# Code generation and normalization
# ═══════════════════════════════════════════════════════════════════

class TestInvitationCode:
    def test_code_length_is_26_by_default(self):
        code = generate_invitation_code()
        assert len(code) == 26

    def test_code_only_contains_crockford_alphabet(self):
        code = generate_invitation_code()
        crockford = set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")
        assert all(c in crockford for c in code)

    def test_code_never_contains_ambiguous_chars(self):
        # Generate 100 codes and check none contain I, L, O, U
        for _ in range(100):
            code = generate_invitation_code()
            assert "I" not in code
            assert "L" not in code
            assert "O" not in code
            assert "U" not in code

    def test_normalize_uppercase(self):
        assert normalize_invitation_code("abcd1234") == "ABCD1234"

    def test_normalize_strips_dashes(self):
        # Grouped display: XXXX-XXXX-XXXX-...
        code = "ABCD-EFGH-JK12-3456-MNPQ-RSTV"
        normalized = normalize_invitation_code(code)
        assert "-" not in normalized
        assert len(normalized) == len(code.replace("-", ""))  # all dashes removed

    def test_normalize_corrects_crockford_confusions(self):
        # I → 1, L → 1, O → 0
        assert normalize_invitation_code("IIII") == "1111"
        assert normalize_invitation_code("LLLL") == "1111"
        assert normalize_invitation_code("OOOO") == "0000"

    def test_hash_then_verify_round_trip(self):
        code = generate_invitation_code()
        hashed = hash_invitation_code(code)
        assert verify_invitation_code(code, hashed) is True

    def test_verify_wrong_code_returns_false(self):
        code = generate_invitation_code()
        hashed = hash_invitation_code(code)
        assert verify_invitation_code("WRONGCODE123456789", hashed) is False

    def test_normalized_input_verifies(self):
        """Lowercase, dashes, and Crockford confusions all verify."""
        code = generate_invitation_code()
        hashed = hash_invitation_code(code)

        # Lowercase version should verify
        assert verify_invitation_code(code.lower(), hashed) is True

        # Dashed version should verify
        dashed = "-".join(code[i:i+4] for i in range(0, len(code), 4))
        assert verify_invitation_code(dashed, hashed) is True


# ═══════════════════════════════════════════════════════════════════
# Code NOT stored in clear anywhere
# ═══════════════════════════════════════════════════════════════════

class TestCodeNotInClear:
    def test_code_not_in_database(self, db):
        """After creating an invitation, the plaintext code must not appear
        anywhere in the database. Only the Argon2id hash is stored."""
        org = create_org(db)
        user = create_user(db, "admin@test.com", "test123", org.id, role="admin")
        inv = create_invitation(db, "invited@test.com", org.id, user.id, code="REALPLAINTEXTCODE")

        # Inspect the database directly
        db_session = SessionLocal()
        row = db_session.query(Invitation).filter(Invitation.id == inv.id).first()
        assert row is not None

        # code_hash must exist and NOT be the plaintext code
        assert row.code_hash is not None
        assert row.code_hash != "REALPLAINTEXTCODE"
        # Must be an Argon2id hash (starts with $argon2id$)
        assert row.code_hash.startswith("$argon2id$")

        # The old 'code' column must NOT exist on the model
        assert not hasattr(row, 'code')

        # Verify the hash actually matches (sanity check)
        assert verify_invitation_code("REALPLAINTEXTCODE", row.code_hash) is True
        db_session.close()

    def test_code_not_in_api_response_list(self, client, db):
        """GET /api/invitations must NOT return the code."""
        org = create_org(db)
        user = create_user(db, "admin2@test.com", "test123", org.id, role="admin")
        create_invitation(db, "inv2@test.com", org.id, user.id, code="SECRETCODE123")

        token = _login(client, "admin2@test.com", "test123", *fetch_captcha(client))
        h = {"Authorization": f"Bearer {token}"}

        r = client.get("/api/invitations", headers=h)
        assert r.status_code == 200
        for inv in r.json():
            assert "code" not in inv, f"code field leaked in list response: {inv}"

    def test_code_in_create_response_only(self, client, db):
        """POST /api/invitations returns the code but only in the creation response."""
        org = create_org(db)
        user = create_user(db, "admin3@test.com", "test123", org.id, role="admin")
        token = _login(client, "admin3@test.com", "test123", *fetch_captcha(client))
        h = {"Authorization": f"Bearer {token}"}

        r = client.post("/api/invitations", json={
            "email": "new@test.com",
            "first_name": "New",
            "last_name": "User",
            "delegue_status": "titulaire",
            "delegue_role": "membre",
        }, headers=h)

        assert r.status_code == 201
        data = r.json()
        assert "code" in data
        code = data["code"]
        assert len(code) == 26
        # Crockford alphabet check
        crockford = set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")
        assert all(c in crockford for c in code)


# ═══════════════════════════════════════════════════════════════════
# Invitation lookup: wrong code → not found
# ═══════════════════════════════════════════════════════════════════

class TestInvitationLookup:
    def test_wrong_code_join_rejected(self, client, db):
        """Joining with a wrong invitation code returns 400."""
        org = create_org(db)
        user = create_user(db, "admin4@test.com", "test123", org.id, role="admin")
        create_invitation(db, "joinme@test.com", org.id, user.id, code="CORRECTCODE123")

        cid, ans = fetch_captcha(client)
        r = client.post("/api/join", json={
            "email": "joinme@test.com",
            "password": "test123456",
            "first_name": "Test",
            "last_name": "User",
            "invitation_code": "WRONGCODE9999999999",
            "captcha_id": cid,
            "captcha_answer": ans,
        })
        assert r.status_code == 400
        assert "invalide" in r.json()["detail"].lower()

    def test_correct_code_normalized_join_succeeds(self, client, db):
        """Joining with a correct but lowercased/dashed code works."""
        org = create_org(db)
        user = create_user(db, "admin5@test.com", "test123", org.id, role="admin")
        # Helper hashes the code internally
        inv = create_invitation(db, "norm@test.com", org.id, user.id, code="MYTESTCODE12345678")

        cid, ans = fetch_captcha(client)
        r = client.post("/api/join", json={
            "email": "norm@test.com",
            "password": "test123456",
            "first_name": "Test",
            "last_name": "User",
            # Use lowercase + dashes — must normalize and match
            "invitation_code": "mYtE-sTcO-dE12-3456-78",
            "captcha_id": cid,
            "captcha_answer": ans,
        })
        assert r.status_code == 201, f"Join failed: {r.json()}"


# ═══════════════════════════════════════════════════════════════════
# Vault envelope: invitation → join exchange
# ═══════════════════════════════════════════════════════════════════

def _make_envelope() -> dict:
    return {
        "wrapped_dek": base64.b64encode(os.urandom(48)).decode("ascii"),
        "nonce": base64.b64encode(os.urandom(12)).decode("ascii"),
        "kdf_salt": base64.b64encode(os.urandom(16)).decode("ascii"),
        "kdf_params": json.dumps({"algo": "argon2id", "m": 65536, "t": 3, "p": 1}),
    }


class TestVaultEnvelopeExchange:
    def test_invitation_envelope_stored_with_invitation_id(self, client, db):
        """Creating an invitation with vault_envelope stores VaultKey with invitation_id."""
        org = create_org(db)
        # Activate vault on the org
        org.pv_vault_enabled = True
        db.commit()

        user = create_user(db, "bureau@test.com", "test123", org.id,
                           delegue_role="president", role="admin")
        token = _login(client, "bureau@test.com", "test123", *fetch_captcha(client))
        h = {"Authorization": f"Bearer {token}"}

        envelope = _make_envelope()
        r = client.post("/api/invitations", json={
            "email": "envelope@test.com",
            "first_name": "Env",
            "last_name": "Test",
            "delegue_status": "titulaire",
            "delegue_role": "membre",
            "vault_envelope": envelope,
        }, headers=h)

        assert r.status_code == 201, f"Create invitation failed: {r.json()}"
        inv_id = r.json()["id"]

        # Check that VaultKey was created with invitation_id set
        db2 = SessionLocal()
        vk = db2.query(VaultKey).filter(VaultKey.invitation_id == inv_id).first()
        assert vk is not None
        assert vk.user_id is None  # invitation envelope, not user envelope
        db2.close()

    def test_invitation_envelope_deleted_after_join(self, client, db):
        """After /join with vault_envelope, the invitation envelope is deleted
        and a user envelope is created."""
        org = create_org(db)
        org.pv_vault_enabled = True
        db.commit()

        user = create_user(db, "bureau2@test.com", "test123", org.id,
                           delegue_role="president", role="admin")
        token = _login(client, "bureau2@test.com", "test123", *fetch_captcha(client))
        h = {"Authorization": f"Bearer {token}"}

        # Create invitation with envelope
        envelope = _make_envelope()
        r = client.post("/api/invitations", json={
            "email": "joiner@test.com",
            "first_name": "Join",
            "last_name": "Test",
            "delegue_status": "titulaire",
            "delegue_role": "membre",
            "vault_envelope": envelope,
        }, headers=h)
        assert r.status_code == 201
        inv_id = r.json()["id"]
        invite_code = r.json()["code"]

        # Verify invitation envelope exists
        db2 = SessionLocal()
        vk_inv = db2.query(VaultKey).filter(VaultKey.invitation_id == inv_id).first()
        assert vk_inv is not None
        db2.close()

        # Join with a new user envelope (re-wrapped)
        new_envelope = _make_envelope()
        cid, ans = fetch_captcha(client)
        r = client.post("/api/join", json={
            "email": "joiner@test.com",
            "password": "test123456",
            "first_name": "Join",
            "last_name": "Test",
            "invitation_code": invite_code,
            "captcha_id": cid,
            "captcha_answer": ans,
            "vault_envelope": new_envelope,
        })
        assert r.status_code == 201, f"Join failed: {r.json()}"

        # Verify old invitation envelope is GONE
        db3 = SessionLocal()
        vk_old = db3.query(VaultKey).filter(VaultKey.invitation_id == inv_id).first()
        assert vk_old is None, "Invitation envelope was not deleted"

        # Verify user envelope was created
        db4 = SessionLocal()
        from app.models.user import User as UserModel
        new_user = db4.query(UserModel).filter(UserModel.email == "joiner@test.com").first()
        vk_user = db4.query(VaultKey).filter(
            VaultKey.organization_id == org.id,
            VaultKey.user_id == new_user.id,
        ).first()
        assert vk_user is not None, "User envelope was not created after join"
        db4.close()

    def test_vault_envelope_on_invitation_without_vault_rejected(self, client, db):
        """Sending vault_envelope when vault is NOT enabled returns 400."""
        org = create_org(db)
        # DO NOT enable vault
        user = create_user(db, "bureau3@test.com", "test123", org.id,
                           delegue_role="president", role="admin")
        token = _login(client, "bureau3@test.com", "test123", *fetch_captcha(client))
        h = {"Authorization": f"Bearer {token}"}

        r = client.post("/api/invitations", json={
            "email": "nope@test.com",
            "first_name": "Nope",
            "last_name": "Test",
            "delegue_status": "titulaire",
            "delegue_role": "membre",
            "vault_envelope": _make_envelope(),
        }, headers=h)

        assert r.status_code == 400
        assert "coffre" in r.json()["detail"].lower()


# ═══════════════════════════════════════════════════════════════════
# Server refuses plaintext content when vault is enabled
# ═══════════════════════════════════════════════════════════════════

class TestEncryptionGuard:
    def test_server_refuses_section_without_nonce_when_vault_enabled(self, client, db):
        """When vault is enabled, create_minute rejects sections without nonce (422)."""
        org = create_org(db)
        org.pv_vault_enabled = True
        db.commit()

        user = create_user(db, "editor@test.com", "test123", org.id,
                           delegue_role="secretaire")
        token = _login(client, "editor@test.com", "test123", *fetch_captcha(client))
        h = {"Authorization": f"Bearer {token}"}

        # Create a meeting first
        from datetime import datetime, timedelta
        r = client.post("/api/meetings", json={
            "title": "Test Meeting",
            "date": (datetime.now() + timedelta(days=1)).isoformat(),
            "points": [{"description": "Point 1", "order": 0}],
            "invitee_ids": [],
        }, headers=h)
        assert r.status_code == 201
        meeting_id = r.json()["id"]

        # Try to create a minute WITHOUT nonce — must be rejected
        r = client.post(
            f"/api/meetings/{meeting_id}/minutes",
            json={
                "sections": [{
                    "position": 0,
                    "title": "Section non chiffrée",
                    "content": base64.b64encode(b"plaintext").decode("ascii"),
                    "visibility": "interne",
                    # Missing nonce!
                }]
            },
            headers=h,
        )
        assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.json()}"

    def test_server_accepts_section_with_nonce_when_vault_enabled(self, client, db):
        """When vault is enabled, sections WITH a valid nonce are accepted."""
        org = create_org(db)
        org.pv_vault_enabled = True
        db.commit()

        # Also need a VaultKey to get dek_version
        user = create_user(db, "editor2@test.com", "test123", org.id,
                           delegue_role="secretaire")
        db2 = SessionLocal()
        db2.add(VaultKey(
            organization_id=org.id,
            user_id=user.id,
            wrapped_dek=os.urandom(48),
            nonce=os.urandom(12),
            kdf_salt=os.urandom(16),
            kdf_params='{"algo":"argon2id","m":65536,"t":3,"p":1}',
            dek_version=1,
        ))
        db2.commit()
        db2.close()

        token = _login(client, "editor2@test.com", "test123", *fetch_captcha(client))
        h = {"Authorization": f"Bearer {token}"}

        from datetime import datetime, timedelta
        r = client.post("/api/meetings", json={
            "title": "Test Meeting 2",
            "date": (datetime.now() + timedelta(days=1)).isoformat(),
            "points": [{"description": "Point 1", "order": 0}],
            "invitee_ids": [],
        }, headers=h)
        assert r.status_code == 201
        meeting_id = r.json()["id"]

        # Encrypted section with nonce
        r = client.post(
            f"/api/meetings/{meeting_id}/minutes",
            json={
                "sections": [{
                    "position": 0,
                    "title": "Section chiffrée",
                    "content": base64.b64encode(os.urandom(64)).decode("ascii"),  # fake ciphertext
                    "nonce": base64.b64encode(os.urandom(12)).decode("ascii"),
                    "content_digest": base64.b64encode(os.urandom(32)).decode("ascii"),
                    "visibility": "interne",
                }]
            },
            headers=h,
        )
        assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.json()}"
        data = r.json()
        assert data["is_encrypted"] is True


# ═══════════════════════════════════════════════════════════════════
# content_digest — fingerprint stable sur le clair pour les PV chiffrés
# ═══════════════════════════════════════════════════════════════════


class TestContentDigestFingerprint:
    """Le fingerprint des sections chiffrées utilise content_digest (HMAC
    du clair) et non le ciphertext (qui change à chaque chiffrement à cause
    du nonce aléatoire)."""

    def _create_encrypted_minute(self, client, db, token, sections):
        """Helper: create meeting → minute with encrypted sections → return minute_id."""
        from datetime import datetime, timedelta
        h = {"Authorization": f"Bearer {token}"}
        r = client.post("/api/meetings", json={
            "title": "Réunion chiffrée",
            "date": (datetime.now() + timedelta(days=1)).isoformat(),
            "points": [{"description": "P1", "order": 0}],
            "invitee_ids": [],
        }, headers=h)
        assert r.status_code == 201, f"Create meeting failed: {r.json()}"
        meeting_id = r.json()["id"]
        r = client.post(
            f"/api/meetings/{meeting_id}/minutes",
            json={"sections": sections},
            headers=h,
        )
        assert r.status_code == 201, f"Create minute failed: {r.json()}"
        return r.json()["id"]

    def test_same_digest_different_ciphertext_stays_validated(self, client, db):
        """PV validé chiffré : renvoyer les MÊMES sections avec un ciphertext
        et un nonce DIFFÉRENTS mais le MÊME content_digest → le PV RESTE validé.

        C'est le test central : avec l'implémentation actuelle (fingerprint sur
        content), ce test ÉCHOUERAIT car le ciphertext change."""
        # Setup: org with vault enabled, VaultKey
        org = create_org(db)
        org.pv_vault_enabled = True
        db.commit()

        user_s = create_user(db, "secretaire@chiffre.lu", "test123", org.id,
                             delegue_role="secretaire")
        user_p = create_user(db, "president@chiffre.lu", "test123", org.id,
                             delegue_role="president")
        db_s = SessionLocal()
        db_s.add(VaultKey(
            organization_id=org.id, user_id=user_s.id,
            wrapped_dek=os.urandom(48), nonce=os.urandom(12),
            kdf_salt=os.urandom(16),
            kdf_params='{"algo":"argon2id","m":65536,"t":3,"p":1}',
            dek_version=1,
        ))
        db_s.commit()
        db_s.close()

        token_s = _login(client, "secretaire@chiffre.lu", "test123", *fetch_captcha(client))
        token_p = _login(client, "president@chiffre.lu", "test123", *fetch_captcha(client))
        h_s = {"Authorization": f"Bearer {token_s}"}
        h_p = {"Authorization": f"Bearer {token_p}"}

        # Two different ciphertexts for the SAME plaintext (different nonces)
        ct1 = base64.b64encode(os.urandom(64)).decode("ascii")
        ct2 = base64.b64encode(os.urandom(64)).decode("ascii")  # different!
        n1 = base64.b64encode(os.urandom(12)).decode("ascii")
        n2 = base64.b64encode(os.urandom(12)).decode("ascii")  # different!
        # Same digest (stable fingerprint of the plaintext)
        digest_b64 = base64.b64encode(os.urandom(32)).decode("ascii")

        sections_v1 = [{
            "position": 0, "title": "Résumé",
            "content": ct1, "nonce": n1,
            "content_digest": digest_b64,
            "visibility": "partage",
        }]

        minute_id = self._create_encrypted_minute(client, db, token_s, sections_v1)

        # Validate by president
        r = client.post(f"/api/minutes/{minute_id}/validate", headers=h_p)
        assert r.status_code == 200, f"Validate failed: {r.json()}"

        # Verify status is valide
        r = client.get(f"/api/minutes/{minute_id}", headers=h_s)
        assert r.json()["status"] == "valide"

        # Re-submit: same sections but DIFFERENT ciphertext + nonce, SAME digest
        r = client.put(
            f"/api/minutes/{minute_id}/sections",
            json={"sections": [{
                "position": 0, "title": "Résumé",
                "content": ct2, "nonce": n2,
                "content_digest": digest_b64,
                "visibility": "partage",
            }]},
            headers=h_s,
        )
        assert r.status_code == 200, f"Update sections failed: {r.json()}"
        data = r.json()
        assert data["status"] == "valide", \
            f"Expected 'valide' but got '{data['status']}' — fingerprint should use digest, not ciphertext"

    def test_different_digest_resets_to_brouillon(self, client, db):
        """PV validé chiffré, digest différent → retour en brouillon."""
        org = create_org(db)
        org.pv_vault_enabled = True
        db.commit()

        user_s = create_user(db, "sec2@chiffre.lu", "test123", org.id,
                             delegue_role="secretaire")
        user_p = create_user(db, "prez2@chiffre.lu", "test123", org.id,
                             delegue_role="president")
        db_s = SessionLocal()
        db_s.add(VaultKey(
            organization_id=org.id, user_id=user_s.id,
            wrapped_dek=os.urandom(48), nonce=os.urandom(12),
            kdf_salt=os.urandom(16),
            kdf_params='{"algo":"argon2id","m":65536,"t":3,"p":1}',
            dek_version=1,
        ))
        db_s.commit()
        db_s.close()

        token_s = _login(client, "sec2@chiffre.lu", "test123", *fetch_captcha(client))
        token_p = _login(client, "prez2@chiffre.lu", "test123", *fetch_captcha(client))
        h_s = {"Authorization": f"Bearer {token_s}"}
        h_p = {"Authorization": f"Bearer {token_p}"}

        ct = base64.b64encode(os.urandom(64)).decode("ascii")
        nonce = base64.b64encode(os.urandom(12)).decode("ascii")
        d1 = base64.b64encode(os.urandom(32)).decode("ascii")
        d2 = base64.b64encode(os.urandom(32)).decode("ascii")  # different

        sections = [{
            "position": 0, "title": "Résumé",
            "content": ct, "nonce": nonce,
            "content_digest": d1, "visibility": "partage",
        }]

        minute_id = self._create_encrypted_minute(client, db, token_s, sections)
        r = client.post(f"/api/minutes/{minute_id}/validate", headers=h_p)
        assert r.status_code == 200

        # Change digest
        r = client.put(
            f"/api/minutes/{minute_id}/sections",
            json={"sections": [{
                "position": 0, "title": "Résumé",
                "content": ct, "nonce": nonce,
                "content_digest": d2, "visibility": "partage",
            }]},
            headers=h_s,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "brouillon", \
            f"Expected 'brouillon' but got '{data['status']}' — different digest must reset"

    def test_direction_preview_returns_ciphertext_and_nonce(self, client, db):
        """direction-preview d'un PV chiffré : content = ciphertext + nonce.

        Régression : la preview réutilisait _projection_fingerprint, qui
        renvoie le digest HMAC (32 o) pour les sections chiffrées → le client
        tentait de déchiffrer un digest → échec AES-GCM, preview jamais
        affichée, export PDF impossible avec coffre actif.
        """
        org = create_org(db)
        org.pv_vault_enabled = True
        db.commit()

        user_s = create_user(db, "sec4@chiffre.lu", "test123", org.id,
                             delegue_role="secretaire")
        db_s = SessionLocal()
        db_s.add(VaultKey(
            organization_id=org.id, user_id=user_s.id,
            wrapped_dek=os.urandom(48), nonce=os.urandom(12),
            kdf_salt=os.urandom(16),
            kdf_params='{"algo":"argon2id","m":65536,"t":3,"p":1}',
            dek_version=1,
        ))
        db_s.commit()
        db_s.close()

        token_s = _login(client, "sec4@chiffre.lu", "test123", *fetch_captcha(client))
        h_s = {"Authorization": f"Bearer {token_s}"}

        ct = base64.b64encode(os.urandom(64)).decode("ascii")
        nonce = base64.b64encode(os.urandom(12)).decode("ascii")
        digest = base64.b64encode(os.urandom(32)).decode("ascii")

        sections = [{
            "position": 0, "title": "Résumé",
            "content": ct, "nonce": nonce,
            "content_digest": digest, "visibility": "partage",
        }]
        minute_id = self._create_encrypted_minute(client, db, token_s, sections)

        r = client.get(f"/api/minutes/{minute_id}/direction-preview", headers=h_s)
        assert r.status_code == 200
        ps = r.json()["sections"]
        assert len(ps) == 1
        assert ps[0]["content"] == ct, "la preview doit renvoyer le ciphertext, pas le digest"
        assert ps[0]["nonce"] == nonce, "le nonce doit accompagner le ciphertext"
        assert ps[0]["content"] != digest, "le digest HMAC ne doit JAMAIS servir de contenu"

    def test_encrypted_section_without_digest_rejected_400(self, client, db):
        """Section marquée is_encrypted (nonce présent) sans content_digest → 400."""
        org = create_org(db)
        org.pv_vault_enabled = True
        db.commit()

        user = create_user(db, "sec3@chiffre.lu", "test123", org.id,
                           delegue_role="secretaire")
        db_s = SessionLocal()
        db_s.add(VaultKey(
            organization_id=org.id, user_id=user.id,
            wrapped_dek=os.urandom(48), nonce=os.urandom(12),
            kdf_salt=os.urandom(16),
            kdf_params='{"algo":"argon2id","m":65536,"t":3,"p":1}',
            dek_version=1,
        ))
        db_s.commit()
        db_s.close()

        token = _login(client, "sec3@chiffre.lu", "test123", *fetch_captcha(client))
        h = {"Authorization": f"Bearer {token}"}

        from datetime import datetime, timedelta
        r = client.post("/api/meetings", json={
            "title": "Test digest manquant",
            "date": (datetime.now() + timedelta(days=1)).isoformat(),
            "points": [{"description": "P1", "order": 0}],
            "invitee_ids": [],
        }, headers=h)
        assert r.status_code == 201
        meeting_id = r.json()["id"]

        r = client.post(
            f"/api/meetings/{meeting_id}/minutes",
            json={"sections": [{
                "position": 0, "title": "Résumé",
                "content": base64.b64encode(os.urandom(64)).decode("ascii"),
                "nonce": base64.b64encode(os.urandom(12)).decode("ascii"),
                # content_digest MANQUANT
                "visibility": "partage",
            }]},
            headers=h,
        )
        assert r.status_code == 400, \
            f"Expected 400 for missing content_digest, got {r.status_code}: {r.json()}"
        assert "digest" in r.json()["detail"].lower()

    def test_non_encrypted_pv_unchanged(self, client, db):
        """Non-régression : les PV non chiffrés continuent de fonctionner
        comme avant (fingerprint sur content)."""
        # Setup: org WITHOUT vault
        org = create_org(db)
        user_s = create_user(db, "noclair@test.lu", "test123", org.id,
                             delegue_role="secretaire")
        user_p = create_user(db, "noclairp@test.lu", "test123", org.id,
                             delegue_role="president")
        token_s = _login(client, "noclair@test.lu", "test123", *fetch_captcha(client))
        token_p = _login(client, "noclairp@test.lu", "test123", *fetch_captcha(client))
        h_s = {"Authorization": f"Bearer {token_s}"}
        h_p = {"Authorization": f"Bearer {token_p}"}

        from datetime import datetime, timedelta

        r = client.post("/api/meetings", json={
            "title": "Réunion clair",
            "date": (datetime.now() + timedelta(days=1)).isoformat(),
            "points": [{"description": "P1", "order": 0}],
            "invitee_ids": [],
        }, headers=h_s)
        assert r.status_code == 201
        meeting_id = r.json()["id"]

        plain_content = base64.b64encode(b"clair v1").decode("ascii")

        r = client.post(
            f"/api/meetings/{meeting_id}/minutes",
            json={"sections": [
                {"position": 0, "title": "S1", "content": plain_content,
                 "visibility": "partage"},
            ]},
            headers=h_s,
        )
        assert r.status_code == 201
        minute_id = r.json()["id"]

        # Validate by other bureau member
        r = client.post(f"/api/minutes/{minute_id}/validate", headers=h_p)
        assert r.status_code == 200

        # No-op update: same sections → stays validated
        r = client.put(
            f"/api/minutes/{minute_id}/sections",
            json={"sections": [
                {"position": 0, "title": "S1", "content": plain_content,
                 "visibility": "partage"},
            ]},
            headers=h_s,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "valide"

        # Change content → resets
        r = client.put(
            f"/api/minutes/{minute_id}/sections",
            json={"sections": [
                {"position": 0, "title": "S1",
                 "content": base64.b64encode(b"clair v2").decode("ascii"),
                 "visibility": "partage"},
            ]},
            headers=h_s,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "brouillon"
