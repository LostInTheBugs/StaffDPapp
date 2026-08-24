"""Tests CORS (origines dev par défaut, pas d'écho des origines inconnues)."""


def test_cors_allows_dev_origins(client):
    r = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_rejects_unknown_origin(client):
    r = client.options(
        "/api/health",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    # origine non listée → pas d'en-tête CORS écho (le navigateur bloque)
    assert r.headers.get("access-control-allow-origin") is None
