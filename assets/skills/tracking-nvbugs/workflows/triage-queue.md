# Triage Queue Workflow

Process a watchlist of bugs for triage. Process P1 bugs first by filtering the watchlist results.

## 1. Find Watchlist

```bash
# List all watchlists
nvbugs-cli watchlist list --json

# Find watchlist ID by name
nvbugs-cli watchlist get-id "My P1 Bugs" --json
```

## 2. Run Watchlist

```bash
# Execute saved search
nvbugs-cli watchlist run <watchlist-id> --json

# Run one watchlist and return all its results, not one page
nvbugs-cli watchlist run-all <watchlist-id> --json

# With pagination
nvbugs-cli watchlist run <watchlist-id> --page 1 --limit 20 --json
```

## 3. Review Each Bug

For each bug in the watchlist:

```bash
# Get details
nvbugs-cli bug get <bug-id> --json

# Check history for recent changes (history-batch checks multiple bugs at once)
nvbugs-cli bug history <bug-id> --json

# Check if blocked
nvbugs-cli bug relationships gated-by <bug-id> --json
```

Check gated-by before assigning: blocked bugs may not be actionable.

## 4. Update Bugs (Requires Write Mode)

```bash
# Add triage comment
nvbugs-cli comment add <bug-id> --text "Triaged: ..." --json

# Update bug fields
nvbugs-cli bug update <bug-id> --priority P1 --json
```
