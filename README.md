# StaffDPapp — Staff Delegation Application

> ⚠️ **Experimental application** — This software is provided for demonstration purposes only. It does not constitute legal advice and is not guaranteed to comply with current Luxembourg legislation. Any use is at the user's own risk. Consult a qualified professional or the [Chambre des Salariés (CSL)](https://www.csl.lu) for any question related to labour law.

Management tool for **staff delegations** in Luxembourg, inspired by the Labour Code (Art. L.412-1, L.414-2, L.414-3, L.415-5, L.416-1).

Current version: **2026.08.011** — [See GitHub releases](https://github.com/LostInTheBugs/StaffDPapp/releases)

## Features

- 🏛️ **Delegation creation**: name, company, headcount → automatic computation of the number of members/deputies
- 👥 **Organisation chart**: board (president, vice-president, secretary) + members + deputies + special designations
- 📅 **Meetings**: calendar, invitations, agenda items, management invitation (J+5 minimum), stats 6 meetings/year including 3 with management
- ⏱️ **My hours**: mandate hours tracking with legal weekly credit (Art. L.415-5)
- 🔐 **Authentication**: JWT, math CAPTCHA, TOTP MFA, multi-language (FR/EN/DE/PT)
- 📝 **Minutes (PV)**: sectioned minutes (internal / shared-with-management), draft & validated statuses, direction preview
- 🔐 **Vault (coffre)**: client-side AES-256-GCM encryption, Argon2id-wrapped DEK, auto-lock on inactivity — plaintext never leaves the browser
- 👁️ **Direction preview + PDF**: management-only projection of shared sections, decrypted in-browser, PDF export
- 📧 **Notifications**: convocations, validated-minutes alerts, member invitations, meeting reminders — configured by the delegation admin, no external infrastructure required:
  - **`.eml` files** (no SMTP access needed — download individually or as a batch)
  - **SMTP** (authenticated or not, STARTTLS/SSL, retry, test email)
  - **Standalone CLI** (`email_sender.py`, Python stdlib) — export JSON, run on any machine with SMTP access
- 🔑 **Secure sharing with management**: link `/p/<token>` + one-time reading code — the server never sees plaintext (DEK wrapped under the code, decrypted in the recipient's browser), 14-day expiry, revocation, PDF export
- 🚀 **Update banner**: notifies when a new version is released on GitHub (the app's only external link)
- 📋 **Consultations (Art. L.414-3)**: opinion/consultation tracking with the employer — 13 legal domains, 2-month decision deadline for internal rules, motivated answer required, direction emails + overdue reminders
- 📊 **Semiannual statistics (Art. L.414-3)**: workforce by sex, per semester (S1/S2), ratio visualization, history managed by the board
- 👤 **My profile**: photo, language, password change, MFA

## Demo

**Test accounts** (Demo organisation, 120 employees, 5 members + 5 deputies):

| Email | Name | Status | Role |
|-------|------|--------|------|
| `sophie@demo.lu` | Sophie Muller | Member | President |
| `marc@demo.lu` | Marc Weber | Member | Vice-president |
| `laura@demo.lu` | Laura Schmit | Member | Secretary |
| `tom@demo.lu` | Tom Wagner | Member | Member |
| `emma@demo.lu` | Emma Kirsch | Member | Member |
| `paul@demo.lu` | Paul Hoffmann | Deputy | Member |
| `anna@demo.lu` | Anna Klein | Deputy | Member |
| `david@demo.lu` | David Fischer | Deputy | Member |
| `clara@demo.lu` | Clara Becker | Deputy | Member |
| `lucas@demo.lu` | Lucas Thill | Deputy | Member |

All passwords: `demo123456`

- 🎮 **Demo**: https://staffdpapp.cloudfr.net

## Installation and deployment

### Prerequisites

- Docker and Docker Compose
- Node.js 20+ (for frontend development)
- Python 3.11+ (for backend development)

### Local development

```bash
# Backend (port 8005 by default)
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
# Build and launch
docker compose up -d --build

# Seed (after volume deletion)
bash seed.sh
```

## Configuration

Copy `.env.example` to `.env` and adjust the variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `SD_PORT` | Backend listen port | `8005` |
| `SD_SECRET_KEY` | JWT signing key | `change-me-in-production-use-openssl-rand-hex-32` |
| `SD_DATABASE_URL` | Database URL | `sqlite:///./data/staff_delegation.db` |
| `SD_ACCESS_TOKEN_EXPIRE_MINUTES` | JWT token expiration | `1440` (24h) |

The port can be overridden via the `SD_PORT` environment variable in all contexts (Docker, local development). All configuration files reference port 8005 by default.

## Main dependencies

- **Frontend**: React 18, TypeScript, Vite, React Router 6
- **Backend**: Python 3.11, FastAPI, SQLAlchemy, python-jose, pyotp
- **Database**: SQLite (development), PostgreSQL (production recommended)
- **Reverse proxy**: Traefik + Let's Encrypt (HTTPS)

## Upgrade

> **⚠️ Updating to the next version logs out all users.** Previously issued JWT tokens are invalidated: everyone will need to log in again. See [CHANGELOG.md](CHANGELOG.md) for details.

**Procedure:**

1. Backup the database: `docker compose exec backend cp /app/data/staff_delegation.db /app/data/backup-$(date +%F).db`
2. Pull the new version: `git pull`
3. Rebuild: `docker compose up -d --build`
4. Apply migrations: `docker compose exec backend alembic upgrade head`

Alembic migrations preserve existing data — **do not delete the volume**.
If the email normalization migration stops, two accounts differ only by case: the error message lists the duplicates to resolve before retrying.

## Tech stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, TypeScript, Vite |
| Backend | Python 3.11, FastAPI, SQLAlchemy |
| Database | SQLite |
| Reverse proxy | Traefik + Let's Encrypt (HTTPS) |
| Deployment | Docker Compose |

## Development cost (LLM)

This project was built entirely through AI-assisted sessions (Hermes Agent, deepseek-v4-pro / deepseek-v4-flash). Usage so far (cumulative as of 2026-08-02):

| Metric | Value |
|---|---|
| Input tokens | 1 798 041 |
| Output tokens | 817 279 |
| **Total (input + output)** | **2 615 320** |
| Cache read (reused at reduced price) | 352 716 416 |
| API calls | 1 927 |
| **Estimated cost** | **≈ 2.65 USD** |

Full breakdown: [TOKENS.md](TOKENS.md).

## Legal references

- Art. L.412-1: Number of delegates according to headcount
- Art. L.414-2/3: Special designations (health/safety, equality)
- Art. L.415-5: Weekly hours credit
- Art. L.416-1: Board (president, vice-president, secretary)

More info: [CSL - Means available to the delegation](https://www.csl.lu/en/your-rights/employees/social-dialogue/staff-delegation/means-available-to-the-delegation/)
