# StaffDPapp — Staff Delegation Application

> ⚠️ **Application expérimentale** — Ce logiciel est fourni à titre de démonstration uniquement. Il ne constitue pas un conseil juridique et n'est pas garanti conforme à la législation luxembourgeoise en vigueur. Toute utilisation se fait aux risques et périls de l'utilisateur. Consultez un professionnel qualifié ou la [Chambre des Salariés (CSL)](https://www.csl.lu) pour toute question relative au droit du travail.

Outil de gestion pour les **délégations du personnel** au Luxembourg, inspiré du Code du travail (Art. L.412-1, L.414-2, L.414-3, L.415-5, L.416-1).

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

- 🧪 **Test** : http://192.168.10.191:3002
- 🌐 **Production** : https://staffdpapp.cloudfr.net

## Déploiement

```bash
# Développement local
cd backend && python -m uvicorn app.main:app --reload
cd frontend && npm run dev

# Docker Compose
docker compose up -d --build

# Seed (après suppression du volume)
bash seed.sh
```

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
