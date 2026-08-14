"""Tests for delegate activities (activités des délégués désignés)."""

from datetime import datetime, timezone

from app.models.user import User


def _designate(db, email, securite=False, egalite=False):
    u = db.query(User).filter(User.email == email).first()
    if securite:
        u.is_delegue_securite_sante = True
    if egalite:
        u.is_delegue_egalite = True
    db.commit()
    return u


def _act(client, token, user_id, domain="securite_sante", category="visite",
         description="Tournée de contrôle", date="2026-08-10T09:00:00"):
    return client.post("/api/delegate-activities",
                       headers={"Authorization": f"Bearer {token}"},
                       json={"user_id": user_id, "domain": domain, "category": category,
                             "description": description, "date": date})


class TestDelegateActivities:
    def test_member_reads_but_cannot_write(self, client, org_with_users, db):
        t = org_with_users
        marc = _designate(db, "marc@testpv.lu", securite=True)

        r = client.get("/api/delegate-activities",
                       headers={"Authorization": f"Bearer {t['tom_token']}"})
        assert r.status_code == 200

        r = _act(client, t["tom_token"], marc.id)
        assert r.status_code == 403

    def test_designated_delegate_logs_own_activity(self, client, org_with_users, db):
        t = org_with_users
        marc = _designate(db, "marc@testpv.lu", securite=True)

        r = _act(client, t["marc_token"], marc.id, category="visite",
                 description="Visite atelier 1")
        assert r.status_code == 201, r.json()
        a = r.json()
        assert a["name"] == "Marc Weber"
        assert a["domain"] == "securite_sante"
        assert a["category"] == "visite"

        # Liste : visible par tous
        r = client.get("/api/delegate-activities",
                       headers={"Authorization": f"Bearer {t['tom_token']}"})
        assert len(r.json()) == 1

    def test_delegate_cannot_log_for_another(self, client, org_with_users, db):
        t = org_with_users
        marc = _designate(db, "marc@testpv.lu", securite=True)
        tom = _designate(db, "tom@testpv.lu", egalite=True)

        # Tom (membre simple désigné égalité) ne peut pas loguer pour Marc
        r = _act(client, t["tom_token"], marc.id, domain="securite_sante", category="visite")
        assert r.status_code == 403

    def test_bureau_can_log_for_any_designated(self, client, org_with_users, db):
        t = org_with_users
        tom = _designate(db, "tom@testpv.lu", egalite=True)

        r = _act(client, t["sophie_token"], tom.id, domain="egalite", category="sensibilisation",
                 description="Atelier sensibilisation")
        assert r.status_code == 201, r.json()

    def test_cannot_log_for_non_designated(self, client, org_with_users, db):
        t = org_with_users
        tom = db.query(User).filter(User.email == "tom@testpv.lu").first()
        r = _act(client, t["sophie_token"], tom.id, domain="securite_sante")
        assert r.status_code == 400

    def test_invalid_category_for_domain_422(self, client, org_with_users, db):
        t = org_with_users
        marc = _designate(db, "marc@testpv.lu", securite=True)
        r = _act(client, t["marc_token"], marc.id, category="action",
                 description="Action égalité sur le domaine sécurité")
        assert r.status_code == 422

    def test_delete_author_or_bureau_only(self, client, org_with_users, db):
        t = org_with_users
        marc = _designate(db, "marc@testpv.lu", securite=True)
        r = _act(client, t["marc_token"], marc.id, description="Visite chaudière")
        aid = r.json()["id"]

        # Un autre membre (non bureau) ne peut pas supprimer
        r = client.delete(f"/api/delegate-activities/{aid}",
                          headers={"Authorization": f"Bearer {t['tom_token']}"})
        assert r.status_code == 403

        # Le bureau peut
        r = client.delete(f"/api/delegate-activities/{aid}",
                          headers={"Authorization": f"Bearer {t['sophie_token']}"})
        assert r.status_code == 204

        # Filtre année
        r = _act(client, t["marc_token"], marc.id, description="Visite 2025",
                 date="2025-05-01T09:00:00")
        r = client.get("/api/delegate-activities?year=2025",
                       headers={"Authorization": f"Bearer {t['sophie_token']}"})
        assert len(r.json()) == 1
