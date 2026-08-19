---
name: tracking-redmine
description: Track and manage Redmine issues via redmine-cli. Query issues, create and update tickets, add comments, search across projects, look up reference data (statuses, trackers, priorities), and resolve users. Use when looking up Redmine issues, creating tickets, updating issue status, commenting on issues, searching Redmine, or checking valid status/tracker/priority IDs.
---
<!--
Progressive Disclosure:
- Level 1 (YAML front matter): Skill metadata and description
- Level 2 (This file): Overview, quick start, key patterns
- Level 3: workflows/

Related skills:
- querying-helios-directory: For employee directory lookups (e.g., resolving assignee names)
-->

# Issue Tracking with redmine-cli

Track and manage issues in Redmine via `redmine-cli`. **WSL note:** In WSL with Windows-installed binaries, append `.exe` to CLI names (`<tool>-cli.exe`).

## Verify Installation

```bash
redmine-cli --version
```

If command not found, see [installation page](https://outlook-cli-80d21a.gitlab-master-pages.nvidia.com/).

**Authentication:** Get your API key at https://redmine.mellanox.com/my/account (API access key > Show), then:
```bash
redmine-cli auth set-token <your-api-key>
redmine-cli auth status
```

For automations, use a dedicated service user (request via ServiceNow).

## When to Use This Skill

Use this skill when users want to:

- **Look up issues**: Get issue details, status, comments by ID
- **Search/filter issues**: Find issues by any Redmine field using `--filter`
- **Create issues**: File new issues in a Redmine project
- **Update issues**: Change status, priority, assignee, or other fields
- **Comment on issues**: Add notes to existing issues
- **Browse projects**: List or inspect Redmine projects
- **Look up reference data**: Discover valid statuses, trackers, and priorities (needed for create/update flags)
- **Resolve users**: Look up user details by ID

## Quick Reference

Run `redmine-cli --help` and `redmine-cli <command> --help` for full syntax.

### Query Issues

```bash
redmine-cli issue get 12345 --json
redmine-cli issue list --project myproject -f "status_id=open" --limit 10 --json
redmine-cli issue list --all-projects -f "assigned_to_id=me" --json
redmine-cli issue list --project myproject -f "subject=~login bug" --json
redmine-cli issue list --all-projects -f "subject=~deployment" --json
redmine-cli issue list --project myproject -f "updated_on=>t-7" -f "status_id=open" --json
```

**Timestamp note:** Root flags like `--relative`, `--utc`, `--local`, and `--timezone` only affect human output. JSON/TOON output keeps original API timestamps.

The `--filter` (`-f`) flag passes raw Redmine filters as `key=value` pairs. Run `redmine-cli issue list --help` for the full operator reference.

### Create and Update Issues

**Important:** Use `redmine-cli lookup` commands to discover valid IDs before creating or updating issues. See [Issue Lifecycle](workflows/issue-lifecycle.md).

```bash
# Create
redmine-cli issue create --project-id 1 --subject "Fix login bug" --priority-id 3 --json

# Update (only specified fields are changed)
redmine-cli issue update 12345 --status-id 3 --notes "Moving to resolved" --json

# Comment
redmine-cli issue comment 12345 --text "Fix deployed to staging" --json
echo "Multi-line comment" | redmine-cli issue comment 12345
```

### Reference Data Lookups

```bash
redmine-cli lookup statuses --json      # Status IDs for --status-id
redmine-cli lookup trackers --json      # Tracker IDs for --tracker-id
redmine-cli lookup priorities --json    # Priority IDs for --priority-id
```

### Projects and Users

```bash
redmine-cli project list --json
redmine-cli project get myproject --json
redmine-cli user get 42 --json
redmine-cli user me --json
```

## Workflows

Detailed multi-step procedures:

1. **[Issue Lifecycle](workflows/issue-lifecycle.md)** — Create, update, comment, and close issues
2. **[Search and Triage](workflows/search-triage.md)** — Find and prioritize issues across projects

## Troubleshooting

**Authentication fails:**
```bash
redmine-cli auth logout
redmine-cli auth set-token <new-key>  # Get key from https://redmine.mellanox.com/my/account
```

**401 Unauthorized:**
- API key may be revoked or expired — generate a new one
- Verify with: `redmine-cli auth status`

**403 Forbidden:**
- You may not have access to the requested project or issue
- Check project membership in Redmine web UI

**Write operation rejected (READ_ONLY_MODE):**
- The CLI build has write support disabled
- Production builds have write access; dev builds are read-only by default

**"--project-id is required" on issue create:**
- Look up project IDs first: `redmine-cli project list --json`

**Invalid status/tracker/priority ID:**
- Look up valid values first: `redmine-cli lookup statuses --json`
