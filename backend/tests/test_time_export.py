"""Tests for time tracking CRUD and CSV export."""

import csv
import io


def test_create_list_delete(client, org_with_users, db):
    t = org_with_users
    h = {"Authorization": f"Bearer {t['sophie_token']}"}

    r = client.post("/api/time", headers=h, json={
        "date": "2026-08-10",
        "hours": 3.5,
        "category": "reunion",
        "description": "Réunion avec la direction",
    })
    assert r.status_code == 201, r.json()
    entry = r.json()
    assert entry["hours"] == 3.5

    r = client.get("/api/time?month=2026-08", headers=h)
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.delete(f"/api/time/{entry['id']}", headers=h)
    assert r.status_code == 204


def test_export_member_only_own(client, org_with_users):
    """Un membre n'exporte que ses propres heures (pas celles des autres)."""
    t = org_with_users
    h_s = {"Authorization": f"Bearer {t['sophie_token']}"}
    h_t = {"Authorization": f"Bearer {t['tom_token']}"}

    client.post("/api/time", headers=h_s, json={
        "date": "2026-08-10", "hours": 3.5, "category": "reunion", "description": "De Sophie",
    })
    client.post("/api/time", headers=h_t, json={
        "date": "2026-08-11", "hours": 2.0, "category": "administratif", "description": "De Tom",
    })

    # Tom (membre simple) : seulement SA ligne, pas de colonne Member
    r = client.get("/api/time/export?month=2026-08", headers=h_t)
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    lines = r.text.lstrip("\ufeff").splitlines()
    assert lines[0] == "Date,Hours,Category,Description"
    assert len(lines) == 2  # header + 1 ligne
    assert "De Tom" in lines[1]
    assert "De Sophie" not in r.text


def test_export_bureau_all_members(client, org_with_users):
    """Le bureau exporte toutes les heures de la délégation avec le membre."""
    t = org_with_users
    h_s = {"Authorization": f"Bearer {t['sophie_token']}"}
    h_t = {"Authorization": f"Bearer {t['tom_token']}"}

    client.post("/api/time", headers=h_s, json={
        "date": "2026-08-10", "hours": 3.5, "category": "reunion", "description": "De Sophie",
    })
    client.post("/api/time", headers=h_t, json={
        "date": "2026-08-11", "hours": 2.0, "category": "administratif", "description": "De Tom",
    })

    r = client.get("/api/time/export?month=2026-08", headers=h_s)
    assert r.status_code == 200
    lines = r.text.lstrip("\ufeff").splitlines()
    assert lines[0] == "Member,Email,Date,Hours,Category,Description"
    assert len(lines) == 3  # header + 2 lignes
    assert "De Sophie" in r.text and "De Tom" in r.text
    # Parse CSV valide
    reader = list(csv.reader(io.StringIO(r.text.lstrip("\ufeff"))))
    assert len(reader) == 3
    assert reader[1][0] != ""  # colonne Member remplie


def test_export_bad_month_422(client, org_with_users):
    t = org_with_users
    h = {"Authorization": f"Bearer {t['sophie_token']}"}
    r = client.get("/api/time/export?month=2026-13", headers=h)
    assert r.status_code == 422
