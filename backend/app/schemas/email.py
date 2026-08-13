from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class EmailConfigResponse(BaseModel):
    enabled: bool
    transport_mode: str
    from_name: Optional[str] = None
    from_email: Optional[str] = None
    reply_to: Optional[str] = None
    signature: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: int
    smtp_user: Optional[str] = None
    has_smtp_password: bool
    smtp_use_tls: bool
    smtp_use_ssl: bool
    direction_email: Optional[str] = None
    remind_days_before: int


class EmailConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    transport_mode: Optional[str] = Field(None, pattern="^(eml|smtp|external)$")
    from_name: Optional[str] = None
    from_email: Optional[EmailStr] = None
    reply_to: Optional[EmailStr] = None
    signature: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = Field(None, ge=1, le=65535)
    smtp_user: Optional[str] = None
    # Vide (ou absent) = ne pas changer ; non vide = nouveau mot de passe
    smtp_password: Optional[str] = None
    smtp_use_tls: Optional[bool] = None
    smtp_use_ssl: Optional[bool] = None
    direction_email: Optional[EmailStr] = None
    remind_days_before: Optional[int] = Field(None, ge=0, le=30)


class EmailTestRequest(BaseModel):
    recipient: EmailStr


class EmailOutboxResponse(BaseModel):
    id: int
    event_type: str
    transport: str
    recipient_name: Optional[str] = None
    recipient_email: str
    lang: str
    subject: str
    status: str
    attempts: int
    last_error: Optional[str] = None
    has_eml: bool
    exported_at: Optional[str] = None
    created_at: Optional[str] = None
    sent_at: Optional[str] = None
    payload: Optional[dict] = None


class ShareLinkCreate(BaseModel):
    # Enveloppe JSON générée côté client : {"algo":"argon2id","salt":b64,"nonce":b64,"wrapped":b64}
    # Le code de lecture n'est JAMAIS transmis au serveur (sinon il pourrait
    # déchiffrer) — il est affiché une fois au créateur, qui le transmet à la
    # direction par un canal séparé.
    envelope: str = Field(min_length=10)
    expires_days: Optional[int] = Field(default=14, ge=1, le=90)


class ShareLinkCreateResponse(BaseModel):
    token: str
    share_url: str
    expires_at: Optional[str] = None


class ShareLinkInfo(BaseModel):
    token: str
    org_name: str
    minute_title: str
    meeting_title: str
    meeting_date: Optional[str] = None
    expires_at: Optional[str] = None
    revoked: bool
    valid: bool


class ShareLinkContent(BaseModel):
    token: str
    minute_title: str
    meeting_title: str
    meeting_date: Optional[str] = None
    org_name: str
    # Enveloppe (DEK chiffrée sous le code de lecture) — le code n'est
    # jamais transmis ; sans lui l'enveloppe est inutilisable.
    envelope: str
    sections: list[dict]
