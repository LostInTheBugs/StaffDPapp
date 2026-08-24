from datetime import datetime, timedelta, timezone
import base64
import json
import re

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import (
    hash_password, create_access_token,
    generate_invitation_code, hash_invitation_code, hash_invitation_code_batch,
    verify_invitation_code,
    normalize_invitation_code, normalize_email,
)
from app.core.captcha import validate_captcha
from app.core.ratelimit import check_rate_limit, client_ip
from app.models import User, UserRole, Organization, Invitation, DelegueStatus, DelegueRole
from app.models.vault_key import VaultKey
from app.schemas.auth import (
    RegisterRequest,
    CreateOrganizationRequest,
    CreateInvitationRequest,
    UpdateOrganizationRequest,
    TokenResponse,
    DashboardResponse,
    InvitationResponse,
    CreateInvitationResponse,
    OrganizationResponse,
    UserResponse,
    BatchInviteItem,
    BatchInviteRequest,
    BatchInviteResponse,
)

router = APIRouter(prefix="/api", tags=["organization"])


def _make_slug(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[-\s]+", "-", s)
    return s.strip("-") or "org"


def _invitation_to_response(inv: Invitation) -> dict:
    return {
        "id": inv.id,
        "email": inv.email,
        "first_name": inv.first_name,
        "last_name": inv.last_name,
        "delegue_status": inv.delegue_status.value if inv.delegue_status else "titulaire",
        "delegue_role": inv.delegue_role.value if inv.delegue_role else "membre",
        "is_delegue_securite_sante": inv.is_delegue_securite_sante,
        "is_delegue_egalite": inv.is_delegue_egalite,
        "is_used": inv.is_used,
        "created_at": inv.created_at.isoformat() if inv.created_at else None,
        "organization_name": inv.organization.name if inv.organization else None,
    }


@router.post("/organizations", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def create_organization(body: CreateOrganizationRequest, request: Request, db: Session = Depends(get_db)):
    # Anti-spam : 5 créations / 1h / IP
    check_rate_limit(f"org:{client_ip(request)}", 5, 3600)
    # CAPTCHA
    if not validate_captcha(body.captcha_id, body.captcha_answer):
        raise HTTPException(status_code=400, detail="CAPTCHA invalide")

    if body.employee_count < 15:
        raise HTTPException(status_code=400, detail="L'effectif minimum est de 15 salariés")
    if db.query(User).filter(User.email == normalize_email(body.admin_email)).first():
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
        email=normalize_email(body.admin_email),
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

    token = create_access_token(data={"sub": str(admin.id), "org_id": org.id, "typ": "access", "ver": admin.token_version or 0})
    return TokenResponse(access_token=token)


@router.post("/join", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def join_organization(body: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    # Anti brute-force : 10 tentatives / 15 min / IP
    check_rate_limit(f"join:{client_ip(request)}", 10, 900)
    # CAPTCHA
    if not validate_captcha(body.captcha_id, body.captcha_answer):
        raise HTTPException(status_code=400, detail="CAPTCHA invalide")

    # The invitation code is hashed with Argon2id — we cannot do an equality
    # lookup. Instead, iterate over all unused invitations for this email, and
    # verify the hash one by one. This is acceptable: invitation tables are small
    # (tens of rows per org), and Argon2id verification is engineered to be
    # moderately expensive (memory-hard) to resist brute-forcing.
    normalized_email = normalize_email(body.email)
    candidates = (
        db.query(Invitation)
        .filter(
            Invitation.is_used == False,
            Invitation.email == normalized_email,
            # Expiration : 30 jours après création (NULL = anciennes, jamais expirées)
            or_(Invitation.expires_at.is_(None), Invitation.expires_at > datetime.now()),
        )
        .all()
    )

    invitation = None
    for inv in candidates:
        if verify_invitation_code(body.invitation_code, inv.code_hash):
            invitation = inv
            break

    if not invitation:
        raise HTTPException(status_code=400, detail="Code d'invitation invalide, expiré ou déjà utilisé")
    if db.query(User).filter(User.email == normalized_email).first():
        raise HTTPException(status_code=409, detail="Cet email existe déjà")

    user = User(
        email=normalized_email,
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
    db.flush()  # get user.id before commit

    # Vault envelope exchange: if the org has a vault and the client sent a
    # re-wrapped envelope, delete the old invitation-key envelope and store
    # the user's envelope.
    if body.vault_envelope:
        _handle_join_vault_envelope(db, body.vault_envelope, invitation, user)

    invitation.is_used = True
    invitation.used_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    token = create_access_token(data={"sub": str(user.id), "org_id": user.organization_id, "typ": "access", "ver": user.token_version or 0})
    return TokenResponse(access_token=token)


@router.post("/invitations", response_model=CreateInvitationResponse, status_code=status.HTTP_201_CREATED)
def create_invitation(
    body: CreateInvitationRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Réservé aux administrateurs")

    _validate_invitation_fields(body.delegue_status, body.delegue_role,
                                body.is_delegue_securite_sante, body.is_delegue_egalite)

    invitation, plaintext_code = _build_invitation(
        db, current_user, body.email, body.first_name, body.last_name,
        body.delegue_status, body.delegue_role,
        body.is_delegue_securite_sante, body.is_delegue_egalite,
        hash_fn=hash_invitation_code,
    )
    db.flush()  # get invitation.id

    # Vault invitation envelope: if the org has a vault and the inviter
    # (who holds the DEK) sent an envelope wrapped under the invitation code,
    # store it in vault_keys with invitation_id set.
    if body.vault_envelope:
        _store_invitation_vault_envelope(
            db, body.vault_envelope, invitation, current_user
        )

    db.commit()
    db.refresh(invitation)

    # ── Déclencheur : email d'invitation avec le code (une seule fois) ──
    _queue_invite_email(db, request, background_tasks, invitation, plaintext_code)

    result = dict(_invitation_to_response(invitation))
    result["code"] = plaintext_code  # ONE-TIME only
    return result


def _validate_invitation_fields(
    delegue_status: str, delegue_role: str,
    is_delegue_securite_sante: bool, is_delegue_egalite: bool,
) -> None:
    """Règles légales communes (invitation simple ET invitation en masse).

    Depuis le chantier « invitation en masse » (2026-08-19), un salarié
    non-élu (delegue_status=employe) PEUT être invité sans désignation
    sécurité/santé : ce sont les comptes « employés » (répondre aux enquêtes,
    consulter les informations de la délégation). Les règles conservées :
    égalité → élu ; non-élu → pas de fonction au bureau.
    """
    valid_statuses = [s.value for s in DelegueStatus]
    if delegue_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Statut invalide : {', '.join(valid_statuses)}")

    valid_roles = [r.value for r in DelegueRole]
    if delegue_role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Rôle invalide : {', '.join(valid_roles)}")

    # Règle : égalité → doit être un élu (titulaire ou suppléant)
    if is_delegue_egalite and delegue_status == DelegueStatus.employe.value:
        raise HTTPException(status_code=400, detail="Le délégué à l'égalité doit être titulaire ou suppléant")

    # Règle : employé (non-élu) → pas de fonction au bureau
    if delegue_status == DelegueStatus.employe.value and delegue_role != DelegueRole.membre.value:
        raise HTTPException(status_code=400, detail="Un salarié non-élu n'a pas de fonction au bureau")


def _build_invitation(
    db: Session, current_user: User,
    email: str, first_name: str, last_name: str,
    delegue_status: str, delegue_role: str,
    is_delegue_securite_sante: bool, is_delegue_egalite: bool,
    hash_fn=hash_invitation_code,
) -> tuple[Invitation, str]:
    """Create the Invitation row + plaintext code (shown once).

    `hash_fn` lets the batch endpoint use the lighter Argon2id params —
    the code entropy (~130 bits) makes brute force infeasible either way.
    """
    plaintext_code = generate_invitation_code()
    code_hash = hash_fn(plaintext_code)

    invitation = Invitation(
        code_hash=code_hash,
        email=normalize_email(email),
        first_name=first_name,
        last_name=last_name,
        delegue_status=DelegueStatus(delegue_status),
        delegue_role=DelegueRole(delegue_role),
        is_delegue_securite_sante=is_delegue_securite_sante,
        is_delegue_egalite=is_delegue_egalite,
        created_by_id=current_user.id,
        organization_id=current_user.organization_id,
        expires_at=datetime.now() + timedelta(days=30),
    )
    db.add(invitation)
    return invitation, plaintext_code


@router.post("/invitations/batch", response_model=BatchInviteResponse)
def create_invitations_batch(
    body: BatchInviteRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Invitation en masse (admin) : chaque ligne est validée séparément —
    une ligne invalide ne fait jamais échouer le lot. Les invités en masse
    sont des salariés non-élus (delegue_status=employe, rôle membre) —
    ils pourront rejoindre avec leur code et répondre aux enquêtes.

    Les enveloppes de coffre (vault) ne sont PAS attachées : l'accès au
    coffre des PV reste réservé aux invitations individuelles (bureau).
    """
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Réservé aux administrateurs")

    results: list[dict] = []
    created = skipped = failed = 0
    seen_emails: set[str] = set()
    now = datetime.now()

    for raw in body.invitations:
        try:
            item = BatchInviteItem.model_validate(raw)
        except ValidationError:
            email_raw = str(raw.get("email", "")).strip() if isinstance(raw, dict) else ""
            results.append({
                "email": email_raw or "(ligne invalide)",
                "status": "invalid",
                "message": "Format invalide : il faut email, prénom et nom (une ligne par personne, séparés par des points-virgules)",
            })
            failed += 1
            continue

        email = normalize_email(item.email)
        first_name = item.first_name.strip()
        last_name = item.last_name.strip()

        # Doublon dans le même lot
        if email in seen_emails:
            results.append({"email": email, "status": "duplicate", "message": "Doublon dans le lot"})
            skipped += 1
            continue
        seen_emails.add(email)

        # Compte existant (email unique globalement — déjà membre d'une org)
        if db.query(User).filter(User.email == email).first() is not None:
            results.append({"email": email, "status": "duplicate", "message": "Un compte existe déjà avec cet email"})
            skipped += 1
            continue

        # Invitation en attente pour ce même email (même org)
        pending = db.query(Invitation).filter(
            Invitation.organization_id == current_user.organization_id,
            Invitation.email == email,
            Invitation.is_used == False,  # noqa: E712
        ).first()
        if pending is not None and (pending.expires_at is None or pending.expires_at > now):
            results.append({"email": email, "status": "duplicate", "message": "Invitation déjà envoyée pour cet email"})
            skipped += 1
            continue

        invitation, plaintext_code = _build_invitation(
            db, current_user, email, first_name, last_name,
            DelegueStatus.employe.value, DelegueRole.membre.value,
            False, False,
            hash_fn=hash_invitation_code_batch,
        )
        db.flush()  # get invitation.id
        _queue_invite_email(db, request, background_tasks, invitation, plaintext_code)

        inv_dict = dict(_invitation_to_response(invitation))
        inv_dict["code"] = plaintext_code  # ONE-TIME only
        results.append({
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "status": "created",
            "invitation": inv_dict,
        })
        created += 1

    db.commit()
    return {"results": results, "created": created, "skipped": skipped, "failed": failed}


@router.delete("/organization/members/{user_id}")
def remove_member(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retirer un membre (admin) — suppression DOUCE : is_active=False.

    Le compte reste en base (les références historiques — PV, heures,
    réunions — restent valides), mais le login et l'API sont bloqués et le
    membre disparaît des listes. C'est le pattern is_active déjà en place.
    """
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Réservé aux administrateurs")

    target = db.query(User).filter(
        User.id == user_id,
        User.organization_id == current_user.organization_id,
    ).first()
    if target is None:
        raise HTTPException(status_code=404, detail="Membre introuvable")
    if target.id == current_user.id:
        raise HTTPException(status_code=400, detail="Impossible de retirer votre propre compte")
    if not target.is_active:
        return {"id": target.id, "removed": False}

    # Garde défensive : ne jamais laisser l'org sans administrateur
    if target.role == UserRole.admin:
        admin_count = db.query(User).filter(
            User.organization_id == current_user.organization_id,
            User.role == UserRole.admin,
            User.is_active == True,  # noqa: E712
        ).count()
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="Impossible de retirer le dernier administrateur de l'organisation")

    target.is_active = False
    # Révocation immédiate de tous les jetons du membre retiré (T9) :
    # sans ça, un jeton déjà émis restait valable jusqu'à expiration (24 h).
    target.token_version = (target.token_version or 0) + 1
    db.commit()
    return {"id": target.id, "removed": True}


def _queue_invite_email(
    db: Session, request: Request, background_tasks: BackgroundTasks,
    invitation: Invitation, plaintext_code: str,
) -> None:
    """Email d'invitation avec le code — silencieux si notifications désactivées."""
    from app.models.email import EmailConfig, EmailEventType, TransportMode
    from app.services.email_service import queue_email, send_ready_smtp

    cfg = db.query(EmailConfig).filter(EmailConfig.organization_id == invitation.organization_id).first()
    if cfg is None or not cfg.enabled:
        return
    recipient_name = f"{invitation.first_name} {invitation.last_name}".strip()
    ctx = {
        "base_url": str(request.base_url),
        "recipient_name": recipient_name,
        "invite_code": plaintext_code,
    }
    queue_email(db, invitation.organization_id, EmailEventType.member_invite.value,
                recipient_name, invitation.email, "fr", ctx)
    if cfg.transport_mode == TransportMode.smtp:
        background_tasks.add_task(send_ready_smtp, db, invitation.organization_id)


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
    # Coordonnées de contact DP (page contact) — vides = champ effacé
    if body.contact_email is not None:
        org.contact_email = body.contact_email.strip() or None
    if body.contact_phone is not None:
        org.contact_phone = body.contact_phone.strip() or None
    if body.contact_hours is not None:
        org.contact_hours = body.contact_hours.strip() or None

    db.commit()
    db.refresh(org)
    return OrganizationResponse.model_validate(org)


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(current_user: User = Depends(get_current_user)):
    return DashboardResponse(
        user=UserResponse.model_validate(current_user),
        organization=OrganizationResponse.model_validate(current_user.organization),
    )


# ── Modules activables / désactivables (personnalisation) ────────────

class ModulesUpdate(BaseModel):
    modules: list[str] = []


@router.get("/organization/modules")
def get_modules(current_user: User = Depends(get_current_user)):
    """Liste des modules actifs pour l'organisation (tout membre)."""
    from app.core.modules import enabled_modules_of, ALL_MODULES
    active = enabled_modules_of(current_user.organization.enabled_modules)
    return {"modules": [m for m in ALL_MODULES if m in active]}


@router.put("/organization/modules", response_model=OrganizationResponse)
def update_modules(
    body: ModulesUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Active/désactive les modules (admin). Modules inconnus → 422."""
    from app.core.modules import ALL_MODULES
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Réservé aux administrateurs")
    unknown = [m for m in body.modules if m not in ALL_MODULES]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Modules inconnus : {', '.join(unknown)}")
    org = current_user.organization
    org.enabled_modules = json.dumps(body.modules)
    db.commit()
    db.refresh(org)
    return OrganizationResponse.model_validate(org)


# ── Logo de l'entreprise (login + pages) ─────────────────────────────

MAX_LOGO_BYTES = 512 * 1024  # 512 Ko (data URL base64)


class LogoUpdate(BaseModel):
    logo_data: str  # data URL : "data:image/png;base64,..."


@router.put("/organization/logo", response_model=OrganizationResponse)
def update_logo(
    body: LogoUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Enregistre le logo de l'entreprise (admin). Data URL ≤ 512 Ko."""
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Réservé aux administrateurs")
    data = body.logo_data.strip()
    if not data.startswith("data:image/"):
        raise HTTPException(status_code=422, detail="Format invalide : data URL d'image attendue (data:image/png;base64,...)")
    if len(data) > MAX_LOGO_BYTES:
        raise HTTPException(status_code=422, detail="Logo trop volumineux (max 512 Ko)")
    org = current_user.organization
    org.logo_data = data
    db.commit()
    db.refresh(org)
    return OrganizationResponse.model_validate(org)


@router.delete("/organization/logo", response_model=OrganizationResponse)
def delete_logo(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Réservé aux administrateurs")
    org = current_user.organization
    org.logo_data = None
    db.commit()
    db.refresh(org)
    return OrganizationResponse.model_validate(org)


# ── Infos publiques d'une organisation (login : logo + nom) ─────────

class PublicOrgResponse(BaseModel):
    name: str
    company_name: str | None = None
    logo_data: str | None = None


@router.get("/organizations/{slug}/public", response_model=PublicOrgResponse)
def get_public_org(slug: str, db: Session = Depends(get_db)):
    """Infos publiques par slug — utilisé par l'écran de connexion pour
    afficher le logo et le nom de l'entreprise AVANT authentification."""
    org = db.query(Organization).filter(Organization.slug == slug).first()
    if org is None:
        raise HTTPException(status_code=404, detail="Organisation introuvable")
    return PublicOrgResponse(name=org.name, company_name=org.company_name, logo_data=org.logo_data)


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
    return [_invitation_to_response(inv) for inv in invitations]


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


@router.put("/organization/members/{user_id}/role")
def change_member_role(
    user_id: int,
    body: dict,  # {"role": "admin" | "member"}
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Réservé aux administrateurs")
    new_role = body.get("role")
    if new_role not in ("admin", "member"):
        raise HTTPException(status_code=400, detail="Rôle invalide (admin ou member)")
    target = db.query(User).filter(User.id == user_id, User.organization_id == current_user.organization_id).first()
    if not target:
        raise HTTPException(status_code=404)
    target.role = new_role
    db.commit()
    return UserResponse.model_validate(target)


@router.put("/organization/members/{user_id}/delegue-role")
def change_delegue_role(
    user_id: int,
    body: dict,  # {"delegue_role": "president"|"vice_president"|"secretaire"|"membre"}
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Réservé aux administrateurs")
    new_role = body.get("delegue_role")
    if new_role not in ("president", "vice_president", "secretaire", "membre"):
        raise HTTPException(status_code=400, detail="Rôle invalide")
    target = db.query(User).filter(User.id == user_id, User.organization_id == current_user.organization_id).first()
    if not target:
        raise HTTPException(status_code=404)
    # Si on assigne un rôle de bureau, on désassigne l'ancien titulaire de ce rôle
    if new_role != "membre":
        db.query(User).filter(
            User.organization_id == current_user.organization_id,
            User.id != user_id,
            User.delegue_role == new_role
        ).update({User.delegue_role: "membre"})
    target.delegue_role = new_role
    # Si on met président/VP/secrétaire, le membre doit être titulaire
    if new_role in ("president", "vice_president", "secretaire") and target.delegue_status == "suppleant":
        target.delegue_status = "titulaire"
    db.commit()
    return UserResponse.model_validate(target)


@router.put("/organization/members/{user_id}/designate")
def designate_member(
    user_id: int,
    body: dict,  # {"field": "securite_sante" | "egalite", "value": true | false}
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "admin" and current_user.delegue_role not in ("president", "vice_president", "secretaire"):
        raise HTTPException(status_code=403, detail="Réservé au bureau ou administrateurs")
    field = body.get("field")
    if field not in ("securite_sante", "egalite"):
        raise HTTPException(status_code=400, detail="Champ invalide")
    value = body.get("value", True)
    target = db.query(User).filter(User.id == user_id, User.organization_id == current_user.organization_id).first()
    if not target:
        raise HTTPException(status_code=404)
    # Si on désigne, on peut aussi désigner le membre précédent
    if value:
        if field == "securite_sante":
            db.query(User).filter(User.organization_id == current_user.organization_id, User.is_delegue_securite_sante == True).update({User.is_delegue_securite_sante: False})
            target.is_delegue_securite_sante = True
        else:
            db.query(User).filter(User.organization_id == current_user.organization_id, User.is_delegue_egalite == True).update({User.is_delegue_egalite: False})
            target.is_delegue_egalite = True
    else:
        if field == "securite_sante":
            target.is_delegue_securite_sante = False
        else:
            target.is_delegue_egalite = False
    db.commit()
    return UserResponse.model_validate(target)


# ── Vault envelope helpers ──────────────────────────────────────────


def _validate_vault_envelope(env: dict) -> dict:
    """Validate a vault envelope dict and return decoded blobs, or raise 400."""
    required = {"wrapped_dek", "nonce", "kdf_salt", "kdf_params"}
    missing = required - set(env.keys())
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"vault_envelope: champs manquants : {', '.join(sorted(missing))}",
        )
    try:
        wrapped_dek = base64.b64decode(env["wrapped_dek"])
        nonce = base64.b64decode(env["nonce"])
        kdf_salt = base64.b64decode(env["kdf_salt"])
    except Exception:
        raise HTTPException(status_code=400, detail="vault_envelope: base64 invalide")

    if len(wrapped_dek) < 48:
        raise HTTPException(status_code=400, detail=f"vault_envelope: wrapped_dek trop court ({len(wrapped_dek)} bytes)")
    if len(nonce) != 12:
        raise HTTPException(status_code=400, detail=f"vault_envelope: nonce: attendu 12 bytes, reçu {len(nonce)}")
    if len(kdf_salt) != 16:
        raise HTTPException(status_code=400, detail=f"vault_envelope: kdf_salt: attendu 16 bytes, reçu {len(kdf_salt)}")

    # Validate kdf_params JSON
    try:
        json.loads(env["kdf_params"])
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=400, detail="vault_envelope: kdf_params: JSON invalide")

    return {"wrapped_dek": wrapped_dek, "nonce": nonce, "kdf_salt": kdf_salt,
            "kdf_params": env["kdf_params"]}


def _store_invitation_vault_envelope(db, envelope: dict, invitation, current_user) -> None:
    """Validate and store a vault invitation envelope."""
    org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    if not org or not org.pv_vault_enabled:
        raise HTTPException(status_code=400, detail="Le coffre n'est pas activé pour cette organisation")

    blobs = _validate_vault_envelope(envelope)

    # Check no existing invitation envelope for this invitation
    existing = db.query(VaultKey).filter(VaultKey.invitation_id == invitation.id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Une enveloppe existe déjà pour cette invitation")

    vk = VaultKey(
        organization_id=current_user.organization_id,
        invitation_id=invitation.id,  # user_id is NULL
        wrapped_dek=blobs["wrapped_dek"],
        nonce=blobs["nonce"],
        kdf_salt=blobs["kdf_salt"],
        kdf_params=blobs["kdf_params"],
        dek_version=1,
    )
    db.add(vk)


def _handle_join_vault_envelope(db, envelope: dict, invitation, user) -> None:
    """Process vault envelope exchange during /join.

    Deletes the old invitation-key envelope and stores the user's new
    password-wrapped envelope.
    """
    blobs = _validate_vault_envelope(envelope)

    # Find and delete the invitation envelope
    invite_key = (
        db.query(VaultKey)
        .filter(
            VaultKey.organization_id == invitation.organization_id,
            VaultKey.invitation_id == invitation.id,
        )
        .first()
    )
    if invite_key:
        db.delete(invite_key)

    # Store the user's new envelope
    vk = VaultKey(
        organization_id=invitation.organization_id,
        user_id=user.id,
        wrapped_dek=blobs["wrapped_dek"],
        nonce=blobs["nonce"],
        kdf_salt=blobs["kdf_salt"],
        kdf_params=blobs["kdf_params"],
        dek_version=1,
    )
    db.add(vk)
