from pydantic import BaseModel, EmailStr


# ── Request schemas ──────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    invitation_code: str


class CreateOrganizationRequest(BaseModel):
    organization_name: str          # nom affiché
    company_name: str | None = None # nom officiel entreprise
    admin_email: EmailStr
    admin_password: str
    admin_full_name: str


class CreateInvitationRequest(BaseModel):
    pass  # pas de champs nécessaires, le code est généré


# ── Response schemas ──────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str

    model_config = {"from_attributes": True}


class OrganizationResponse(BaseModel):
    id: int
    name: str
    slug: str
    company_name: str | None
    country: str

    model_config = {"from_attributes": True}


class DashboardResponse(BaseModel):
    user: UserResponse
    organization: OrganizationResponse


class InvitationResponse(BaseModel):
    code: str
    organization_name: str

    model_config = {"from_attributes": True}
