# Sprint Review Workflow

Use when the user wants sprint context: boards, the active sprint, and issues currently in flight.
Before making write changes, confirm which Jira identity is in use with `user me`.

## 1. List boards and pick the one that matters

If the board name is ambiguous, use `project list` or `project get`.

```bash
jira-cli board list --json
```

## 2. Get the active sprint for the board

```bash
jira-cli sprint current 42 --json
```

## 3. List sprint issues

```bash
jira-cli sprint issues 314 --json
```

## 4. Drill into specific issues if needed

Use `issue find` with sprint-specific JQL when you need filtering beyond the raw sprint issue list.

```bash
jira-cli issue get PROJ-123 --toon
jira-cli issue find 'sprint = 314 AND status != Done' --limit 20 --json
```
