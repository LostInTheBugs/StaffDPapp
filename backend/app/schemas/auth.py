from pydantic import BaseModel, EmailStr, Field, field_validator


# ── CAPTCHA ───────────────────────────────────────────────────────

class CaptchaResponse(BaseModel):
    challenge_id: str
    question: str


# ── Mots de passe ─────────────────────────────────────────────────

# bcrypt tronque silencieusement à 72 OCTETS (pas caractères) : tout mot de
# passe plus long serait stocké tronqué et deviendrait invalide. La limite
# est appliquée ici (validation Pydantic) ET dans la route de changement.
BCRYPT_MAX_BYTES = 72


def _bcrypt_length_limit(v: str) -> str:
    if len(v.encode("utf-8")) > BCRYPT_MAX_BYTES:
        raise ValueError("Mot de passe trop long (72 octets maximum)")
    return v


# ── Auth / Register ───────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    captcha_id: str
    captcha_answer: str


class MfaLoginRequest(BaseModel):
    mfa_token: str
    totp_code: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, description="Au moins 8 caractères")
    first_name: str
    last_name: str
    invitation_code: str
    captcha_id: str
    captcha_answer: str
    # Optional vault envelope: if the org has a vault, the client unwraps the
    # DEK with the invitation code, re-wraps it under the user's password,
    # and sends this envelope. The server stores it and deletes the old
    # invitation envelope.
    vault_envelope: dict | None = None  # {wrapped_dek, nonce, kdf_salt, kdf_params}

    @field_validator("password")
    @classmethod
    def _password_max_bytes(cls, v: str) -> str:
        return _bcrypt_length_limit(v)


class CreateOrganizationRequest(BaseModel):
    organization_name: str
    company_name: str | None = None
    employee_count: int
    admin_email: EmailStr
    admin_password: str = Field(min_length=8, description="Au moins 8 caractères")
    admin_first_name: str
    admin_last_name: str
    admin_delegue_status: str = "titulaire"
    admin_delegue_role: str = "president"
    captcha_id: str
    captcha_answer: str

    @field_validator("admin_password")
    @classmethod
    def _admin_password_max_bytes(cls, v: str) -> str:
        return _bcrypt_length_limit(v)


# ── MFA ───────────────────────────────────────────────────────────

class MfaSetupResponse(BaseModel):
    secret: str
    qr_code_b64: str
    uri: str


class MfaVerifyRequest(BaseModel):
    totp_code: str


class MfaDisableRequest(BaseModel):
    password: str


# ── Invitation ────────────────────────────────────────────────────

class CreateInvitationRequest(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    delegue_status: str = "titulaire"
    delegue_role: str = "membre"
    is_delegue_securite_sante: bool = False
    is_delegue_egalite: bool = False
    # Optional vault envelope: if the org has a vault, the inviting member
    # (who holds the DEK) wraps it under a KEK derived from the invitation
    # code and sends this envelope. The server stores it in vault_keys
    # with invitation_id set (user_id NULL), so the invitee can unwrap
    # the DEK during /join.
    vault_envelope: dict | None = None  # {wrapped_dek, nonce, kdf_salt, kdf_params}


# ── Organization update ────────────────────────────────────────────

class UpdateOrganizationRequest(BaseModel):
    name: str | None = None
    company_name: str | None = None
    employee_count: int | None = None
    mandate_end_date: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    contact_hours: str | None = None


# ── Response schemas ──────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    mfa_required: bool = False
    mfa_token: str | None = None


class UserResponse(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    full_name: str
    avatar_url: str | None = None
    language: str = "fr"
    delegue_status: str
    delegue_role: str
    role: str
    totp_enabled: bool = False
    is_delegue_securite_sante: bool = False
    is_delegue_egalite: bool = False

    model_config = {"from_attributes": True}


class OrganizationResponse(BaseModel):
    id: int
    name: str
    slug: str
    company_name: str | None
    country: str
    employee_count: int
    mandate_end_date: str | None = None
    required_titulaires: int
    weekly_credit_hours: float | None = None
    enabled_modules: list[str] = Field(default_factory=list)
    logo_data: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    contact_hours: str | None = None

    model_config = {"from_attributes": True}

    @field_validator("enabled_modules", mode="before")
    @classmethod
    def _resolve_modules(cls, v):
        from app.core.modules import enabled_modules_of, ALL_MODULES
        active = enabled_modules_of(v)
        return [m for m in ALL_MODULES if m in active]


class DashboardResponse(BaseModel):
    user: UserResponse
    organization: OrganizationResponse


class InvitationResponse(BaseModel):
    """Invitation as listed in the admin panel.

    The code is NOT included — it was shown once at creation and the server
    only stores an Argon2id hash. Admins identify invitations by email+name.
    """
    id: int
    email: str
    first_name: str
    last_name: str
    delegue_status: str
    delegue_role: str
    is_delegue_securite_sante: bool = False
    is_delegue_egalite: bool = False
    is_used: bool = False
    created_at: str | None = None
    organization_name: str | None = None

    model_config = {"from_attributes": True}


class CreateInvitationResponse(InvitationResponse):
    """Returned on invitation creation — includes the ONE-TIME plaintext code.

    The code MUST be displayed immediately and never available again.
    """
    code: str  # plaintext, 26 characters (Crockford base32)


# ── Batch invitations ──────────────────────────────────────────────

class BatchInviteItem(BaseModel):
    """One line of a mass invitation import (plain employee by default)."""
    email: EmailStr
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)


class BatchInviteRequest(BaseModel):
    """Raw dicts on purpose — each line is validated individually in the
    route so one malformed line never kills the whole batch (per-line
    results instead of a global 422)."""
    invitations: list[dict]

    @field_validator("invitations")
    @classmethod
    def _cap_batch_size(cls, v: list[dict]) -> list[dict]:
        if len(v) > 200:
            raise ValueError("Maximum 200 invitations par lot")
        return v


class BatchInviteResult(BaseModel):
    email: str
    first_name: str | None = None
    last_name: str | None = None
    status: str  # created | duplicate | invalid
    message: str | None = None
    # Present ONLY for created invitations (includes the one-time code)
    invitation: CreateInvitationResponse | None = None


class BatchInviteResponse(BaseModel):
    results: list[BatchInviteResult]
    created: int
    skipped: int
    failed: int
