"""Reset quotidien de la démo (cron matinal).

Demande Fred 2026-08-20 : si un visiteur change un mot de passe (compte ou
coffre), tout revient à l'état de départ le matin suivant.

Fait (pour l'organisation de slug "demo" uniquement — ne touche JAMAIS aux
autres orgs) :
1. Tous les mots de passe des comptes → demo123456
2. TOTP désactivé (secret effacé, compteurs d'échec remis à zéro)
3. Coffre : restaure l'enveloppe d'origine de CHAQUE VaultKey de l'org
   (wrapped_dek + nonce + kdf_salt + kdf_params) → le coffre se redéverrouille
   avec le mot de passe d'origine, SANS perte des PV (la DEK ne change pas :
   l'enveloppe change seule quand quelqu'un change le mdp).

Au PREMIER passage, si une VaultKey n'a pas encore de reset_envelope, on
CAPTURE son enveloppe actuelle (état d'origine = coffre créé avec le mdp
de démo). Ensuite chaque passage RESTAURE l'enveloppe capturée.

Le serveur ne voit jamais les mots de passe : reset_envelope stocke
l'enveloppe CHIFFRÉE (AES-GCM), pas la clé.

Usage (dans le conteneur backend, via cron hôte) :
    docker compose exec -T backend python3 /app/scripts/reset_demo.py
"""

import base64
import json
import os
import sys
from datetime import datetime, timezone

# Lancer depuis le conteneur : python3 /app/scripts/reset_demo.py
# → /app/scripts est sys.path[0], il faut ajouter /app pour trouver app.*
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import Organization, User, VaultKey
import app.models.meeting  # enregistre les mappers (relation "Meeting" lazy) — piège script isolé

ORG_SLUG = "demo"
DEMO_PASSWORD = "demo123456"


def _load_or_capture(vk: VaultKey) -> None:
    """Restaure l'enveloppe d'origine ; la capture au premier passage."""
    if vk.reset_envelope:
        env = json.loads(vk.reset_envelope)
        vk.wrapped_dek = base64.b64decode(env["wrapped"])
        vk.nonce = base64.b64decode(env["nonce"])
        vk.kdf_salt = base64.b64decode(env["salt"])
        vk.kdf_params = env["params"]
    else:
        vk.reset_envelope = json.dumps({
            "wrapped": base64.b64encode(vk.wrapped_dek).decode("ascii"),
            "nonce": base64.b64encode(vk.nonce).decode("ascii"),
            "salt": base64.b64encode(vk.kdf_salt).decode("ascii"),
            "params": vk.kdf_params,
        })


def main() -> int:
    db = SessionLocal()
    try:
        org = db.query(Organization).filter(Organization.slug == ORG_SLUG).first()
        if org is None:
            print(f"[reset-demo] org '{ORG_SLUG}' introuvable — rien à faire")
            return 0

        password_hash = hash_password(DEMO_PASSWORD)

        # 1+2. Mots de passe + TOTP
        users = db.query(User).filter(
            User.organization_id == org.id,
            User.is_active == True,  # noqa: E712
        ).all()
        for u in users:
            u.password_hash = password_hash
            u.totp_enabled = False
            u.totp_secret = None
            u.totp_failed_attempts = 0
            u.totp_locked_until = None

        # 3. Coffre : restaurer/capturer les enveloppes
        keys = db.query(VaultKey).filter(VaultKey.organization_id == org.id).all()
        captured, restored = 0, 0
        for vk in keys:
            if vk.reset_envelope:
                _load_or_capture(vk)
                restored += 1
            else:
                _load_or_capture(vk)
                captured += 1

        db.commit()
        print(f"[reset-demo] {datetime.now(timezone.utc).replace(tzinfo=None).isoformat()} — "
              f"{len(users)} comptes reset (demo123456), TOTP désactivé, "
              f"{captured} enveloppe(s) capturée(s), {restored} restaurée(s)")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
