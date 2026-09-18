#!/bin/bash
# export-page.sh - Export a Confluence page with simple metadata frontmatter

set -euo pipefail

PAGE_ID=${1:-}
OUTPUT_FILE=${2:-}

if [ -z "$PAGE_ID" ]; then
  echo "Usage: $0 <page-id> [output-file]"
  exit 1
fi

PAGE_INFO=$(confluence-cli page get "$PAGE_ID" --json)
TITLE=$(echo "$PAGE_INFO" | jq -r '.data.title')
SPACE=$(echo "$PAGE_INFO" | jq -r '.data.spaceKey')
VERSION=$(echo "$PAGE_INFO" | jq -r '.data.version')
MODIFIED=$(echo "$PAGE_INFO" | jq -r '.data.updatedAt')
AUTHOR=$(echo "$PAGE_INFO" | jq -r '.data.updatedBy')

if [ -z "$OUTPUT_FILE" ]; then
  OUTPUT_FILE=$(echo "$TITLE" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd '[:alnum:]-').md
fi

{
  echo "---"
  echo "title: \"$TITLE\""
  echo "page_id: $PAGE_ID"
  echo "space: $SPACE"
  echo "version: $VERSION"
  echo "last_modified: \"$MODIFIED\""
  echo "author: \"$AUTHOR\""
  echo "exported: \"$(date -Iseconds)\""
  echo "---"
  echo
  confluence-cli page get "$PAGE_ID"
} > "$OUTPUT_FILE"

printf 'Exported %s to %s\n' "$TITLE" "$OUTPUT_FILE"
