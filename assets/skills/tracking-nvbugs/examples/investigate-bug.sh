#!/bin/bash
# investigate-bug.sh - Investigate a bug: details, history, and dependencies
#
# Usage: ./investigate-bug.sh <bug-id>
# Example: ./investigate-bug.sh 12345

set -e

BUG_ID="$1"

if [ -z "$BUG_ID" ]; then
    echo "Usage: $0 <bug-id>"
    echo ""
    echo "Retrieves bug details, audit trail, and gated-by dependencies."
    echo ""
    echo "Examples:"
    echo "  $0 12345"
    echo "  $0 67890"
    exit 1
fi

echo "Investigating bug $BUG_ID..."
echo ""

# Get bug details
echo "Bug Details"
echo "════════════════════════════════════════"
nvbugs-cli bug get "$BUG_ID" --json | jq -r '"  Synopsis: \(.synopsis)\n  Status: \(.status)\n  Priority: \(.priority)\n  Severity: \(.severity)\n  Engineer: \(.engineer)\n  Division: \(.divisionName)"'
echo ""

# Get audit trail
echo "Recent History"
echo "════════════════════════════════════════"
TRAIL=$(nvbugs-cli bug history "$BUG_ID" --json)
COUNT=$(echo "$TRAIL" | jq '.count')
echo "  $COUNT audit trail entries"
echo ""
echo "$TRAIL" | jq -r '.entries[:5][] | "  [\(.date)] \(.auditTrailType) by \(.userFullName): \(.description)"'
[ "$COUNT" -gt 5 ] && echo "  ... and $((COUNT - 5)) more entries"
echo ""

# Get gated-by dependencies
echo "Blocked By (gated-by)"
echo "════════════════════════════════════════"
GATED=$(nvbugs-cli bug relationships gated-by "$BUG_ID" --json 2>/dev/null) && {
    echo "$GATED" | jq -r '.hierarchy.gatedByBugs[]? | "  Bug \(.bugID): \(.synopsis) [\(.status)]"'
    GCOUNT=$(echo "$GATED" | jq '.hierarchy.gatedByBugs | length')
    [ "$GCOUNT" -eq 0 ] && echo "  No blocking dependencies"
} || echo "  Could not retrieve dependencies"

echo ""
echo "Next steps:"
echo "  # View full description:"
echo "  nvbugs-cli bug description $BUG_ID --json"
echo ""
echo "  # Check what this bug blocks:"
echo "  nvbugs-cli bug relationships gating $BUG_ID --json"
