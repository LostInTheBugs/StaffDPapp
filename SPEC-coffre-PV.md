# StaffDPapp — Spécification : coffre-fort PV + double version

Destinataire : Hermes Agent
Version : 1.0 — 30 juillet 2026
Portée : module PV (procès-verbaux) uniquement. Le reste de la base reste en clair.

---

## 0. Décisions d'architecture actées

| Décision | Choix |
|---|---|
| Accès direction | **Export uniquement.** La direction n'a jamais de compte. Aucune clé ne sort de la délégation. |
| Modèle des deux versions | **PV sectionné + projection.** Un seul PV, sections marquées `interne` ou `partage`. La version direction est générée, jamais ressaisie. |
| Emplacement de la crypto | **Client (navigateur, WebCrypto).** Le backend ne voit jamais de PV en clair. |
| Activation | **Optionnelle par organisation** (`pv_vault_enabled`). Sans le coffre, les PV sont stockés en clair comme aujourd'hui. |

Conséquences assumées :
- Pas de recherche plein texte côté serveur dans les PV chiffrés.
- Perte du mot de passe d'un membre = perte de son accès (pas des PV, tant qu'un autre membre détient la DEK).
- Perte de **tous** les membres = perte définitive des PV. Prévoir l'export papier/PDF comme filet.

---

## 1. Modèle cryptographique (enveloppe)

### 1.1 Clés

- **DEK** (Data Encryption Key) : 256 bits aléatoires, **une par organisation**, générée dans le navigateur du créateur du coffre (`crypto.getRandomValues`). Chiffre tous les contenus de PV en AES-256-GCM.
- **KEK** (Key Encryption Key) : dérivée du mot de passe de chaque membre via **Argon2id** (paramètres : m=64 Mio, t=3, p=1, salt aléatoire 16 octets par utilisateur, stocké en clair). Sert uniquement à envelopper la DEK.
- La DEK n'existe jamais en clair hors du navigateur, ni en base, ni dans les logs, ni en mémoire serveur.

### 1.2 Enveloppes stockées

Nouvelle table `vault_keys` :

```
id                 INTEGER PK
organization_id    FK  NOT NULL
user_id            FK  NULL   -- NULL si enveloppe d'invitation
invitation_id      FK  NULL   -- NULL si enveloppe de membre
wrapped_dek        BLOB NOT NULL  -- AES-GCM(KEK, DEK)
nonce              BLOB NOT NULL  -- 12 octets
kdf_salt           BLOB NOT NULL  -- 16 octets
kdf_params         TEXT NOT NULL  -- JSON : {"algo":"argon2id","m":65536,"t":3,"p":1}
dek_version        INTEGER NOT NULL DEFAULT 1
created_at         DATETIME
```

Contrainte : exactement un de `user_id` / `invitation_id` est non nul.

### 1.3 Cycle de vie

**Création du coffre** (par un membre du bureau) : le client génère la DEK, dérive sa KEK depuis son mot de passe, envoie `wrapped_dek` + `nonce` + `kdf_salt`. Le serveur stocke, sans jamais rien pouvoir déchiffrer.

**Ouverture de session** : au login, le client dérive la KEK (Argon2id en WebAssembly), récupère son enveloppe, déchiffre la DEK et la conserve **en mémoire JavaScript uniquement**. Jamais dans `localStorage`, `sessionStorage`, ni un cookie. Onglet fermé = DEK perdue, il faut ressaisir le mot de passe.

**Invitation d'un nouveau membre** : l'inviteur (qui détient la DEK) génère un **code d'invitation de 26 caractères en base32 Crockford** (≈130 bits d'entropie — remplace impérativement les 8 caractères actuels, qui ne font que 41 bits et sont brute-forçables en secondes). Le client dérive une KEK depuis ce code, enveloppe la DEK, et envoie l'enveloppe. **Le serveur stocke un hash du code (Argon2id), jamais le code lui-même** — c'est le point qui manque aujourd'hui et qui rendait l'idée initiale inopérante. Le code est transmis hors bande (papier, SMS, de vive voix).

**Inscription** : le nouveau membre saisit le code + son mot de passe. Le client déverrouille la DEK avec le code, la ré-enveloppe sous sa propre KEK, envoie la nouvelle enveloppe. Le serveur supprime alors l'enveloppe d'invitation.

**Changement de mot de passe** : ré-enveloppe côté client. Instantané, aucun rechiffrement de contenu.

**Départ d'un membre** : suppression de son enveloppe, puis **rotation de la DEK** (nouvelle DEK, rechiffrement de tous les PV côté client par un membre du bureau, `dek_version` incrémentée). Sans rotation, un ancien membre ayant copié la DEK garde l'accès. À exposer explicitement dans l'interface, pas en silence.

**Mot de passe oublié** : aucun mécanisme de récupération côté serveur — ce serait exactement le trou qu'on cherche à fermer. Un autre membre réinvite la personne, qui repart d'une nouvelle enveloppe.

---

## 2. Modèle de données PV

Nouvelle table `minutes` (PV) :

```
id                  INTEGER PK
meeting_id          FK -> meetings  NOT NULL
organization_id     FK  NOT NULL
status              ENUM('brouillon','valide','diffuse')  DEFAULT 'brouillon'
is_encrypted        BOOLEAN NOT NULL DEFAULT 0
dek_version         INTEGER NULL     -- NULL si non chiffré
created_by_id       FK -> users
validated_by_id     FK -> users  NULL
validated_at        DATETIME NULL
published_at        DATETIME NULL
created_at, updated_at
```

Nouvelle table `minute_sections` :

```
id              INTEGER PK
minute_id       FK  NOT NULL
position        INTEGER NOT NULL       -- ordre d'affichage
title           TEXT NOT NULL          -- toujours en clair (navigation)
visibility      ENUM('interne','partage') NOT NULL DEFAULT 'interne'
content         BLOB NOT NULL          -- texte clair OU AES-GCM(DEK, texte)
nonce           BLOB NULL              -- non NULL si chiffré
```

**Points de conception importants :**

- `visibility` par défaut à **`interne`**. Le défaut doit être le plus fermé : une section qu'on oublie de classer ne part pas à la direction.
- Le `title` reste en clair pour permettre la navigation et le sommaire. **Documenter ce choix** : les titres de sections fuient de l'information (« Litige M. X », « Préparation négociation salariale »). Conseiller dans l'interface des titres neutres et numérotés.
- La version direction n'est **jamais stockée**. Elle est générée à la demande par projection sur `visibility = 'partage'`, puis exportée en PDF.

---

## 3. Flux de diffusion (le garde-fou principal)

Une projection automatique peut avoir un bug ; un PV envoyé à la direction ne se rattrape pas. D'où une **barrière humaine obligatoire** :

1. Le secrétaire rédige le PV et classe chaque section.
2. Il demande la génération de la version direction.
3. **L'application affiche la version direction telle qu'elle sera transmise**, intégralement, dans un écran de prévisualisation distinct et visuellement différencié (bandeau « CE QUE LA DIRECTION VERRA »).
4. Un membre du bureau **autre que le rédacteur** valide explicitement (double contrôle, comme pour la validation des PV en pratique).
5. Le PDF est généré, `published_at` est horodaté, et l'événement est journalisé (qui a diffusé, quand, quelles sections, hash SHA-256 du PDF).

Après diffusion, toute modification d'une section `partage` doit forcer un nouveau cycle de validation et signaler que la version diffusée est obsolète.

---

## 4. Export PDF — pièges à éviter

L'export est le maillon où fuient réellement les documents caviardés :

- **Générer le PDF depuis les seules sections `partage`.** Ne jamais produire le PDF complet pour ensuite masquer : le texte masqué reste extractible.
- **Purger les métadonnées** : auteur, titre, producteur, dates de création du logiciel de rendu.
- Aucune numérotation de sections qui révèle les trous (ne pas afficher « 1, 2, 5, 7 » — renuméroter en continu, sinon la direction déduit l'existence et le volume des sections retirées).
- Pas de sommaire incluant les titres internes.
- **Générer le PDF côté client** (les données sont déchiffrées uniquement là). `pdf-lib` ou `jsPDF` conviennent ; pas d'aller-retour serveur avec du texte clair.
- Ajouter un test automatisé qui extrait le texte du PDF produit et **vérifie qu'aucun contenu de section `interne` n'y apparaît**. C'est le test le plus important de tout le module.

---

## 5. API

```
POST   /api/vault                    créer le coffre (wrapped_dek, nonce, kdf_salt, kdf_params)
GET    /api/vault/key                récupérer son enveloppe
PUT    /api/vault/key                ré-enveloppe (changement de mot de passe)
POST   /api/vault/rotate             rotation de DEK (bureau uniquement)
DELETE /api/vault/key/{user_id}      révoquer un membre (bureau uniquement)

POST   /api/meetings/{id}/minutes    créer un PV
GET    /api/minutes/{id}             lire (renvoie les blobs, le client déchiffre)
PUT    /api/minutes/{id}/sections    remplacer les sections
POST   /api/minutes/{id}/validate    valider (validateur ≠ rédacteur)
POST   /api/minutes/{id}/publish     marquer diffusé + journaliser le hash du PDF
```

Le serveur ne doit **jamais** exposer d'endpoint acceptant ou renvoyant du contenu de PV en clair quand `is_encrypted = 1`.

---

## 6. Correctifs de sécurité préalables — bloquants

Le coffre n'a aucune valeur tant que ces trois failles existantes ne sont pas corrigées. À traiter **avant** le module PV.

1. **Contournement du MFA.** `core/deps.py` — `get_current_user` ne vérifie pas le flag `mfa` du payload. Le token temporaire émis entre le mot de passe et le TOTP (`{"sub": id, "mfa": true}`, 3 min) est accepté comme token d'accès complet sur tous les endpoints. Correctif : rejeter tout payload contenant `mfa: true` dans `get_current_user`. Ajouter aussi un claim `typ` explicite (`"access"` / `"mfa_pending"`) et le vérifier.

2. **CAPTCHA optionnel.** `routes/auth.py:login`, `routes/organization.py:join_organization` et `create_organization` — la condition `if body.captcha_id and body.captcha_answer:` permet de sauter la validation en omettant simplement les deux champs. Rendre les champs obligatoires côté schéma Pydantic. Ajouter un rate-limiting par IP et par compte sur `/login` (verrouillage progressif).

3. **Code d'invitation détaché de l'email.** `routes/organization.py:join_organization` — l'invitation est recherchée par code seul, `body.email` n'est jamais comparé à `invitation.email`. Un code intercepté permet de s'inscrire sous une autre identité avec le statut prévu pour un tiers. Correctif : filtrer sur `code` **et** `email`.

Secondaires : pas de révocation de token (un changement de mot de passe n'invalide rien), pas de blocage du rejeu TOTP, mot de passe à 6 caractères et aucune contrainte à l'inscription, store CAPTCHA en mémoire (incompatible multi-workers), possibilité de supprimer le dernier admin.

---

## 7. Infrastructure

- **Alembic est un prérequis.** Ce module ajoute trois tables et modifie `invitations`. Sans migrations, chaque mise à jour chez un utilisateur en local détruit ses données. À mettre en place avant toute autre chose.
- **SQLCipher ou chiffrement de disque** en complément, pas en remplacement : le coffre protège les PV contre l'administrateur de la machine, SQLCipher protège **tout le reste** (identités des délégués, heures de mandat, ordres du jour) contre le portable volé ou la sauvegarde égarée. Les deux sont utiles et ne se recouvrent pas.
- Rappel du contexte : déploiement local, hors Internet, mono-instance. SQLite reste le bon choix.

---

## 8. Tests attendus

1. **Étanchéité de l'export** (priorité absolue) : extraction du texte du PDF direction, assertion qu'aucun contenu ni titre de section `interne` n'y figure. Inclure des cas piégeux : section interne vide, section repassée de `partage` à `interne` après une première diffusion, caractères Unicode.
2. Cycle complet de coffre : création → invitation → inscription → changement de mot de passe → révocation → rotation. Vérifier qu'après rotation, l'ancienne enveloppe ne déchiffre plus rien.
3. Vérification que le serveur ne peut pas déchiffrer : test qui inspecte la base et confirme qu'aucun contenu de section n'y est lisible.
4. Défaut de visibilité : une section créée sans `visibility` explicite doit être `interne`.
5. Double contrôle : la validation par le rédacteur lui-même doit être refusée.
6. **Barèmes légaux** (indépendant du coffre, mais toujours absent) : tests paramétrés sur `required_titulaires` et `weekly_credit_hours` aux bornes — 15, 25, 26, 50, 51, 149, 150, 249, 250, 5500, 5501, 6000. C'est aussi la meilleure pièce justificative de conformité au Code du travail.

---

## 9. Ordre de réalisation suggéré

1. Alembic + les trois correctifs de sécurité (§6)
2. Tests des barèmes légaux (§8.6) — rapide, et sécurise le socle existant
3. Modèle PV sectionné **en clair**, avec projection, prévisualisation et double validation (§2, §3)
4. Export PDF + test d'étanchéité (§4, §8.1)
5. Coffre-fort chiffré par-dessus, en option activable (§1)

Livrer le §3 et le §4 avant le §5 : la double version est utile immédiatement, le chiffrement est une couche qui se pose ensuite sans rien réécrire.
