import base64
import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User, Organization
from app.models.vault_key import VaultKey
from app.schemas.vault import (
    CreateVaultRequest, ReplaceKeyRequest,
    VaultKeyResponse, VaultStatusResponse,
)

router = APIRouter(tags=["vault"])

BUREAU_ROLES = {"president", "vice_president", "secretaire"}


def _vault_key_to_response(vk: VaultKey) -> VaultKeyResponse:
    return VaultKeyResponse(
        wrapped_dek=base64.b64encode(vk.wrapped_dek).decode("ascii"),
        nonce=base64.b64encode(vk.nonce).decode("ascii"),
        kdf_salt=base64.b64encode(vk.kdf_salt).decode("ascii"),
        kdf_params=vk.kdf_params,
        dek_version=vk.dek_version,
    )


# ── POST /api/vault ────────────────────────────────────────────────

@router.post("/api/vault", response_model=VaultKeyResponse, status_code=status.HTTP_201_CREATED)
def create_vault(
    body: CreateVaultRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create the vault for the organization. Bureau only. Refuse if vault already exists (409)."""
    org_id = current_user.organization_id

    # Bureau only
    if current_user.delegue_role.value not in BUREAU_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Seuls les membres du bureau (président, vice-président, secrétaire) peuvent créer le coffre",
        )

    # Reject if vault already exists
    existing = db.query(VaultKey).filter(VaultKey.organization_id == org_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Un coffre existe déjà pour cette organisation")

    # Reject any field that looks like a plaintext secret
    _reject_plaintext_secrets(body)

    # Decode and store
    wrapped_dek = base64.b64decode(body.wrapped_dek)
    nonce = base64.b64decode(body.nonce)
    kdf_salt = base64.b64decode(body.kdf_salt)

    # Final size guards (schema validators already ran, but be defensive)
    if len(nonce) != 12:
        raise HTTPException(status_code=400, detail=f"nonce: expected 12 bytes, got {len(nonce)}")
    if len(kdf_salt) != 16:
        raise HTTPException(status_code=400, detail=f"kdf_salt: expected 16 bytes, got {len(kdf_salt)}")
    if len(wrapped_dek) < 48:
        raise HTTPException(status_code=400, detail=f"wrapped_dek too short: {len(wrapped_dek)} bytes")

    # Validate kdf_params is valid JSON
    try:
        json.loads(body.kdf_params)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="kdf_params: invalid JSON")

    vk = VaultKey(
        organization_id=org_id,
        user_id=current_user.id,  # first envelope = creator's
        wrapped_dek=wrapped_dek,
        nonce=nonce,
        kdf_salt=kdf_salt,
        kdf_params=body.kdf_params,
        dek_version=1,
    )
    db.add(vk)

    # Activate vault on org
    org = db.query(Organization).filter(Organization.id == org_id).first()
    org.pv_vault_enabled = True

    db.commit()
    db.refresh(vk)

    return _vault_key_to_response(vk)


# ── GET /api/vault/key ─────────────────────────────────────────────

@router.get("/api/vault/key", response_model=VaultKeyResponse)
def get_own_key(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the current user's key envelope. 404 if they don't have one."""
    vk = (
        db.query(VaultKey)
        .filter(
            VaultKey.organization_id == current_user.organization_id,
            VaultKey.user_id == current_user.id,
        )
        .first()
    )
    if not vk:
        raise HTTPException(status_code=404, detail="Aucune enveloppe de clé trouvée pour cet utilisateur")

    return _vault_key_to_response(vk)


# ── PUT /api/vault/key ─────────────────────────────────────────────

@router.put("/api/vault/key", response_model=VaultKeyResponse)
def replace_own_key(
    body: ReplaceKeyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Replace own key envelope (password change: client re-wraps DEK)."""
    vk = (
        db.query(VaultKey)
        .filter(
            VaultKey.organization_id == current_user.organization_id,
            VaultKey.user_id == current_user.id,
        )
        .first()
    )
    if not vk:
        raise HTTPException(status_code=404, detail="Aucune enveloppe de clé trouvée pour cet utilisateur")

    _reject_plaintext_secrets(body)

    wrapped_dek = base64.b64decode(body.wrapped_dek)
    nonce = base64.b64decode(body.nonce)
    kdf_salt = base64.b64decode(body.kdf_salt)

    if len(nonce) != 12:
        raise HTTPException(status_code=400, detail=f"nonce: expected 12 bytes, got {len(nonce)}")
    if len(kdf_salt) != 16:
        raise HTTPException(status_code=400, detail=f"kdf_salt: expected 16 bytes, got {len(kdf_salt)}")
    if len(wrapped_dek) < 48:
        raise HTTPException(status_code=400, detail=f"wrapped_dek too short: {len(wrapped_dek)} bytes")

    try:
        json.loads(body.kdf_params)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="kdf_params: invalid JSON")

    vk.wrapped_dek = wrapped_dek
    vk.nonce = nonce
    vk.kdf_salt = kdf_salt
    vk.kdf_params = body.kdf_params
    db.commit()
    db.refresh(vk)

    return _vault_key_to_response(vk)


# ── GET /api/vault/status ──────────────────────────────────────────

@router.get("/api/vault/status", response_model=VaultStatusResponse)
def get_vault_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return vault status for the current user's organization."""
    org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    if not org:
        raise HTTPException(status_code=404)

    own_key = (
        db.query(VaultKey)
        .filter(
            VaultKey.organization_id == current_user.organization_id,
            VaultKey.user_id == current_user.id,
        )
        .first()
    )

    return VaultStatusResponse(
        enabled=bool(org.pv_vault_enabled),
        has_key=own_key is not None,
        dek_version=own_key.dek_version if own_key else None,
    )


# ── Guards ─────────────────────────────────────────────────────────

_FORBIDDEN_FIELDS = {"password", "dek", "kek", "secret", "passphrase", "key", "plaintext"}


def _reject_plaintext_secrets(body) -> None:
    """Reject any request field that could be a secret in clear.

    The server must NEVER accept a password, DEK, or KEK. This is a
    defense-in-depth guard: even if a developer accidentally adds such
    a field to the request schema, the endpoint will refuse it.
    """
    if hasattr(body, "model_dump"):
        data = body.model_dump()
    elif hasattr(body, "dict"):
        data = body.dict()
    else:
        data = body

    for key in data:
        if key.lower() in _FORBIDDEN_FIELDS:
            raise HTTPException(
                status_code=422,
                detail=f"Le serveur n'accepte pas le champ '{key}' — les secrets ne doivent jamais transiter en clair",
            )
