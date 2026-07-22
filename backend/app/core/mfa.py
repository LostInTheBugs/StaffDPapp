import pyotp
import qrcode
from io import BytesIO
import base64

from app.core.config import get_settings

settings = get_settings()


def generate_totp_secret() -> str:
    """Generate a new TOTP secret for a user."""
    return pyotp.random_base32()


def generate_totp_uri(email: str, secret: str) -> str:
    """Generate the otpauth:// URI for QR code."""
    org_name = settings.app_name or "Staff Delegation"
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=email, issuer_name=org_name
    )


def generate_qr_code_b64(uri: str) -> str:
    """Generate a QR code as base64 PNG image for display."""
    img = qrcode.make(uri)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def verify_totp(secret: str, code: str) -> bool:
    """Verify a TOTP code against a secret."""
    totp = pyotp.TOTP(secret)
    return totp.verify(code)
