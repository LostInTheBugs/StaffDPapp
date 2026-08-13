# Changelog

## [2026.08.008] — 2026-08-13 (stable)

Stable release validated by the user — same features as v2026.08.007
(test pre-release). See the 2026.08.007 section for full details.

## [2026.08.007] — 2026-08-13 (test pre-release)

### Added — Email notifications (configured by the delegation administrator)
- **3 delivery modes**, interchangeable without changing the app:
  1. **`.eml` files** (no SMTP required): individual download + batch export — for "internal server without SMTP access"
  2. **SMTP**: direct send (STARTTLS/SSL, with or without auth), automatic retry, test email
  3. **Standalone**: JSON export + `email_sender.py` CLI (Python stdlib) runnable on any machine with SMTP access
- **Single outbox queue**: statuses (ready/sent/failed/cancelled), retry, cancel, manual marking (standalone mode)
- **Triggers**: meeting invitation (members + management), reminder J-X before meeting, member invitation (with the code), **validated minutes → management** (secure link), **validated minutes → whole delegation**
- **Secure minutes sharing with management**: `/p/<token>` link + reading code — the server never sees plaintext (DEK wrapped under the code, decrypted in the recipient's browser), 14-day expiry, revocation, reader-side PDF export
- Multilingual templates FR/EN/DE/PT (recipient's language)
- **"New version available" banner** (GitHub releases) — the app's only external link

### Migration
- Alembic `20260801_0005` (idempotent): `email_configs`, `email_outbox`, `minute_share_links` tables

## [2026.08.006-c2] — 2026-08-13

### Fixed
- **Direction preview unusable with an active vault**: `direction_preview` returned the HMAC digest (32 bytes) instead of the ciphertext for encrypted sections → silent AES-GCM DOMException, modal never shown, PDF export blocked. The preview now returns the `partage` sections as-is (ciphertext + nonce), continuous renumbering preserved (no total count leak). +1 regression test (193 backend).

## [2026.08.006-c1] — 2026-08-13

### Fixed
- **New sections sent in clear text when the vault is active**: `prepareSectionsForSave` routed unwrapped sections (`_encrypted: null`) as plaintext → server rejected them (422) → impossible to add a section with an active vault. New sections are now encrypted as soon as the vault is active (`vault.status !== 'disabled'`), fail-closed (`VaultLockedError` if locked). +2 tests (91 frontend).

## [2026.08.006] — 2026-08-12

### Added
- **Minutes vault**: optional end-to-end encryption per organization (`pv_vault_enabled`). Section contents are AES-256-GCM encrypted in the browser; the server never sees plaintext.
- **Key envelope**: each member derives a KEK via Argon2id from their password. The DEK is generated in the browser and never exists in clear outside of it.
- **Unlock UI**: vault status badge (locked/unlocked/disabled), password unlock form, vault creation by a board member with irreversibility warning.
- **Secure invitations**: 26-character Crockford base32 invitation code (~130 bits), hashed server-side (Argon2id). The code is shown only once. The key envelope travels with the invitation, encrypted under the code.
- **Transparent minutes encryption**: on load, encrypted sections are decrypted with the session DEK. On save, only modified sections are re-encrypted (random nonce per section). The `content_digest` (HMAC-SHA256 of plaintext, keyed by DEK) lets the server detect changes without seeing content.
- **PDF export with vault**: direction preview sections are decrypted before PDF export. Export impossible while the vault is locked (no blank PDF, no ciphertext transmitted).
- **Neutral titles hint**: subtle reminder in the UI when the vault is active, suggesting neutral section headings (titles remain in clear text).
- **Idempotent Alembic migrations**: compatible with the app's `create_all`, app/migration startup order no longer matters.

### Fixed
- **Browser bundle crashed**: `require('@pdf-lib/fontkit')` left as CJS in the bundle → `ReferenceError: require is not defined` → blank page. Clean ESM import, embedded DejaVuSans font.
- **MFA bypass**: `get_current_user` rejects temporary MFA tokens (`mfa: true`). An explicit `typ` claim (`access` / `mfa_pending`) is verified.
- **Mandatory CAPTCHA**: `captcha_id` and `captcha_answer` are required in the Pydantic schemas on `/login`, `/join` and `/organizations`.
- **Invitation code bound to email**: `join_organization` filters on `code` AND `email`, preventing identity theft via an intercepted code.

### Changed
- **Sectioned minutes**: a minute is made of sections marked `interne` or `partage`. The management version is a projection, never stored.
- **Double validation**: minute validation is blocked for the author; only another board member can validate.
- **Management PDF export**: generated client-side (`pdf-lib`), purged metadata, continuous numbering, fail-closed filter on `visibility: 'partage'`.
- **Alembic**: migrations for `minutes`, `minute_sections`, `minute_publications`, `vault_keys` tables and the `code_hash` column on `invitations` (9 existing invitations migrated without loss).

## [2026.08.004] — 2026-08-12

### Added
- **Rate limiting** (anti brute-force): login and join 10 attempts/15 min/IP, mfa/login 10/15 min/IP, organization creation 5/1h/IP → HTTP 429
- **TOTP lockout**: 5 invalid codes → account blocked for 15 minutes (`totp_failed_attempts`, `totp_locked_until` columns)
- **Invitation expiry**: 30 days (`invitations.expires_at`, backfill +30 days on existing ones)
- **Password policy**: minimum 8 characters (backend + frontend forms)
- **Alembic migration** `4b6d8e9f0a1c` (chain: baseline → lowercase emails → hardening) — no more volume deletion on schema changes
- **13 hardening tests** (117 total)

### Changed
- Deployment: `alembic stamp 31140e6e07a7` + `upgrade head` instead of deleting the volume

## [2026.08.002] — 2026-08-12

### Added
- Backend test suite (104 tests: security, legal scales, MFA, CAPTCHA, emails) — merge of the `fix/securite-auth` branch
- Alembic migration (baseline + lowercase email normalization)

### Fixed
- **Broken meeting stats**: `/api/meetings/stats` returned 422 (route ordering) — the banner displayed `undefined/6`
- **Bypassable CAPTCHA**: now mandatory backend-side on login/join/organization creation (422 without captcha)
- **MFA bypass**: MFA-pending tokens (`typ=mfa_pending`) can no longer access protected routes
- **Invitation**: the code is now bound to the email (impossible to join with another identity)
- **L.412-1 scale >5500 employees**: rounded down (full 500-slice), per the official text
- **Email normalization**: case-insensitive comparison (login with `Sophie@Demo.lu` accepted)
- **Frontend version aligned**: `index.html` and footer still displayed 2026.07.001

## [2026.08.001] — 2026-08-01

### Added
- `VERSION` file at the root containing version `2026.08.001`
- `CHANGELOG.md` with version tracking
- `SD_PORT` environment variable for the backend listening port

### Changed
- Project version unified to `2026.08.001` in all manifests (`package.json`, `app/main.py`)
- Default backend listening port: `8000` → `8005`
- Backend Dockerfile: the port is now overridable via `${SD_PORT:-8005}` instead of hardcoded
- `.env.example`: added `SD_PORT=8005`
- `docker-compose.yml`: added `SD_PORT` in the backend environment variables
- `frontend/nginx.conf`: API proxy to the backend on port `8005`
- `frontend/vite.config.ts`: development proxy to `localhost:8005`
- `README.md`: enriched with current version, GitHub releases link, full configuration, dependencies

### Fixed
- Port consistency across all configuration files (Docker, dev, nginx, vite)
