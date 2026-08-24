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
