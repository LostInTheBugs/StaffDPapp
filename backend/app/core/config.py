from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "Staff Delegation"
    database_url: str = "sqlite:///./staff_delegation.db"
    secret_key: str = "change-me-in-production-use-openssl-rand-hex-32"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours
    invitation_code_length: int = 8

    model_config = {"env_prefix": "SD_", "env_file": ".env"}


# Valeurs d'exemple connues publiquement (doc, README, anciens défauts) —
# un déploiement qui démarre avec l'une d'elles a des jetons forgeables.
EXAMPLE_SECRET_KEYS = {
    "change-me-in-production",
    "change-me-in-production-use-openssl-rand-hex-32",
}


def assert_secret_key_is_set() -> None:
    """Refuse le démarrage avec une clé de signature JWT faible ou par défaut.

    Sans cette garde, un déploiement qui oublie son `.env` tourne avec une
    clé publiquement connue → n'importe qui peut forger des jetons pour
    n'importe quel compte, y compris administrateur. Exigences : clé
    différente des valeurs d'exemple ET au moins 32 caractères.
    """
    key = get_settings().secret_key
    if key in EXAMPLE_SECRET_KEYS or len(key) < 32:
        raise RuntimeError(
            "SD_SECRET_KEY doit être définie (clé aléatoire d'au moins 32 "
            "caractères — ex. `openssl rand -hex 32`). Refus de démarrer "
            "avec la valeur par défaut : des jetons JWT seraient forgeables."
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
