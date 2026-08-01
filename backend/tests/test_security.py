"""Tests de sécurité — FAILLE 1 (MFA bypass), FAILLE 2 (CAPTCHA), FAILLE 3 (invitation email)."""

import os
import pytest
from .helpers import (
    create_org, create_user, create_invitation, fetch_captcha, get_totp_code,
)
from app.core.security import create_access_token, hash_invitation_code, normalize_email
from app.core.mfa import generate_totp_secret
from app.models import User, Organization, Invitation, DelegueStatus, DelegueRole
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


# ═══════════════════════════════════════════════════════════════════
# EMAIL NORMALIZATION — insensible à la casse
# ═══════════════════════════════════════════════════════════════════

class TestEmailNormalization:

    def test_register_with_mixed_case_login_with_lowercase(self, client, db):
        """Inscription avec 'Sophie@Demo.LU' puis login avec 'sophie@demo.lu'."""
        cid, cans = fetch_captcha(client)
        resp = client.post("/api/organizations", json={
            "organization_name": "CasseMixte",
            "employee_count": 120,
            "admin_email": "Sophie@Demo.LU",
            "admin_password": "pass12345678",
            "admin_first_name": "Sophie",
            "admin_last_name": "Muller",
            "captcha_id": cid,
            "captcha_answer": cans,
        })
        assert resp.status_code == 201

        cid2, cans2 = fetch_captcha(client)
        resp2 = client.post("/api/auth/login", json={
            "email": "sophie@demo.lu",
            "password": "pass12345678",
            "captcha_id": cid2,
            "captcha_answer": cans2,
        })
        assert resp2.status_code == 200

    def test_create_org_mixed_case_admin_login_lowercase(self, client, db):
        """Création d'organisation avec admin_email mixte, login en minuscules."""
        cid, cans = fetch_captcha(client)
        resp = client.post("/api/organizations", json={
            "organization_name": "AdminMixte",
            "employee_count": 50,
            "admin_email": "Admin@TestOrg.LU",
            "admin_password": "securepassword",
            "admin_first_name": "Admin",
            "admin_last_name": "Test",
            "captcha_id": cid,
            "captcha_answer": cans,
        })
        assert resp.status_code == 201

        cid2, cans2 = fetch_captcha(client)
        resp2 = client.post("/api/auth/login", json={
            "email": "admin@testorg.lu",
            "password": "securepassword",
            "captcha_id": cid2,
            "captcha_answer": cans2,
        })
        assert resp2.status_code == 200

    def test_register_refused_if_email_exists_different_case(self, client, db):
        """Refus d'inscription si l'email existe déjà avec une casse différente (409)."""
        cid, cans = fetch_captcha(client)
        # Créer un premier compte
        resp1 = client.post("/api/organizations", json={
            "organization_name": "FirstOrg",
            "employee_count": 30,
            "admin_email": "Dupont@test.lu",
            "admin_password": "pass12345678",
            "admin_first_name": "Jean",
            "admin_last_name": "Dupont",
            "captcha_id": cid,
            "captcha_answer": cans,
        })
        assert resp1.status_code == 201

        # Tenter de créer un autre compte avec casse différente
        cid2, cans2 = fetch_captcha(client)
        resp2 = client.post("/api/organizations", json={
            "organization_name": "SecondOrg",
            "employee_count": 25,
            "admin_email": "dupont@test.lu",
            "admin_password": "otherpassword",
            "admin_first_name": "Jean2",
            "admin_last_name": "Dupont2",
            "captcha_id": cid2,
            "captcha_answer": cans2,
        })
        assert resp2.status_code == 409

    def test_update_profile_refuses_email_different_case(self, client, db):
        """update_profile refuse un email déjà pris dans une autre casse."""
        # Créer deux comptes
        cid, cans = fetch_captcha(client)
        resp1 = client.post("/api/organizations", json={
            "organization_name": "ProfileOrg",
            "employee_count": 40,
            "admin_email": "alice@test.lu",
            "admin_password": "pass12345678",
            "admin_first_name": "Alice",
            "admin_last_name": "One",
            "captcha_id": cid,
            "captcha_answer": cans,
        })
        assert resp1.status_code == 201
        token_admin = resp1.json()["access_token"]

        # Créer une invitation pour un second membre
        from .helpers import create_invitation, create_user
        admin_user = db.query(User).filter(User.email == "alice@test.lu").first()
        inv = create_invitation(db, "bob@test.lu", admin_user.organization_id, admin_user.id, code="BOB123")

        cid2, cans2 = fetch_captcha(client)
        resp2 = client.post("/api/join", json={
            "email": "bob@test.lu",
            "password": "bobpassword",
            "first_name": "Bob",
            "last_name": "Two",
            "invitation_code": "BOB123",
            "captcha_id": cid2,
            "captcha_answer": cans2,
        })
        assert resp2.status_code == 201
        token_bob = resp2.json()["access_token"]

        # Bob tente de changer son email en "Alice@Test.LU" (casse différente)
        resp3 = client.put(
            "/api/auth/profile",
            json={"email": "Alice@Test.LU"},
            headers={"Authorization": f"Bearer {token_bob}"},
        )
        assert resp3.status_code == 409


# ═══════════════════════════════════════════════════════════════════
# MIGRATION ALEMBIC — normalisation des emails
# ═══════════════════════════════════════════════════════════════════

class TestMigrationEmailNormalization:
    """Tests de la migration Alembic 1f40476853f5 (normalisation des emails).

    Importe et appelle les fonctions réelles du module de migration
    (_find_collisions et _do_upgrade) plutôt que de réécrire le SQL.
    """

    @staticmethod
    def _load_migration():
        """Importe le module de migration par son chemin fichier."""
        import importlib.util
        from pathlib import Path
        spec = importlib.util.spec_from_file_location(
            "migration_lowercase",
            Path(__file__).parent.parent
            / "alembic" / "versions" / "1f40476853f5_lowercase_all_emails.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_migration_lowercase_succeeds(self, db):
        """Base peuplée d'emails en casse mixte → après migration, tout normalisé."""
        from app.core.security import hash_password
        from app.models import User, Organization, Invitation

        migration = self._load_migration()

        org = Organization(name="MigOrg", slug="migorg", employee_count=100)
        db.add(org)
        db.commit()

        user = User(
            email="Sophie@Demo.LU",
            password_hash=hash_password("test"),
            first_name="S",
            last_name="M",
            organization_id=org.id,
        )
        db.add(user)
        db.commit()

        inv = Invitation(
            code_hash=hash_invitation_code("MIG001"),
            email="Invited@Demo.LU",
            first_name="I",
            last_name="P",
            created_by_id=user.id,
            organization_id=org.id,
        )
        db.add(inv)
        db.commit()

        assert user.email == "Sophie@Demo.LU"
        assert inv.email == "Invited@Demo.LU"

        # Appeler la VRAIE fonction de migration
        migration._do_upgrade(db)
        db.commit()

        db.refresh(user)
        db.refresh(inv)

        assert user.email == "sophie@demo.lu"
        assert inv.email == "invited@demo.lu"

    def test_migration_collision_on_users_raises(self, db):
        """Collision réelle sur users → blocage propre avec message listant les doublons."""
        from app.models import User, Organization
        from app.core.security import hash_password

        migration = self._load_migration()

        org = Organization(name="CollOrg", slug="collorg", employee_count=100)
        db.add(org)
        db.commit()

        db.add(User(
            email="dupont@test.lu",
            password_hash=hash_password("test"),
            first_name="A", last_name="B",
            organization_id=org.id,
        ))
        db.add(User(
            email="DUPONT@test.lu",
            password_hash=hash_password("test"),
            first_name="C", last_name="D",
            organization_id=org.id,
        ))
        db.commit()

        # _find_collisions doit détecter le doublon
        collisions = migration._find_collisions(db)
        assert len(collisions) == 1
        assert "dupont@test.lu" in collisions[0]
        assert "2 occurrences" in collisions[0]

        # _do_upgrade doit lever une exception
        import pytest as _pytest
        with _pytest.raises(Exception) as exc_info:
            migration._do_upgrade(db)
        assert "MIGRATION BLOQUÉE" in str(exc_info.value)
        assert "dupont@test.lu" in str(exc_info.value)

    def test_migration_multiple_invitations_same_email_succeeds(self, db):
        """Plusieurs invitations avec le même email en casses différentes → la migration réussit."""
        from app.models import User, Organization, Invitation
        from app.core.security import hash_password

        migration = self._load_migration()

        org = Organization(name="InvOrg", slug="invorg", employee_count=100)
        db.add(org)
        db.commit()

        user = User(
            email="admin@test.lu",
            password_hash=hash_password("test"),
            first_name="A", last_name="B",
            organization_id=org.id,
        )
        db.add(user)
        db.commit()

        db.add(Invitation(
            code_hash=hash_invitation_code("INV-A"), email="Jean@Test.LU",
            first_name="J1", last_name="D1",
            created_by_id=user.id, organization_id=org.id,
        ))
        db.add(Invitation(
            code_hash=hash_invitation_code("INV-B"), email="JEAN@test.lu",
            first_name="J2", last_name="D2",
            created_by_id=user.id, organization_id=org.id,
        ))
        db.commit()

        # Ne doit PAS lever d'exception (invitations pas de contrainte unique)
        migration._do_upgrade(db)
        db.commit()

        # Vérifier que les deux invitations sont normalisées
        invs = db.query(Invitation).order_by(Invitation.created_at).all()
        assert len(invs) == 2
        assert invs[0].email == "jean@test.lu"
        assert invs[1].email == "jean@test.lu"

    def test_migration_normalizes_spaces(self, db):
        """Un email avec espaces parasites est normalisé correctement (strip + lower)."""
        from app.models import User, Organization
        from app.core.security import hash_password, normalize_email

        migration = self._load_migration()

        org = Organization(name="SpaceOrg", slug="spaceorg", employee_count=100)
        db.add(org)
        db.commit()

        user = User(
            email=" Sophie@Demo.LU ",
            password_hash=hash_password("test"),
            first_name="S", last_name="M",
            organization_id=org.id,
        )
        db.add(user)
        db.commit()

        assert user.email == " Sophie@Demo.LU "

        migration._do_upgrade(db)
        db.commit()

        db.refresh(user)
        expected = normalize_email(" Sophie@Demo.LU ")
        assert user.email == expected
        assert user.email == "sophie@demo.lu"

    def test_migration_idempotent(self, db):
        """Relancer la migration sur une base déjà normalisée ne change rien et ne lève pas d'erreur."""
        from app.models import User, Organization, Invitation
        from app.core.security import hash_password

        migration = self._load_migration()

        org = Organization(name="IdemOrg", slug="idemorg", employee_count=100)
        db.add(org)
        db.commit()

        user = User(
            email="sophie@demo.lu",
            password_hash=hash_password("test"),
            first_name="S", last_name="M",
            organization_id=org.id,
        )
        db.add(user)
        db.commit()

        inv = Invitation(
            code_hash=hash_invitation_code("IDEM01"),
            email="invited@demo.lu",
            first_name="I", last_name="P",
            created_by_id=user.id, organization_id=org.id,
        )
        db.add(inv)
        db.commit()

        # Premier passage
        migration._do_upgrade(db)
        db.commit()

        db.refresh(user)
        db.refresh(inv)
        email_u1 = user.email
        email_i1 = inv.email
        assert email_u1 == "sophie@demo.lu"
        assert email_i1 == "invited@demo.lu"

        # Deuxième passage
        migration._do_upgrade(db)
        db.commit()

        db.refresh(user)
        db.refresh(inv)
        assert user.email == email_u1
        assert inv.email == email_i1
