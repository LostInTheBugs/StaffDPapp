from pydantic import BaseModel
from datetime import datetime


class SectionSchema(BaseModel):
    id: int | None = None
    position: int
    title: str
    visibility: str = "interne"
    content: str  # base64-encoded for JSON transport

    model_config = {"from_attributes": True}


class MinuteResponse(BaseModel):
    id: int
    meeting_id: int
    status: str
    is_encrypted: bool = False
    created_by_id: int
    created_by_name: str | None = None
    validated_by_id: int | None = None
    validated_by_name: str | None = None
    validated_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    sections: list[SectionSchema] = []

    model_config = {"from_attributes": True}


class CreateMinuteRequest(BaseModel):
    sections: list[SectionSchema]


class UpdateSectionsRequest(BaseModel):
    sections: list[SectionSchema]


class DirectionPreviewResponse(BaseModel):
    minute_id: int
    meeting_title: str | None = None
    validated_by_name: str | None = None
    validated_at: datetime | None = None
    sections: list[SectionSchema]
    generated_at: datetime
