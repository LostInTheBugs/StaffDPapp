from datetime import datetime, timezone
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import hash_password, create_access_token, generate_invitation_code
from app.core.captcha import validate_captcha
from app.models import User, UserRole, Organization, Invitation, DelegueStatus, DelegueRole
from app.schemas.auth import (
    RegisterRequest,
    CreateOrganizationRequest,
    CreateInvitationRequest,
    UpdateOrganizationRequest,
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
        "delegue_status": inv.delegue_status.value if inv.delegue_status else "titulaire",
        "delegue_role": inv.delegue_role.value if inv.delegue_role else "membre",
        "is_delegue_securite_sante": inv.is_delegue_securite_sante,
        "is_delegue_egalite": inv.is_delegue_egalite,
        "organization_name": inv.organization.name if inv.organization else None,
    }


@router.post("/organizations", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def create_organization(body: CreateOrganizationRequest, db: Session = Depends(get_db)):
    # CAPTCHA
    if body.captcha_id and body.captcha_answer:
        if not validate_captcha(body.captcha_id, body.captcha_answer):
            raise HTTPException(status_code=400, detail="CAPTCHA invalide")

    if body.employee_count < 15:
        raise HTTPException(status_code=400, detail="L'effectif minimum est de 15 salariés")
    if db.query(User).filter(User.email == body.admin_email).first():
        raise HTTPException(status_code=409, detail="Cet email existe déjà")

    base_slug = _make_slug(body.organization_name)
    slug = base_slug
    counter = 1
    while db.query(Organization).filter(Organization.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    org = Organization(
        name=body.organization_name, slug=slug,
        company_name=body.company_name, employee_count=body.employee_count, country="LU",
    )
    db.add(org)
    db.flush()

    admin = User(
        email=body.admin_email,
        password_hash=hash_password(body.admin_password),
        first_name=body.admin_first_name,
        last_name=body.admin_last_name,
        delegue_status=DelegueStatus(body.admin_delegue_status),
        delegue_role=DelegueRole(body.admin_delegue_role),
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
    # CAPTCHA
    if body.captcha_id and body.captcha_answer:
        if not validate_captcha(body.captcha_id, body.captcha_answer):
            raise HTTPException(status_code=400, detail="CAPTCHA invalide")

    invitation = (
        db.query(Invitation)
        .filter(Invitation.code == body.invitation_code.upper(), Invitation.is_used == False)
        .first()
    )
    if not invitation:
        raise HTTPException(status_code=400, detail="Code d'invitation invalide ou déjà utilisé")
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=409, detail="Cet email existe déjà")

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        first_name=body.first_name,
        last_name=body.last_name,
        delegue_status=invitation.delegue_status,
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
        raise HTTPException(status_code=403, detail="Réservé aux administrateurs")

    valid_statuses = [s.value for s in DelegueStatus]
    if body.delegue_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Statut invalide : {', '.join(valid_statuses)}")

    valid_roles = [r.value for r in DelegueRole]
    if body.delegue_role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Rôle invalide : {', '.join(valid_roles)}")

    # Règle : égalité → doit être un élu (titulaire ou suppléant)
    if body.is_delegue_egalite and body.delegue_status == DelegueStatus.employe.value:
        raise HTTPException(status_code=400, detail="Le délégué à l'égalité doit être titulaire ou suppléant")

    # Règle : employé (non-élu) → obligatoirement délégué sécurité/santé
    if body.delegue_status == DelegueStatus.employe.value and not body.is_delegue_securite_sante:
        raise HTTPException(status_code=400, detail="Un salarié non-élu doit être désigné délégué à la sécurité et à la santé")

    # Règle : employé (non-élu) → pas de fonction au bureau
    if body.delegue_status == DelegueStatus.employe.value and body.delegue_role != DelegueRole.membre.value:
        raise HTTPException(status_code=400, detail="Un salarié non-élu n'a pas de fonction au bureau")

    code = generate_invitation_code()
    while db.query(Invitation).filter(Invitation.code == code).first():
        code = generate_invitation_code()

    invitation = Invitation(
        code=code,
        email=body.email,
        first_name=body.first_name,
        last_name=body.last_name,
        delegue_status=DelegueStatus(body.delegue_status),
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


@router.put("/organization", response_model=OrganizationResponse)
def update_organization(
    body: UpdateOrganizationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Réservé aux administrateurs")

    org = current_user.organization
    if body.name is not None:
        org.name = body.name
        org.slug = _make_slug(body.name)
        counter = 1
        base = org.slug
        while db.query(Organization).filter(Organization.slug == org.slug, Organization.id != org.id).first():
            org.slug = f"{base}-{counter}"
            counter += 1
    if body.company_name is not None:
        org.company_name = body.company_name
    if body.employee_count is not None:
        if body.employee_count < 15:
            raise HTTPException(status_code=400, detail="L'effectif minimum est de 15 salariés")
        org.employee_count = body.employee_count
    if body.mandate_end_date is not None:
        from datetime import datetime
        org.mandate_end_date = datetime.fromisoformat(body.mandate_end_date.replace("Z", "+00:00"))

    db.commit()
    db.refresh(org)
    return OrganizationResponse.model_validate(org)


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
        raise HTTPException(status_code=403)
    invitations = (
        db.query(Invitation)
        .filter(Invitation.organization_id == current_user.organization_id, Invitation.is_used == False)
        .all()
    )
    return [InvitationResponse(**_invitation_to_response(inv)) for inv in invitations]


@router.get("/organization/members", response_model=list[UserResponse])
def list_members(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    members = (
        db.query(User)
        .filter(User.organization_id == current_user.organization_id, User.is_active == True)
        .all()
    )
    return [UserResponse.model_validate(m) for m in members]
