# Search and Triage Workflow

Find and prioritize Redmine issues across projects.

## Step 1: Search by Keyword

```bash
redmine-cli issue list --project infrastructure -f "subject=~memory leak" --json
redmine-cli issue list --all-projects -f "subject=~deployment failure" --json
```

## Step 2: Filter Issues

```bash
# Open issues in a project, sorted by priority
redmine-cli issue list --project myproject -f "status_id=open" --sort "priority:desc" --json

# Issues assigned to current user
redmine-cli issue list --all-projects -f "assigned_to_id=me" --json

# High-priority bugs
redmine-cli issue list --project myproject -f "tracker_id=1" -f "status_id=open" --sort "priority:desc" --limit 20 --json

# Updated in the last 7 days
redmine-cli issue list --project myproject -f "updated_on=>t-7" --json

# Created this month
redmine-cli issue list --project myproject -f "created_on=m" --json
```

Run `redmine-cli issue list --help` for the full operator reference.

## Step 3: Review an Issue

```bash
redmine-cli issue get 12345 --json
```

The response includes journals (comments) so you can see the full history.

## Step 4: Triage Actions

Based on review, take one of these actions:

**Reassign:**
```bash
redmine-cli issue update 12345 --assigned-to-id 42 --notes "Routing to backend team" --json
```

**Reprioritize:**
```bash
redmine-cli issue update 12345 --priority-id 4 --notes "Escalating — customer-facing" --json
```

**Request info:**
```bash
redmine-cli issue comment 12345 --text "Need repro steps. What version are you running?" --json
```

**Close as duplicate or invalid:**
```bash
redmine-cli issue update 12345 --status-id 6 --notes "Duplicate of #67890" --json
```
