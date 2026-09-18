# Issue Lifecycle Workflow

Create, update, comment on, and close Redmine issues.

## Step 1: Discover Reference Data

Before creating or updating issues, look up valid IDs:

```bash
redmine-cli lookup statuses --json
redmine-cli lookup trackers --json
redmine-cli lookup priorities --json
redmine-cli project list --json
```

## Step 2: Create an Issue

```bash
redmine-cli issue create \
  --project-id 1 \
  --subject "Summary of the issue" \
  --description "Detailed description" \
  --tracker-id 1 \
  --priority-id 3 \
  --assigned-to-id 42 \
  --json
```

Required: `--project-id` and `--subject`. All other flags are optional.

## Step 3: Update an Issue

Only flags you provide are changed; omitted fields are left as-is.

```bash
# Change status
redmine-cli issue update 12345 --status-id 2 --json

# Reassign with a note
redmine-cli issue update 12345 --assigned-to-id 99 --notes "Reassigning to backend team" --json

# Update progress
redmine-cli issue update 12345 --done-ratio 75 --json
```

## Step 4: Add Comments

```bash
# Inline text
redmine-cli issue comment 12345 --text "Investigated — root cause is in auth module" --json

# From file
redmine-cli issue comment 12345 --file analysis.md

# From stdin (useful for piping)
echo "Automated comment from CI" | redmine-cli issue comment 12345
```

## Step 5: Close an Issue

Look up the "Closed" status ID, then update:

```bash
# Find the closed status ID
redmine-cli lookup statuses --json | jq '.data[] | select(.name == "Closed")'

# Close with a note
redmine-cli issue update 12345 --status-id 5 --done-ratio 100 --notes "Fix verified in production" --json
```
