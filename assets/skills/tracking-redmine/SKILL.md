---
name: tracking-redmine
description: >-
  Fallback path for Redmine, used **ONLY when the nvidia-redmine MCP tools are unavailable or
  failing** — look for the deferred MCP tools first and prefer them in every normal session. Then
  use redmine-cli to query, create, update, comment, search, and look up reference data. For
  deciding which tracker a new ticket belongs in, see skill `utopx-regression-ticket`.
---

# Issue Tracking with redmine-cli

**Use the `nvidia-redmine` MCP first; this CLI is the fallback.** When the MCP is connected,
`yai__get_tickets` / `yai__search_tickets` / `yai__list_tickets` / `yai__update_ticket` /
`yai__resolve_redmine_url` do everything below and are easier to drive from an agent: no
container, no TTY, no API key to place, and URLs resolve directly.

- Some runtimes load MCP tools lazily: search or inspect the available tool catalogue before
  concluding they are absent.
- Use `redmine-cli` only when MCP discovery or calls fail, and say which path you used when
  reporting results.
- **Writing descriptions and comments:** use HTML as the web editor stores it (`<p>`, `<code>`,
  `<pre>`, `<ul>`), not textile, and correct a comment by editing its journal in place — skill `utopx-regression-ticket` → "Writing to Redmine".
- **WSL:** with Windows-installed binaries, append `.exe` to CLI names (`<tool>-cli.exe`).

## Setup

```bash
redmine-cli --version
```

If the command is not found, see the [installation page](https://outlook-cli-80d21a.gitlab-master-pages.nvidia.com/).

**Authentication:** get your API key at https://redmine.nvidia.com/my/account (API access key >
Show), then:

```bash
redmine-cli auth set-token <your-api-key>
redmine-cli auth status
```

For automations, use a dedicated service user (request via ServiceNow).

**API host:** since the 2026-10-05 domain migration the API lives at
`https://redmine-api.nvidia.com`, but redmine-cli still defaults to the retired
`https://redmine-api.mellanox.com`. Check `redmine-cli auth status` and set it once; it is kept
in `~/.ai-pim-utils/config.toml`:

```bash
redmine-cli config set base_url https://redmine-api.nvidia.com
redmine-cli auth status    # base_url: https://redmine-api.nvidia.com (config file)
```

## Quick Reference

Full syntax: `redmine-cli --help`, `redmine-cli <command> --help`.

### Query issues

```bash
redmine-cli issue get 12345 --json
redmine-cli issue list --project myproject -f "status_id=open" --limit 10 --json
redmine-cli issue list --all-projects -f "assigned_to_id=me" --json
redmine-cli issue list --project myproject -f "subject=~login bug" --json
redmine-cli issue list --all-projects -f "subject=~deployment" --json
redmine-cli issue list --project myproject -f "updated_on=>t-7" -f "status_id=open" --json
```

- `--filter` (`-f`) passes raw Redmine filters as `key=value` pairs; operator reference:
  `redmine-cli issue list --help`.
- Root flags `--relative`, `--utc`, `--local` and `--timezone` only affect human output; JSON/TOON
  output keeps the original API timestamps.

### Create, update, comment

Discover valid ids with the `redmine-cli lookup` commands before creating or updating — see
[Issue Lifecycle](workflows/issue-lifecycle.md).

```bash
# Create
redmine-cli issue create --project-id 1 --subject "Fix login bug" --priority-id 3 --json

# Update (only specified fields are changed)
redmine-cli issue update 12345 --status-id 3 --notes "Moving to resolved" --json

# Comment
redmine-cli issue comment 12345 --text "Fix deployed to staging" --json
echo "Multi-line comment" | redmine-cli issue comment 12345
```

### Reference data

```bash
redmine-cli lookup statuses --json      # Status IDs for --status-id
redmine-cli lookup trackers --json      # Tracker IDs for --tracker-id
redmine-cli lookup priorities --json    # Priority IDs for --priority-id
```

### Projects and users

```bash
redmine-cli project list --json
redmine-cli project get myproject --json
redmine-cli user get 42 --json
redmine-cli user me --json
```

## Workflows

1. **[Issue Lifecycle](workflows/issue-lifecycle.md)** — create, update, comment, and close issues
2. **[Search and Triage](workflows/search-triage.md)** — find and prioritize issues across projects

## Troubleshooting

| symptom | action |
|---|---|
| authentication fails | `redmine-cli auth logout`, then `redmine-cli auth set-token <new-key>` (key from https://redmine.nvidia.com/my/account) |
| 401 Unauthorized | the API key may be revoked or expired — generate a new one; verify with `redmine-cli auth status` |
| 403 Forbidden | no access to the requested project or issue — check project membership in the Redmine web UI |
| write rejected (`READ_ONLY_MODE`) | the CLI build has write support disabled: production builds have write access, dev builds are read-only by default |
| "--project-id is required" on issue create | look up project ids first: `redmine-cli project list --json` |
| invalid status/tracker/priority ID | look up valid values first: `redmine-cli lookup statuses --json` |
