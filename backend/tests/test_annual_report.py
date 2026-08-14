"""Tests for the annual activity report (rapport d'activité annuel)."""

from datetime import datetime, timezone

from app.models.user import User


def _add_entry(client, token, date, hours, category="reunion", description=None):
    r = client.post("/api/time", headers={"Authorization": f"Bearer {token}"}, json={
        "date": date,
        "hours": hours,
        "category": category,
        "description": description,
    })
    assert r.status_code == 201, r.json()
    return r.json()


class TestAnnualReport:
    def test_bureau_can_generate(self, client, org_with_users):
        t = org_with_users
        r = client.get("/api/stats/annual-report?year=2026",
                       headers={"Authorization": f"Bearer {t['sophie_token']}"})
        assert r.status_code == 200, r.json()
        data = r.json()
        assert data["year"] == 2026
        assert data["organization"]["employee_count"] == 120
        assert data["workforce"] == []
        assert data["hours"]["total"] == 0
        assert data["meetings"]["total"] == 0
        assert data["consultations"]["total"] == 0
        assert data["designates"] == []

    def test_member_rejected_403(self, client, org_with_users):
        t = org_with_users
        r = client.get("/api/stats/annual-report?year=2026",
                       headers={"Authorization": f"Bearer {t['tom_token']}"})
        assert r.status_code == 403

    def test_invalid_year_422(self, client, org_with_users):
        t = org_with_users
        r = client.get("/api/stats/annual-report?year=1999",
                       headers={"Authorization": f"Bearer {t['sophie_token']}"})
        assert r.status_code == 422

    def test_aggregates_hours_workforce_meetings(self, client, org_with_users, db):
        t = org_with_users
        h = {"Authorization": f"Bearer {t['sophie_token']}"}

        # Heures de la délégation (2 membres)
        _add_entry(client, t["sophie_token"], "2026-03-10", 3.5, "reunion", "Réunion")
        _add_entry(client, t["sophie_token"], "2026-03-11", 2.0, "tournee", "Tournée sécurité")
        _add_entry(client, t["tom_token"], "2026-04-01", 1.5, "administratif")

        # Stats semestrielles 2026
        r = client.post("/api/workforce-stats", headers=h, json={
            "semester": "2026-1", "male_count": 60, "female_count": 55,
        })
        assert r.status_code == 201, r.json()

        # Réunion avec direction (J+7 calendaires minimum — règle L.415-6)
        from datetime import timedelta
        future = (datetime.now(timezone.utc) + timedelta(days=10)).strftime("%Y-%m-%dT10:00:00")
        r = client.post("/api/meetings", headers=h, json={
            "title": "Réunion annuelle",
            "date": future,
            "direction_invited": True,
        })
        assert r.status_code == 201, r.json()

        data = client.get("/api/stats/annual-report?year=2026", headers=h).json()
        assert data["workforce"] == [{"semester": "2026-1", "male_count": 60, "female_count": 55, "total": 115}]
        assert data["hours"]["total"] == 7.0
        assert data["hours"]["by_category"]["reunion"] == 3.5
        assert data["hours"]["by_category"]["tournee"] == 2.0
        assert len(data["hours"]["by_user"]) == 2
        assert data["meetings"]["total"] == 1
        assert data["meetings"]["with_direction"] == 1

        # Autre année → vide
        data2 = client.get("/api/stats/annual-report?year=2025", headers=h).json()
        assert data2["hours"]["total"] == 0
        assert data2["workforce"] == []

    def test_designated_delegates_included(self, client, org_with_users, db):
        """Les délégués désignés (sécurité/santé + égalité) et leurs heures."""
        t = org_with_users
        h = {"Authorization": f"Bearer {t['sophie_token']}"}

        # Marc = délégué sécurité/santé, Tom = délégué égalité (via BDD, comme l'UI)
        marc = db.query(User).filter(User.email == "marc@testpv.lu").first()
        marc.is_delegue_securite_sante = True
        tom = db.query(User).filter(User.email == "tom@testpv.lu").first()
        tom.is_delegue_egalite = True
        db.commit()

        _add_entry(client, t["marc_token"], "2026-02-01", 2.5, "tournee", "Tournée de contrôle")
        _add_entry(client, t["tom_token"], "2026-02-02", 4.0, "reunion", "Réunion égalité")

        # Activité du délégué sécurité/santé (déclarée par lui-même)
        r = client.post("/api/delegate-activities",
                        headers={"Authorization": f"Bearer {t['marc_token']}"},
                        json={"user_id": marc.id, "domain": "securite_sante",
                              "category": "visite", "description": "Visite atelier",
                              "date": "2026-02-03T09:00:00"})
        assert r.status_code == 201, r.json()

        data = client.get("/api/stats/annual-report?year=2026", headers=h).json()
        assert len(data["designates"]) == 2

        by_name = {d["name"]: d for d in data["designates"]}
        marc_entry = by_name.get("Marc Weber")
        assert marc_entry is not None
        assert marc_entry["roles"] == ["securite_sante"]
        assert marc_entry["total_hours"] == 2.5
        assert marc_entry["hours_by_category"]["tournee"] == 2.5
        assert marc_entry["activities_count"] == 1
        assert marc_entry["activities_by_category"]["visite"] == 1

        tom_entry = by_name.get("Tom Wagner")
        assert tom_entry is not None
        assert tom_entry["roles"] == ["egalite"]
        assert tom_entry["total_hours"] == 4.0

        # Crédits légaux
        assert data["organization"]["equality_monthly_credit"] == 10  # 76-150 salariés

    def test_equality_credit_brackets(self):
        from app.routes.annual_report import equality_monthly_credit
        assert equality_monthly_credit(20) == 4   # 15-25
        assert equality_monthly_credit(40) == 6   # 26-50
        assert equality_monthly_credit(60) == 8   # 51-75
        assert equality_monthly_credit(120) == 10  # 76-150
        assert equality_monthly_credit(200) == 16  # >150 (4h/semaine)
