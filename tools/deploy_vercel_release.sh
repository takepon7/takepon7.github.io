#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PROJECT_NAME="${VERCEL_PROJECT_NAME:-gitai}"
WEB_DOMAIN="${GITAI_WEB_DOMAIN:-gitai.game}"
API_DOMAIN="${GITAI_API_DOMAIN:-api.gitai.game}"

require_vercel_auth() {
  if [[ -z "${VERCEL_TOKEN:-}" ]]; then
    vercel whoami >/dev/null
  else
    vercel whoami --token "$VERCEL_TOKEN" >/dev/null
  fi
}

vercel_cmd() {
  if [[ -n "${VERCEL_TOKEN:-}" ]]; then
    vercel "$@" --token "$VERCEL_TOKEN"
  else
    vercel "$@"
  fi
}

set_env() {
  local key="$1"
  local value="$2"
  if vercel_cmd env ls production 2>/dev/null | grep -q "^${key}[[:space:]]"; then
    printf '%s' "$value" | vercel_cmd env update "$key" production --yes >/dev/null
  else
    printf '%s' "$value" | vercel_cmd env add "$key" production --yes >/dev/null
  fi
}

require_vercel_auth

if [[ ! -d .vercel ]]; then
  vercel_cmd link --yes --project "$PROJECT_NAME"
fi

set_env GITAI_CORS_ORIGINS "https://${WEB_DOMAIN},capacitor://localhost"
set_env GITAI_PUBLIC_WEB_URL "https://${WEB_DOMAIN}"
set_env GITAI_STATIC_DIR "web/dist"
set_env GITAI_RUNTIME_DB "/tmp/gitai.sqlite"
set_env GITAI_IMAGE_STORE "/tmp/gitai-submissions"
set_env GITAI_MODEL "heuristic"
set_env GITAI_OCR "fingerprint"
set_env GITAI_MODERATION "fingerprint"
set_env GITAI_SEASON_ID "season-1"
set_env GITAI_SEASON_LABEL "Season 1"
set_env GITAI_DAILY_LLM_SPEND_CAP "100"
set_env GITAI_USER_DAILY_COMMENT_LIMIT "3"
set_env GITAI_DAILY_SUBMISSION_LIMIT "10"
if [[ -n "${GITAI_OPERATOR_TOKEN:-}" ]]; then
  set_env GITAI_OPERATOR_TOKEN "$GITAI_OPERATOR_TOKEN"
fi

deployment_url="$(vercel_cmd deploy --prod --yes)"

vercel_cmd domains add "$WEB_DOMAIN" "$PROJECT_NAME" --yes >/dev/null || true
vercel_cmd domains add "$API_DOMAIN" "$PROJECT_NAME" --yes >/dev/null || true
vercel_cmd alias set "$deployment_url" "$WEB_DOMAIN" >/dev/null
vercel_cmd alias set "$deployment_url" "$API_DOMAIN" >/dev/null

printf 'Deployment: %s\n' "$deployment_url"
printf 'Web: https://%s\n' "$WEB_DOMAIN"
printf 'API: https://%s/healthz\n' "$API_DOMAIN"
