from datetime import datetime, timezone
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import hash_password, create_access_token, generate_invitation_code
from app.models import User, UserRole, Organization, Invitation
from app.schemas.auth import (
    RegisterRequest,
    CreateOrganizationRequest,
    CreateInvitationRequest,
    TokenResponse,
    DashboardResponse,
    InvitationResponse,
    OrganizationResponse,
)

router = APIRouter(prefix="/api", tags=["organization"])


def _make_slug(name: str) -> str:
    """Create a URL-safe slug from an organization name."""
    s = name.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[-\s]+", "-", s)
    return s.strip("-") or "org"


@router.post("/organizations", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def create_organization(body: CreateOrganizationRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.admin_email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un compte avec cet email existe déjà",
        )

    base_slug = _make_slug(body.organization_name)
    slug = base_slug
    counter = 1
    while db.query(Organization).filter(Organization.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    org = Organization(
        name=body.organization_name,
        slug=slug,
        company_name=body.company_name,
        country="LU",
    )
    db.add(org)
    db.flush()

    admin = User(
        email=body.admin_email,
        password_hash=hash_password(body.admin_password),
        full_name=body.admin_full_name,
        role=UserRole.admin,
        organization_id=org.id,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    token = create_access_token(data={"sub": str(admin.id), "org_id": org.id})
    return TokenResponse(access_token=token)


@router.post("/join", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def join_organization(body: RegisterRequest, db: Session = Depends(get_db)):
    invitation = (
        db.query(Invitation)
        .filter(Invitation.code == body.invitation_code.upper(), Invitation.is_used == False)
        .first()
    )
    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Code d'invitation invalide ou déjà utilisé",
        )

    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un compte avec cet email existe déjà",
        )

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        role=UserRole.member,
        organization_id=invitation.organization_id,
    )
    db.add(user)

    invitation.is_used = True
    invitation.used_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(user)

    token = create_access_token(data={"sub": str(user.id), "org_id": user.organization_id})
    return TokenResponse(access_token=token)


@router.post("/invitations", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
def create_invitation(
    body: CreateInvitationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seul un administrateur peut créer des invitations",
        )

    code = generate_invitation_code()
    while db.query(Invitation).filter(Invitation.code == code).first():
        code = generate_invitation_code()

    invitation = Invitation(
        code=code,
        created_by_id=current_user.id,
        organization_id=current_user.organization_id,
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)

    return InvitationResponse(
        code=invitation.code,
        organization_name=current_user.organization.name,
    )


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(current_user: User = Depends(get_current_user)):
    return DashboardResponse(
        user=current_user,
        organization=current_user.organization,
    )


@router.get("/invitations", response_model=list[InvitationResponse])
def list_invitations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    invitations = (
        db.query(Invitation)
        .filter(
            Invitation.organization_id == current_user.organization_id,
            Invitation.is_used == False,
        )
        .all()
    )
    return [
        InvitationResponse(code=inv.code, organization_name=current_user.organization.name)
        for inv in invitations
    ]
