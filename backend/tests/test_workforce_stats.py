"""Tests for L.414-3 semiannual workforce statistics by sex."""

from app.models import WorkforceStat


def test_crud_and_permissions(client, org_with_users):
    t = org_with_users
    h = {"Authorization": f"Bearer {t['sophie_token']}"}  # présidente

    # Liste vide au départ
    r = client.get("/api/workforce-stats", headers=h)
    assert r.status_code == 200
    assert r.json() == []

    # Création par le bureau
    r = client.post("/api/workforce-stats", headers=h, json={
        "semester": "2026-1",
        "male_count": 68,
        "female_count": 52,
    })
    assert r.status_code == 201, r.json()
    s = r.json()
    assert s["total"] == 120
    assert s["semester"] == "2026-1"

    # Doublon → 409
    r = client.post("/api/workforce-stats", headers=h, json={
        "semester": "2026-1",
        "male_count": 1,
        "female_count": 1,
    })
    assert r.status_code == 409

    # Semestre invalide → 422
    r = client.post("/api/workforce-stats", headers=h, json={
        "semester": "2026-3",
        "male_count": 1,
        "female_count": 1,
    })
    assert r.status_code == 422

    # Visible par un membre
    h_tom = {"Authorization": f"Bearer {t['tom_token']}"}
    r = client.get("/api/workforce-stats", headers=h_tom)
    assert r.status_code == 200
    assert len(r.json()) == 1

    # /latest
    r = client.get("/api/workforce-stats/latest", headers=h_tom)
    assert r.status_code == 200
    assert r.json()["semester"] == "2026-1"

    # Membre non-bureau ne peut PAS créer
    r = client.post("/api/workforce-stats", headers=h_tom, json={
        "semester": "2026-2",
        "male_count": 60,
        "female_count": 60,
    })
    assert r.status_code == 403

    # Modification par le bureau
    r = client.put("/api/workforce-stats/1", headers=h, json={"female_count": 55})
    assert r.status_code == 200
    assert r.json()["female_count"] == 55
    assert r.json()["total"] == 123

    # IDOR : autre organisation → 404
    h_other = {"Authorization": f"Bearer {t['other_token']}"}
    r = client.put("/api/workforce-stats/1", headers=h_other, json={"male_count": 1})
    assert r.status_code == 404
    r = client.delete("/api/workforce-stats/1", headers=h_other)
    assert r.status_code == 404

    # Suppression par le bureau
    r = client.delete("/api/workforce-stats/1", headers=h)
    assert r.status_code == 204
    r = client.get("/api/workforce-stats", headers=h)
    assert r.json() == []

    # Suppression par un membre → 403
    r = client.post("/api/workforce-stats", headers=h, json={
        "semester": "2026-2",
        "male_count": 60,
        "female_count": 60,
    })
    assert r.status_code == 201
    r = client.delete("/api/workforce-stats/2", headers=h_tom)
    assert r.status_code == 403


def test_db_model_saved(client, org_with_users, db):
    t = org_with_users
    h = {"Authorization": f"Bearer {t['sophie_token']}"}
    client.post("/api/workforce-stats", headers=h, json={
        "semester": "2025-2",
        "male_count": 70,
        "female_count": 50,
    })
    rows = db.query(WorkforceStat).filter(WorkforceStat.organization_id == 1).all()
    assert len(rows) == 1
    assert rows[0].semester == "2025-2"
    assert rows[0].male_count == 70
