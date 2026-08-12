from pydantic import BaseModel, field_validator
import base64
import json


class CreateVaultRequest(BaseModel):
    """Create a vault: client sends its key envelope. Server never sees secrets in clear."""
    wrapped_dek: str   # base64-encoded AES-GCM(KEK, DEK) — 48 bytes
    nonce: str         # base64-encoded 12-byte nonce
    kdf_salt: str      # base64-encoded 16-byte KDF salt
    kdf_params: str    # JSON string: {"algo":"argon2id","m":65536,"t":3,"p":1}

    @field_validator("wrapped_dek")
    @classmethod
    def validate_wrapped_dek(cls, v: str) -> str:
        raw = base64.b64decode(v)
        if len(raw) < 48:
            raise ValueError(f"wrapped_dek too short: {len(raw)} bytes (expected ≥ 48)")
        return v

    @field_validator("nonce")
    @classmethod
    def validate_nonce(cls, v: str) -> str:
        raw = base64.b64decode(v)
        if len(raw) != 12:
            raise ValueError(f"nonce: expected 12 bytes, got {len(raw)}")
        return v

    @field_validator("kdf_salt")
    @classmethod
    def validate_salt(cls, v: str) -> str:
        raw = base64.b64decode(v)
        if len(raw) != 16:
            raise ValueError(f"kdf_salt: expected 16 bytes, got {len(raw)}")
        return v

    @field_validator("kdf_params")
    @classmethod
    def validate_kdf_params(cls, v: str) -> str:
        try:
            parsed = json.loads(v)
        except json.JSONDecodeError:
            raise ValueError("kdf_params: invalid JSON")
        if not isinstance(parsed, dict):
            raise ValueError("kdf_params: must be a JSON object")
        return v


class ReplaceKeyRequest(BaseModel):
    """Replace own key envelope (password change: re-wraps client-side)."""
    wrapped_dek: str
    nonce: str
    kdf_salt: str
    kdf_params: str

    @field_validator("wrapped_dek")
    @classmethod
    def validate_wrapped_dek(cls, v: str) -> str:
        raw = base64.b64decode(v)
        if len(raw) < 48:
            raise ValueError(f"wrapped_dek too short: {len(raw)} bytes (expected ≥ 48)")
        return v

    @field_validator("nonce")
    @classmethod
    def validate_nonce(cls, v: str) -> str:
        raw = base64.b64decode(v)
        if len(raw) != 12:
            raise ValueError(f"nonce: expected 12 bytes, got {len(raw)}")
        return v

    @field_validator("kdf_salt")
    @classmethod
    def validate_salt(cls, v: str) -> str:
        raw = base64.b64decode(v)
        if len(raw) != 16:
            raise ValueError(f"kdf_salt: expected 16 bytes, got {len(raw)}")
        return v

    @field_validator("kdf_params")
    @classmethod
    def validate_kdf_params(cls, v: str) -> str:
        try:
            json.loads(v)
        except json.JSONDecodeError:
            raise ValueError("kdf_params: invalid JSON")
        return v


class VaultKeyResponse(BaseModel):
    """The key envelope as stored on the server — opaque blobs, no secrets."""
    wrapped_dek: str   # base64
    nonce: str         # base64
    kdf_salt: str      # base64
    kdf_params: str    # JSON
    dek_version: int


class VaultStatusResponse(BaseModel):
    enabled: bool
    has_key: bool
    dek_version: int | None
