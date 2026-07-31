"""Tests for the minutes (PV) module — sectioned PV with projection and double validation."""
import base64
import pytest


def _b64(s: str) -> str:
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


def _create_meeting(client, token, title="Réunion test", **kwargs):
    from datetime import datetime, timedelta
    body = {
        "title": title,
        "date": (datetime.now() + timedelta(days=10)).isoformat(),
        "location": kwargs.get("location"),
        "direction_invited": kwargs.get("direction_invited", False),
        "points": kwargs.get("points", [{"description": "Point 1", "order": 0}]),
        "invitee_ids": kwargs.get("invitee_ids", []),
    }
    h = {"Authorization": f"Bearer {token}"}
    r = client.post("/api/meetings", json=body, headers=h)
    assert r.status_code == 201, f"Create meeting failed: {r.json()}"
    return r.json()


def _login(client, email, password, captcha_id, captcha_answer):
    r = client.post("/api/auth/login", json={
        "email": email, "password": password,
        "captcha_id": captcha_id, "captcha_answer": captcha_answer,
    })
    assert r.status_code == 200, f"Login failed: {r.json()}"
    return r.json()["access_token"]


# ═══════════════════════════════════════════════════════════════════
# Fixture
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def org_with_users(client):
    """Create an org with president (sophie), secretary (marc), and member (tom)."""
    from tests.helpers import fetch_captcha, create_invitation
    from app.core.database import SessionLocal
    from app.models.user import User

    # Create org
    cid, ans = fetch_captcha(client)
    r = client.post("/api/organizations", json={
        "organization_name": "TestPV",
        "company_name": "TestPV SA",
        "employee_count": 120,
        "admin_email": "sophie@testpv.lu",
        "admin_password": "test123456",
        "admin_first_name": "Sophie",
        "admin_last_name": "Muller",
        "admin_delegue_status": "titulaire",
        "admin_delegue_role": "president",
        "captcha_id": cid,
        "captcha_answer": ans,
    })
    assert r.status_code == 201, f"Create org failed: {r.json()}"

    # Login as sophie
    cid2, ans2 = fetch_captcha(client)
    sophie_token = _login(client, "sophie@testpv.lu", "test123456", cid2, ans2)
    h = {"Authorization": f"Bearer {sophie_token}"}

    # Get org_id
    r = client.get("/api/dashboard", headers=h)
    org_id = r.json()["organization"]["id"]

    # Get sophie's user_id
    db = SessionLocal()
    sophie = db.query(User).filter(User.email == "sophie@testpv.lu").first()
    sophie_id = sophie.id
    db.close()

    # Invite marc as secretaire
    db2 = SessionLocal()
    create_invitation(db2, "marc@testpv.lu", org_id, sophie_id, "MARC123",
                      delegue_status="titulaire", delegue_role="secretaire")
    db2.close()

    # Marc joins
    cid3, ans3 = fetch_captcha(client)
    client.post("/api/join", json={
        "email": "marc@testpv.lu", "password": "test123456",
        "first_name": "Marc", "last_name": "Weber",
        "invitation_code": "MARC123",
        "captcha_id": cid3, "captcha_answer": ans3,
    })

    # Invite tom as membre
    db3 = SessionLocal()
    create_invitation(db3, "tom@testpv.lu", org_id, sophie_id, "TOM456",
                      delegue_status="titulaire", delegue_role="membre")
    db3.close()

    cid4, ans4 = fetch_captcha(client)
    client.post("/api/join", json={
        "email": "tom@testpv.lu", "password": "test123456",
        "first_name": "Tom", "last_name": "Wagner",
        "invitation_code": "TOM456",
        "captcha_id": cid4, "captcha_answer": ans4,
    })

    # Also create another org for IDOR tests
    cid5, ans5 = fetch_captcha(client)
    r2 = client.post("/api/organizations", json={
        "organization_name": "OtherOrg",
        "company_name": "Other SA",
        "employee_count": 50,
        "admin_email": "other@other.lu",
        "admin_password": "test123456",
        "admin_first_name": "Other",
        "admin_last_name": "User",
        "admin_delegue_status": "titulaire",
        "admin_delegue_role": "president",
        "captcha_id": cid5,
        "captcha_answer": ans5,
    })
    assert r2.status_code == 201

    cid6, ans6 = fetch_captcha(client)
    other_token = _login(client, "other@other.lu", "test123456", cid6, ans6)

    # Authentication tokens for the three users
    cid_s, ans_s = fetch_captcha(client)
    stok = _login(client, "sophie@testpv.lu", "test123456", cid_s, ans_s)
    cid_m, ans_m = fetch_captcha(client)
    mtok = _login(client, "marc@testpv.lu", "test123456", cid_m, ans_m)
    cid_t, ans_t = fetch_captcha(client)
    ttok = _login(client, "tom@testpv.lu", "test123456", cid_t, ans_t)

    return {
        "org_id": org_id,
        "sophie_token": stok,
        "marc_token": mtok,
        "tom_token": ttok,
        "other_token": other_token,
    }


# ═══════════════════════════════════════════════════════════════════
# Test: default visibility is 'interne'
# ═══════════════════════════════════════════════════════════════════


def test_section_default_visibility_is_interne(client, org_with_users):
    """Une section créée sans visibility explicite est interne."""
    token = org_with_users["sophie_token"]
    h = {"Authorization": f"Bearer {token}"}
    meeting = _create_meeting(client, token)

    r = client.post(
        f"/api/meetings/{meeting['id']}/minutes",
        json={
            "sections": [
                {"position": 0, "title": "Section sans visibilité", "content": _b64("contenu test")},
            ]
        },
        headers=h,
    )
    assert r.status_code == 201, f"Create minute failed: {r.json()}"
    data = r.json()
    assert data["sections"][0]["visibility"] == "interne"


def test_section_explicit_interne(client, org_with_users):
    """Une section créée avec visibility='interne' est bien interne."""
    token = org_with_users["sophie_token"]
    h = {"Authorization": f"Bearer {token}"}
    meeting = _create_meeting(client, token)

    r = client.post(
        f"/api/meetings/{meeting['id']}/minutes",
        json={
            "sections": [
                {"position": 0, "title": "Section interne", "content": _b64("secret"), "visibility": "interne"},
                {"position": 1, "title": "Section partage", "content": _b64("public"), "visibility": "partage"},
            ]
        },
        headers=h,
    )
    assert r.status_code == 201
    sections = r.json()["sections"]
    assert sections[0]["visibility"] == "interne"
    assert sections[1]["visibility"] == "partage"


# ═══════════════════════════════════════════════════════════════════
# Test: direction-preview excludes interne sections
# ═══════════════════════════════════════════════════════════════════


def test_direction_preview_excludes_interne(client, org_with_users):
    """direction-preview ne contient AUCUN contenu ni titre de section interne."""
    token = org_with_users["sophie_token"]
    h = {"Authorization": f"Bearer {token}"}
    meeting = _create_meeting(client, token)

    r = client.post(
        f"/api/meetings/{meeting['id']}/minutes",
        json={
            "sections": [
                {"position": 0, "title": "Confidentiel", "content": _b64("secret défense"), "visibility": "interne"},
                {"position": 1, "title": "Résumé public", "content": _b64("tout va bien"), "visibility": "partage"},
            ]
        },
        headers=h,
    )
    minute_id = r.json()["id"]

    r = client.get(f"/api/minutes/{minute_id}/direction-preview", headers=h)
    assert r.status_code == 200
    preview = r.json()
    sections = preview["sections"]
    assert len(sections) == 1
    assert sections[0]["title"] == "Résumé public"
    content = base64.b64decode(sections[0]["content"]).decode("utf-8")
    assert content == "tout va bien"
    all_text = str(sections)
    assert "Confidentiel" not in all_text
    assert "secret défense" not in all_text


def test_direction_preview_empty_interne_section(client, org_with_users):
    """Les sections internes vides sont exclues de la preview."""
    token = org_with_users["sophie_token"]
    h = {"Authorization": f"Bearer {token}"}
    meeting = _create_meeting(client, token)

    r = client.post(
        f"/api/meetings/{meeting['id']}/minutes",
        json={
            "sections": [
                {"position": 0, "title": "Section vide", "content": _b64(""), "visibility": "interne"},
                {"position": 1, "title": "Publique", "content": _b64("info"), "visibility": "partage"},
            ]
        },
        headers=h,
    )
    minute_id = r.json()["id"]
    r = client.get(f"/api/minutes/{minute_id}/direction-preview", headers=h)
    sections = r.json()["sections"]
    assert len(sections) == 1
    assert sections[0]["title"] == "Publique"


def test_direction_preview_unicode_interne(client, org_with_users):
    """Les caractères Unicode dans les sections internes ne fuient pas."""
    token = org_with_users["sophie_token"]
    h = {"Authorization": f"Bearer {token}"}
    meeting = _create_meeting(client, token)

    r = client.post(
        f"/api/meetings/{meeting['id']}/minutes",
        json={
            "sections": [
                {"position": 0, "title": "秘密のセクション", "content": _b64("秘密 🔒 données confidentielles 機密"), "visibility": "interne"},
                {"position": 1, "title": "公開", "content": _b64("publique 公開"), "visibility": "partage"},
            ]
        },
        headers=h,
    )
    minute_id = r.json()["id"]
    r = client.get(f"/api/minutes/{minute_id}/direction-preview", headers=h)
    all_text = str(r.json())
    assert "秘密" not in all_text
    assert "confidentielles" not in all_text
    assert "機密" not in all_text
    assert "公開" in all_text


def test_direction_preview_renumbers_continuously(client, org_with_users):
    """La preview renumérote les sections en continu (pas de trous)."""
    token = org_with_users["sophie_token"]
    h = {"Authorization": f"Bearer {token}"}
    meeting = _create_meeting(client, token)

    r = client.post(
        f"/api/meetings/{meeting['id']}/minutes",
        json={
            "sections": [
                {"position": 0, "title": "Interne 1", "content": _b64("x"), "visibility": "interne"},
                {"position": 1, "title": "Partage 1", "content": _b64("a"), "visibility": "partage"},
                {"position": 2, "title": "Interne 2", "content": _b64("x"), "visibility": "interne"},
                {"position": 3, "title": "Partage 2", "content": _b64("b"), "visibility": "partage"},
            ]
        },
        headers=h,
    )
    minute_id = r.json()["id"]
    r = client.get(f"/api/minutes/{minute_id}/direction-preview", headers=h)
    sections = r.json()["sections"]
    assert len(sections) == 2
    assert sections[0]["position"] == 0
    assert sections[0]["title"] == "Partage 1"
    assert sections[1]["position"] == 1
    assert sections[1]["title"] == "Partage 2"


# ═══════════════════════════════════════════════════════════════════
# Test: validation rules
# ═══════════════════════════════════════════════════════════════════


def test_creator_cannot_validate_own_minute(client, org_with_users):
    """Le rédacteur ne peut pas valider son propre PV (403)."""
    token = org_with_users["sophie_token"]
    h = {"Authorization": f"Bearer {token}"}
    meeting = _create_meeting(client, token)

    r = client.post(
        f"/api/meetings/{meeting['id']}/minutes",
        json={
            "sections": [
                {"position": 0, "title": "S1", "content": _b64("test"), "visibility": "partage"},
            ]
        },
        headers=h,
    )
    minute_id = r.json()["id"]
    r = client.post(f"/api/minutes/{minute_id}/validate", headers=h)
    assert r.status_code == 403


def test_other_bureau_member_can_validate(client, org_with_users):
    """Un autre membre du bureau peut valider."""
    sophie_token = org_with_users["sophie_token"]
    marc_token = org_with_users["marc_token"]
    h_s = {"Authorization": f"Bearer {sophie_token}"}
    h_m = {"Authorization": f"Bearer {marc_token}"}

    meeting = _create_meeting(client, sophie_token)
    r = client.post(
        f"/api/meetings/{meeting['id']}/minutes",
        json={
            "sections": [
                {"position": 0, "title": "S1", "content": _b64("test"), "visibility": "partage"},
            ]
        },
        headers=h_s,
    )
    minute_id = r.json()["id"]

    r = client.post(f"/api/minutes/{minute_id}/validate", headers=h_m)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    r = client.get(f"/api/minutes/{minute_id}", headers=h_s)
    assert r.json()["status"] == "valide"
    assert r.json()["validated_by_id"] is not None


def test_non_bureau_member_cannot_validate(client, org_with_users):
    """Un membre hors bureau ne peut pas valider."""
    sophie_token = org_with_users["sophie_token"]
    tom_token = org_with_users["tom_token"]
    h_s = {"Authorization": f"Bearer {sophie_token}"}
    h_t = {"Authorization": f"Bearer {tom_token}"}

    meeting = _create_meeting(client, sophie_token)
    r = client.post(
        f"/api/meetings/{meeting['id']}/minutes",
        json={
            "sections": [
                {"position": 0, "title": "S1", "content": _b64("test"), "visibility": "partage"},
            ]
        },
        headers=h_s,
    )
    minute_id = r.json()["id"]
    r = client.post(f"/api/minutes/{minute_id}/validate", headers=h_t)
    assert r.status_code == 403


# ═══════════════════════════════════════════════════════════════════
# Test: IDOR — cross-organization isolation
# ═══════════════════════════════════════════════════════════════════


def _create_minute_for_org(client, token):
    """Helper: create a meeting + minute, return minute_id."""
    h = {"Authorization": f"Bearer {token}"}
    meeting = _create_meeting(client, token)
    r = client.post(
        f"/api/meetings/{meeting['id']}/minutes",
        json={
            "sections": [
                {"position": 0, "title": "S1", "content": _b64("test"), "visibility": "interne"},
            ]
        },
        headers=h,
    )
    assert r.status_code == 201
    return r.json()["id"], meeting["id"]


def test_idor_get_minute(client, org_with_users):
    """Un utilisateur d'une autre organisation reçoit 404 sur GET /api/minutes/{id}."""
    sophie_token = org_with_users["sophie_token"]
    other_token = org_with_users["other_token"]
    minute_id, _ = _create_minute_for_org(client, sophie_token)
    h_other = {"Authorization": f"Bearer {other_token}"}
    r = client.get(f"/api/minutes/{minute_id}", headers=h_other)
    assert r.status_code == 404


def test_idor_update_sections(client, org_with_users):
    """IDOR sur PUT /api/minutes/{id}/sections."""
    sophie_token = org_with_users["sophie_token"]
    other_token = org_with_users["other_token"]
    minute_id, _ = _create_minute_for_org(client, sophie_token)
    h_other = {"Authorization": f"Bearer {other_token}"}
    r = client.put(
        f"/api/minutes/{minute_id}/sections",
        json={"sections": [{"position": 0, "title": "X", "content": _b64("y"), "visibility": "interne"}]},
        headers=h_other,
    )
    assert r.status_code == 404


def test_idor_validate(client, org_with_users):
    """IDOR sur POST /api/minutes/{id}/validate."""
    sophie_token = org_with_users["sophie_token"]
    other_token = org_with_users["other_token"]
    minute_id, _ = _create_minute_for_org(client, sophie_token)
    h_other = {"Authorization": f"Bearer {other_token}"}
    r = client.post(f"/api/minutes/{minute_id}/validate", headers=h_other)
    assert r.status_code == 404


def test_idor_direction_preview(client, org_with_users):
    """IDOR sur GET /api/minutes/{id}/direction-preview."""
    sophie_token = org_with_users["sophie_token"]
    other_token = org_with_users["other_token"]
    minute_id, _ = _create_minute_for_org(client, sophie_token)
    h_other = {"Authorization": f"Bearer {other_token}"}
    r = client.get(f"/api/minutes/{minute_id}/direction-preview", headers=h_other)
    assert r.status_code == 404


def test_idor_create_minute(client, org_with_users):
    """IDOR sur POST /api/meetings/{id}/minutes."""
    sophie_token = org_with_users["sophie_token"]
    other_token = org_with_users["other_token"]
    h_s = {"Authorization": f"Bearer {sophie_token}"}
    meeting = _create_meeting(client, sophie_token)
    h_other = {"Authorization": f"Bearer {other_token}"}
    r = client.post(
        f"/api/meetings/{meeting['id']}/minutes",
        json={"sections": [{"position": 0, "title": "S1", "content": _b64("test"), "visibility": "interne"}]},
        headers=h_other,
    )
    assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# Test: modifying partage section after validation resets status
# ═══════════════════════════════════════════════════════════════════


def test_modify_partage_after_validation_resets_to_brouillon(client, org_with_users):
    """Modifier une section partage après validation repasse le PV en brouillon."""
    sophie_token = org_with_users["sophie_token"]
    marc_token = org_with_users["marc_token"]
    h_s = {"Authorization": f"Bearer {sophie_token}"}
    h_m = {"Authorization": f"Bearer {marc_token}"}

    meeting = _create_meeting(client, sophie_token)
    r = client.post(
        f"/api/meetings/{meeting['id']}/minutes",
        json={
            "sections": [
                {"position": 0, "title": "S1", "content": _b64("v1"), "visibility": "partage"},
                {"position": 1, "title": "S2", "content": _b64("interne"), "visibility": "interne"},
            ]
        },
        headers=h_s,
    )
    minute_id = r.json()["id"]

    # Validate by Marc
    r = client.post(f"/api/minutes/{minute_id}/validate", headers=h_m)
    assert r.status_code == 200

    # Verify status is valide
    r = client.get(f"/api/minutes/{minute_id}", headers=h_s)
    assert r.json()["status"] == "valide"

    # Modify sections
    r = client.put(
        f"/api/minutes/{minute_id}/sections",
        json={
            "sections": [
                {"position": 0, "title": "S1 modifié", "content": _b64("v2"), "visibility": "partage"},
                {"position": 1, "title": "S2", "content": _b64("interne v2"), "visibility": "interne"},
            ]
        },
        headers=h_s,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "brouillon"
    assert data["validated_by_id"] is None
    assert data["validated_at"] is None


# ═══════════════════════════════════════════════════════════════════
# Test: sections are sorted by position
# ═══════════════════════════════════════════════════════════════════


def test_sections_sorted_by_position(client, org_with_users):
    """Les sections sont renvoyées triées par position."""
    token = org_with_users["sophie_token"]
    h = {"Authorization": f"Bearer {token}"}
    meeting = _create_meeting(client, token)

    r = client.post(
        f"/api/meetings/{meeting['id']}/minutes",
        json={
            "sections": [
                {"position": 3, "title": "Troisième", "content": _b64("3"), "visibility": "interne"},
                {"position": 1, "title": "Première", "content": _b64("1"), "visibility": "partage"},
                {"position": 2, "title": "Deuxième", "content": _b64("2"), "visibility": "interne"},
            ]
        },
        headers=h,
    )
    assert r.status_code == 201
    sections = r.json()["sections"]
    positions = [s["position"] for s in sections]
    assert positions == sorted(positions), f"Sections not sorted: {positions}"


def test_one_minute_per_meeting(client, org_with_users):
    """Une réunion a au plus un PV."""
    token = org_with_users["sophie_token"]
    h = {"Authorization": f"Bearer {token}"}
    meeting = _create_meeting(client, token)

    r = client.post(
        f"/api/meetings/{meeting['id']}/minutes",
        json={
            "sections": [
                {"position": 0, "title": "S1", "content": _b64("test"), "visibility": "interne"},
            ]
        },
        headers=h,
    )
    assert r.status_code == 201

    r = client.post(
        f"/api/meetings/{meeting['id']}/minutes",
        json={
            "sections": [
                {"position": 0, "title": "S2", "content": _b64("test2"), "visibility": "interne"},
            ]
        },
        headers=h,
    )
    assert r.status_code == 400
    assert "existe déjà" in r.json()["detail"]


def test_create_minute_meeting_not_found(client, org_with_users):
    """404 si la réunion n'existe pas."""
    token = org_with_users["sophie_token"]
    h = {"Authorization": f"Bearer {token}"}
    r = client.post(
        "/api/meetings/99999/minutes",
        json={"sections": [{"position": 0, "title": "S", "content": _b64("x"), "visibility": "interne"}]},
        headers=h,
    )
    assert r.status_code == 404
