from datetime import datetime, timedelta, timezone
from typing import Optional
import os
import secrets

import bcrypt
from jose import JWTError, jwt
from argon2 import PasswordHasher, Type
from argon2.exceptions import VerificationError

from app.core.config import get_settings

settings = get_settings()
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
    """Hash bcrypt direct (passlib retiré : non maintenu, casse sur bcrypt ≥4.1).

    ⚠️ bcrypt tronque SILENCIEUSEMENT à 72 octets : la validation serveur
    (schemas/auth.py, route /api/auth/password) refuse les mots de passe
    plus longs — ne jamais lever la garde ici.

    Le niveau bcrypt est piloté par SD_BCRYPT_ROUNDS (défaut 12 = prod).
    En test, conftest/run_tests.sh le baisse (ex. 4) : le niveau est stocké
    DANS le hash et verify_password le respecte, donc aucun impact fonctionnel
    sur les tests (roundtrip, legacy, 72-octets) — c'est juste plus rapide.
    """
    rounds = int(os.environ.get("SD_BCRYPT_ROUNDS", "12"))
    salt = bcrypt.gensalt(rounds=rounds)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Vérifie un hash bcrypt (même format $2b$ que passlib — rétrocompatible)."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False  # hash malformé → échec silencieux (comportement passlib)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    # jti : identifiant unique du jeton — permet un logout ciblé
    # (table jwt_revocations). ver : version de sécurité du compte
    # (users.token_version) — toute différence = jeton révoqué.
    to_encode.setdefault("jti", secrets.token_hex(16))
    to_encode.setdefault("ver", 0)
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
