# StaffDPapp — Staff Delegation Application

> ⚠️ **Application expérimentale** — Ce logiciel est fourni à titre de démonstration uniquement. Il ne constitue pas un conseil juridique et n'est pas garanti conforme à la législation luxembourgeoise en vigueur. Toute utilisation se fait aux risques et périls de l'utilisateur. Consultez un professionnel qualifié ou la [Chambre des Salariés (CSL)](https://www.csl.lu) pour toute question relative au droit du travail.

Outil de gestion pour les **délégations du personnel** au Luxembourg, inspiré du Code du travail (Art. L.412-1, L.414-2, L.414-3, L.415-5, L.416-1).

Version courante : **2026.08.001** — [Voir les releases GitHub](https://github.com/LostInTheBugs/StaffDPapp/releases)

## Fonctionnalités

- 🏛️ **Création de délégation** : nom, entreprise, effectif → calcul automatique du nombre de titulaires/suppléants
- 👥 **Organigramme** : bureau (président, vice-président, secrétaire) + titulaires + suppléants + désignations spéciales
- 📅 **Réunions** : calendrier, invitations, points à l'ordre du jour, invitation de la direction (J+5 minimum), stats 6 réunions/an dont 3 avec direction
- ⏱️ **Mes heures** : suivi des heures de mandat avec crédit hebdomadaire légal (Art. L.415-5)
- 🔐 **Authentification** : JWT, CAPTCHA mathématique, MFA TOTP, multi-langue (FR/EN/DE/PT)
- 👤 **Mon profil** : photo, langue, changement de mot de passe, MFA

## Démo

**Comptes de test** (organisation Demo, 120 salariés, 5 titulaires + 5 suppléants) :

| Email | Nom | Statut | Fonction |
|-------|-----|--------|----------|
| `sophie@demo.lu` | Sophie Muller | Titulaire | Présidente |
| `marc@demo.lu` | Marc Weber | Titulaire | Vice-président |
| `laura@demo.lu` | Laura Schmit | Titulaire | Secrétaire |
| `tom@demo.lu` | Tom Wagner | Titulaire | Membre |
| `emma@demo.lu` | Emma Kirsch | Titulaire | Membre |
| `paul@demo.lu` | Paul Hoffmann | Suppléant | Membre |
| `anna@demo.lu` | Anna Klein | Suppléant | Membre |
| `david@demo.lu` | David Fischer | Suppléant | Membre |
| `clara@demo.lu` | Clara Becker | Suppléant | Membre |
| `lucas@demo.lu` | Lucas Thill | Suppléant | Membre |

Tous MDP : `demo123456`

- 🎮 **Demo** : https://staffdpapp.cloudfr.net

## Installation et déploiement

### Prérequis

- Docker et Docker Compose
- Node.js 20+ (pour le développement frontend)
- Python 3.11+ (pour le développement backend)

### Développement local

```bash
# Backend (port 8005 par défaut)
cd backend
pip install -r requirements.txt
SD_PORT=8005 python -m uvicorn app.main:app --host 0.0.0.0 --port 8005 --reload

# Frontend (port 5173)
cd frontend
npm install
npm run dev
```

### Docker Compose

```bash
# Build et lancement
docker compose up -d --build

# Seed (après suppression du volume)
bash seed.sh
```

## Configuration

Copier `.env.example` vers `.env` et adapter les variables :

| Variable | Description | Défaut |
|----------|-------------|--------|
| `SD_PORT` | Port d'écoute du backend | `8005` |
| `SD_SECRET_KEY` | Clé de signature JWT | `change-me-in-production-use-openssl-rand-hex-32` |
| `SD_DATABASE_URL` | URL de la base de données | `sqlite:///./data/staff_delegation.db` |
| `SD_ACCESS_TOKEN_EXPIRE_MINUTES` | Expiration des tokens JWT | `1440` (24h) |

Le port est surchargeable via la variable d'environnement `SD_PORT` dans tous les contextes (Docker, développement local). Les fichiers de configuration référencent tous le port 8005 par défaut.

## Dépendances principales

- **Frontend** : React 18, TypeScript, Vite, React Router 6
- **Backend** : Python 3.11, FastAPI, SQLAlchemy, python-jose, pyotp
- **Base de données** : SQLite (développement), PostgreSQL (production recommandé)
- **Reverse proxy** : Traefik + Let's Encrypt (HTTPS)

## Stack technique

| Couche | Technologie |
|--------|-------------|
| Frontend | React 18, TypeScript, Vite |
| Backend | Python 3.11, FastAPI, SQLAlchemy |
| Base de données | SQLite |
| Reverse proxy | Traefik + Let's Encrypt (HTTPS) |
| Déploiement | Docker Compose |

## Références légales

- Art. L.412-1 : Nombre de délégués selon l'effectif
- Art. L.414-2/3 : Désignations spéciales (sécurité/santé, égalité)
- Art. L.415-5 : Crédit d'heures hebdomadaire
- Art. L.416-1 : Bureau (président, vice-président, secrétaire)

Plus d'infos : [CSL - Moyens à disposition de la délégation](https://www.csl.lu/fr/vos-droits/salaries/dialogue-social/representation-du-personnel/moyens-a-disposition-de-la-delegation-du-personnel/)
