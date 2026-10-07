# Issue Triage Workflow

Use when the user needs to find active work, inspect a ticket, then update or route it. Use
`--json` when another tool or script needs to process the result.

## 1. Find candidate issues with JQL

```bash
jira-cli issue find 'assignee = currentUser() AND status != Done' --limit 10 --json
jira-cli issue find 'project = PROJ AND priority = High ORDER BY updated DESC' --limit 10 --json
```

## 2. Inspect the most relevant issue

Use `issue open` when the user needs the browser view or deeper manual follow-up.

```bash
jira-cli issue get PROJ-123 --toon
jira-cli issue open PROJ-123 --no-browser --json
```

## 3. Check which transitions are allowed

Prefer this over guessing a target status name.

```bash
jira-cli issue transitions PROJ-123 --json
```

## 4. Reassign, transition, or comment as needed

```bash
jira-cli issue assign PROJ-123 <account-id> --json
jira-cli issue transition PROJ-123 Done --json
jira-cli issue comment PROJ-123 'Reviewed and handed off.' --json
```
