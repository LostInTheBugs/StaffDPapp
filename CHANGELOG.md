# Changelog

## [2026.08.029] — 2026-08-20 (test pre-release)

### Added — organization customization: feature modules, company logo, contact page + demo reset (personnalisation, logo, contact, reset démo)
- **🧩 Optional feature modules** (admin toggles in My organisation → "Fonctionnalités activées"): elections, time tracking (Mes heures), notice board, compliance cockpit, consultations, workforce stats + annual report, delegate activities, legal pages (formation/register/protection), contact page. Disabled module → nav links hidden, direct URL access redirected, **backend 403 on every route of the module** (new `require_module()` dependency on 9 routers). Default: all enabled (no behaviour change for existing orgs). Migration `20260801_0014` (part 1: `enabled_modules`).
- **🏷️ Company logo**: admin uploads an image (PNG/JPG/SVG, data URL ≤ 512 KB) shown in the app header on every page AND on the login screen before authentication — the login form takes the organisation identifier (slug, remembered in localStorage) and displays the logo + company name via a new public endpoint `GET /api/organizations/{slug}/public`. `PUT/DELETE /api/organization/logo` (admin).
- **📇 Staff delegation contact page** (`/contact`, link visible to all members): contact email, phone and office hours — editable by the admin in My organisation — plus the bureau table (president, vice-president, secretary, admins).
- **🔄 Demo auto-reset** (`backend/scripts/reset_demo.py`, cron 06:30 UTC on the demo host): every morning all demo accounts' passwords return to `demo123456`, TOTP is disabled, and the vault envelope is restored to the originally captured one — the vault re-locks to its demo password **without losing encrypted minutes** (same DEK, envelope swap only; the server never sees passwords — `reset_envelope` stores the encrypted envelope). Migration `20260801_0015`.
- **📚 Demo seed data** (`backend/scripts/seed_demo_data.py`, idempotent): 7 sample meetings (6 in 2026, 3 with direction — compliance green), 2 consultations (1 pending, 1 closed with answer), designated delegates (Marc 🛡️, Laura ⚖️) + 3 activities, semester workforce stats S1 2026, pinned notice, compliance events (plenary, bureau names), current-month hours, and an announced election with 2 eligible candidates.
- **🧹 Bug fixes**: `queue_email` idempotence contract restored (returned the existing outbox row instead of `None`, inflating reminder counters); compliance-reminder scan fixed (`WorkforceStat` has no `year` column — filter by `semester`; `recipient_name` must be in the template context); migration `20260801_0013` made idempotent (missing guards would crash fresh deployments).
- Tests: 7 new backend (modules, logo, contact) — **303 total**; frontend 115 total. i18n FR/EN/DE/PT/LB (parity: 465 keys).

## [2026.08.027] — 2026-08-19 (test pre-release)

### Added — Lëtzebuergesch (Luxembourgish) interface language
- **🇱🇺 New language: Lëtzebuergesch** — full UI translation (384 keys, parity with FR/EN/DE/PT verified programmatically), selectable in the language picker (Profile + login screen) and persisted per user (backend accepts `lb`).
- Legal terms follow official Luxembourgish usage (*Personalvertriedung*, *Plenierversammlung*, *Recuperatiounsschlëssel*, *Walbarkeet*, *Schwarzt Brëtt*…); article numbers stay in French (L.414-16…).
- No schema change (no migration). Tests: backend auth language validation extended to `lb` — 284 total.

## [2026.08.025] — 2026-08-19 (test pre-release)

### Added — virtual notice board, compliance cockpit, elections module (tableau d'affichage, conformité, élections)
- **📌 Virtual notice board** (`/notices`, Art. L.414-16 — verified on Legilux 2026-08-19: posting on supports accessible to staff, *including electronic ones*): the delegation, the safety/health delegate and the equality delegate may post (admin, bureau, `is_delegue_securite_sante`, `is_delegue_egalite`); **all staff including plain employees read the board** (no write access); title + body + pin; edit/delete by author or bureau; org isolation. Migration `20260801_0010`.
- **⚖️ Compliance cockpit** (`/compliance`): live status of 10 legal obligations aggregated from real app data — annual meetings L.415-6 (6/year, 3 with direction), plenary assembly L.415-7 (1/year, logged), semester workforce stats L.414-3, consultations with overdue tracking L.414-3, validated minutes L.416-5, designated delegates L.414-14/15, bureau names communicated to the head of company L.416-1 (3-day rule, logged), election renewal window L.413-2 (Feb 1–Mar 31), eco-financial reports L.414-5 (≥150 employees, 2/year, logged), notice board activity L.414-16. Bureau/admin log events (plenary, eco report, names communication) with history. Migration `20260801_0011`.
- **🗳️ Elections module** (`/elections`, L.413-1 to L.413-6): full cycle — announcement poster (PDF, L.413-2), candidacies with **automatic eligibility check** (L.413-4: 18yo, 12-month seniority, honor declaration on exclusions), **anonymous secret ballot by construction** (identity in `election_ballots`, choice in `election_votes` — no join possible, verified by test), d'Hondt proportional tally (≥100 employees) or relative majority (<100), titulaires + suppléants per list, constitutive meeting reminder (L.416-1). Bureau/admin manage, all members vote once. Migration `20260801_0012`.
- Tests: 15 new (notices + compliance) + 6 new (elections) — **293 total**. Frontend i18n FR/EN/DE/PT for all three modules.

## [2026.08.023] — 2026-08-19 (test pre-release)

### Added — mass invitations + member lifecycle (invitation en masse, gestion des membres)
- **👥 Mass invitations** (admin dashboard): paste one `email;first;last` per line (semicolon or comma separated) → one unique invitation code per person, shown once with a per-line copy button. Per-line results never fail the whole batch: ✅ created / ⚠️ duplicate (existing account, pending invitation, or same batch) / ❌ invalid line. Batch capped at 200.
- **Mass-invited users are plain employees** (`delegue_status=employe`, role member) — the rule forcing every non-elected employee to be a sécurité/santé designated delegate is relaxed (égalité → elected and non-elected → no bureau function rules are kept). This unblocks real employee accounts (e.g. for anonymous surveys).
- **🗑️ Remove member** (`DELETE /api/organization/members/{id}`, admin): soft-delete (`is_active=False`) — login and API blocked, member disappears from lists, history (minutes, hours, meetings) stays intact. Guards: cannot remove yourself, cannot remove the last admin, cross-org targets → 404.
- **Batch invitation codes** use a lighter Argon2id (16 MiB, time_cost 1 — codes carry ~130 bits of entropy so brute force stays infeasible; parameters are embedded in the hash, so the standard verifier accepts them). 200 invitations now take seconds instead of minutes.
- No schema change (no migration). Tests: 12 new backend (admin-only, employee creation, duplicates, partial invalid lines, batch cap, relaxed rule, remove member flow/guards) — 263 total. Frontend i18n FR/EN/DE/PT.

## [2026.08.021] — 2026-08-14 (test pre-release)

### Added — designated delegates activities module (activités des délégués désignés)
- **🛡️ New "Activités délégués" page** (`/delegate-activities`): control tours, enquiries, trainings, reports (sécurité/santé L.414-14) and actions, awareness sessions, trainings, reports (égalité L.414-15) — dated, described, archived per year with category/domain filters.
- **Access rules**: every member reads; the designated delegate logs their own activities; bureau members log for any designated delegate; only the author or bureau deletes. Category/domain coherence validated (422), target must be currently designated (400).
- **Annual report integration**: designated-delegate rows now show the yearly activity count + breakdown by category (PDF table gains an "Activités" column).
- Migration `20260801_0009` (delegate_activities). Tests: 7 new backend (read/write rules, self-only for non-bureau delegates, bureau for any, non-designated rejected, category/domain 422, delete rules, year filter) — 251 total; frontend 115 total. i18n FR/EN/DE/PT.

## [2026.08.020] — 2026-08-14 (test pre-release)

### Added — annual activity report (rapport d'activité annuel)
- **`GET /api/stats/annual-report?year=YYYY`** (bureau/admin): one-year aggregation — workforce by sex (L.414-3), delegation hours by category and per member (L.415-5), meetings (total + with direction, L.415-6), consultations (total + answered, L.414-3), **designated delegates** (sécurité/santé L.414-14, égalité L.414-15): declared hours per delegate + legal credits (equality monthly credit by workforce bracket, safety training 40h/mandate).
- **📄 "Rapport d'activité annuel" button** on the statistics page with a year selector: single A4 PDF (embedded Unicode font, purged metadata) covering the 5 sections.
- No schema change (no migration). Tests: 6 new backend (bureau-only 403, year 422, aggregates, designated delegates, credit brackets) — 244 total; 4 new frontend (valid PDF, all sections present, empty year, metadata purge) — 115 total.

## [2026.08.019] — 2026-08-14 (test pre-release)

### Added — vault recovery key (coffre : clé de récupération)
- **Recovery key**: a one-time-displayed key (`XXXX-XXXX-XXXX-XXXX`, 128-bit) generated at vault creation or on demand, unlocking the vault when the password is forgotten and letting the user set a new password — **zero data loss, zero security compromise**: the server only stores the opaque envelope (PBKDF2-SHA256 wrapped DEK), never the key itself.
- **Unlock overlay**: "Forgot password? → Use my recovery key" link (only when configured), then a guided new-password step (DEK re-wrapped client-side).
- **Organization settings**: manage section — generate / replace (invalidates the previous key) / revoke, with a clear one-time display + storage warning.
- Migration `20260801_0008` (4 optional columns on vault_keys). Tests backend (PUT/DELETE, bureau-only, size guards, status reporting, replace semantics) — 238 total; frontend (format, wrap/unwrap roundtrip, wrong key, uniqueness) — 111 total. i18n FR/EN/DE/PT.

## [2026.08.018] — 2026-08-14 (test pre-release)

### Added — minutes archive
- **📚 Archive page** (`/archive`): metadata library of all delegation minutes — meeting title/date, status badge (draft/validated), author, validator + validation date, 🔒 marker for encrypted content (vault). Search by meeting title + status filter.
- **`GET /api/minutes`**: archive endpoint returning metadata ONLY — never section content (even ciphertext stays out of the list).
- Clicking a row opens the existing minutes detail page (content decrypts in-browser when the vault is unlocked).
- Tests backend (metadata only, no content in payload, validated info) — 229 total. i18n FR/EN/DE/PT.

## [2026.08.017] — 2026-08-14 (stable)

Stable release validated by the user — same features as v2026.08.016
(test pre-release). See the 2026.08.016 section for full details.

## [2026.08.016] — 2026-08-14 (test pre-release)

### Added — workforce statistics PDF report
- **🖨️ Report PDF button** on the statistics page: A4 document with the organisation name, the semiannual table (semester, men, women, total, %), a cumulative total row and the legal L.414-3 quote in the footer.
- Generated client-side (pdf-lib + embedded Unicode font), metadata purged like the minutes PDF. Tests: PDF validity, text content, metadata purge, empty history — 105 frontend tests total.

## [2026.08.015] — 2026-08-14 (stable)

Stable release validated by the user — same features as v2026.08.014
(test pre-release). See the 2026.08.014 section for full details.

## [2026.08.014] — 2026-08-14 (test pre-release)

### Added — hours CSV export
- **`GET /api/time/export?month=YYYY-MM`**: CSV export (UTF-8 BOM, Excel-ready) — members export only their own entries; board/admin export the whole delegation with member name/email columns.
- **Buttons on "My hours"**: ⬇️ Export (mine) for everyone, ⬇️ Export delegation (board only), respecting the month filter. Invalid month → 422.
- Tests backend (member isolation, board global export, CSV validity, 422) — 226 total.

## [2026.08.013] — 2026-08-14 (test pre-release)

### Added — dashboard vitrine (overview widgets)
- **Overview cards** on the dashboard: annual meetings (count vs. the 6/year legal minimum, management-invited count vs. 3, next upcoming meeting), consultations (pending, overdue badge ⚠️, received/closed), hours logged this month vs. credit, latest workforce-by-sex with ratio bar, delegation members (titular/deputies).
- i18n FR/EN/DE/PT. No backend change (reuses existing endpoints).

## [2026.08.012] — 2026-08-14 (stable)

Stable release validated by the user — same features as v2026.08.011
(test pre-release). See the 2026.08.011 section for full details.

## [2026.08.011] — 2026-08-14 (test pre-release)

### Added — semiannual workforce statistics (L.414-3)
- **Statistics page** (`/workforce-stats`): the semiannual workforce statistics broken down by sex that the employer must compile and communicate to the staff delegation (Art. L.414-3).
- **Latest semester card**: men / women / total with a visual ratio bar (percentages).
- **Report history**: table of all published semesters (S1/S2), board can add, edit and delete reports (one entry per semester — 409 on duplicates, validated format `YYYY-1`/`YYYY-2`).
- **Access control**: visible by all members; creation, edition and deletion reserved to the board (president, vice-president, secretary) and admins.
- i18n FR/EN/DE/PT + nav link, tests backend (CRUD, permissions, IDOR, validation) and frontend.

### Migration
- Alembic `20260801_0007` (idempotent): `workforce_stats` table.

## [2026.08.010] — 2026-08-14 (stable)

Stable release validated by the user — same features as v2026.08.009
(test pre-release). See the 2026.08.009 section for full details.

## [2026.08.009] — 2026-08-14 (test pre-release)

### Added — L.414-3 consultations tracking
- **Consultations page** (`/consultations`): track the delegation's consultations with the employer (Art. L.414-3 of the Labour Code) — opinions and proposals on working conditions, internal rules, working time, pension scheme, training plans, internal reassignment, plus prior information/consultation (collective redundancies, transfers, temporary agency workers).
- **13 legal domains** (working conditions, internal rules, working time, pension, training, reassignment, collective redundancies, transfer, agency workers, social works, gender statistics, telework/disconnection, other).
- **Legal rules enforced**: internal rules → employer's decision due within **2 months** (response deadline auto-set to +60 days); **motivated answer required** to close a consultation (L.414-1: consultation = exchange of views + motivated answer — 422 without it); overdue deadline flagged in the UI and in stats.
- **Access control**: visible by all members; creation, answer recording, closing and deletion reserved to the board (president, vice-president, secretary) and admins.
- **Notifications**: `consultation_created` email to the direction (via the existing outbox, direction email from config) + `consultation_reminder` when the response deadline is exceeded (max 1 reminder/day per consultation, scanned at startup). Templates FR/EN/DE/PT.
- Stats badges: total / pending / **overdue ⚠️** / answers received / closed.

### Migration
- Alembic `20260801_0006` (idempotent): `consultations` table.

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
