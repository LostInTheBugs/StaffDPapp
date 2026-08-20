"""Tests personnalisation organisation (v2026.08.030) :
modules activables/désactivables (403 sur routes du module), logo
entreprise (PUT/DELETE + endpoint public), coordonnées contact DP."""

import json

from app.core.database import SessionLocal
from app.models import Organization


def _set_modules(org_id: int, modules: list[str]) -> None:
    db = SessionLocal()
    org = db.query(Organization).get(org_id)
    org.enabled_modules = json.dumps(modules)
    db.commit()
    db.close()


def test_modules_default_all_enabled(client, org_with_users):
    """Par défaut (enabled_modules NULL) : tous les modules actifs."""
    r = client.get("/api/organization/modules", headers={
        "Authorization": f"Bearer {org_with_users['marc_token']}"})
    assert r.status_code == 200
    mods = r.json()["modules"]
    assert "elections" in mods and "time_tracking" in mods and "contact" in mods
    assert len(mods) >= 9


def test_modules_update_admin_only(client, org_with_users):
    """Seul l'admin peut changer les modules ; module inconnu → 422."""
    # membre simple (tom) → 403
    r = client.put("/api/organization/modules", headers={
        "Authorization": f"Bearer {org_with_users['tom_token']}"},
        json={"modules": ["elections"]})
    assert r.status_code == 403
    # admin (sophie) → 200
    r = client.put("/api/organization/modules", headers={
        "Authorization": f"Bearer {org_with_users['sophie_token']}"},
        json={"modules": ["elections", "contact"]})
    assert r.status_code == 200
    assert r.json()["enabled_modules"] == ["elections", "contact"]
    # module inconnu → 422
    r = client.put("/api/organization/modules", headers={
        "Authorization": f"Bearer {org_with_users['sophie_token']}"},
        json={"modules": ["elections", "hack_module"]})
    assert r.status_code == 422


def test_disabled_module_blocks_routes(client, org_with_users):
    """Module désactivé → 403 sur TOUTES les routes du router."""
    _set_modules(org_with_users["org_id"], ["contact"])
    h = {"Authorization": f"Bearer {org_with_users['marc_token']}"}
    # élections
    assert client.get("/api/elections", headers=h).status_code == 403
    assert client.post("/api/elections", headers=h, json={}).status_code == 403
    # mes heures
    assert client.get("/api/time", headers=h).status_code == 403
    assert client.get("/api/time/summary", headers=h).status_code == 403
    # notices / conformité / consultations / stats / activités / legal
    assert client.get("/api/notices", headers=h).status_code == 403
    assert client.get("/api/compliance/overview", headers=h).status_code == 403
    assert client.get("/api/consultations", headers=h).status_code == 403
    assert client.get("/api/workforce-stats", headers=h).status_code == 403
    assert client.get("/api/delegate-activities", headers=h).status_code == 403
    assert client.get("/api/formation/overview", headers=h).status_code == 403
    # les routes hors module restent accessibles
    assert client.get("/api/organization/members", headers=h).status_code == 200


def test_disabled_module_dashboard_org_still_works(client, org_with_users):
    """Dashboard (organisation) reste accessible quand un module est coupé."""
    _set_modules(org_with_users["org_id"], ["contact"])
    r = client.get("/api/dashboard", headers={
        "Authorization": f"Bearer {org_with_users['marc_token']}"})
    assert r.status_code == 200
    assert r.json()["organization"]["enabled_modules"] == ["contact"]


def test_logo_put_delete(client, org_with_users):
    """Logo : PUT admin → visible dans dashboard + endpoint public ; DELETE retire."""
    h_admin = {"Authorization": f"Bearer {org_with_users['sophie_token']}"}
    # membre → 403
    r = client.put("/api/organization/logo", headers={
        "Authorization": f"Bearer {org_with_users['tom_token']}"},
        json={"logo_data": "data:image/png;base64,AAAA"})
    assert r.status_code == 403
    # format invalide → 422
    r = client.put("/api/organization/logo", headers=h_admin,
                   json={"logo_data": "https://evil.com/x.png"})
    assert r.status_code == 422
    # trop gros → 422
    r = client.put("/api/organization/logo", headers=h_admin,
                   json={"logo_data": "data:image/png;base64," + "A" * (512 * 1024)})
    assert r.status_code == 422
    # valide → 200
    r = client.put("/api/organization/logo", headers=h_admin,
                   json={"logo_data": "data:image/png;base64,iVBORw0KGgo="})
    assert r.status_code == 200
    assert r.json()["logo_data"] == "data:image/png;base64,iVBORw0KGgo="
    # endpoint public (slug) → logo + nom
    slug = r.json()["slug"]
    r2 = client.get(f"/api/organizations/{slug}/public")
    assert r2.status_code == 200
    assert r2.json()["logo_data"] == "data:image/png;base64,iVBORw0KGgo="
    assert r2.json()["name"] == r.json()["name"]
    # DELETE → logo retiré
    r3 = client.delete("/api/organization/logo", headers=h_admin)
    assert r3.status_code == 200
    assert r3.json()["logo_data"] is None
    assert client.get(f"/api/organizations/{slug}/public").json()["logo_data"] is None


def test_public_org_404(client):
    assert client.get("/api/organizations/does-not-exist/public").status_code == 404


def test_contact_update(client, org_with_users):
    """Coordonnées de contact : PUT /organization (admin) → dashboard."""
    h_admin = {"Authorization": f"Bearer {org_with_users['sophie_token']}"}
    r = client.put("/api/organization", headers=h_admin, json={
        "contact_email": "dp@testpv.lu",
        "contact_phone": "+352 12 34 56",
        "contact_hours": "Permanence mardi 14h-16h",
    })
    assert r.status_code == 200
    assert r.json()["contact_email"] == "dp@testpv.lu"
    assert r.json()["contact_phone"] == "+352 12 34 56"
    assert r.json()["contact_hours"] == "Permanence mardi 14h-16h"
    # visible pour tous les membres via dashboard
    r2 = client.get("/api/dashboard", headers={
        "Authorization": f"Bearer {org_with_users['tom_token']}"})
    assert r2.json()["organization"]["contact_email"] == "dp@testpv.lu"
    # effacement : chaîne vide → None
    r3 = client.put("/api/organization", headers=h_admin, json={"contact_email": ""})
    assert r3.json()["contact_email"] is None
    assert r3.json()["contact_phone"] == "+352 12 34 56"  # inchangé
