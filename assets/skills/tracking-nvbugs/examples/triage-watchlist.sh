#!/bin/bash
# triage-watchlist.sh - Run a watchlist and display bugs for triage
#
# Usage: ./triage-watchlist.sh <watchlist-id>
# Example: ./triage-watchlist.sh 54321

set -e

WATCHLIST_ID="$1"

if [ -z "$WATCHLIST_ID" ]; then
    echo "Usage: $0 <watchlist-id>"
    echo ""
    echo "Runs a watchlist and displays bugs sorted for triage."
    echo ""
    echo "To find your watchlist IDs:"
    echo "  nvbugs-cli watchlist list --json"
    exit 1
fi

echo "Running watchlist $WATCHLIST_ID..."
echo ""

RESULTS=$(nvbugs-cli watchlist run "$WATCHLIST_ID" --json)
COUNT=$(echo "$RESULTS" | jq '.count')

echo "Triage Queue ($COUNT bugs)"
echo "════════════════════════════════════════"
echo ""

# Display bugs sorted by priority
echo "$RESULTS" | jq -r '.bugs | sort_by(.priority) | .[] | "\(.bugId)|\(.priority)|\(.severity)|\(.status)|\(.synopsis)"' | \
    while IFS='|' read -r id priority severity status synopsis; do
        # Truncate synopsis
        synopsis=$(echo "$synopsis" | head -c 60)
        printf "  %-8s %-4s %-4s %-12s %s\n" "$id" "$priority" "$severity" "$status" "$synopsis"
    done

echo ""
echo "────────────────────────────────────────"
echo ""
echo "Commands for triage:"
echo ""
echo "  # Investigate a specific bug:"
echo "  nvbugs-cli bug get <bug-id> --json"
echo ""
echo "  # View full history:"
echo "  nvbugs-cli bug history <bug-id> --json"
echo ""
echo "  # Check dependencies:"
echo "  nvbugs-cli bug relationships gated-by <bug-id> --json"
