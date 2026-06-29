#!/usr/bin/env bash
set -euo pipefail

SUBJECT_REGEX='^(build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)(\([a-z0-9._/-]+\))?!?: .{3,100}$'
REQUIRED_PR_SECTIONS=("## Summary" "## Change Type" "## Tests" "## Checklist")

validate_subjects() {
  tmp_file="$(mktemp)"
  cat > "$tmp_file"
  status=0
  python3 - "$SUBJECT_REGEX" "$tmp_file" <<'PY' || status=$?
import re
import sys

pattern = re.compile(sys.argv[1])
with open(sys.argv[2], "r", encoding="utf-8") as fh:
    subjects = [line.rstrip("\n") for line in fh if line.rstrip("\n")]

if not subjects:
    print("No commit subjects found to validate.")
    sys.exit(0)

bad = [subject for subject in subjects if not pattern.fullmatch(subject)]

if bad:
    print("Commit or PR title format check failed.")
    print("")
    print("Expected: type(scope): summary")
    print("Allowed types: build, chore, ci, docs, feat, fix, perf, refactor, revert, style, test")
    print("Scope is optional and must use lowercase letters, numbers, '.', '_', '-', or '/'.")
    print("Examples:")
    print("  feat(ai): add provider settings")
    print("  ci(workflow): enforce commit and PR templates")
    print("")
    print("Invalid title(s):")
    for subject in bad:
        print(f"  - {subject}")
    sys.exit(1)

print(f"Validated {len(subjects)} commit/PR title(s).")
PY
  rm -f "$tmp_file"
  return "$status"
}

subjects_from_event_commits() {
  python3 - <<'PY'
import json
import os

event_path = os.environ.get("GITHUB_EVENT_PATH")
if not event_path:
    raise SystemExit(0)

with open(event_path, "r", encoding="utf-8") as fh:
    event = json.load(fh)

for commit in event.get("commits", []):
    message = commit.get("message", "")
    subject = message.splitlines()[0].strip() if message else ""
    if subject:
        print(subject)
PY
}

validate_pr_payload() {
  python3 - "$SUBJECT_REGEX" "${REQUIRED_PR_SECTIONS[@]}" <<'PY'
import json
import os
import re
import sys

pattern = re.compile(sys.argv[1])
required_sections = sys.argv[2:]
event_path = os.environ.get("GITHUB_EVENT_PATH")
if not event_path:
    print("GITHUB_EVENT_PATH is not set; cannot validate pull request payload.")
    sys.exit(1)

with open(event_path, "r", encoding="utf-8") as fh:
    event = json.load(fh)

pull_request = event.get("pull_request") or {}
title = (pull_request.get("title") or "").strip()
body = pull_request.get("body") or ""

errors = []
if not pattern.fullmatch(title):
    errors.append(f"PR title must follow 'type(scope): summary'. Current title: {title!r}")

missing_sections = [section for section in required_sections if section not in body]
if missing_sections:
    errors.append("PR body is missing required section(s): " + ", ".join(missing_sections))

if errors:
    print("Pull request format check failed.")
    for error in errors:
        print(f"- {error}")
    sys.exit(1)

print("Pull request title and body format passed.")
PY
}

subjects_from_pr_range() {
  base_ref="${GITHUB_BASE_REF:?GITHUB_BASE_REF is required for pull_request events}"
  git fetch --no-tags --depth=200 origin "${base_ref}:refs/remotes/origin/${base_ref}" >/dev/null 2>&1 || true
  git log --no-merges --format=%s "origin/${base_ref}..HEAD"
}

subjects_from_local_head() {
  git log --no-merges -1 --format=%s HEAD
}

main() {
  if [ "${1:-}" = "--subject" ]; then
    shift
    printf '%s\n' "$@" | validate_subjects
    exit 0
  fi

  event_name="${GITHUB_EVENT_NAME:-local}"

  if [ "$event_name" = "pull_request" ]; then
    validate_pr_payload
    subjects_from_pr_range | validate_subjects
    exit 0
  fi

  if [ "$event_name" = "push" ]; then
    subjects="$(subjects_from_event_commits)"
    if [ -n "$subjects" ]; then
      printf '%s\n' "$subjects" | validate_subjects
    else
      subjects_from_local_head | validate_subjects
    fi
    exit 0
  fi

  subjects_from_local_head | validate_subjects
}

main "$@"
