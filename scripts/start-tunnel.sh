#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-${PROJECT_DIR}/.env}"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared is not installed."
  echo "macOS:  brew install cloudflared"
  echo "Linux:  https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
  exit 1
fi

if [ ! -f "${ENV_FILE}" ]; then
  echo ".env not found at ${ENV_FILE}"
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

TARGET_HOST="${TUNNEL_TARGET_HOST:-127.0.0.1}"
TARGET_PORT="${TUNNEL_PORT:-${NGINX_PORT:-8080}}"
MODE="${1:-${TUNNEL_MODE:-${APP_ENV:-app}}}"

if command -v nc >/dev/null 2>&1; then
  if ! nc -z "${TARGET_HOST}" "${TARGET_PORT}" >/dev/null 2>&1; then
    echo "App entry is not listening on ${TARGET_HOST}:${TARGET_PORT}."
    echo "Please start the ${MODE} environment first."
    exit 1
  fi
else
  if ! (echo >/dev/tcp/"${TARGET_HOST}"/"${TARGET_PORT}") >/dev/null 2>&1; then
    echo "App entry is not listening on ${TARGET_HOST}:${TARGET_PORT}."
    echo "Please start the ${MODE} environment first."
    exit 1
  fi
fi

echo "Cloudflare Quick Tunnel started (${MODE})."
echo "Env file: ${ENV_FILE}"
echo "Target: http://${TARGET_HOST}:${TARGET_PORT}"
echo "Share this URL with reviewers/teachers:"
echo "(The public URL will be printed by cloudflared below)"

exec cloudflared tunnel --url "http://${TARGET_HOST}:${TARGET_PORT}"
