from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class WorkforceStatBase(BaseModel):
    semester: str = Field(..., description="Semestre, ex. 2026-1 (S1) / 2026-2 (S2)")
    male_count: int = Field(..., ge=0)
    female_count: int = Field(..., ge=0)

    @field_validator("semester")
    @classmethod
    def check_semester(cls, v: str) -> str:
        v = v.strip()
        parts = v.split("-")
        if len(parts) != 2 or not parts[0].isdigit() or parts[1] not in ("1", "2"):
            raise ValueError("Format attendu : AAAA-1 ou AAAA-2 (ex. 2026-1)")
        year = int(parts[0])
        if year < 2000 or year > 2100:
            raise ValueError("Année hors limites")
        return v


class WorkforceStatCreate(WorkforceStatBase):
    pass


class WorkforceStatUpdate(BaseModel):
    male_count: Optional[int] = Field(None, ge=0)
    female_count: Optional[int] = Field(None, ge=0)


class WorkforceStatRead(WorkforceStatBase):
    id: int
    organization_id: int
    total: int
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
