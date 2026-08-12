"""Rate limiting simple (fenêtre fixe, en mémoire).

Suffisant pour un worker unique (uvicorn par défaut). Le store est
volatile : un redémarrage du conteneur remet les compteurs à zéro.

Les clés sont typées par préfixe (login:, mfa:, join:, org:) + IP
client (X-Forwarded-For derrière Traefik/nginx).
"""

import time
from collections import defaultdict

from fastapi import HTTPException, Request

_windows: dict[str, list[float]] = defaultdict(list)
_sweep_counter = 0


def reset_rate_limits() -> None:
    """Vide le store (utilisé par les tests)."""
    _windows.clear()


def check_rate_limit(key: str, max_attempts: int, window_seconds: int = 900) -> None:
    """Compte une tentative ; HTTP 429 si le seuil est dépassé sur la fenêtre."""
    global _sweep_counter
    now = time.time()
    hits = [t for t in _windows[key] if now - t < window_seconds]
    if len(hits) >= max_attempts:
        raise HTTPException(
            status_code=429,
            detail="Trop de tentatives. Réessayez dans quelques minutes.",
        )
    hits.append(now)
    _windows[key] = hits

    # Purge périodique des clés mortes pour éviter la croissance mémoire
    _sweep_counter += 1
    if _sweep_counter >= 100:
        _sweep_counter = 0
        cutoff = now - 3600
        for k in [k for k, v in _windows.items() if not v or v[-1] < cutoff]:
            del _windows[k]


def client_ip(request: Request) -> str:
    """IP du client derrière un reverse proxy (Traefik → nginx)."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"
