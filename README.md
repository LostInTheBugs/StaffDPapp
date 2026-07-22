# Staff Delegation 🏢

Application web de gestion pour les **délégations du personnel** au Luxembourg.

Une personne arrivant sur le site peut :
- 🔑 Se connecter avec un accès existant
- ✉️ Créer un accès via un code d'invitation (rejoindre une délégation existante)
- 🏛️ Créer une nouvelle délégation du personnel (devient administrateur)

## Stack

| Couche | Technologie |
|--------|------------|
| Frontend | React 18 + TypeScript + Vite |
| Backend | Python FastAPI + SQLAlchemy |
| Base de données | SQLite (dev) / PostgreSQL (prod) |
| Auth | JWT + bcrypt |
| Déploiement | Docker Compose + Traefik |

## Installation (développement)

### Prérequis
- Python 3.11+
- Node.js 20+
- npm

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env   # adapter SD_SECRET_KEY
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Le frontend tourne sur `http://localhost:5173` avec proxy API vers le backend.

## Déploiement (Docker)

```bash
# Créer le réseau Traefik si pas déjà fait
docker network create traefik-public

# Lancer
docker compose up -d --build
```

Le frontend est exposé sur le port `8080`. Les labels Traefik sont préconfigurés pour les domaines :
- `staff-delegation.cloudfr.net` → frontend
- `sd-api.cloudfr.net` → backend API

## API

| Endpoint | Méthode | Auth | Description |
|----------|---------|------|-------------|
| `/api/health` | GET | - | Health check |
| `/api/auth/login` | POST | - | Connexion |
| `/api/auth/me` | GET | Bearer | Profil utilisateur |
| `/api/organizations` | POST | - | Créer une délégation |
| `/api/join` | POST | - | Rejoindre via code |
| `/api/invitations` | POST | Bearer | Créer une invitation (admin) |
| `/api/invitations` | GET | Bearer | Lister les invitations actives |
| `/api/dashboard` | GET | Bearer | Dashboard utilisateur |

## Structure du projet

```
staff-delegation/
├── backend/
│   ├── app/
│   │   ├── core/          # Config, sécurité, DB
│   │   ├── models/        # SQLAlchemy (User, Organization, Invitation)
│   │   ├── routes/        # Endpoints API
│   │   ├── schemas/       # Pydantic
│   │   └── main.py        # FastAPI app
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/           # Client API
│   │   ├── components/    # ProtectedRoute
│   │   ├── hooks/         # useAuth context
│   │   └── pages/         # Landing, Login, Join, Create, Dashboard
│   ├── Dockerfile
│   └── nginx.conf
├── docker-compose.yml
├── .env.example
└── LICENSE
```

## Licence

MIT — voir [LICENSE](LICENSE)
