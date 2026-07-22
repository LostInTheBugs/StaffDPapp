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


@lru_cache
def get_settings() -> Settings:
    return Settings()
