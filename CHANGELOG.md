# Changelog

## [2026.08.008] — 2026-08-13 (stable)

Version stable validée par l'utilisateur — fonctionnalités identiques à la v2026.08.007
(pré-release de test). Voir la section 2026.08.007 pour le détail complet.

## [2026.08.007] — 2026-08-13 (pré-release de test)

### Ajouté — Notifications par email (configurables par l'administrateur de la délégation)
- **3 modes d'acheminement**, interchangeables sans changer l'application :
  1. **Fichiers .eml** (aucun SMTP requis) : téléchargement individuel + export en lot — cas « serveur interne sans accès au SMTP »
  2. **SMTP** : envoi direct (STARTTLS/SSL, authentifié ou non), retry automatique, email de test
  3. **Standalone** : export JSON + CLI `email_sender.py` (Python stdlib) exécutable sur n'importe quelle machine ayant un accès SMTP
- **File de sortie unique (outbox)** : statuts (prêt/envoyé/échec/annulé), réessai, annulation, marquage manuel (mode standalone)
- **Déclencheurs** : convocation de réunion (membres + direction), rappel J-X avant réunion, invitation membre (avec le code), **PV validé → direction** (lien sécurisé), **PV validé → ensemble de la délégation**
- **Partage sécurisé du PV avec la direction** : lien `/p/<token>` + code de lecture — le serveur ne voit jamais le clair (enveloppe DEK chiffrée sous le code, déchiffrement dans le navigateur du destinataire), expiration 14 jours, révocation possible, export PDF côté lecteur
- Templates multilingues FR/EN/DE/PT (langue du destinataire)
- **Bandeau « nouvelle version disponible »** (GitHub releases) — seul lien externe de l'application

### Migration
- Alembic `20260801_0005` (idempotente) : tables `email_configs`, `email_outbox`, `minute_share_links`

## [2026.08.006-c2] — 2026-08-13

### Corrigé
- **Preview direction inutilisable avec coffre actif** : `direction_preview` renvoyait le digest HMAC (32 o) au lieu du ciphertext pour les sections chiffrées → DOMException AES-GCM silencieuse, modale jamais affichée, export PDF bloqué. La preview renvoie désormais les sections `partage` telles quelles (ciphertext + nonce), renumérotation continue conservée (pas de fuite du compte total). +1 test de non-régression (193 backend).

## [2026.08.006-c1] — 2026-08-13

### Corrigé
- **Nouvelles sections envoyées en clair quand le coffre est actif** : `prepareSectionsForSave` routait les sections sans enveloppe (`_encrypted: null`) en clair → le serveur les rejetait (422) → impossibilité d'ajouter une section avec coffre actif. Les nouvelles sections sont désormais chiffrées dès que le coffre est actif (`vault.status !== 'disabled'`), fail-closed (`VaultLockedError` si verrouillé). +2 tests (91 frontend).

## [2026.08.006] — 2026-08-12

### Ajouté
- **Coffre-fort des PV** : chiffrement de bout en bout optionnel par organisation (`pv_vault_enabled`). Les contenus des sections sont chiffrés en AES-256-GCM dans le navigateur ; le serveur ne voit jamais le clair.
- **Enveloppe de clé** : chaque membre dérive une KEK par Argon2id depuis son mot de passe. La DEK est générée dans le navigateur et n'existe jamais en clair hors de celui-ci.
- **Interface de déverrouillage** : badge d'état du coffre (verrouillé/déverrouillé/désactivé) dans l'interface, formulaire de déverrouillage par mot de passe, création du coffre par un membre du bureau avec avertissement d'irréversibilité.
- **Invitations sécurisées** : code d'invitation Crockford base32 de 26 caractères (~130 bits), hashé côté serveur (Argon2id). Le code n'est affiché qu'une seule fois. L'enveloppe de clé est transmise avec l'invitation, chiffrée sous le code.
- **Chiffrement transparent des PV** : au chargement, les sections chiffrées sont déchiffrées avec la DEK de session. À l'enregistrement, seules les sections modifiées sont rechiffrées (nonce aléatoire par section). Le `content_digest` (HMAC-SHA256 du clair, keyé par la DEK) permet au serveur de détecter les changements sans voir le contenu.
- **Export PDF avec coffre** : les sections de la preview direction sont déchiffrées avant l'export PDF. Export impossible si le coffre est verrouillé (pas de PDF vide ni de ciphertext transmis).
- **Titres neutres conseillés** : rappel discret dans l'interface lorsque le coffre est actif, invitant à des intitulés de sections neutres (les titres restent en clair).
- **Migrations Alembic idempotentes** : compatibles avec `create_all` de l'app, l'ordre de démarrage app/migration n'a plus d'importance.

### Corrigé
- **Bundle navigateur plantait** : `require('@pdf-lib/fontkit')` laissé en CJS dans le bundle → `ReferenceError: require is not defined` → page blanche. Import ESM propre, police DejaVuSans embarquée.
- **Contournement MFA** : `get_current_user` rejette les tokens temporaires MFA (`mfa: true`). Un claim `typ` explicite (`access` / `mfa_pending`) est vérifié.
- **CAPTCHA obligatoire** : les champs `captcha_id` et `captcha_answer` sont requis côté schéma Pydantic sur `/login`, `/join` et `/organizations`.
- **Code d'invitation lié à l'email** : `join_organization` filtre sur `code` ET `email`, empêchant l'usurpation d'identité via un code intercepté.

### Modifié
- **PV sectionné** : un PV est composé de sections marquées `interne` ou `partage`. La version direction est une projection, jamais stockée.
- **Double validation** : la validation du PV est bloquée pour le rédacteur ; seul un autre membre du bureau peut valider.
- **Export PDF direction** : généré côté client (`pdf-lib`), métadonnées purgées, numérotation continue, filtre fail-closed sur `visibility: 'partage'`.
- **Alembic** : migrations pour les tables `minutes`, `minute_sections`, `minute_publications`, `vault_keys` et la colonne `code_hash` sur `invitations` (9 invitations existantes migrées sans perte).

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
