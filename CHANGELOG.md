# Changelog

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
