#!/usr/bin/env python3
"""Scan des rappels email (réunions, consultations, conformité légale).

Point d'entrée CRON — remplace le thread quotidien qui vivait dans le
process web (main.py) : un thread meurt au redémarrage sans rattrapage,
se duplique à chaque worker uvicorn, et couplait le planificateur à la
disponibilité du web. Les scans sont idempotents (aucun doublon en file) ;
le scan conformité ne déclenche que les 1er et 15 du mois.

Crontab (conteneur) — même mécanisme que le reset démo :

    0 5 * * * cd /srv/staff-delegation && docker compose exec -T backend \
        python3 /app/scripts/scan_reminders.py >> /tmp/sd-reminders.log 2>&1

Les trois scans s'exécutent aussi UNE FOIS au démarrage du web
(main.py, on_startup) pour rattraper les échéances manquées après un
redémarrage — ce sont des scans ponctuels, pas un planificateur.

Le script purge aussi les révocabations JWT expirées (voir
purge_expired_revocations) — ce rôle ne vit que dans le cron, pas au
démarrage du web.
"""

from datetime import datetime, timedelta, timezone

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app.models.meeting  # noqa: F401  (enregistre les mappers SQLAlchemy)

from app.core.database import SessionLocal  # noqa: E402
from app.models.jwt_revocation import JwtRevocation  # noqa: E402
from app.services.email_service import (  # noqa: E402
    scan_due_reminders,
    scan_consultation_reminders,
    scan_compliance_reminders,
)

# Une ligne jwt_revocations ne sert plus rien passé l'expiration du jeton
# (24 h au maximum) — on purge avec une marge de 48 h pour ne laisser que
# ce qui est encore consulté par get_current_user.
REVOCATION_PURGE_AFTER = timedelta(hours=48)


def purge_expired_revocations(db) -> int:
    """Supprime les révocabations JWT plus anciennes que REVOCATION_PURGE_AFTER.

    Un jti ne peut plus rejeter quoi que ce soit une fois son jeton expiré ;
    sans cette purge, la table croît d'une ligne par logout, indéfiniment.
    Idempotent — un DELETE avec cutoff n'efface jamais deux fois la même ligne.
    """
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - REVOCATION_PURGE_AFTER
    purged = db.query(JwtRevocation).filter(JwtRevocation.revoked_at < cutoff).delete()
    db.commit()
    return purged


def main() -> int:
    base_url = os.environ.get("SD_BASE_URL", "")
    total = 0
    db = SessionLocal()
    try:
        total += scan_due_reminders(db, base_url=base_url)
        total += scan_consultation_reminders(db, base_url=base_url)
        total += scan_compliance_reminders(db, base_url=base_url)
        purged = purge_expired_revocations(db)
    finally:
        db.close()
    print(f"[scan-reminders] {total} rappel(s) mis en file, {purged} révocabation(s) JWT purgée(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
