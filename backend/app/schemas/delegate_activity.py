"""Pydantic schemas for delegate activities (activités des délégués désignés)."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

# Catégories autorisées par domaine (L.414-14 sécurité/santé, L.414-15 égalité)
DOMAIN_CATEGORIES = {
    "securite_sante": {"visite", "enquete", "formation", "signalement", "autre"},
    "egalite": {"action", "sensibilisation", "formation", "signalement", "autre"},
}


class DelegateActivityCreate(BaseModel):
    user_id: int = Field(..., gt=0)
    domain: str = Field(..., pattern="^(securite_sante|egalite)$")
    category: str = Field(..., min_length=2, max_length=30)
    description: str = Field(..., min_length=3, max_length=2000)
    date: datetime

    @field_validator("category")
    @classmethod
    def check_category(cls, v: str, info) -> str:
        domain = info.data.get("domain")
        if domain and v not in DOMAIN_CATEGORIES.get(domain, set()):
            raise ValueError(f"Catégorie « {v} » non valide pour le domaine « {domain} »")
        return v


class DelegateActivityResponse(BaseModel):
    id: int
    user_id: int
    name: str
    domain: str
    category: str
    description: str
    date: datetime
    created_by_id: int
    created_at: datetime | None = None
