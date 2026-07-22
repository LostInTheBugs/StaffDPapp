from datetime import datetime, timezone
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import hash_password, create_access_token, generate_invitation_code
from app.models import User, UserRole, Organization, Invitation, DelegueRole
from app.schemas.auth import (
    RegisterRequest,
    CreateOrganizationRequest,
    CreateInvitationRequest,
    TokenResponse,
    DashboardResponse,
    InvitationResponse,
    OrganizationResponse,
    UserResponse,
)

router = APIRouter(prefix="/api", tags=["organization"])


def _make_slug(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[-\s]+", "-", s)
    return s.strip("-") or "org"


def _invitation_to_response(inv: Invitation) -> dict:
    return {
        "code": inv.code,
        "email": inv.email,
        "first_name": inv.first_name,
        "last_name": inv.last_name,
        "delegue_role": inv.delegue_role.value if inv.delegue_role else "titulaire",
        "is_delegue_securite_sante": inv.is_delegue_securite_sante,
        "is_delegue_egalite": inv.is_delegue_egalite,
        "organization_name": inv.organization.name if inv.organization else None,
    }


@router.post("/organizations", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def create_organization(body: CreateOrganizationRequest, db: Session = Depends(get_db)):
    if body.employee_count < 15:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="L'effectif minimum est de 15 salariés pour constituer une délégation",
        )
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
        employee_count=body.employee_count,
        country="LU",
    )
    db.add(org)
    db.flush()

    admin = User(
        email=body.admin_email,
        password_hash=hash_password(body.admin_password),
        first_name=body.admin_first_name,
        last_name=body.admin_last_name,
        delegue_role=DelegueRole.president,
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
        first_name=body.first_name,
        last_name=body.last_name,
        delegue_role=invitation.delegue_role,
        role=UserRole.member,
        organization_id=invitation.organization_id,
        is_delegue_securite_sante=invitation.is_delegue_securite_sante,
        is_delegue_egalite=invitation.is_delegue_egalite,
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

    valid_roles = [r.value for r in DelegueRole]
    if body.delegue_role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Rôle invalide. Valeurs possibles : {', '.join(valid_roles)}",
        )

    # Cohérence : égalité doit être un membre de la délégation
    if body.is_delegue_egalite and body.delegue_role == DelegueRole.employe.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le délégué à l'égalité doit être un membre élu de la délégation (titulaire ou suppléant)",
        )

    code = generate_invitation_code()
    while db.query(Invitation).filter(Invitation.code == code).first():
        code = generate_invitation_code()

    invitation = Invitation(
        code=code,
        email=body.email,
        first_name=body.first_name,
        last_name=body.last_name,
        delegue_role=DelegueRole(body.delegue_role),
        is_delegue_securite_sante=body.is_delegue_securite_sante,
        is_delegue_egalite=body.is_delegue_egalite,
        created_by_id=current_user.id,
        organization_id=current_user.organization_id,
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)

    return InvitationResponse(**_invitation_to_response(invitation))


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(current_user: User = Depends(get_current_user)):
    return DashboardResponse(
        user=UserResponse.model_validate(current_user),
        organization=OrganizationResponse.model_validate(current_user.organization),
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
    return [InvitationResponse(**_invitation_to_response(inv)) for inv in invitations]
