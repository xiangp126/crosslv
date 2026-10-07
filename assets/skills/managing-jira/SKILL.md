---
name: managing-jira
description: Manage Jira issues, projects, boards, sprints, and current-user context via jira-cli. Use when working with Jira tickets, JQL searches, issue status changes, assignments, or sprint/board review.
---

# Jira Management

Use `jira-cli` to search issues with JQL; inspect, create, update, transition, assign, or comment
on tickets, or open them in the browser; and review project, board, sprint, or current-user
context. For Confluence work, use `managing-confluence`.

**WSL note:** In WSL with Windows-installed binaries, append `.exe` to CLI names (`<tool>-cli.exe`).

## Verify Installation

Check authentication before any other call:

```bash
jira-cli --version
jira-cli auth status          # want: Authenticated: true
```

If it reports `Authenticated: false`, stop and ask Peter to authenticate — creating and storing
the token are his steps. He creates an API token at
https://id.atlassian.com/manage-profile/security/api-tokens, then runs:

```bash
jira-cli config set user user@nvidia.com     # Atlassian account email
jira-cli auth set-token <api-token>
```

The site defaults to `https://nvidia-jira.atlassian.net`; `jira-cli config show` prints the
resolved site and user. Re-run `jira-cli auth status` afterwards.

## Quick Start

```bash
# Issues
jira-cli issue get PROJ-123 --toon
jira-cli issue find 'project = PROJ AND status != Done' --toon
jira-cli issue create --project PROJ --summary 'New task' --type Task --json
jira-cli issue transition PROJ-123 Done --json
jira-cli issue assign PROJ-123 <account-id> --json

# Project / sprint context
jira-cli project list --toon
jira-cli board list --toon
jira-cli sprint current 42 --toon
jira-cli sprint issues 314 --toon

# Identity
jira-cli user me --toon
```

- Timestamps: for human-readable commands, root flags `--relative`, `--utc`, `--local`, or
  `--timezone America/New_York` change display only; JSON/TOON output keeps the original API
  timestamps.
- Exact syntax and flags: `jira-cli <command> --help`; full command surface: `jira-cli --help`.

## Workflows

- **Issue Triage** — [workflows/issue-triage.md](workflows/issue-triage.md)
- **Sprint Review** — [workflows/sprint-review.md](workflows/sprint-review.md)

## Troubleshooting

- **Not authenticated**: ask Peter to run `jira-cli config set user ...` and
  `jira-cli auth set-token ...` (see Verify Installation)
- **Wrong Jira site**: `jira-cli config set base_url https://<your-site>`; check with
  `jira-cli config show`
- **JQL returns no results**: simplify the query, then add filters back one at a time
- **Transition fails**: inspect `jira-cli issue transitions <key>` first
