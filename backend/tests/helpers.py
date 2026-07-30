"""Shared helpers for security tests — can be imported from both conftest and test files."""

import re
import pyotp
from app.core.security import hash_password, normalize_email
from app.models import User, UserRole, Organization, Invitation, DelegueStatus, DelegueRole


def create_org(db, name="TestOrg", employee_count=120):
    slug = re.sub(r"[^\w\s-]", "", name.lower().strip())
    slug = re.sub(r"[-\s]+", "-", slug).strip("-") or "org"
    org = Organization(name=name, slug=slug, employee_count=employee_count)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def create_user(db, email, password, org_id, role="member", delegue_status="titulaire", **kwargs):
    user = User(
        email=email,
        password_hash=hash_password(password),
        first_name="Test",
        last_name="User",
        delegue_status=DelegueStatus(delegue_status),
        delegue_role=DelegueRole(kwargs.pop("delegue_role", "membre")),
        role=UserRole(role),
        organization_id=org_id,
        is_active=True,
        totp_enabled=kwargs.pop("totp_enabled", False),
        totp_secret=kwargs.pop("totp_secret", None),
        **kwargs,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_invitation(db, email, org_id, created_by_id, code="TESTCODE", **kwargs):
    inv = Invitation(
        code=code,
        email=normalize_email(email),
        first_name="Invited",
        last_name="Person",
        delegue_status=DelegueStatus(kwargs.pop("delegue_status", "titulaire")),
        delegue_role=DelegueRole(kwargs.pop("delegue_role", "membre")),
        is_used=False,
        created_by_id=created_by_id,
        organization_id=org_id,
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


def fetch_captcha(client):
    """Get a CAPTCHA challenge, parse answer, return (challenge_id, answer)."""
    resp = client.get("/api/auth/captcha")
    assert resp.status_code == 200
    data = resp.json()
    m = re.search(r"font (\d+) \+ (\d+)", data["question"])
    assert m, f"Unexpected question format: {data['question']}"
    a, b = int(m.group(1)), int(m.group(2))
    return data["challenge_id"], str(a + b)


def get_totp_code(secret):
    """Get current TOTP code for a given secret."""
    totp = pyotp.TOTP(secret)
    return totp.now()
