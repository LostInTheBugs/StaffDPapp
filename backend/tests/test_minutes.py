"""Tests for the minutes (PV) module — sectioned PV with projection and double validation."""
import base64
import pytest
from app.models.minute import MinuteStatus, Minute


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


# ═══════════════════════════════════════════════════════════════════
# Défaut 1 — direction-preview : aucune fuite d'id ni d'existence
# ═══════════════════════════════════════════════════════════════════


def _recursive_no_key(obj, key: str):
    """Vérifie récursivement qu'aucune clé n'existe dans l'arbre JSON."""
    if isinstance(obj, dict):
        assert key not in obj, f"Clé '{key}' trouvée dans: {obj}"
        for v in obj.values():
            _recursive_no_key(v, key)
    elif isinstance(obj, list):
        for item in obj:
            _recursive_no_key(item, key)


def test_direction_preview_no_id_anywhere(client, org_with_users):
    """La réponse direction-preview ne contient AUCUN champ 'id', à aucun niveau."""
    token = org_with_users["sophie_token"]
    h = {"Authorization": f"Bearer {token}"}
    meeting = _create_meeting(client, token)

    r = client.post(
        f"/api/meetings/{meeting['id']}/minutes",
        json={
            "sections": [
                {"position": 0, "title": "Interne", "content": _b64("secret"),
                 "visibility": "interne"},
                {"position": 1, "title": "Public", "content": _b64("public"),
                 "visibility": "partage"},
            ]
        },
        headers=h,
    )
    minute_id = r.json()["id"]

    r = client.get(f"/api/minutes/{minute_id}/direction-preview", headers=h)
    assert r.status_code == 200
    data = r.json()

    # minute_id is at top level of the response, not inside sections
    # The check: no 'id' inside any section object
    _recursive_no_key(data["sections"], "id")


def test_direction_preview_interleaved_no_count_leak(client, org_with_users):
    """PV avec 5 sections entrelacées : rien ne permet de déduire le compte total."""
    token = org_with_users["sophie_token"]
    h = {"Authorization": f"Bearer {token}"}
    meeting = _create_meeting(client, token)

    r = client.post(
        f"/api/meetings/{meeting['id']}/minutes",
        json={
            "sections": [
                {"position": 0, "title": "I1", "content": _b64("x"),
                 "visibility": "interne"},
                {"position": 1, "title": "P1", "content": _b64("a"),
                 "visibility": "partage"},
                {"position": 2, "title": "I2", "content": _b64("x"),
                 "visibility": "interne"},
                {"position": 3, "title": "I3", "content": _b64("x"),
                 "visibility": "interne"},
                {"position": 4, "title": "P2", "content": _b64("b"),
                 "visibility": "partage"},
            ]
        },
        headers=h,
    )
    minute_id = r.json()["id"]

    r = client.get(f"/api/minutes/{minute_id}/direction-preview", headers=h)
    assert r.status_code == 200
    data = r.json()

    sections = data["sections"]
    assert len(sections) == 2
    # Positions renumérotées en continu
    assert sections[0]["position"] == 0
    assert sections[0]["title"] == "P1"
    assert sections[1]["position"] == 1
    assert sections[1]["title"] == "P2"

    # Rien dans la réponse ne permet de déduire qu'il y avait 5 sections au total
    # (pas de count, pas d'id, pas de metadata par section)
    assert "count" not in data
    assert "total" not in data
    # Vérifie qu'aucun id ni référence interne ne fuite
    _recursive_no_key(sections, "id")
    raw = str(data)
    assert "I1" not in raw
    assert "I2" not in raw
    assert "I3" not in raw


# ═══════════════════════════════════════════════════════════════════
# Défaut 2 — règles de retour en brouillon (projection fingerprint)
# ═══════════════════════════════════════════════════════════════════


def _create_validated_minute(client, token_s, token_validator, sections=None):
    """Helper : crée un PV, le fait valider, retourne (minute_id, validated_by_id, validated_at)."""
    h_s = {"Authorization": f"Bearer {token_s}"}
    h_v = {"Authorization": f"Bearer {token_validator}"}

    if sections is None:
        sections = [
            {"position": 0, "title": "Interne", "content": _b64("secret"),
             "visibility": "interne"},
            {"position": 1, "title": "Public", "content": _b64("public"),
             "visibility": "partage"},
        ]

    meeting = _create_meeting(client, token_s)
    r = client.post(
        f"/api/meetings/{meeting['id']}/minutes",
        json={"sections": sections},
        headers=h_s,
    )
    assert r.status_code == 201
    minute_id = r.json()["id"]

    # Validate
    r = client.post(f"/api/minutes/{minute_id}/validate", headers=h_v)
    assert r.status_code == 200

    # Read back to get validated_by_id and validated_at
    r = client.get(f"/api/minutes/{minute_id}", headers=h_s)
    data = r.json()
    assert data["status"] == "valide"
    return minute_id, data["validated_by_id"], data["validated_at"]


def test_modify_only_interne_keeps_validated(client, org_with_users):
    """PV validé + modif UNIQUEMENT section interne → le PV RESTE validé."""
    sophie_token = org_with_users["sophie_token"]
    marc_token = org_with_users["marc_token"]
    h_s = {"Authorization": f"Bearer {sophie_token}"}

    minute_id, old_validated_by, old_validated_at = _create_validated_minute(
        client, sophie_token, marc_token,
        sections=[
            {"position": 0, "title": "Interne", "content": _b64("v1"),
             "visibility": "interne"},
            {"position": 1, "title": "Public", "content": _b64("v1"),
             "visibility": "partage"},
        ],
    )

    # Modifier UNIQUEMENT la section interne
    r = client.put(
        f"/api/minutes/{minute_id}/sections",
        json={
            "sections": [
                {"position": 0, "title": "Interne modifié", "content": _b64("v2"),
                 "visibility": "interne"},
                {"position": 1, "title": "Public", "content": _b64("v1"),
                 "visibility": "partage"},
            ]
        },
        headers=h_s,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "valide", f"Expected 'valide' but got '{data['status']}'"
    assert data["validated_by_id"] == old_validated_by
    assert data["validated_at"] == old_validated_at


def test_modify_partage_content_resets(client, org_with_users):
    """PV validé + modif CONTENU section partagée → retour en brouillon."""
    sophie_token = org_with_users["sophie_token"]
    marc_token = org_with_users["marc_token"]
    h_s = {"Authorization": f"Bearer {sophie_token}"}

    minute_id, _, _ = _create_validated_minute(
        client, sophie_token, marc_token,
        sections=[
            {"position": 0, "title": "Interne", "content": _b64("v1"),
             "visibility": "interne"},
            {"position": 1, "title": "Public", "content": _b64("v1"),
             "visibility": "partage"},
        ],
    )

    r = client.put(
        f"/api/minutes/{minute_id}/sections",
        json={
            "sections": [
                {"position": 0, "title": "Interne", "content": _b64("v1"),
                 "visibility": "interne"},
                {"position": 1, "title": "Public", "content": _b64("v2"),
                 "visibility": "partage"},
            ]
        },
        headers=h_s,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "brouillon"
    assert data["validated_by_id"] is None
    assert data["validated_at"] is None


def test_modify_partage_title_resets(client, org_with_users):
    """PV validé + modif TITRE section partagée → retour en brouillon."""
    sophie_token = org_with_users["sophie_token"]
    marc_token = org_with_users["marc_token"]
    h_s = {"Authorization": f"Bearer {sophie_token}"}

    minute_id, _, _ = _create_validated_minute(
        client, sophie_token, marc_token,
        sections=[
            {"position": 0, "title": "Interne", "content": _b64("v1"),
             "visibility": "interne"},
            {"position": 1, "title": "Public", "content": _b64("v1"),
             "visibility": "partage"},
        ],
    )

    r = client.put(
        f"/api/minutes/{minute_id}/sections",
        json={
            "sections": [
                {"position": 0, "title": "Interne", "content": _b64("v1"),
                 "visibility": "interne"},
                {"position": 1, "title": "Public modifié", "content": _b64("v1"),
                 "visibility": "partage"},
            ]
        },
        headers=h_s,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "brouillon"
    assert data["validated_by_id"] is None


def test_reorder_partage_resets(client, org_with_users):
    """PV validé + RÉORDONNEMENT de deux sections partagées → retour en brouillon."""
    sophie_token = org_with_users["sophie_token"]
    marc_token = org_with_users["marc_token"]
    h_s = {"Authorization": f"Bearer {sophie_token}"}

    minute_id, _, _ = _create_validated_minute(
        client, sophie_token, marc_token,
        sections=[
            {"position": 0, "title": "PA", "content": _b64("a"),
             "visibility": "partage"},
            {"position": 1, "title": "PB", "content": _b64("b"),
             "visibility": "partage"},
        ],
    )

    # Inverser l'ordre
    r = client.put(
        f"/api/minutes/{minute_id}/sections",
        json={
            "sections": [
                {"position": 0, "title": "PB", "content": _b64("b"),
                 "visibility": "partage"},
                {"position": 1, "title": "PA", "content": _b64("a"),
                 "visibility": "partage"},
            ]
        },
        headers=h_s,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "brouillon"
    assert data["validated_by_id"] is None


def test_delete_all_partage_resets(client, org_with_users):
    """PV validé + SUPPRESSION de toutes les sections partagées → retour en brouillon."""
    sophie_token = org_with_users["sophie_token"]
    marc_token = org_with_users["marc_token"]
    h_s = {"Authorization": f"Bearer {sophie_token}"}

    minute_id, _, _ = _create_validated_minute(
        client, sophie_token, marc_token,
        sections=[
            {"position": 0, "title": "Interne", "content": _b64("v1"),
             "visibility": "interne"},
            {"position": 1, "title": "Public", "content": _b64("v1"),
             "visibility": "partage"},
        ],
    )

    # Supprimer la section partagée (ne garder qu'interne)
    r = client.put(
        f"/api/minutes/{minute_id}/sections",
        json={
            "sections": [
                {"position": 0, "title": "Interne", "content": _b64("v1"),
                 "visibility": "interne"},
            ]
        },
        headers=h_s,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "brouillon"
    assert data["validated_by_id"] is None


def test_noop_update_keeps_validated(client, org_with_users):
    """PV validé + renvoi des MÊMES sections → le PV RESTE validé."""
    sophie_token = org_with_users["sophie_token"]
    marc_token = org_with_users["marc_token"]
    h_s = {"Authorization": f"Bearer {sophie_token}"}

    sections = [
        {"position": 0, "title": "Interne", "content": _b64("v1"),
         "visibility": "interne"},
        {"position": 1, "title": "Public", "content": _b64("v1"),
         "visibility": "partage"},
    ]
    minute_id, old_validated_by, old_validated_at = _create_validated_minute(
        client, sophie_token, marc_token, sections=sections,
    )

    # Renvoyer exactement les mêmes sections
    r = client.put(
        f"/api/minutes/{minute_id}/sections",
        json={"sections": sections},
        headers=h_s,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "valide"
    assert data["validated_by_id"] == old_validated_by
    assert data["validated_at"] == old_validated_at


def test_add_interne_keeps_validated(client, org_with_users):
    """PV validé + ajout d'une nouvelle section interne → le PV RESTE validé."""
    sophie_token = org_with_users["sophie_token"]
    marc_token = org_with_users["marc_token"]
    h_s = {"Authorization": f"Bearer {sophie_token}"}

    minute_id, old_validated_by, old_validated_at = _create_validated_minute(
        client, sophie_token, marc_token,
        sections=[
            {"position": 0, "title": "Interne", "content": _b64("v1"),
             "visibility": "interne"},
            {"position": 1, "title": "Public", "content": _b64("v1"),
             "visibility": "partage"},
        ],
    )

    # Ajouter une nouvelle section interne
    r = client.put(
        f"/api/minutes/{minute_id}/sections",
        json={
            "sections": [
                {"position": 0, "title": "Interne", "content": _b64("v1"),
                 "visibility": "interne"},
                {"position": 1, "title": "Public", "content": _b64("v1"),
                 "visibility": "partage"},
                {"position": 2, "title": "Nouvelle interne", "content": _b64("new"),
                 "visibility": "interne"},
            ]
        },
        headers=h_s,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "valide"
    assert data["validated_by_id"] == old_validated_by
    assert data["validated_at"] == old_validated_at


def test_reorder_partage_resets_when_sections_sent_out_of_order(client, org_with_users):
    """Réordonnancement détecté même si le client envoie les sections dans le
    désordre. Sans order_by explicite côté serveur, l'empreinte "après" dépendrait
    de l'ordre de retour des lignes SQLite, qui n'est garanti nulle part."""
    sophie_token = org_with_users["sophie_token"]
    marc_token = org_with_users["marc_token"]
    h_s = {"Authorization": f"Bearer {sophie_token}"}

    minute_id, _, _ = _create_validated_minute(
        client, sophie_token, marc_token,
        sections=[
            {"position": 0, "title": "PA", "content": _b64("a"), "visibility": "partage"},
            {"position": 1, "title": "PB", "content": _b64("b"), "visibility": "partage"},
        ],
    )

    # Inversion, mais envoyée dans un ordre de liste inverse des positions :
    # position 1 en premier, position 0 en second.
    r = client.put(
        f"/api/minutes/{minute_id}/sections",
        json={
            "sections": [
                {"position": 1, "title": "PA", "content": _b64("a"), "visibility": "partage"},
                {"position": 0, "title": "PB", "content": _b64("b"), "visibility": "partage"},
            ]
        },
        headers=h_s,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "brouillon"


def test_noop_update_sent_out_of_order_keeps_validated(client, org_with_users):
    """Aucun changement réel, mais sections envoyées dans le désordre :
    le PV doit RESTER validé (pas de faux positif)."""
    sophie_token = org_with_users["sophie_token"]
    marc_token = org_with_users["marc_token"]
    h_s = {"Authorization": f"Bearer {sophie_token}"}

    minute_id, _, _ = _create_validated_minute(
        client, sophie_token, marc_token,
        sections=[
            {"position": 0, "title": "PA", "content": _b64("a"), "visibility": "partage"},
            {"position": 1, "title": "PB", "content": _b64("b"), "visibility": "partage"},
        ],
    )

    r = client.put(
        f"/api/minutes/{minute_id}/sections",
        json={
            "sections": [
                {"position": 1, "title": "PB", "content": _b64("b"), "visibility": "partage"},
                {"position": 0, "title": "PA", "content": _b64("a"), "visibility": "partage"},
            ]
        },
        headers=h_s,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "valide"


# ═══════════════════════════════════════════════════════════════════
# PUBLISH TESTS — POST /api/minutes/{id}/publish
# ═══════════════════════════════════════════════════════════════════


def _create_validated_for_publish(client, token_creator, token_validator, sections=None):
    """Create a validated minute and return (minute_id, sections_count)."""
    if sections is None:
        sections = [
            {"position": 0, "title": "Interne", "content": _b64("secret"),
             "visibility": "interne"},
            {"position": 1, "title": "Public", "content": _b64("info"),
             "visibility": "partage"},
        ]
    h_c = {"Authorization": f"Bearer {token_creator}"}
    h_v = {"Authorization": f"Bearer {token_validator}"}
    meeting = _create_meeting(client, token_creator)
    r = client.post(
        f"/api/meetings/{meeting['id']}/minutes",
        json={"sections": sections},
        headers=h_c,
    )
    assert r.status_code == 201
    minute_id = r.json()["id"]
    r = client.post(f"/api/minutes/{minute_id}/validate", headers=h_v)
    assert r.status_code == 200
    return minute_id


def _publish(client, minute_id, token, sha256="a" * 64):
    h = {"Authorization": f"Bearer {token}"}
    return client.post(
        f"/api/minutes/{minute_id}/publish",
        json={"pdf_sha256": sha256},
        headers=h,
    )


def test_publish_refused_to_non_bureau(client, org_with_users):
    """Un membre hors bureau ne peut pas diffuser (403)."""
    sophie_token = org_with_users["sophie_token"]
    marc_token = org_with_users["marc_token"]
    tom_token = org_with_users["tom_token"]
    minute_id = _create_validated_for_publish(client, sophie_token, marc_token)
    r = _publish(client, minute_id, tom_token)
    assert r.status_code == 403


def test_publish_refused_to_other_org(client, org_with_users):
    """IDOR: un utilisateur d'une autre organisation reçoit 404."""
    sophie_token = org_with_users["sophie_token"]
    marc_token = org_with_users["marc_token"]
    other_token = org_with_users["other_token"]
    minute_id = _create_validated_for_publish(client, sophie_token, marc_token)
    r = _publish(client, minute_id, other_token)
    assert r.status_code == 404


def test_publish_refused_non_valide(client, org_with_users):
    """Diffusion refusée sur un PV non validé (409)."""
    sophie_token = org_with_users["sophie_token"]
    h = {"Authorization": f"Bearer {sophie_token}"}
    meeting = _create_meeting(client, sophie_token)
    r = client.post(
        f"/api/meetings/{meeting['id']}/minutes",
        json={"sections": [
            {"position": 0, "title": "S1", "content": _b64("test"),
             "visibility": "partage"},
        ]},
        headers=h,
    )
    minute_id = r.json()["id"]
    r = _publish(client, minute_id, sophie_token)
    assert r.status_code == 409
    assert "validé" in r.json()["detail"].lower()


def test_publish_creates_history(client, org_with_users):
    """Une diffusion crée une ligne d'historique et passe le statut à 'diffuse'."""
    sophie_token = org_with_users["sophie_token"]
    marc_token = org_with_users["marc_token"]
    minute_id = _create_validated_for_publish(client, sophie_token, marc_token)
    r = _publish(client, minute_id, marc_token, sha256="e" * 64)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    # Check minute now has status diffuse
    h = {"Authorization": f"Bearer {sophie_token}"}
    r = client.get(f"/api/minutes/{minute_id}", headers=h)
    assert r.json()["status"] == "diffuse"
    assert len(r.json()["publications"]) == 1
    pub = r.json()["publications"][0]
    assert pub["pdf_sha256"] == "e" * 64
    assert pub["sections_count"] == 1


def test_publish_twice_creates_two_history_entries(client, org_with_users):
    """Deux diffusions successives créent deux lignes d'historique."""
    sophie_token = org_with_users["sophie_token"]
    marc_token = org_with_users["marc_token"]
    minute_id = _create_validated_for_publish(client, sophie_token, marc_token,
        sections=[
            {"position": 0, "title": "S1", "content": _b64("a"), "visibility": "partage"},
        ])

    # First publish
    _publish(client, minute_id, marc_token, sha256="a" * 64)
    # Manually set status back to valide for the second publish
    from app.core.database import SessionLocal
    db = SessionLocal()
    m = db.query(Minute).filter(Minute.id == minute_id).first()
    m.status = MinuteStatus.valide
    db.commit()
    db.close()

    r = _publish(client, minute_id, marc_token, sha256="b" * 64)
    assert r.status_code == 200

    h = {"Authorization": f"Bearer {sophie_token}"}
    r = client.get(f"/api/minutes/{minute_id}", headers=h)
    assert len(r.json()["publications"]) == 2
    hashes = [p["pdf_sha256"] for p in r.json()["publications"]]
    assert "a" * 64 in hashes
    assert "b" * 64 in hashes


def test_modify_partage_after_publish_resets_to_brouillon(client, org_with_users):
    """Modifier une section partagée après diffusion repasse le PV en brouillon."""
    sophie_token = org_with_users["sophie_token"]
    marc_token = org_with_users["marc_token"]
    h_s = {"Authorization": f"Bearer {sophie_token}"}

    minute_id = _create_validated_for_publish(client, sophie_token, marc_token,
        sections=[
            {"position": 0, "title": "Interne", "content": _b64("secret"),
             "visibility": "interne"},
            {"position": 1, "title": "Public", "content": _b64("v1"),
             "visibility": "partage"},
        ])

    _publish(client, minute_id, marc_token, sha256="c" * 64)

    # Modify the shared section
    r = client.put(
        f"/api/minutes/{minute_id}/sections",
        json={"sections": [
            {"position": 0, "title": "Interne", "content": _b64("secret"),
             "visibility": "interne"},
            {"position": 1, "title": "Public modifié", "content": _b64("v2"),
             "visibility": "partage"},
        ]},
        headers=h_s,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "brouillon"
    assert r.json()["validated_by_id"] is None
