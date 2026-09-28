#!/bin/bash
# Copyright 2026 NVIDIA Corporation
# SPDX-License-Identifier: Apache-2.0

# find-and-download.sh - Search SharePoint and retrieve matching file content
# Usage: ./find-and-download.sh "search query" [limit]

set -euo pipefail

if ! command -v sharepoint-cli &> /dev/null; then
    echo "Error: sharepoint-cli not found. See installation docs."
    exit 1
fi

QUERY="${1:?Usage: $0 \"search query\" [limit]}"
LIMIT="${2:-5}"

echo "=== Searching: $QUERY ==="
RESULTS=$(sharepoint-cli search --query "$QUERY" --limit "$LIMIT" --output json)

# Count results
COUNT=$(echo "$RESULTS" | jq '.data.results | length')
echo "Found $COUNT results"
echo

# Display results
echo "$RESULTS" | jq -r '.data.results[] | "\(.document.title // .title)\t\(.url)"' | \
  nl -ba | while IFS=$'\t' read -r NUM TITLE URL; do
    echo "  $NUM. $TITLE"
    echo "     $URL"
done

echo
HAS_MORE=$(echo "$RESULTS" | jq -r '.data.hasMoreResults // false')
if [ "$HAS_MORE" = "true" ]; then
    CURSOR=$(echo "$RESULTS" | jq -r '.data.cursor')
    echo "More results available. Next page: sharepoint-cli search --query \"$QUERY\" --cursor \"$CURSOR\""
fi
