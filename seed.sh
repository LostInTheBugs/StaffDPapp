#!/bin/bash
# Script de seed — crée les comptes de test après un déploiement
HOST=${1:-localhost:3002}

echo "🌱 Seeding $HOST ..."

# Helper: fetch a CAPTCHA challenge, compute the answer, output "challenge_id:answer"
fetch_captcha() {
  local resp=$(curl -sf "$HOST/api/auth/captcha")
  local cid=$(echo "$resp" | python3 -c 'import sys,json; print(json.load(sys.stdin)["challenge_id"])')
  local question=$(echo "$resp" | python3 -c 'import sys,json; print(json.load(sys.stdin)["question"])')
  # question format: "Combien font A + B ?"
  local a=$(echo "$question" | sed 's/.*font \([0-9]*\) + \([0-9]*\).*/\1/')
  local b=$(echo "$question" | sed 's/.*font \([0-9]*\) + \([0-9]*\).*/\2/')
  local ans=$((a + b))
  echo "${cid}:${ans}"
}

# 1. Créer l'organisation + admin (Présidente)
CAPTCHA=$(fetch_captcha)
CID="${CAPTCHA%%:*}"
CANS="${CAPTCHA##*:}"
curl -sf -X POST "$HOST/api/organizations" -H 'Content-Type: application/json' \
  -d "{\"organization_name\":\"Demo\",\"employee_count\":120,\"admin_email\":\"sophie@demo.lu\",\"admin_password\":\"demo123456\",\"admin_first_name\":\"Sophie\",\"admin_last_name\":\"Muller\",\"admin_delegue_status\":\"titulaire\",\"admin_delegue_role\":\"president\",\"captcha_id\":\"$CID\",\"captcha_answer\":\"$CANS\"}" >/dev/null && echo "  admin (Sophie Muller - Présidente) OK"

# Login pour récupérer le token admin
CAPTCHA=$(fetch_captcha)
CID="${CAPTCHA%%:*}"
CANS="${CAPTCHA##*:}"
TOK=$(curl -sf -X POST "$HOST/api/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"sophie@demo.lu\",\"password\":\"demo123456\",\"captcha_id\":\"$CID\",\"captcha_answer\":\"$CANS\"}" | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

# Fonction pour créer un compte
invite_and_join() {
  local email=$1 first=$2 last=$3 status=$4 role=$5
  local CODE=$(curl -sf -X POST "$HOST/api/invitations" -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
    -d "{\"email\":\"$email\",\"first_name\":\"$first\",\"last_name\":\"$last\",\"delegue_status\":\"$status\",\"delegue_role\":\"$role\"}" | python3 -c 'import sys,json; print(json.load(sys.stdin)["code"])')
  CAPTCHA=$(fetch_captcha)
  CID="${CAPTCHA%%:*}"
  CANS="${CAPTCHA##*:}"
  curl -sf -X POST "$HOST/api/join" -H 'Content-Type: application/json' \
    -d "{\"email\":\"$email\",\"password\":\"demo123456\",\"first_name\":\"$first\",\"last_name\":\"$last\",\"invitation_code\":\"$CODE\",\"captcha_id\":\"$CID\",\"captcha_answer\":\"$CANS\"}" >/dev/null
  echo "  $first $last ($role) OK"
}

# Bureau
invite_and_join "marc@demo.lu" "Marc" "Weber" "titulaire" "vice_president"
invite_and_join "laura@demo.lu" "Laura" "Schmit" "titulaire" "secretaire"

# Titulaires restants
invite_and_join "tom@demo.lu" "Tom" "Wagner" "titulaire" "membre"
invite_and_join "emma@demo.lu" "Emma" "Kirsch" "titulaire" "membre"

# Suppléants
invite_and_join "paul@demo.lu" "Paul" "Hoffmann" "suppleant" "membre"
invite_and_join "anna@demo.lu" "Anna" "Klein" "suppleant" "membre"
invite_and_join "david@demo.lu" "David" "Fischer" "suppleant" "membre"
invite_and_join "clara@demo.lu" "Clara" "Becker" "suppleant" "membre"
invite_and_join "lucas@demo.lu" "Lucas" "Thill" "suppleant" "membre"

echo "✅ Seed terminé"
