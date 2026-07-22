import secrets
import time

# In-memory store for CAPTCHA challenges (key: challenge_id, value: {answer, expires_at})
_captcha_store: dict[str, dict] = {}

CAPTCHA_TTL = 300  # 5 minutes


def generate_captcha() -> dict:
    """Generate a simple math CAPTCHA challenge."""
    a = secrets.randbelow(10) + 1  # 1-10
    b = secrets.randbelow(10) + 1  # 1-10
    answer = str(a + b)
    challenge_id = secrets.token_hex(16)
    _captcha_store[challenge_id] = {
        "answer": answer,
        "expires_at": time.time() + CAPTCHA_TTL,
    }
    # Cleanup old entries
    now = time.time()
    for key in list(_captcha_store.keys()):
        if _captcha_store[key]["expires_at"] < now:
            del _captcha_store[key]
    return {
        "challenge_id": challenge_id,
        "question": f"Combien font {a} + {b} ?",
    }


def validate_captcha(challenge_id: str, answer: str) -> bool:
    """Validate a CAPTCHA answer. One-time use."""
    entry = _captcha_store.pop(challenge_id, None)
    if entry is None:
        return False
    if time.time() > entry["expires_at"]:
        return False
    return entry["answer"] == answer.strip()
