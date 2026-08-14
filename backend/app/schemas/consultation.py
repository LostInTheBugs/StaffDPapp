from pydantic import BaseModel, Field
from typing import Optional

from app.models.consultation import ConsultationCategory


class ConsultationCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=300)
    category: ConsultationCategory
    description: Optional[str] = None
    # Date limite de réponse de l'employeur (facultatif — défaut légal selon la
    # catégorie si non fourni, voir DEFAULT_RESPONSE_DAYS)
    response_due: Optional[str] = None


class ConsultationUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=300)
    category: Optional[ConsultationCategory] = None
    description: Optional[str] = None
    response_due: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(requested|response_received|closed)$")
    direction_response: Optional[str] = None


class ConsultationResponse(BaseModel):
    id: int
    title: str
    category: str
    description: Optional[str] = None
    status: str
    requested_at: Optional[str] = None
    response_due: Optional[str] = None
    direction_responded_at: Optional[str] = None
    direction_response: Optional[str] = None
    created_by_name: Optional[str] = None

    model_config = {"from_attributes": True}


class ConsultationStats(BaseModel):
    total: int
    pending: int          # requested (en attente de réponse)
    overdue: int          # requested avec response_due dépassée
    received: int         # response_received
    closed: int
