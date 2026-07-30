"""Tests de sécurité — FAILLE 1 (MFA bypass), FAILLE 2 (CAPTCHA), FAILLE 3 (invitation email)."""

import pytest
from .helpers import (
    create_org, create_user, create_invitation, fetch_captcha, get_totp_code,
)
from app.core.security import create_access_token
from app.core.mfa import generate_totp_secret
from datetime import timedelta


# ═══════════════════════════════════════════════════════════════════
# FAILLE 1 — MFA bypass
# ═══════════════════════════════════════════════════════════════════

class TestMfaBypass:
    """Vérifie qu'un token mfa_pending est rejeté sur les endpoints protégés."""

    def test_mfa_pending_token_rejected_on_me(self, client, db):
        """Un token typ=mfa_pending doit être refusé (401) sur /api/auth/me."""
        org = create_org(db)
        user = create_user(
            db, "mfa@test.com", "pass1234", org.id,
            totp_enabled=True, totp_secret=generate_totp_secret(),
        )

        mfa_token = create_access_token(
            data={"sub": str(user.id), "mfa": True, "typ": "mfa_pending"},
            expires_delta=timedelta(minutes=3),
        )

        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {mfa_token}"})
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"

    def test_mfa_pending_token_rejected_on_business_endpoint(self, client, db):
        """Un token mfa_pending est refusé sur un endpoint métier (/api/dashboard)."""
        org = create_org(db)
        user = create_user(
            db, "mfa2@test.com", "pass1234", org.id,
            totp_enabled=True, totp_secret=generate_totp_secret(),
        )

        mfa_token = create_access_token(
            data={"sub": str(user.id), "mfa": True, "typ": "mfa_pending"},
            expires_delta=timedelta(minutes=3),
        )

        resp = client.get("/api/dashboard", headers={"Authorization": f"Bearer {mfa_token}"})
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"

    def test_mfa_full_flow_succeeds(self, client, db):
        """Parcours MFA complet : login → mfa_token → mfa_login → accès OK."""
        org = create_org(db)
        secret = generate_totp_secret()
        user = create_user(
            db, "mfa3@test.com", "pass1234", org.id,
            totp_enabled=True, totp_secret=secret,
        )

        # Step 1: login
        cid, cans = fetch_captcha(client)
        resp = client.post("/api/auth/login", json={
            "email": "mfa3@test.com",
            "password": "pass1234",
            "captcha_id": cid,
            "captcha_answer": cans,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["mfa_required"] is True
        mfa_token = data["mfa_token"]
        assert mfa_token

        # Step 2: mfa_login avec le bon code TOTP
        totp_code = get_totp_code(secret)
        resp = client.post("/api/auth/mfa/login", json={
            "mfa_token": mfa_token,
            "totp_code": totp_code,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"]
        access_token = data["access_token"]

        # Step 3: accès avec le token final
        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})
        assert resp.status_code == 200
        assert resp.json()["email"] == "mfa3@test.com"

    def test_mfa_login_rejects_access_token(self, client, db):
        """mfa_login refuse un token qui n'est pas typ=mfa_pending."""
        org = create_org(db)
        user = create_user(db, "mfa4@test.com", "pass1234", org.id)

        access_token = create_access_token(
            data={"sub": str(user.id), "org_id": org.id, "typ": "access"},
        )

        resp = client.post("/api/auth/mfa/login", json={
            "mfa_token": access_token,
            "totp_code": "000000",
        })
        assert resp.status_code == 401

    def test_old_style_token_without_typ_rejected(self, client, db):
        """Un token sans claim typ (ancien format) est rejeté."""
        org = create_org(db)
        user = create_user(db, "oldstyle@test.com", "pass1234", org.id)

        old_token = create_access_token(
            data={"sub": str(user.id), "org_id": org.id},
        )

        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {old_token}"})
        assert resp.status_code == 401

    def test_token_with_mfa_true_rejected(self, client, db):
        """Un token avec mfa=True (même avec typ=access) est rejeté."""
        org = create_org(db)
        user = create_user(db, "mfatrue@test.com", "pass1234", org.id)

        bogus_token = create_access_token(
            data={"sub": str(user.id), "mfa": True, "org_id": org.id, "typ": "access"},
        )

        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {bogus_token}"})
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════════
# FAILLE 2 — CAPTCHA obligatoire
# ═══════════════════════════════════════════════════════════════════

class TestCaptchaRequired:

    def test_login_without_captcha_fields_returns_422(self, client, db):
        """Login sans captcha_id/captcha_answer → 422 (Pydantic validation)."""
        org = create_org(db)
        create_user(db, "nocaptcha@test.com", "pass1234", org.id)

        resp = client.post("/api/auth/login", json={
            "email": "nocaptcha@test.com",
            "password": "pass1234",
        })
        assert resp.status_code == 422

    def test_login_with_wrong_captcha_returns_400(self, client, db):
        """Login avec mauvaise réponse CAPTCHA → 400."""
        org = create_org(db)
        create_user(db, "wrongcap@test.com", "pass1234", org.id)

        cid, _ = fetch_captcha(client)
        resp = client.post("/api/auth/login", json={
            "email": "wrongcap@test.com",
            "password": "pass1234",
            "captcha_id": cid,
            "captcha_answer": "999",
        })
        assert resp.status_code == 400
        assert "CAPTCHA" in resp.json()["detail"]

    def test_login_with_correct_captcha_returns_200(self, client, db):
        """Login avec bonne réponse CAPTCHA → 200."""
        org = create_org(db)
        create_user(db, "goodcap@test.com", "pass1234", org.id)

        cid, cans = fetch_captcha(client)
        resp = client.post("/api/auth/login", json={
            "email": "goodcap@test.com",
            "password": "pass1234",
            "captcha_id": cid,
            "captcha_answer": cans,
        })
        assert resp.status_code == 200
        assert resp.json()["access_token"]

    def test_create_org_without_captcha_returns_422(self, client):
        """Création d'org sans CAPTCHA → 422."""
        resp = client.post("/api/organizations", json={
            "organization_name": "TestOrg",
            "employee_count": 120,
            "admin_email": "admin@test.com",
            "admin_password": "pass1234",
            "admin_first_name": "Admin",
            "admin_last_name": "Test",
        })
        assert resp.status_code == 422

    def test_join_without_captcha_returns_422(self, client):
        """Join sans CAPTCHA → 422."""
        resp = client.post("/api/join", json={
            "email": "user@test.com",
            "password": "pass1234",
            "first_name": "User",
            "last_name": "Test",
            "invitation_code": "TESTCODE",
        })
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════
# FAILLE 3 — Invitation code détaché de l'email
# ═══════════════════════════════════════════════════════════════════

class TestInvitationEmailBinding:

    def test_join_with_wrong_email_fails(self, client, db):
        """Un code d'invitation ne fonctionne qu'avec le bon email."""
        org = create_org(db)
        admin = create_user(db, "admin@test.com", "admin123", org.id, role="admin")
        inv = create_invitation(db, "invited@test.com", org.id, admin.id, code="INVCODE1")

        cid, cans = fetch_captcha(client)
        resp = client.post("/api/join", json={
            "email": "attacker@test.com",
            "password": "attacker123",
            "first_name": "Hacker",
            "last_name": "Bad",
            "invitation_code": "INVCODE1",
            "captcha_id": cid,
            "captcha_answer": cans,
        })
        assert resp.status_code == 400
        assert "invalide" in resp.json()["detail"].lower()

    def test_join_with_matching_email_succeeds(self, client, db):
        """Un code d'invitation avec le bon email fonctionne."""
        org = create_org(db)
        admin = create_user(db, "admin2@test.com", "admin123", org.id, role="admin")
        inv = create_invitation(db, "invited2@test.com", org.id, admin.id, code="INVCODE2")

        cid, cans = fetch_captcha(client)
        resp = client.post("/api/join", json={
            "email": "invited2@test.com",
            "password": "legit1234",
            "first_name": "Legit",
            "last_name": "User",
            "invitation_code": "INVCODE2",
            "captcha_id": cid,
            "captcha_answer": cans,
        })
        assert resp.status_code == 201
        assert resp.json()["access_token"]

    def test_join_email_case_insensitive(self, client, db):
        """La comparaison d'email est insensible à la casse."""
        org = create_org(db)
        admin = create_user(db, "admin3@test.com", "admin123", org.id, role="admin")
        inv = create_invitation(db, "MixedCase@Test.com", org.id, admin.id, code="INVCODE3")

        cid, cans = fetch_captcha(client)
        resp = client.post("/api/join", json={
            "email": "mixedcase@test.com",
            "password": "legit1234",
            "first_name": "Legit",
            "last_name": "User",
            "invitation_code": "INVCODE3",
            "captcha_id": cid,
            "captcha_answer": cans,
        })
        assert resp.status_code == 201

    def test_wrong_email_error_message_is_generic(self, client, db):
        """Le message d'erreur ne révèle pas l'existence de l'invitation."""
        org = create_org(db)
        admin = create_user(db, "admin4@test.com", "admin123", org.id, role="admin")
        inv = create_invitation(db, "secret@test.com", org.id, admin.id, code="SECRET99")

        cid, cans = fetch_captcha(client)
        resp = client.post("/api/join", json={
            "email": "wrong@test.com",
            "password": "pass1234",
            "first_name": "Wrong",
            "last_name": "Email",
            "invitation_code": "SECRET99",
            "captcha_id": cid,
            "captcha_answer": cans,
        })
        assert resp.status_code == 400

        cid2, cans2 = fetch_captcha(client)
        resp2 = client.post("/api/join", json={
            "email": "nobody@test.com",
            "password": "pass1234",
            "first_name": "Nobody",
            "last_name": "Nowhere",
            "invitation_code": "NOTEXIST",
            "captcha_id": cid2,
            "captcha_answer": cans2,
        })
        assert resp2.status_code == 400
        assert resp.json()["detail"] == resp2.json()["detail"]
