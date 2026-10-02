#!/usr/bin/env bash
# Re-download the Product Brain source files this reference is based on (read only, needs `gh` auth
# with access to josefigueredo/acme-agent). Usage: ./refresh.sh [git-ref]   (default: main)
set -euo pipefail

REPO="josefigueredo/acme-agent"
REF="${1:-main}"
BASE="acme-gpt-back/api/src"
DEST="$(cd "$(dirname "$0")" && pwd)/upstream"
FILES=(
  "db/base-templates.ts"
  "modules/documents/completion.ts"
  "modules/documents/pipeline/open-questions-validation.ts"
  "modules/documents/pipeline/field-groups.ts"
  "modules/chat/document-completion-guard.ts"
  "modules/agents/agent-prompts.config.ts"
)

mkdir -p "$DEST"
SHA="$(gh api "repos/$REPO/commits/$REF" --jq .sha)"
for file in "${FILES[@]}"; do
  gh api "repos/$REPO/contents/$BASE/$file?ref=$SHA" --jq .content | base64 --decode > "$DEST/$(basename "$file")"
  echo "fetched $file"
done
printf '%s %s\n' "$SHA" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$DEST/SOURCE_COMMIT"
echo "upstream/ now matches $REPO@$SHA"
echo "Compare with the commit recorded in README.md; if the templates changed, update the prompts in skills/wow-pack/references/."
