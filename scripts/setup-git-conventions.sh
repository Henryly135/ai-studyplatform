#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

git config --local commit.template .github/commit_message_template.txt
git config --local commit.cleanup strip

echo "Configured local commit template:"
echo "  .github/commit_message_template.txt"
echo ""
echo "Commit titles must use:"
echo "  type(scope): summary"
