"""Tests de durcissement auth : rate limiting, verrouillage TOTP,
expiration des invitations, politique de mot de passe."""

from datetime import datetime, timedelta

from .helpers import (
    create_org, create_user, create_invitation, fetch_captcha, get_totp_code,
)
from app.core.security import create_access_token
from app.core.mfa import generate_totp_secret
from app.models import Invitation


# ═══════════════════════════════════════════════════════════════════
# Rate limiting — login
# ═══════════════════════════════════════════════════════════════════

class TestLoginRateLimit:
    """10 tentatives / 15 min / IP, puis 429."""

    def test_429_after_10_attempts(self, client, db):
        org = create_org(db)
        create_user(db, "rl@test.com", "pass1234", org.id)

        for _ in range(10):
            cid, ans = fetch_captcha(client)
            r = client.post("/api/auth/login", json={
                "email": "rl@test.com", "password": "wrongpass",
                "captcha_id": cid, "captcha_answer": ans,
            })
            assert r.status_code == 401, f"expected 401, got {r.status_code}"

        cid, ans = fetch_captcha(client)
        r = client.post("/api/auth/login", json={
            "email": "rl@test.com", "password": "wrongpass",
            "captcha_id": cid, "captcha_answer": ans,
        })
        assert r.status_code == 429, f"expected 429, got {r.status_code}"

    def test_no_429_before_limit(self, client, db):
        """9 échecs + 1 succès (10 appels) : pas de 429, login OK."""
        org = create_org(db)
        create_user(db, "rl2@test.com", "pass1234", org.id)

        for _ in range(9):
            cid, ans = fetch_captcha(client)
            r = client.post("/api/auth/login", json={
                "email": "rl2@test.com", "password": "wrongpass",
                "captcha_id": cid, "captcha_answer": ans,
            })
            assert r.status_code == 401

        cid, ans = fetch_captcha(client)
        r = client.post("/api/auth/login", json={
            "email": "rl2@test.com", "password": "pass1234",
            "captcha_id": cid, "captcha_answer": ans,
        })
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"


# ═══════════════════════════════════════════════════════════════════
# Rate limiting — création d'organisation (anti-spam)
# ═══════════════════════════════════════════════════════════════════

class TestOrgRateLimit:
    """5 créations / 1h / IP, puis 429."""

    def test_429_after_5_creations(self, client):
        for i in range(5):
            cid, ans = fetch_captcha(client)
            r = client.post("/api/organizations", json={
                "organization_name": f"Org{i}", "employee_count": 120,
                "admin_email": f"admin{i}@test.com", "admin_password": "pass1234",
                "admin_first_name": "A", "admin_last_name": "B",
                "captcha_id": cid, "captcha_answer": ans,
            })
            assert r.status_code == 201, f"expected 201, got {r.status_code}: {r.text}"

        cid, ans = fetch_captcha(client)
        r = client.post("/api/organizations", json={
            "organization_name": "Org6", "employee_count": 120,
            "admin_email": "admin6@test.com", "admin_password": "pass1234",
            "admin_first_name": "A", "admin_last_name": "B",
            "captcha_id": cid, "captcha_answer": ans,
        })
        assert r.status_code == 429, f"expected 429, got {r.status_code}"


# ═══════════════════════════════════════════════════════════════════
# Verrouillage TOTP
# ═══════════════════════════════════════════════════════════════════

class TestTotpLockout:
    """5 codes TOTP invalides → compte verrouillé 15 min."""

    def _login_mfa_token(self, client, email, password="pass1234"):
        cid, ans = fetch_captcha(client)
        r = client.post("/api/auth/login", json={
            "email": email, "password": password,
            "captcha_id": cid, "captcha_answer": ans,
        })
        assert r.status_code == 200
        return r.json()["mfa_token"]

    def test_lockout_after_5_failures(self, client, db):
        org = create_org(db)
        secret = generate_totp_secret()
        create_user(db, "totp@test.com", "pass1234", org.id,
                    totp_enabled=True, totp_secret=secret)

        mfa_token = self._login_mfa_token(client, "totp@test.com")

        # 5 codes invalides → 401 à chaque fois
        for _ in range(5):
            r = client.post("/api/auth/mfa/login", json={
                "mfa_token": mfa_token, "totp_code": "000000",
            })
            assert r.status_code == 401, f"expected 401, got {r.status_code}"

        # Même le bon code est refusé pendant le verrouillage
        r = client.post("/api/auth/mfa/login", json={
            "mfa_token": mfa_token, "totp_code": get_totp_code(secret),
        })
        assert r.status_code == 429, f"expected 429, got {r.status_code}: {r.text}"

    def test_unlock_after_lock_expiry(self, client, db):
        org = create_org(db)
        secret = generate_totp_secret()
        user = create_user(db, "totp2@test.com", "pass1234", org.id,
                           totp_enabled=True, totp_secret=secret)

        mfa_token = self._login_mfa_token(client, "totp2@test.com")

        for _ in range(5):
            r = client.post("/api/auth/mfa/login", json={
                "mfa_token": mfa_token, "totp_code": "000000",
            })
            assert r.status_code == 401

        # Simule l'écoulement du délai de verrouillage
        user.totp_locked_until = datetime.now() - timedelta(minutes=1)
        user.totp_failed_attempts = 0
        db.commit()

        r = client.post("/api/auth/mfa/login", json={
            "mfa_token": mfa_token, "totp_code": get_totp_code(secret),
        })
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"

    def test_success_resets_counter(self, client, db):
        """Un code valide après 2 échecs réinitialise le compteur."""
        org = create_org(db)
        secret = generate_totp_secret()
        user = create_user(db, "totp3@test.com", "pass1234", org.id,
                           totp_enabled=True, totp_secret=secret)

        mfa_token = self._login_mfa_token(client, "totp3@test.com")

        for _ in range(2):
            r = client.post("/api/auth/mfa/login", json={
                "mfa_token": mfa_token, "totp_code": "000000",
            })
            assert r.status_code == 401

        r = client.post("/api/auth/mfa/login", json={
            "mfa_token": mfa_token, "totp_code": get_totp_code(secret),
        })
        assert r.status_code == 200
        db.refresh(user)
        assert user.totp_failed_attempts == 0
        assert user.totp_locked_until is None


# ═══════════════════════════════════════════════════════════════════
# Expiration des invitations
# ═══════════════════════════════════════════════════════════════════

class TestInvitationExpiry:
    """Une invitation expirée est refusée ; une invitation fraîche est acceptée."""

    def test_expired_invitation_rejected(self, client, db):
        org = create_org(db)
        admin = create_user(db, "admin@test.com", "pass1234", org.id, role="admin")
        inv = create_invitation(db, "expired@test.com", org.id, admin.id, code="EXPIRE1")
        inv.expires_at = datetime.now() - timedelta(days=1)
        db.commit()

        cid, ans = fetch_captcha(client)
        r = client.post("/api/join", json={
            "email": "expired@test.com", "password": "pass1234",
            "first_name": "I", "last_name": "N",
            "invitation_code": "EXPIRE1",
            "captcha_id": cid, "captcha_answer": ans,
        })
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"

    def test_fresh_invitation_accepted(self, client, db):
        org = create_org(db)
        admin = create_user(db, "admin2@test.com", "pass1234", org.id, role="admin")
        inv = create_invitation(db, "fresh@test.com", org.id, admin.id, code="FRESH01")
        inv.expires_at = datetime.now() + timedelta(days=29)
        db.commit()

        cid, ans = fetch_captcha(client)
        r = client.post("/api/join", json={
            "email": "fresh@test.com", "password": "pass1234",
            "first_name": "I", "last_name": "N",
            "invitation_code": "FRESH01",
            "captcha_id": cid, "captcha_answer": ans,
        })
        assert r.status_code == 201, f"expected 201, got {r.status_code}: {r.text}"

    def test_legacy_invitation_without_expiry_accepted(self, client, db):
        """Invitations sans expires_at (NULL) : toujours valides (rétro-compat)."""
        org = create_org(db)
        admin = create_user(db, "admin3@test.com", "pass1234", org.id, role="admin")
        create_invitation(db, "legacy@test.com", org.id, admin.id, code="LEGACY1")

        cid, ans = fetch_captcha(client)
        r = client.post("/api/join", json={
            "email": "legacy@test.com", "password": "pass1234",
            "first_name": "I", "last_name": "N",
            "invitation_code": "LEGACY1",
            "captcha_id": cid, "captcha_answer": ans,
        })
        assert r.status_code == 201, f"expected 201, got {r.status_code}: {r.text}"

    def test_api_sets_30_days_expiry(self, client, db):
        """L'API définit expires_at = création + 30 jours."""
        org = create_org(db)
        admin = create_user(db, "admin4@test.com", "pass1234", org.id, role="admin")
        token = create_access_token(data={"sub": str(admin.id), "org_id": org.id, "typ": "access"})

        r = client.post("/api/invitations", headers={"Authorization": f"Bearer {token}"}, json={
            "email": "inv@test.com", "first_name": "I", "last_name": "N",
            "delegue_status": "titulaire", "delegue_role": "membre",
        })
        assert r.status_code == 201, f"expected 201, got {r.status_code}: {r.text}"

        inv = db.query(Invitation).filter(Invitation.code == r.json()["code"]).first()
        assert inv is not None
        assert inv.expires_at is not None
        assert inv.expires_at > datetime.now()


# ═══════════════════════════════════════════════════════════════════
# Politique de mot de passe (min 8 caractères)
# ═══════════════════════════════════════════════════════════════════

class TestPasswordPolicy:
    """Les mots de passe < 8 caractères sont refusés à l'inscription."""

    def test_short_password_create_org_rejected(self, client):
        cid, ans = fetch_captcha(client)
        r = client.post("/api/organizations", json={
            "organization_name": "ShortPwd", "employee_count": 120,
            "admin_email": "short@test.com", "admin_password": "short7",
            "admin_first_name": "A", "admin_last_name": "B",
            "captcha_id": cid, "captcha_answer": ans,
        })
        assert r.status_code == 422, f"expected 422, got {r.status_code}"

    def test_short_password_join_rejected(self, client, db):
        org = create_org(db)
        admin = create_user(db, "admin5@test.com", "pass1234", org.id, role="admin")
        create_invitation(db, "shortjoin@test.com", org.id, admin.id, code="SHORT1")

        cid, ans = fetch_captcha(client)
        r = client.post("/api/join", json={
            "email": "shortjoin@test.com", "password": "short7",
            "first_name": "I", "last_name": "N",
            "invitation_code": "SHORT1",
            "captcha_id": cid, "captcha_answer": ans,
        })
        assert r.status_code == 422, f"expected 422, got {r.status_code}"

    def test_change_password_min_8(self, client, db):
        org = create_org(db)
        user = create_user(db, "chpwd@test.com", "pass1234", org.id)
        token = create_access_token(data={"sub": str(user.id), "org_id": org.id, "typ": "access"})

        r = client.put("/api/auth/password", headers={"Authorization": f"Bearer {token}"}, json={
            "old_password": "pass1234", "new_password": "short7",
        })
        assert r.status_code == 400, f"expected 400, got {r.status_code}"

        r = client.put("/api/auth/password", headers={"Authorization": f"Bearer {token}"}, json={
            "old_password": "pass1234", "new_password": "longpass1",
        })
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
