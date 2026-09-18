#!/bin/bash
# search-and-list.sh - Search Confluence pages and print a simple summary

set -euo pipefail

QUERY=${1:-}
SPACE=${2:-}
LIMIT=${3:-25}

if [ -z "$QUERY" ]; then
  echo "Usage: $0 <query> [space] [limit]"
  exit 1
fi

if [ -n "$SPACE" ]; then
  RESULTS=$(confluence-cli page find "$QUERY" --space "$SPACE" --limit "$LIMIT" --json)
else
  RESULTS=$(confluence-cli page find "$QUERY" --limit "$LIMIT" --json)
fi

COUNT=$(echo "$RESULTS" | jq '.data | length')
echo "Found $COUNT page(s)"

echo "$RESULTS" | jq -r '.data[] | "- \(.title) [\(.spaceKey)] id=\(.id)"'
