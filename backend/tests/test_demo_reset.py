"""Tests du reset automatique de la démo (scripts/reset_demo.py).

Vérifie : mots de passe remis à demo123456, TOTP désactivé, enveloppe du
coffre capturée au 1er passage puis restaurée (DEK préservée).
"""

import base64
import json

from app.core.database import SessionLocal
from app.core.security import verify_password
from app.models import Organization, User, VaultKey

from scripts.reset_demo import main as reset_main  # noqa: E402


def _enable_emails(org_id: int) -> None:  # pragma: no cover — inutilisé ici
    pass


def _setup_vault(db, org_id: int, user_id: int) -> VaultKey:
    vk = VaultKey(
        organization_id=org_id, user_id=user_id,
        wrapped_dek=b"\x01" * 48, nonce=b"\x02" * 12,
        kdf_salt=b"\x03" * 16, kdf_params='{"algo":"argon2id","m":65536,"t":3,"p":1}',
    )
    db.add(vk)
    db.commit()
    db.refresh(vk)
    return vk


def test_reset_demo_passwords_totp_and_vault(client, org_with_users):
    oid = org_with_users["org_id"]
    db = SessionLocal()

    # Force l'org au slug "demo" (le reset ne touche que celle-ci)
    org = db.query(Organization).get(oid)
    org.slug = "demo"
    db.commit()

    sophie = db.query(User).filter(User.organization_id == oid,
                                   User.email == "sophie@testpv.lu").first()
    # Altérer l'état : mdp inconnu, TOTP activé
    from app.core.security import hash_password
    sophie.password_hash = hash_password("changed-password")
    sophie.totp_enabled = True
    sophie.totp_secret = "JBSWY3DPEHPK3PXP"
    db.commit()

    vk = _setup_vault(db, oid, sophie.id)

    # ── 1er passage : capture de l'enveloppe, pas de modification de la DEK
    assert reset_main() == 0
    db.expire_all()
    vk = db.query(VaultKey).get(vk.id)
    assert vk.reset_envelope is not None
    env = json.loads(vk.reset_envelope)
    assert env["wrapped"] == base64.b64encode(b"\x01" * 48).decode("ascii")
    assert vk.wrapped_dek == b"\x01" * 48  # DEK inchangée au 1er passage

    # mdp remis à demo123456, TOTP désactivé
    db.expire_all()
    sophie = db.query(User).filter(User.organization_id == oid,
                                   User.email == "sophie@testpv.lu").first()
    assert verify_password("demo123456", sophie.password_hash)
    assert sophie.totp_enabled is False
    assert sophie.totp_secret is None

    # ── Quelqu'un change le mdp du coffre (nouvelle enveloppe)
    vk = db.query(VaultKey).get(vk.id)
    vk.wrapped_dek = b"\xEE" * 48
    db.commit()

    # ── 2e passage : restauration de l'enveloppe d'origine
    assert reset_main() == 0
    db.expire_all()
    vk = db.query(VaultKey).get(vk.id)
    assert vk.wrapped_dek == b"\x01" * 48  # enveloppe restaurée
    assert vk.reset_envelope is not None  # toujours capturée

    # une autre org (slug différent) n'est JAMAIS touchée
    other_org = Organization(name="Other", slug="other-org", employee_count=15)
    db.add(other_org)
    db.commit()
    other_user = User(
        email="outsider@elsewhere.lu",
        password_hash=hash_password("do-not-touch"),
        first_name="O", last_name="U",
        delegue_status="titulaire", delegue_role="membre",
        role="member", organization_id=other_org.id, is_active=True,
    )
    db.add(other_user)
    db.commit()
    assert reset_main() == 0
    db.expire_all()
    ou = db.query(User).filter(User.email == "outsider@elsewhere.lu").first()
    assert verify_password("do-not-touch", ou.password_hash)
    db.close()
