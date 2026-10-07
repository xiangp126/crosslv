---
name: tracking-nvbugs
description: >-
  NVBugs via nvbugs-cli - the only write path (file, update or clone a bug, comment, attach, set
  relationships) because the nvidia-nvbugs MCP is read-only; the fallback for reads when the MCP
  tools are missing or failing; and the path for what they do not offer such as watchlists and
  module management. Prefer the MCP for reads whenever the session has it (Claude Code may list
  its tools as deferred tools to load first). Use nvbugs-cli to query bugs, view history and
  relationships, update fields, look up reference data, and track RCCA/fix info.
---
<!--
Progressive Disclosure:
- Level 1 (YAML front matter): Skill metadata and description
- Level 2 (This file): Overview, quick start, key patterns
- Level 3: workflows/, examples/
-->

# Bug Tracking with nvbugs-cli

> **Use the `nvidia-nvbugs` MCP first for reads.** When it is connected, its tools look up,
> search, summarize and audit bugs without a container or a TTY; this CLI is the fallback for
> when they are missing or failing, and for what they do not offer, such as watchlists and module
> management. **The MCP is read-only**: every write — file, update or clone a bug, comment,
> attach, set relationships — goes through `nvbugs-cli`. Details: skill `aipim-cli-env` →
> "NVBugs: MCP for reads, `nvbugs-cli` for writes".

**WSL note:** In WSL with Windows-installed binaries, append `.exe` to CLI names (`<tool>-cli.exe`).

## Setup

Check authentication before any other call:

```bash
nvbugs-cli --version
nvbugs-cli auth status        # want: Authenticated: true
```

If it reports `Authenticated: false`, stop and ask Peter to authenticate — creating and storing
the token are his steps: he creates a token at https://nv-auth.nvidia.com/tokens and runs
`nvbugs-cli auth set-token <your-token>`. Re-run `nvbugs-cli auth status` afterwards.

## Quick Reference

Full syntax: `nvbugs-cli --help`, `nvbugs-cli <command> --help`.

### Read Bug Data

```bash
nvbugs-cli bug get 12345 --json
nvbugs-cli bug get-any 12345 --json        # Includes security-restricted bugs
nvbugs-cli bug description 12345 --json
nvbugs-cli bug images list 12345 --json
nvbugs-cli bug images extract 12345 --output-dir /tmp/bug-12345-images
```

### Search Bugs

`--engineer` and `--requester` take **full names**, not usernames — resolve usernames via
helios-cli first. Raw `--criteria` uses **database field names** like `BugEngineerFullName`,
`BugRequesterFullName`, and `ActionReqByFullName` (not `Engineer=` or `Requester=`). Always
combine person searches with `--module` or `--status` to avoid timeouts. Details:
[Search Strategies](workflows/search-strategies.md).

```bash
# By person (full name required, narrow with --module or --status)
nvbugs-cli search bugs --requester "Julie Yaunches" --module "Open-Source-Review-Board" --json
nvbugs-cli search bugs --engineer "John Smith" --status open --json

# By criteria
nvbugs-cli search bugs --criteria "BugEngineerFullName=John Smith" --criteria BugAction=Open --json
nvbugs-cli search bugs --module "Graphics Driver" --priority P1 --json

# By synopsis text (use specific phrases, add --module-id to avoid timeouts)
nvbugs-cli search by-synopsis "OSRB: Request to contribute" --json

# Watchlists (saved searches)
nvbugs-cli watchlist list --json
nvbugs-cli watchlist run 12345 --json
```

### Watchlist Management

Syntax: `nvbugs-cli watchlist --help`.

- `watchlist create` creates new watchlists; clone-based copies are isolated in `watchlist clone`
  (`create` no longer accepts `--clone-from`).
- Standard NIM batches: pass repeatable `--keyword` values (or `"A AND B"`), optional `--module`,
  and module API `--division` values (`Software`/`sw`/`1`, `Hardware`/`hw`/`2`,
  `Information Systems`/`is`/`3`).
- Before writing, inspect the planned filters and request payloads with `--dry-run --json`.

### Bug History and Relationships

```bash
nvbugs-cli bug history 12345 --json
nvbugs-cli bug history-batch 12345 67890 11111 --json
nvbugs-cli bug relationships gated-by 12345 --json
nvbugs-cli bug relationships gating 12345 --max-depth 3 --flat --json
```

Root flags `--relative`, `--utc`, `--local`, and `--timezone` only affect human output; JSON/TOON
output keeps the original API timestamps.

### Comments and Attachments

```bash
nvbugs-cli comment list 12345 --json
nvbugs-cli attachment list 12345 --json
nvbugs-cli attachment download 12345 <attachment-guid> --output output.txt
```

### Write Operations

```bash
nvbugs-cli comment add 12345 --text "Fix verified" --json
nvbugs-cli attachment upload 12345 screenshot.png --json
nvbugs-cli bug relationships add-gated 12345 67890 --json
```

### Reference Data Lookups

```bash
nvbugs-cli lookup bug-types --div-id 100 --json
nvbugs-cli lookup bug-actions --div-id 100 --type-id 6 --json
nvbugs-cli lookup dispositions --div-id 100 --type-id 6 --json
nvbugs-cli lookup action-disposition-pairs --div-id 100 --type-id 6 --json
nvbugs-cli lookup priorities --div-id 100 --type-id 6 --json
nvbugs-cli lookup hardware --hardware-type "GPU/Board" --json
```

### Modules

```bash
nvbugs-cli module list "GPU Driver" --json
nvbugs-cli module get "GPU Driver" --app-division 1 --json    # numeric division ID, 1-5
nvbugs-cli module categories "GPU Driver" --json
nvbugs-cli module members list "GPU Driver" --app-division 1 --json
```

### RCCA & Fix Info

```bash
nvbugs-cli rcca fix-info <bug-id> --json        # read-only: no CLI command writes fix info
nvbugs-cli rcca escape-areas --json
nvbugs-cli rcca test-escape-data <bug-id> --json
```

## Workflows

| Task | Workflow |
|---|---|
| Find bugs by person, topic, module; timeouts and name-format pitfalls | [Search Strategies](workflows/search-strategies.md) |
| Look up a bug: details, description, history, comments, dependencies | [Bug Investigation](workflows/bug-investigation.md) |
| Process watchlist (saved search) bugs: prioritize, assign | [Triage Queue](workflows/triage-queue.md) |
| Map gated-by/gating trees, find blockers | [Dependency Analysis](workflows/dependency-analysis.md) |
| Create, update, comment, manage attachments, set relationships | [Bug Update](workflows/bug-update.md) |
| Valid bug types, actions, dispositions, priorities, severities, platforms, hardware | [Reference Data Lookup](workflows/reference-data-lookup.md) |
| Search modules; members, categories, NSpect IDs, Redmine mappings | [Module Management](workflows/module-management.md) |
| Root cause, fix details, risk assessment, escape tracking data | [RCCA & Fix Info](workflows/rcca-fix-info.md) |

## Example Scripts

- **[examples/investigate-bug.sh](examples/investigate-bug.sh)** — Investigate a bug: details, history, and dependencies
- **[examples/triage-watchlist.sh](examples/triage-watchlist.sh)** — Run a watchlist and display bugs for triage

## Troubleshooting

| Symptom | Fix |
|---|---|
| Command not found | Verify `nvbugs-cli` is in PATH: `which nvbugs-cli`. See the [installation page](https://outlook-cli-80d21a.gitlab-master-pages.nvidia.com/) |
| Authentication fails, or `401 Unauthorized` (token may be expired) | Check `nvbugs-cli auth status`, then ask Peter for a new token: he creates it at https://nv-auth.nvidia.com/tokens and runs `nvbugs-cli auth logout` and `nvbugs-cli auth set-token <new-token>`. Verify with `nvbugs-cli auth status` |
| Write operation rejected | Verify the CLI was built with write support enabled: dev builds are read-only by default, production builds have write access |
| Bug create fails with "Bugtype cant be empty" | `--bug-type` is required — look up valid values first: `nvbugs-cli lookup bug-types --div-id <id> --json` |
| Bug create/update fails with an action/disposition error | The API rejects `Key: 0` for action/disposition — pass `--action-id` and `--disposition-id` with valid IDs; look up valid pairs: `nvbugs-cli lookup action-disposition-pairs --div-id <id> --type-id <id> --json` |
| Hardware lookup returns 0 results | The hardware type filter must be exact (e.g., `"GPU/Board"` not `"GPU"`); list valid types with `nvbugs-cli lookup hardware --json` (no filter returns all) |
| Module categories returns HTTP 500 | The module name doesn't exist — verify with `nvbugs-cli module list "<name>" --json` first |
| Applications lookup fails with "at least one filter required" | Provide `--name` or `--type-id` (or both) |
| Bug clone fails with "disposition not allowed via API" | The source bug has a disposition that can't be assigned through the API — an NVBugs API limitation, not a CLI bug |
