"""Tests validation de langue (accepte fr/en/de/pt/lb, refuse les autres)."""


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def test_profile_language_accepts_lb(client, org_with_users):
    r = client.put("/api/auth/profile", json={"language": "lb"},
                   headers=_h(org_with_users["sophie_token"]))
    assert r.status_code == 200, r.text
    assert r.json().get("language") == "lb"


def test_profile_language_rejects_unknown(client, org_with_users):
    # passe d'abord en lb (validé par le test précédent)
    client.put("/api/auth/profile", json={"language": "lb"},
               headers=_h(org_with_users["sophie_token"]))
    # langue inconnue : silencieusement ignorée, la langue précédente reste
    r = client.put("/api/auth/profile", json={"language": "xx"},
                   headers=_h(org_with_users["sophie_token"]))
    assert r.status_code == 200
    assert r.json().get("language") == "lb"
