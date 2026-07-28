#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$PROJECT_DIR"

if [ ! -f ".env" ]; then
  echo ".env not found"
  exit 1
fi

# In non-interactive SSH sessions on macOS, osxkeychain may be unavailable.
# Use an isolated Docker config to avoid credential-helper lookup failures.
export DOCKER_CONFIG="${DOCKER_CONFIG:-/tmp/docker-config-${USER}}"
mkdir -p "$DOCKER_CONFIG"
if [ ! -f "$DOCKER_CONFIG/config.json" ]; then
  printf '{"auths":{}}' > "$DOCKER_CONFIG/config.json"
fi

docker compose --env-file .env -f infra/docker-compose.yml config --quiet
docker compose --env-file .env -f infra/docker-compose.yml down --remove-orphans
docker compose --env-file .env -f infra/docker-compose.yml up -d --build
docker compose --env-file .env -f infra/docker-compose.yml ps

if [ -n "${DEMO_ACCESS_TOKEN:-}" ]; then
  bash scripts/demo-preflight.sh
else
  echo "DEMO_ACCESS_TOKEN is not set; run bash scripts/demo-preflight.sh manually before presenting the Demo"
fi
