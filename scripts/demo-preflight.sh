#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${DEMO_BASE_URL:-http://localhost:8080}"
ACCESS_TOKEN="${DEMO_ACCESS_TOKEN:-}"
COURSE_UUID="${DEMO_COURSE_UUID:-}"
ATTEMPTS="${DEMO_PREFLIGHT_ATTEMPTS:-30}"
INTERVAL_SECONDS="${DEMO_PREFLIGHT_INTERVAL_SECONDS:-2}"

BASE_URL="${BASE_URL%/}"

for command_name in curl jq; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "$command_name is required"
    exit 2
  fi
done

if [ -z "$ACCESS_TOKEN" ]; then
  echo "DEMO_ACCESS_TOKEN must contain an administrator access token"
  exit 2
fi

if [ -z "$COURSE_UUID" ]; then
  echo "DEMO_COURSE_UUID must contain the course UUID to verify RAG coverage"
  exit 2
fi

wait_for_url() {
  local url="$1"
  local attempt
  for ((attempt = 1; attempt <= ATTEMPTS; attempt += 1)); do
    if curl --fail --silent --show-error "$url" >/dev/null; then
      return 0
    fi
    sleep "$INTERVAL_SECONDS"
  done
  echo "health check failed after ${ATTEMPTS} attempts: $url"
  return 1
}

echo "Checking service health..."
wait_for_url "$BASE_URL/api/health"
wait_for_url "$BASE_URL/api/learning/health"
wait_for_url "$BASE_URL/api/communication/health"
wait_for_url "$BASE_URL/api/ai/health"

AUTH_HEADER="Authorization: Bearer ${ACCESS_TOKEN}"
CATALOG_URL="$BASE_URL/api/ai/models"
if [ "${DEMO_TRIGGER_BACKFILL:-false}" = "true" ]; then
  echo "Queuing multi-embedding backfill..."
  curl --fail --silent --show-error \
    -X POST \
    -H "$AUTH_HEADER" \
    "$BASE_URL/api/ai/admin/telemetry/index-jobs/reindex-all" \
    >/dev/null
fi

CATALOG_JSON=""
for ((attempt = 1; attempt <= ATTEMPTS; attempt += 1)); do
  CATALOG_JSON="$(
    curl --fail --silent --show-error \
      -H "$AUTH_HEADER" \
      --get \
      --data-urlencode "courseUuid=${COURSE_UUID}" \
      "$CATALOG_URL"
  )"
  if echo "$CATALOG_JSON" | jq --exit-status '
    [
      .items[]
      | select(
          .available == true
          and (
            .capabilities.chat? == true
            or ((.capabilities | type) == "array" and ((.capabilities | index("chat")) != null))
          )
        )
    ] as $available_chat
    | ($available_chat | length) > 0
    and ([$available_chat[].provider] | unique | sort) == ["gemini", "glm", "openrouter"]
    and all($available_chat[]; .ragReady == true and .indexCoverage >= 1)
  ' >/dev/null; then
    break
  fi
  if [ "$attempt" -eq "$ATTEMPTS" ]; then
    echo "course multi-embedding coverage did not become ready"
    exit 1
  fi
  sleep "$INTERVAL_SECONDS"
done

PROVIDERS_JSON="$(
  curl --fail --silent --show-error \
    -H "$AUTH_HEADER" \
    "$BASE_URL/api/ai/admin/ai/providers"
)"

echo "$CATALOG_JSON" | jq --exit-status '
  def is_chat:
    .supportsChat == true
    or (.capabilities.chat? == true)
    or (
      (.capabilities | type) == "array"
      and ((.capabilities | index("chat")) != null)
    );
  ([.items[].provider] | unique | sort) == ["gemini", "glm", "openrouter"]
  and ([.items[] | select(is_chat)] | length > 0)
  and (
    [
      .items[]
      | select(is_chat and .available == true)
      | .provider
    ]
    | unique
    | sort
  ) == ["gemini", "glm", "openrouter"]
  and all(
    .items[] | select(is_chat);
    (.pairedEmbeddingModelId | type) == "string"
    and (.pairedEmbeddingModelId | length) > 0
    and .embeddingDimension == 1024
  )
' >/dev/null

echo "$PROVIDERS_JSON" | jq --exit-status '
  ([.providers[].provider] | sort) == ["gemini", "glm", "openrouter"]
  and all(.providers[]; .configured == true and .healthStatus == "ready")
' >/dev/null

echo "$CATALOG_JSON" | jq --exit-status '
  def is_chat:
    .supportsChat == true
    or (.capabilities.chat? == true)
    or (
      (.capabilities | type) == "array"
      and ((.capabilities | index("chat")) != null)
    );
  [.items[] | select(is_chat and .available == true)] as $available_chat
  | ($available_chat | length) > 0
  and ([$available_chat[].provider] | unique | sort) == ["gemini", "glm", "openrouter"]
  and all($available_chat[]; .ragReady == true and .indexCoverage >= 1)
' >/dev/null

echo "Provider summary:"
echo "$CATALOG_JSON" | jq -r '
  def is_chat:
    .supportsChat == true
    or (.capabilities.chat? == true)
    or (
      (.capabilities | type) == "array"
      and ((.capabilities | index("chat")) != null)
    );
  .items[]
  | select(is_chat)
  | "- \(.provider): \(.displayName // .name) -> \(.pairedEmbeddingModelName // .pairedEmbeddingModelId) | RAG=\(.ragReady // "not checked") | coverage=\(.indexCoverage // "not checked")"
'

echo "Demo preflight passed."
