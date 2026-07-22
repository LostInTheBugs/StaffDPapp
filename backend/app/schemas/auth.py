from pydantic import BaseModel, EmailStr


# ── CAPTCHA ───────────────────────────────────────────────────────

class CaptchaResponse(BaseModel):
    challenge_id: str
    question: str


# ── Auth / Register ───────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    captcha_id: str | None = None
    captcha_answer: str | None = None


class MfaLoginRequest(BaseModel):
    mfa_token: str
    totp_code: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    invitation_code: str
    captcha_id: str | None = None
    captcha_answer: str | None = None


class CreateOrganizationRequest(BaseModel):
    organization_name: str
    company_name: str | None = None
    employee_count: int
    admin_email: EmailStr
    admin_password: str
    admin_first_name: str
    admin_last_name: str
    captcha_id: str | None = None
    captcha_answer: str | None = None


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
    required_titulaires: int

    model_config = {"from_attributes": True}


class DashboardResponse(BaseModel):
    user: UserResponse
    organization: OrganizationResponse


class InvitationResponse(BaseModel):
    code: str
    email: str
    first_name: str
    last_name: str
    delegue_status: str
    delegue_role: str
    is_delegue_securite_sante: bool = False
    is_delegue_egalite: bool = False
    organization_name: str | None = None

    model_config = {"from_attributes": True}
