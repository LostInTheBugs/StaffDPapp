from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import verify_password, create_access_token, hash_password, decode_access_token
from app.core.captcha import validate_captcha
from app.core.mfa import generate_totp_secret, generate_totp_uri, generate_qr_code_b64, verify_totp
from app.models import User
from app.schemas.auth import (
    LoginRequest, MfaLoginRequest, TokenResponse, UserResponse,
    MfaSetupResponse, MfaVerifyRequest, MfaDisableRequest,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ── CAPTCHA ────────────────────────────────────────────────────────

@router.get("/captcha")
def get_captcha():
    from app.core.captcha import generate_captcha
    from app.schemas.auth import CaptchaResponse
    return CaptchaResponse(**generate_captcha())


# ── LOGIN (with MFA) ──────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    # Validate CAPTCHA
    if body.captcha_id and body.captcha_answer:
        if not validate_captcha(body.captcha_id, body.captcha_answer):
            raise HTTPException(status_code=400, detail="CAPTCHA invalide")

    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Compte désactivé")

    # MFA: if enabled, return a temporary MFA token (2 min expiry)
    if user.totp_enabled:
        mfa_token = create_access_token(
            data={"sub": str(user.id), "mfa": True, "org_id": user.organization_id},
            expires_delta=None  # default 24h — but we want short-lived
        )
        # Create a short-lived token specifically for MFA
        from datetime import timedelta
        mfa_token = create_access_token(
            data={"sub": str(user.id), "mfa": True},
            expires_delta=timedelta(minutes=3),
        )
        return TokenResponse(access_token="", mfa_required=True, mfa_token=mfa_token)

    token = create_access_token(data={"sub": str(user.id), "org_id": user.organization_id})
    return TokenResponse(access_token=token, mfa_required=False)


@router.post("/mfa/login", response_model=TokenResponse)
def mfa_login(body: MfaLoginRequest, db: Session = Depends(get_db)):
    """Second step: verify TOTP code after password."""
    payload = decode_access_token(body.mfa_token)
    if payload is None or not payload.get("mfa"):
        raise HTTPException(status_code=401, detail="Token MFA invalide ou expiré")

    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Utilisateur non trouvé")
    if not user.totp_enabled or not user.totp_secret:
        raise HTTPException(status_code=400, detail="MFA non configuré")

    if not verify_totp(user.totp_secret, body.totp_code):
        raise HTTPException(status_code=401, detail="Code TOTP invalide")

    token = create_access_token(data={"sub": str(user.id), "org_id": user.organization_id})
    return TokenResponse(access_token=token, mfa_required=False)


# ── MFA SETUP ──────────────────────────────────────────────────────

@router.post("/mfa/setup", response_model=MfaSetupResponse)
def mfa_setup(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.totp_enabled:
        raise HTTPException(status_code=400, detail="MFA déjà activé. Désactivez-le d'abord.")

    secret = generate_totp_secret()
    uri = generate_totp_uri(current_user.email, secret)
    qr_b64 = generate_qr_code_b64(uri)

    # Store secret temporarily (not enabled yet)
    current_user.totp_secret = secret
    db.commit()

    return MfaSetupResponse(secret=secret, qr_code_b64=qr_b64, uri=uri)


@router.post("/mfa/verify")
def mfa_verify(
    body: MfaVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.totp_secret:
        raise HTTPException(status_code=400, detail="Aucun secret TOTP généré. Faites /mfa/setup d'abord.")
    if current_user.totp_enabled:
        raise HTTPException(status_code=400, detail="MFA déjà activé")

    if not verify_totp(current_user.totp_secret, body.totp_code):
        raise HTTPException(status_code=401, detail="Code TOTP invalide. Réessayez.")

    current_user.totp_enabled = True
    db.commit()
    return {"status": "ok", "message": "MFA activé avec succès"}


@router.post("/mfa/disable")
def mfa_disable(
    body: MfaDisableRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.totp_enabled:
        raise HTTPException(status_code=400, detail="MFA n'est pas activé")

    if not verify_password(body.password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Mot de passe incorrect")

    current_user.totp_secret = None
    current_user.totp_enabled = False
    db.commit()
    return {"status": "ok", "message": "MFA désactivé"}


# ── PROFILE ────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    return UserResponse.model_validate(user)


# ── PASSWORD CHANGE ────────────────────────────────────────────────

@router.put("/password")
def change_password(
    body: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    old_password = body.get("old_password")
    new_password = body.get("new_password")
    if not old_password or not new_password:
        raise HTTPException(status_code=400, detail="Ancien et nouveau mot de passe requis")
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Le mot de passe doit contenir au moins 6 caractères")
    if not verify_password(old_password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Ancien mot de passe incorrect")
    current_user.password_hash = hash_password(new_password)
    db.commit()
    return {"status": "ok"}


# ── PROFILE UPDATE ─────────────────────────────────────────────────

@router.put("/profile", response_model=UserResponse)
def update_profile(
    body: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if "first_name" in body:
        current_user.first_name = body["first_name"]
    if "last_name" in body:
        current_user.last_name = body["last_name"]
    if "email" in body:
        # Check uniqueness
        existing = db.query(User).filter(User.email == body["email"], User.id != current_user.id).first()
        if existing:
            raise HTTPException(status_code=409, detail="Cet email est déjà utilisé")
        current_user.email = body["email"]
    db.commit()
    db.refresh(current_user)
    return UserResponse.model_validate(current_user)
