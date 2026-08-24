"""Tests for L.414-3 consultations (tracking + direction notifications)."""

from datetime import datetime, timedelta, timezone

from app.core.database import SessionLocal
from app.models.consultation import Consultation
from app.models.email import EmailConfig, EmailOutbox


def _enable_email(client, token, transport="eml", direction="direction@testpv.lu"):
    r = client.put("/api/emails/config", headers={"Authorization": f"Bearer {token}"}, json={
        "enabled": True,
        "transport_mode": transport,
        "from_name": "TestPV",
        "from_email": "delegation@testpv.lu",
        "direction_email": direction,
    })
    assert r.status_code == 200, r.json()


def test_create_list_stats(client, org_with_users):
    t = org_with_users
    h = {"Authorization": f"Bearer {t['sophie_token']}"}

    r = client.post("/api/consultations", headers=h, json={
        "title": "Nouveau règlement intérieur",
        "category": "reglement_interieur",
        "description": "Révision des horaires",
    })
    assert r.status_code == 201, r.json()
    c = r.json()
    assert c["status"] == "requested"
    assert c["created_by_name"] == "Sophie Muller"
    # Règle légale : règlement intérieur → décision de l'employeur sous 2 mois
    assert c["response_due"] is not None
    due = datetime.fromisoformat(c["response_due"])
    assert due > datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=50)

    # Liste visible par un membre
    h_tom = {"Authorization": f"Bearer {t['tom_token']}"}
    r = client.get("/api/consultations", headers=h_tom)
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.get("/api/consultations/stats", headers=h_tom)
    assert r.status_code == 200
    assert r.json()["total"] == 1
    assert r.json()["pending"] == 1
    assert r.json()["overdue"] == 0


def test_member_cannot_create_or_update(client, org_with_users):
    t = org_with_users
    h_tom = {"Authorization": f"Bearer {t['tom_token']}"}

    r = client.post("/api/consultations", headers=h_tom, json={
        "title": "Interdit",
        "category": "autre",
    })
    assert r.status_code == 403


def test_consultation_not_in_other_org(client, org_with_users):
    """IDOR : un utilisateur d'une autre organisation ne voit pas la consultation."""
    t = org_with_users
    h = {"Authorization": f"Bearer {t['sophie_token']}"}
    r = client.post("/api/consultations", headers=h, json={
        "title": "Confidentiel TestPV",
        "category": "conditions_travail",
    })
    assert r.status_code == 201

    h_other = {"Authorization": f"Bearer {t['other_token']}"}
    r = client.get("/api/consultations", headers=h_other)
    assert r.status_code == 200
    assert len(r.json()) == 0


def test_response_requires_motivated_answer(client, org_with_users):
    """L.414-1 : consultation = échange + réponse motivée — impossible de clore sans réponse."""
    t = org_with_users
    h = {"Authorization": f"Bearer {t['sophie_token']}"}
    r = client.post("/api/consultations", headers=h, json={
        "title": "Temps de travail",
        "category": "temps_travail",
    })
    cid = r.json()["id"]

    # Sans réponse motivée → 422
    r = client.patch(f"/api/consultations/{cid}", headers=h, json={"status": "response_received"})
    assert r.status_code == 422

    # Avec réponse motivée → OK, direction_responded_at rempli
    r = client.patch(f"/api/consultations/{cid}", headers=h, json={
        "status": "response_received",
        "direction_response": "La direction accepte le nouveau régime horaire à partir du 1er octobre.",
    })
    assert r.status_code == 200, r.json()
    assert r.json()["status"] == "response_received"
    assert r.json()["direction_responded_at"] is not None


def test_create_notifies_direction(client, org_with_users):
    """La création d'une consultation met un email à la direction en file (outbox)."""
    t = org_with_users
    h = {"Authorization": f"Bearer {t['sophie_token']}"}
    _enable_email(client, t["sophie_token"])

    r = client.post("/api/consultations", headers=h, json={
        "title": "Plan de formation",
        "category": "formation",
        "description": "Demande de précisions sur le budget formation",
    })
    assert r.status_code == 201

    db = SessionLocal()
    try:
        msgs = db.query(EmailOutbox).filter(EmailOutbox.event_type == "consultation_created").all()
        assert len(msgs) == 1
        assert msgs[0].recipient_email == "direction@testpv.lu"
        assert "Plan de formation" in msgs[0].subject
        assert "demande de précisions" in msgs[0].body_text.lower()
    finally:
        db.close()


def test_create_without_email_config_is_silent(client, org_with_users):
    """Pas de config email → la consultation se crée quand même, aucun email."""
    t = org_with_users
    h = {"Authorization": f"Bearer {t['sophie_token']}"}
    r = client.post("/api/consultations", headers=h, json={
        "title": "Sans config",
        "category": "autre",
    })
    assert r.status_code == 201
    db = SessionLocal()
    try:
        assert db.query(EmailOutbox).filter(EmailOutbox.event_type == "consultation_created").count() == 0
    finally:
        db.close()


def test_reminder_scan_idempotent(client, org_with_users):
    """Rappel envoyé à la direction quand l'échéance est dépassée, au plus 1/jour."""
    from app.services.email_service import scan_consultation_reminders

    t = org_with_users
    h = {"Authorization": f"Bearer {t['sophie_token']}"}
    _enable_email(client, t["sophie_token"])

    r = client.post("/api/consultations", headers=h, json={
        "title": "Consultation en retard",
        "category": "conditions_travail",
        "response_due": (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=2)).isoformat(),
    })
    cid = r.json()["id"]

    db = SessionLocal()
    try:
        # 1er scan → 1 rappel + last_reminded_at posé
        n = scan_consultation_reminders(db)
        assert n == 1
        # 2e scan immédiat → idempotent (1/jour max)
        n2 = scan_consultation_reminders(db)
        assert n2 == 0
        c = db.query(Consultation).get(cid)
        assert c.last_reminded_at is not None

        msgs = db.query(EmailOutbox).filter(EmailOutbox.event_type == "consultation_reminder").all()
        assert len(msgs) == 1
        assert msgs[0].recipient_email == "direction@testpv.lu"
        assert "en retard" in msgs[0].subject
    finally:
        db.close()


def test_delete_rules(client, org_with_users):
    t = org_with_users
    h = {"Authorization": f"Bearer {t['sophie_token']}"}

    r = client.post("/api/consultations", headers=h, json={"title": "A supprimer", "category": "autre"})
    cid = r.json()["id"]
    r = client.delete(f"/api/consultations/{cid}", headers=h)
    assert r.status_code == 204

    # Une consultation clôturée ne peut pas être supprimée
    r = client.post("/api/consultations", headers=h, json={"title": "Clôturée", "category": "autre"})
    cid2 = r.json()["id"]
    client.patch(f"/api/consultations/{cid2}", headers=h, json={
        "status": "response_received",
        "direction_response": "Réponse motivée de test",
    })
    client.patch(f"/api/consultations/{cid2}", headers=h, json={"status": "closed"})
    r = client.delete(f"/api/consultations/{cid2}", headers=h)
    assert r.status_code == 400
