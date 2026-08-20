"""Modules fonctionnels activables/désactivables par organisation.

Chaque module regroupe un ensemble de pages/routes. L'admin choisit ceux
qui sont actifs (GET/PUT /api/organization/modules). Les routes des modules
désactivés renvoient 403 (dépendance `require_module` dans deps.py) et la
navigation frontend masque les liens correspondants.

Convention : `enabled_modules` sur Organization = liste JSON de noms de
modules. `None` ou liste vide = TOUS les modules actifs (rétrocompatibilité).
"""

# Modules optionnels (tout le reste du cœur — réunions, PV/coffre, membres,
# invitations, dashboard — reste toujours actif).
ALL_MODULES: list[str] = [
    "elections",          # Élections L.413
    "time_tracking",      # Mes heures
    "notices",            # Tableau d'affichage L.414-16
    "compliance",         # Cockpit conformité
    "consultations",      # Consultations L.414-3
    "workforce_stats",    # Stats semestrielles L.414-3 + rapport annuel
    "delegate_activities",# Activités délégués désignés
    "legal",              # Formation L.415-9, registre S&S, protection
    "contact",            # Page contact DP
]


def enabled_modules_of(enabled_modules: str | list | None) -> set[str]:
    """Résout la liste effective des modules actifs d'une organisation.

    None / vide / liste invalide → tous les modules (rétrocompatibilité).
    """
    if not enabled_modules:
        return set(ALL_MODULES)
    if isinstance(enabled_modules, list):
        return {m for m in enabled_modules if m in ALL_MODULES}
    # stockage texte (JSON string) — migration avant normalisation
    import json
    try:
        data = json.loads(enabled_modules)
    except (ValueError, TypeError):
        return set(ALL_MODULES)
    if not isinstance(data, list):
        return set(ALL_MODULES)
    return {m for m in data if m in ALL_MODULES}
