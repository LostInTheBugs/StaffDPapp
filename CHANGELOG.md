# Changelog

## [2026.08.004] — 2026-08-12

### Added
- **Rate limiting** (anti brute-force) : login et join 10 tentatives/15 min/IP, mfa/login 10/15 min/IP, création d'organisation 5/1h/IP → HTTP 429
- **Verrouillage TOTP** : 5 codes invalides → compte bloqué 15 minutes (colonnes `totp_failed_attempts`, `totp_locked_until`)
- **Expiration des invitations** : 30 jours (`invitations.expires_at`, backfill +30 j sur les existantes)
- **Politique de mot de passe** : minimum 8 caractères (backend + formulaires frontend)
- **Migration Alembic** `4b6d8e9f0a1c` (chaîne : baseline → lowercase emails → hardening) — fini la suppression de volume à chaque changement de schéma
- **13 tests** de durcissement (117 au total)

### Changed
- Déploiement : `alembic stamp 31140e6e07a7` + `upgrade head` au lieu de supprimer le volume

## [2026.08.002] — 2026-08-12

### Added
- Suite de tests backend (104 tests : sécurité, barèmes légaux, MFA, CAPTCHA, emails) — fusion de la branche `fix/securite-auth`
- Migration Alembic (baseline + normalisation emails en minuscules)

### Fixed
- **Stats réunions cassées** : `/api/meetings/stats` renvoyait 422 (ordre des routes) — le bandeau affichait `undefined/6`
- **CAPTCHA contournable** : désormais obligatoire côté backend sur login/join/création d'organisation (422 sans captcha)
- **Contournement MFA** : les tokens MFA-pending (`typ=mfa_pending`) ne peuvent plus accéder aux routes protégées
- **Invitation** : le code est désormais lié à l'email (impossible de rejoindre avec une autre identité)
- **Barème L.412-1 >5500 salariés** : arrondi inférieur (tranche entière de 500), conforme au texte officiel
- **Normalisation des emails** : comparaison insensible à la casse (login avec `Sophie@Demo.lu` accepté)
- **Version frontend alignée** : `index.html` et footer affichaient encore 2026.07.001

## [2026.08.001] — 2026-08-01

### Added
- Fichier `VERSION` à la racine contenant la version `2026.08.001`
- `CHANGELOG.md` avec suivi des versions
- Variable d'environnement `SD_PORT` pour le port d'écoute du backend

### Changed
- Version du projet uniformisée à `2026.08.001` dans tous les manifestes (`package.json`, `app/main.py`)
- Port d'écoute par défaut du backend : `8000` → `8005`
- Backend Dockerfile : le port est désormais surchargeable via `${SD_PORT:-8005}` au lieu d'être codé en dur
- `.env.example` : ajout de `SD_PORT=8005`
- `docker-compose.yml` : ajout de `SD_PORT` dans les variables d'environnement du backend
- `frontend/nginx.conf` : proxy API vers le backend sur le port `8005`
- `frontend/vite.config.ts` : proxy de développement vers `localhost:8005`
- `README.md` : enrichi avec version courante, lien releases GitHub, configuration complète, dépendances

### Fixed
- Cohérence du port entre tous les fichiers de configuration (Docker, dev, nginx, vite)
