#!/bin/bash
# Script de seed — crée les comptes de test après un déploiement
# Usage: bash seed.sh [HOST]
HOST=${1:-localhost:3002}

echo "🌱 Seeding $HOST ..."

# 1. Créer l'organisation + admin
curl -sf -X POST "$HOST/api/organizations" -H 'Content-Type: application/json' \
  -d '{"organization_name":"Demo","employee_count":50,"admin_email":"admin@staffdel.lu","admin_password":"demo123456","admin_first_name":"Admin","admin_last_name":"President","admin_delegue_status":"titulaire","admin_delegue_role":"president"}' >/dev/null && echo "  admin OK"

# 2. Login admin pour récupérer le token
TOK=$(curl -sf -X POST "$HOST/api/auth/login" -H 'Content-Type: application/json' \
  -d '{"email":"admin@staffdel.lu","password":"demo123456"}' | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

# 3. Invitation titulaire
CODE_T=$(curl -sf -X POST "$HOST/api/invitations" -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"email":"titulaire@staffdel.lu","first_name":"Jean","last_name":"Titulaire","delegue_status":"titulaire","delegue_role":"membre"}' | python3 -c 'import sys,json; print(json.load(sys.stdin)["code"])')

# 4. Invitation suppléant
CODE_S=$(curl -sf -X POST "$HOST/api/invitations" -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"email":"suppleant@staffdel.lu","first_name":"Marie","last_name":"Suppleante","delegue_status":"suppleant","delegue_role":"membre"}' | python3 -c 'import sys,json; print(json.load(sys.stdin)["code"])')

# 5. Join titulaire
curl -sf -X POST "$HOST/api/join" -H 'Content-Type: application/json' \
  -d "{\"email\":\"titulaire@staffdel.lu\",\"password\":\"demo123456\",\"first_name\":\"Jean\",\"last_name\":\"Titulaire\",\"invitation_code\":\"$CODE_T\"}" >/dev/null && echo "  titulaire OK"

# 6. Join suppléant
curl -sf -X POST "$HOST/api/join" -H 'Content-Type: application/json' \
  -d "{\"email\":\"suppleant@staffdel.lu\",\"password\":\"demo123456\",\"first_name\":\"Marie\",\"last_name\":\"Suppleante\",\"invitation_code\":\"$CODE_S\"}" >/dev/null && echo "  suppleant OK"

echo "✅ Seed terminé"
