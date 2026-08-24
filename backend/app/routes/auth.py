from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import verify_password, create_access_token, hash_password, decode_access_token, normalize_email
from app.core.captcha import validate_captcha
from app.core.mfa import generate_totp_secret, generate_totp_uri, generate_qr_code_b64, verify_totp
from app.core.ratelimit import check_rate_limit, client_ip
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
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    # Anti brute-force : 10 tentatives / 15 min / IP
    check_rate_limit(f"login:{client_ip(request)}", 10, 900)
    # Validate CAPTCHA
    if not validate_captcha(body.captcha_id, body.captcha_answer):
        raise HTTPException(status_code=400, detail="CAPTCHA invalide")

    user = db.query(User).filter(User.email == normalize_email(body.email)).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Compte désactivé")

    # MFA: if enabled, return a temporary MFA token (3 min expiry)
    if user.totp_enabled:
        from datetime import timedelta
        mfa_token = create_access_token(
            data={"sub": str(user.id), "mfa": True, "typ": "mfa_pending"},
            expires_delta=timedelta(minutes=3),
        )
        return TokenResponse(access_token="", mfa_required=True, mfa_token=mfa_token)

    token = create_access_token(data={"sub": str(user.id), "org_id": user.organization_id, "typ": "access"})
    return TokenResponse(access_token=token, mfa_required=False)


@router.post("/mfa/login", response_model=TokenResponse)
def mfa_login(body: MfaLoginRequest, request: Request, db: Session = Depends(get_db)):
    """Second step: verify TOTP code after password."""
    # Anti brute-force : 10 tentatives / 15 min / IP
    check_rate_limit(f"mfa:{client_ip(request)}", 10, 900)

    payload = decode_access_token(body.mfa_token)
    if payload is None or payload.get("typ") != "mfa_pending" or not payload.get("mfa"):
        raise HTTPException(status_code=401, detail="Token MFA invalide ou expiré")

    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Utilisateur non trouvé")
    if not user.totp_enabled or not user.totp_secret:
        raise HTTPException(status_code=400, detail="MFA non configuré")

    # Verrouillage anti brute-force TOTP : 5 échecs → 15 min de blocage
    now = datetime.now()
    if user.totp_locked_until and user.totp_locked_until > now:
        raise HTTPException(
            status_code=429,
            detail="Trop de tentatives MFA. Compte verrouillé temporairement (15 minutes).",
        )

    if not verify_totp(user.totp_secret, body.totp_code):
        user.totp_failed_attempts = (user.totp_failed_attempts or 0) + 1
        if user.totp_failed_attempts >= 5:
            user.totp_locked_until = now + timedelta(minutes=15)
            user.totp_failed_attempts = 0
        db.commit()
        raise HTTPException(status_code=401, detail="Code TOTP invalide")

    # Succès → réinitialisation du compteur
    user.totp_failed_attempts = 0
    user.totp_locked_until = None
    db.commit()

    token = create_access_token(data={"sub": str(user.id), "org_id": user.organization_id, "typ": "access"})
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
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Le mot de passe doit contenir au moins 8 caractères")
    if len(new_password.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="Le mot de passe est trop long (72 octets maximum)")
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
        existing = db.query(User).filter(User.email == normalize_email(body["email"]), User.id != current_user.id).first()
        if existing:
            raise HTTPException(status_code=409, detail="Cet email est déjà utilisé")
        current_user.email = normalize_email(body["email"])
    if "avatar_url" in body:
        current_user.avatar_url = body["avatar_url"]
    if "language" in body and body["language"] in ("fr", "en", "de", "pt", "lb"):
        current_user.language = body["language"]
    db.commit()
    db.refresh(current_user)
    return UserResponse.model_validate(current_user)
