#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/infra/docker-compose.yml"
ENV_FILE="$ROOT_DIR/.env"
SERVICES=(
  identity-service
  communication-service
  learning-service
  ai-service
)

cd "$ROOT_DIR"

for service in "${SERVICES[@]}"; do
  echo "==> Running coverage for ${service}"
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T "$service" \
    pytest tests --cov=app --cov-report=json:coverage.json --cov-report=term-missing
done

python - "$ROOT_DIR" "${SERVICES[@]}" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
services = sys.argv[2:]
total_covered = 0
total_statements = 0

for service in services:
    coverage_path = root / "services" / service / "coverage.json"
    with coverage_path.open(encoding="utf-8") as file:
        totals = json.load(file)["totals"]

    covered = int(totals["covered_lines"])
    statements = int(totals["num_statements"])
    percent = round((covered / statements) * 100, 2) if statements else 100.0

    print(f"{service} coverage: {percent}% ({covered} / {statements})")
    total_covered += covered
    total_statements += statements

total_percent = round((total_covered / total_statements) * 100, 2) if total_statements else 100.0
print(f"TOTAL backend coverage: {total_percent}% ({total_covered} / {total_statements})")

if total_percent < 80:
    raise SystemExit(1)
PY
