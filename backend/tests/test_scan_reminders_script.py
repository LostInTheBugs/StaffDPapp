"""Test du script cron scripts/scan_reminders.py (T6 : planificateur hors web)."""

import importlib.util
from pathlib import Path


def _load_script():
    path = Path(__file__).resolve().parent.parent / "scripts" / "scan_reminders.py"
    spec = importlib.util.spec_from_file_location("scan_reminders", path)
    assert spec is not None and spec.loader is not None, "spec introuvable"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_scan_reminders_script_runs(client):
    """Le script s'importe et ses trois scans s'exécutent sans erreur (base de test vide → 0 rappel)."""
    mod = _load_script()
    assert mod.main() == 0


def test_scan_reminders_script_is_idempotent(client):
    """Deux exécutions successives ne doublent rien (les scans sont idempotents)."""
    mod = _load_script()
    assert mod.main() == 0
    assert mod.main() == 0


def test_purge_expired_jwt_revocations(db):
    """Purge du cron : les révocabations JWT > 48 h partent, les récentes restent.

    Un jti ne sert plus rien passé l'expiration du jeton (24 h max) — sans
    purge, jwt_revocations croît d'une ligne par logout, indéfiniment."""
    from datetime import datetime, timedelta, timezone

    from app.models.jwt_revocation import JwtRevocation
    from tests.helpers import create_org, create_user

    mod = _load_script()
    org = create_org(db)
    user = create_user(db, "purge@example.org", "Passw0rd!", org.id)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(JwtRevocation(user_id=user.id, jti="jti-72h", revoked_at=now - timedelta(hours=72)))
    db.add(JwtRevocation(user_id=user.id, jti="jti-50h", revoked_at=now - timedelta(hours=50)))
    db.add(JwtRevocation(user_id=user.id, jti="jti-1h", revoked_at=now - timedelta(hours=1)))
    db.commit()

    assert mod.purge_expired_revocations(db) == 2
    assert {r.jti for r in db.query(JwtRevocation).all()} == {"jti-1h"}

    # Idempotence : rien à purger au second passage
    assert mod.purge_expired_revocations(db) == 0
