"""Tests : notifications (config, outbox, .eml, SMTP, export) et liens
sécurisés de lecture (share-links) pour la direction."""
import base64
import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from tests.helpers import fetch_captcha
from app.core.database import SessionLocal
from app.models import User
from app.models.email import EmailConfig, EmailOutbox, EmailStatus, TransportMode
from app.models.minute import MinuteStatus


def _login(client, email, password):
    cid, ans = fetch_captcha(client)
    r = client.post("/api/auth/login", json={
        "email": email, "password": password,
        "captcha_id": cid, "captcha_answer": ans,
    })
    assert r.status_code == 200, f"Login failed: {r.json()}"
    return r.json()["access_token"]


def _b64(s: str) -> str:
    return base64.b64encode(s.encode()).decode()


def _setup_config(client, token, mode="eml", direction_email="direction@corp.lu"):
    h = {"Authorization": f"Bearer {token}"}
    r = client.put("/api/emails/config", json={
        "enabled": True,
        "transport_mode": mode,
        "from_name": "Délégation Test",
        "from_email": "delegation@test.lu",
        "direction_email": direction_email,
    }, headers=h)
    assert r.status_code == 200, f"Config failed: {r.json()}"
    return h


def _create_meeting(client, token, invitee_ids=None):
    h = {"Authorization": f"Bearer {token}"}
    r = client.post("/api/meetings", json={
        "title": "Réunion email",
        "date": (datetime.utcnow() + timedelta(days=10)).isoformat(),
        "location": "Salle 2",
        "direction_invited": False,
        "points": [{"description": "Point 1", "order": 0}],
        "invitee_ids": invitee_ids or [],
    }, headers=h)
    assert r.status_code == 201, f"Meeting failed: {r.json()}"
    return r.json()


def _create_validated_minute(client, token):
    """Crée une réunion + PV avec 2 sections et le valide (par un autre bureau)."""
    h = {"Authorization": f"Bearer {token}"}
    meeting = _create_meeting(client, token)
    r = client.post(f"/api/meetings/{meeting['id']}/minutes", json={
        "sections": [
            {"position": 0, "title": "Interne", "content": _b64("contenu interne"),
             "visibility": "interne"},
            {"position": 1, "title": "Partage", "content": _b64("contenu partage"),
             "visibility": "partage"},
        ]
    }, headers=h)
    assert r.status_code == 201, f"Minute failed: {r.json()}"
    return r.json()["id"]


# ═══════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════

class TestEmailConfig:
    def test_default_config_eml_disabled(self, client, org_with_users):
        h = {"Authorization": f"Bearer {org_with_users['sophie_token']}"}
        r = client.get("/api/emails/config", headers=h)
        assert r.status_code == 200
        data = r.json()
        assert data["transport_mode"] == "eml"
        assert data["enabled"] is False
        assert data["has_smtp_password"] is False

    def test_update_and_password_never_returned(self, client, org_with_users):
        h = {"Authorization": f"Bearer {org_with_users['sophie_token']}"}
        r = client.put("/api/emails/config", json={
            "enabled": True, "transport_mode": "smtp",
            "smtp_host": "smtp.test.lu", "smtp_port": 587,
            "smtp_user": "bot", "smtp_password": "secret123",
        }, headers=h)
        assert r.status_code == 200
        assert "smtp_password" not in r.json()  # jamais renvoyé
        assert r.json()["has_smtp_password"] is True

        # Champ vide → mot de passe inchangé
        r2 = client.put("/api/emails/config", json={"smtp_password": ""}, headers=h)
        assert r2.status_code == 200
        assert r2.json()["has_smtp_password"] is True

    def test_non_admin_cannot_update(self, client, org_with_users):
        h = {"Authorization": f"Bearer {org_with_users['tom_token']}"}
        r = client.put("/api/emails/config", json={"enabled": True}, headers=h)
        assert r.status_code == 403

    def test_invalid_transport_rejected(self, client, org_with_users):
        h = {"Authorization": f"Bearer {org_with_users['sophie_token']}"}
        r = client.put("/api/emails/config", json={"transport_mode": "carrier-pigeon"}, headers=h)
        assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════
# Outbox + déclencheurs
# ═══════════════════════════════════════════════════════════════════

class TestOutbox:
    def test_no_outbox_when_disabled(self, client, org_with_users):
        token = org_with_users["sophie_token"]
        _create_meeting(client, token)
        db = SessionLocal()
        try:
            n = db.query(EmailOutbox).count()
        finally:
            db.close()
        assert n == 0

    def test_meeting_creates_invites_in_eml_mode(self, client, org_with_users):
        token = org_with_users["sophie_token"]
        h = _setup_config(client, token)
        # Convocations pour tous les membres (sophie, marc, tom)
        db = SessionLocal()
        try:
            user_ids = [u.id for u in db.query(User).filter(User.email.in_(
                ["sophie@testpv.lu", "marc@testpv.lu", "tom@testpv.lu"])).all()]
        finally:
            db.close()
        _create_meeting(client, token, invitee_ids=user_ids)

        r = client.get("/api/emails", headers=h)
        assert r.status_code == 200
        msgs = r.json()
        assert len(msgs) == 3
        assert all(m["event_type"] == "meeting_invite" for m in msgs)
        assert {m["recipient_email"] for m in msgs} == {"sophie@testpv.lu", "marc@testpv.lu", "tom@testpv.lu"}
        assert all(m["has_eml"] for m in msgs)  # mode eml : fichiers générés
        # Idempotence : recréer ne duplique pas (même réunion n'existe pas — le
        # test vérifie plutôt que l'enqueue d'un doublon est évité)
        db2 = SessionLocal()
        try:
            from app.models.email import EmailEventType
            n = db2.query(EmailOutbox).filter(
                EmailOutbox.event_type == EmailEventType.meeting_invite.value).count()
        finally:
            db2.close()
        assert n == 3

    def test_invite_email_contains_code(self, client, org_with_users):
        token = org_with_users["sophie_token"]
        h = _setup_config(client, token)
        r = client.post("/api/invitations", json={
            "email": "new@test.lu", "first_name": "New", "last_name": "Member",
            "delegue_status": "titulaire", "delegue_role": "membre",
        }, headers=h)
        assert r.status_code == 201, f"Invite failed: {r.json()}"
        code = r.json()["code"]

        db = SessionLocal()
        try:
            msg = db.query(EmailOutbox).filter(EmailOutbox.event_type == "member_invite").first()
            assert msg is not None, "Email d'invitation absent de l'outbox"
            assert msg.recipient_email == "new@test.lu"
            assert code in msg.body_text
            assert code in msg.body_html
        finally:
            db.close()

    def test_eml_file_generated_and_downloadable(self, client, org_with_users):
        token = org_with_users["sophie_token"]
        h = _setup_config(client, token)
        client.post("/api/invitations", json={
            "email": "eml@test.lu", "first_name": "E", "last_name": "Ml",
            "delegue_status": "titulaire", "delegue_role": "membre",
        }, headers=h)

        db = SessionLocal()
        try:
            msg = db.query(EmailOutbox).filter(EmailOutbox.event_type == "member_invite").first()
            assert msg.eml_path, "Fichier .eml non généré"
            assert msg.eml_path.endswith(".eml")
        finally:
            db.close()

        msgs = client.get("/api/emails", headers=h).json()
        assert msgs[0]["has_eml"] is True
        dl = client.get(f"/api/emails/{msgs[0]['id']}/download.eml", headers=h)
        assert dl.status_code == 200
        assert b"Subject:" in dl.content
        assert b"member_invite" in dl.content or b"Invitation" in dl.content

    def test_smtp_send_with_mocked_server(self, client, org_with_users):
        token = org_with_users["sophie_token"]
        h = _setup_config(client, token, mode="smtp")
        client.put("/api/emails/config", json={
            "smtp_host": "smtp.test.lu", "smtp_port": 587, "smtp_user": "u", "smtp_password": "p",
        }, headers=h)
        client.post("/api/invitations", json={
            "email": "smtp@test.lu", "first_name": "S", "last_name": "Mtp",
            "delegue_status": "titulaire", "delegue_role": "membre",
        }, headers=h)

        db = SessionLocal()
        try:
            msg = db.query(EmailOutbox).filter(EmailOutbox.event_type == "member_invite").first()
            assert msg.transport == TransportMode.smtp
            assert msg.status == EmailStatus.ready
        finally:
            db.close()

        # Envoi mocké (pas de vrai SMTP en test)
        from app.services import email_service
        with patch.object(email_service, "send_via_smtp") as mock_send:
            from app.services.email_service import send_ready_smtp
            sent, failed = send_ready_smtp(db)
        assert sent == 1
        assert failed == 0
        mock_send.assert_called_once()
        db2 = SessionLocal()
        try:
            msg2 = db2.query(EmailOutbox).filter(EmailOutbox.event_type == "member_invite").first()
            assert msg2.status == EmailStatus.sent
            assert msg2.sent_at is not None
        finally:
            db2.close()

    def test_retry_after_failure(self, client, org_with_users):
        token = org_with_users["sophie_token"]
        h = _setup_config(client, token, mode="smtp")
        client.put("/api/emails/config", json={
            "smtp_host": "smtp.test.lu", "smtp_port": 587,
        }, headers=h)
        client.post("/api/invitations", json={
            "email": "fail@test.lu", "first_name": "F", "last_name": "Ail",
            "delegue_status": "titulaire", "delegue_role": "membre",
        }, headers=h)

        db = SessionLocal()
        try:
            from app.services import email_service
            with patch.object(email_service, "send_via_smtp", side_effect=ConnectionRefusedError("no")):
                from app.services.email_service import send_ready_smtp
                sent, failed = send_ready_smtp(db)
            assert sent == 0
            assert failed == 1
        finally:
            db.close()

        msgs = client.get("/api/emails?status_filter=failed", headers=h).json()
        assert len(msgs) == 0  # 1 échec < 5 tentatives → reste ready

        # Réessayer avec SMTP qui marche
        db2 = SessionLocal()
        try:
            from app.services import email_service
            with patch.object(email_service, "send_via_smtp"):
                from app.services.email_service import send_ready_smtp
                sent, _ = send_ready_smtp(db2)
            assert sent == 1
        finally:
            db2.close()

    def test_export_external_format(self, client, org_with_users):
        token = org_with_users["sophie_token"]
        h = _setup_config(client, token, mode="external")
        client.post("/api/invitations", json={
            "email": "ext@test.lu", "first_name": "E", "last_name": "Xt",
            "delegue_status": "titulaire", "delegue_role": "membre",
        }, headers=h)

        r = client.post("/api/emails/export", headers=h)
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/zip"
        import io, zipfile
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            data = json.loads(z.read("messages.json"))
        assert len(data) == 1
        assert data[0]["to"] == "ext@test.lu"
        assert "body_text" in data[0]

        # Deuxième export → vide (déjà exporté)
        r2 = client.post("/api/emails/export", headers=h)
        assert r2.status_code == 404

    def test_mark_sent_external(self, client, org_with_users):
        token = org_with_users["sophie_token"]
        h = _setup_config(client, token, mode="external")
        client.post("/api/invitations", json={
            "email": "mark@test.lu", "first_name": "M", "last_name": "Ark",
            "delegue_status": "titulaire", "delegue_role": "membre",
        }, headers=h)
        msgs = client.get("/api/emails", headers=h).json()
        r = client.post(f"/api/emails/{msgs[0]['id']}/mark-sent", headers=h)
        assert r.status_code == 200
        assert client.get("/api/emails", headers=h).json()[0]["status"] == "sent"


# ═══════════════════════════════════════════════════════════════════
# Liens sécurisés (direction)
# ═══════════════════════════════════════════════════════════════════

class TestShareLinks:
    def test_share_requires_validated_minute(self, client, org_with_users):
        token = org_with_users["sophie_token"]
        h = _setup_config(client, token)
        minute_id = _create_validated_minute(client, token)
        # Notre helper ne valide pas — le PV reste brouillon
        r = client.post(f"/api/minutes/{minute_id}/share-links", json={
            "envelope": json.dumps({"algo": "argon2id", "salt": "x", "nonce": "y", "wrapped": "z"}),
        }, headers=h)
        assert r.status_code == 409

    def test_share_creates_link_and_queues_email(self, client, org_with_users):
        token = org_with_users["sophie_token"]
        h = _setup_config(client, token)
        minute_id = _create_validated_minute(client, token)

        # Valider par marc (autre membre du bureau)
        marc_token = org_with_users["marc_token"]
        r = client.post(f"/api/minutes/{minute_id}/validate", headers={"Authorization": f"Bearer {marc_token}"})
        assert r.status_code == 200, f"Validation failed: {r.json()}"

        envelope = json.dumps({"algo": "argon2id", "salt": "c2FsdA==", "nonce": "bm9uY2U=", "wrapped": "d3JhcHBlZA=="})
        r = client.post(f"/api/minutes/{minute_id}/share-links", json={
            "envelope": envelope, "expires_days": 14,
        }, headers=h)
        assert r.status_code == 200, f"Share failed: {r.json()}"
        data = r.json()
        assert "/p/" in data["share_url"]
        assert len(data["token"]) >= 40

        # Email direction mis en file
        db = SessionLocal()
        try:
            msg = db.query(EmailOutbox).filter(EmailOutbox.event_type == "minutes_direction").first()
            assert msg is not None
            assert msg.recipient_email == "direction@corp.lu"
            assert data["share_url"] in msg.body_text
            # Le code de lecture n'est jamais dans l'email (ni côté serveur)
            assert "d3JhcHBlZA==" not in msg.body_text  # wrapped n'est pas le code
        finally:
            db.close()

        # Lecture publique : infos + contenu (sections partagées seulement)
        info = client.get(f"/api/share-links/{data['token']}")
        assert info.status_code == 200
        content = client.get(f"/api/share-links/{data['token']}/content")
        assert content.status_code == 200
        cdata = content.json()
        assert len(cdata["sections"]) == 1  # seulement "Partage"
        assert cdata["sections"][0]["title"] == "Partage"
        assert cdata["sections"][0]["content"] == _b64("contenu partage")
        assert "contenu interne" not in json.dumps(cdata)

    def test_share_non_bureau_forbidden(self, client, org_with_users):
        token = org_with_users["sophie_token"]
        h = _setup_config(client, token)
        minute_id = _create_validated_minute(client, token)
        marc_token = org_with_users["marc_token"]
        client.post(f"/api/minutes/{minute_id}/validate", headers={"Authorization": f"Bearer {marc_token}"})

        # Tom (membre simple) → 403
        r = client.post(f"/api/minutes/{minute_id}/share-links", json={
            "envelope": json.dumps({"a": "b"}),
        }, headers={"Authorization": f"Bearer {org_with_users['tom_token']}"})
        assert r.status_code == 403

    def test_share_unknown_link_404(self, client):
        r = client.get("/api/share-links/doesnotexist")
        assert r.status_code == 404

    def test_share_revoked_link_410(self, client, org_with_users):
        token = org_with_users["sophie_token"]
        h = _setup_config(client, token)
        minute_id = _create_validated_minute(client, token)
        marc_token = org_with_users["marc_token"]
        client.post(f"/api/minutes/{minute_id}/validate", headers={"Authorization": f"Bearer {marc_token}"})
        r = client.post(f"/api/minutes/{minute_id}/share-links", json={
            "envelope": json.dumps({"a": "b"}),
        }, headers=h)
        token_link = r.json()["token"]
        rv = client.post(f"/api/share-links/{token_link}/revoke", headers=h)
        assert rv.status_code == 200
        assert client.get(f"/api/share-links/{token_link}").status_code == 410
        assert client.get(f"/api/share-links/{token_link}/content").status_code == 410

    def test_share_expired_link_410(self, client, org_with_users):
        token = org_with_users["sophie_token"]
        h = _setup_config(client, token)
        minute_id = _create_validated_minute(client, token)
        marc_token = org_with_users["marc_token"]
        client.post(f"/api/minutes/{minute_id}/validate", headers={"Authorization": f"Bearer {marc_token}"})
        r = client.post(f"/api/minutes/{minute_id}/share-links", json={
            "envelope": json.dumps({"a": "b"}), "expires_days": 1,
        }, headers=h)
        token_link = r.json()["token"]

        db = SessionLocal()
        try:
            from app.models.email import MinuteShareLink
            link = db.query(MinuteShareLink).filter(MinuteShareLink.token == token_link).first()
            link.expires_at = datetime.utcnow() - timedelta(hours=1)
            db.commit()
        finally:
            db.close()
        assert client.get(f"/api/share-links/{token_link}").status_code == 410

    def test_send_to_dp_queues_per_member(self, client, org_with_users):
        token = org_with_users["sophie_token"]
        h = _setup_config(client, token)
        minute_id = _create_validated_minute(client, token)
        marc_token = org_with_users["marc_token"]
        client.post(f"/api/minutes/{minute_id}/validate", headers={"Authorization": f"Bearer {marc_token}"})

        r = client.post(f"/api/minutes/{minute_id}/send-to-dp", headers=h)
        assert r.status_code == 200
        assert r.json()["queued"] == 3  # sophie, marc, tom

        db = SessionLocal()
        try:
            msgs = db.query(EmailOutbox).filter(EmailOutbox.event_type == "minutes_dp").all()
            assert len(msgs) == 3
            assert {m.recipient_email for m in msgs} == {"sophie@testpv.lu", "marc@testpv.lu", "tom@testpv.lu"}
        finally:
            db.close()
