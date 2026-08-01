from pydantic import BaseModel
from datetime import datetime


class SectionSchema(BaseModel):
    id: int | None = None
    position: int
    title: str
    visibility: str = "interne"
    content: str  # base64-encoded for JSON transport (plaintext or ciphertext)
    nonce: str | None = None  # base64-encoded 12-byte AES-GCM nonce (set iff encrypted)

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


class PreviewSectionSchema(BaseModel):
    """Section destinée à la direction : pas d'id.

    `visibility` est présent et vaut toujours "partage". Ce n'est pas une
    redondance : l'export PDF côté client refuse de rendre toute section qui
    ne porte pas explicitement cette marque (fail-closed). Si la projection
    régressait un jour, le PDF ne partirait pas avec du contenu interne.
    """
    position: int
    title: str
    content: str  # base64-encoded (ciphertext if vault is enabled)
    visibility: str = "partage"
    nonce: str | None = None  # base64-encoded 12-byte nonce, set iff encrypted

    model_config = {"from_attributes": True}


class DirectionPreviewResponse(BaseModel):
    minute_id: int
    meeting_title: str | None = None
    validated_by_name: str | None = None
    validated_at: datetime | None = None
    sections: list[PreviewSectionSchema]
    generated_at: datetime


class PublishRequest(BaseModel):
    pdf_sha256: str  # hex-encoded SHA-256 of the PDF generated client-side


class PublicationHistorySchema(BaseModel):
    id: int
    published_by_name: str | None = None
    published_at: datetime
    pdf_sha256: str
    sections_count: int

    model_config = {"from_attributes": True}


class MinuteDetailResponse(MinuteResponse):
    publications: list[PublicationHistorySchema] = []
