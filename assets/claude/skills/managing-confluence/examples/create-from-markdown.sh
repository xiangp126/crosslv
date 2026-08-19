#!/bin/bash
# create-from-markdown.sh - Create or update a Confluence page from a markdown file

set -euo pipefail

TITLE=${1:-}
FILE=${2:-}
PARENT=${3:-}

if [ -z "$TITLE" ] || [ -z "$FILE" ]; then
  echo "Usage: $0 <title> <markdown-file> [parent-page-id-or-title]"
  exit 1
fi

if [ ! -f "$FILE" ]; then
  echo "File not found: $FILE"
  exit 1
fi

if [ -n "$PARENT" ]; then
  confluence-cli page upsert --parent "$PARENT" --title "$TITLE" --file "$FILE" --json
else
  confluence-cli page create "$TITLE" "$(cat "$FILE")" --update-if-exists --json
fi
