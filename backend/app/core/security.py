from datetime import datetime, timedelta, timezone
from typing import Optional
import secrets

from jose import JWTError, jwt
from passlib.context import CryptContext
from argon2 import PasswordHasher, Type
from argon2.exceptions import VerificationError

from app.core.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# Argon2id for invitation code hashing (not bcrypt — invitation codes need ~130 bits
# of entropy and Argon2id is tuned for key/password hashing with memory hardness)
_ph = PasswordHasher(
    time_cost=3,        # 3 iterations
    memory_cost=65536,  # 64 MiB
    parallelism=1,
    hash_len=32,
    type=Type.ID,          # Argon2id
)

# Argon2id allégé pour les invitations EN MASSE uniquement. Les codes font
# 26 caractères Crockford (~130 bits d'entropie) : le brute force est
# infaisable quel que soit le coût du KDF, un KDF plus léger est donc sûr.
# Les paramètres sont stockés DANS le hash (format argon2 standard), donc
# verify_invitation_code (hasher par défaut) valide ces hash sans souci.
_ph_batch = PasswordHasher(
    time_cost=1,
    memory_cost=16384,  # 16 MiB (vs 64 MiB)
    parallelism=1,
    hash_len=32,
    type=Type.ID,
)

# ── Crockford base32 alphabet (no I, L, O, U) ──────────────────────
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_CROCKFORD_NORMALIZE = str.maketrans({
    'i': '1', 'I': '1',
    'l': '1', 'L': '1',
    'o': '0', 'O': '0',
    '-': '',           # strip grouping dashes
})


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None


def generate_invitation_code(length: int | None = None) -> str:
    """Generate a Crockford base32 invitation code (26 chars, ~130 bits entropy).

    By default, generates the long secure code. The old 8-char parameter is
    retained only for backward compatibility in tests that pass an explicit length.
    """
    n = length if length is not None else 26
    return "".join(secrets.choice(_CROCKFORD) for _ in range(n))


def normalize_invitation_code(code: str) -> str:
    """Normalize a user-entered invitation code.

    - Uppercase
    - Strip grouping dashes (XXXX-XXXX-...)
    - Correct Crockford confusions: I, L → 1; O → 0
    """
    return code.translate(_CROCKFORD_NORMALIZE).upper()


def hash_invitation_code(code: str) -> str:
    """Hash an invitation code with Argon2id for server-side storage."""
    normalized = normalize_invitation_code(code)
    return _ph.hash(normalized)


def hash_invitation_code_batch(code: str) -> str:
    """Hash an invitation code with the lighter Argon2id (batch import only).

    The resulting hash is verifiable with verify_invitation_code (params are
    embedded in the argon2 string). Only used by the mass-invitation endpoint
    to keep ~200 codes generatable in a few seconds instead of minutes.
    """
    return _ph_batch.hash(normalize_invitation_code(code))


def verify_invitation_code(plain: str, hashed: str) -> bool:
    """Verify a plaintext invitation code against its Argon2id hash."""
    normalized = normalize_invitation_code(plain)
    try:
        return _ph.verify(hashed, normalized)
    except VerificationError:
        return False


def normalize_email(email: str) -> str:
    """Trim whitespace and lower-case an email for case-insensitive comparisons."""
    return email.strip().lower()
