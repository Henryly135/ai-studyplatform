#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/infra/docker-compose.yml"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"
SERVICES=(
  identity-service
  communication-service
  learning-service
  ai-service
)

cd "$ROOT_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
  cat >&2 <<EOF
Missing env file: $ENV_FILE
Create one with:
  cp .env.example .env
or run with:
  ENV_FILE=$ROOT_DIR/.env.example $0
EOF
  exit 1
fi

for service in "${SERVICES[@]}"; do
  echo "==> Running pytest for ${service}"
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T "$service" pytest tests -q
done

echo "All backend service tests passed."
