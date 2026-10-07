---
name: managing-confluence
description: >-
  Read, search, export, create, and update Confluence content. Use the runtime's available MCP for
  indexed prose discovery, confluence-cli for exact page metadata and exports, and the raw-curl
  helper for agent writes because CLI write commands require an interactive TTY. **This is the
  entry point for all Confluence content work** — lookup, search, export, page creation and
  updates, comments, labels, attachments. The agent write procedure lives in skill
  `aipim-cli-env` ("Confluence writes — the AI-only path"), which also covers a broken CLI
  container.
---

# Confluence Content Management

## Which tool does what

| Need | Use |
|---|---|
| broad prose discovery / search | the current runtime's MCP route; read the host adapter below |
| exact page id, version, hierarchy, labels, attachments, or export | `confluence-cli` read commands |
| create / update from an interactive human terminal | `confluence-cli page create/update` |
| create / update from an agent | `~/myGit/crosslv/assets/aipim/confluence-update` (raw curl); CLI writes are TTY-gated and exit 11 before reaching the API |

- Before MCP discovery or invocation, read `references/hosts/claude.md` in Claude Code or
  `references/hosts/codex.md` in Codex. Do not assume that a catalogued MCP is active.
- Glean MCP (`glean_search`, `glean_get_file`, `system="confluence"`) is the cheapest route for
  prose and research reads, but it returns Glean's *index*: no page id, no version, no ancestors.
  Reads that need the page id or version, and every read that precedes a write, use the CLI.
- The CLI is not read-only: it is the interactive human publishing tool. An agent cannot drive its
  typed confirmation gate, hence the raw-curl helper.

## Agent sessions

The command reference further down is written for a human at an interactive terminal. From an
agent:

1. **Call the CLI through the container.** The 28 `*-cli` names are bashrc shell functions; a
   non-interactive shell falls through to the native binary and dies on glibc. Spell out the
   container call the wrapper would have made:

   ```bash
   docker exec -e AI_PIM_UTILS_TELEMETRY_DISABLED=1 -w "$PWD" pim confluence-cli <args>
   ```

2. **Never write with the CLI.** `page create` and `page update` both sit behind a
   typed-confirmation gate that needs stdin *and* stderr to be TTYs; from an agent they exit
   **11 / CONFIRMATION_REQUIRED** without reaching the API. There is no `--yes` or `--force` flag,
   and the exit-code table's wording ("destructive operation") misleadingly suggests page creation
   is exempt. It is not.
3. **Write with `~/myGit/crosslv/assets/aipim/confluence-update`** (raw curl, runs natively on the
   host, no container). It does GET page → `version+1` → PUT, so it needs a page id and version —
   get those with the read commands. Usage, page creation, the token check and the measured gate
   evidence: skill `aipim-cli-env` → "Confluence writes — the AI-only path".
4. **Reads work:** `page get`, `page find`, `page ancestors`, `page export`, `space get`, CQL
   search. For a liveness check use a bounded read — `space get <KEY>` or
   `space list --limit 5` — never bare `space list`, which enumerates every space and can exceed
   a 120 s timeout.

**WSL:** with Windows-installed binaries, append `.exe` to CLI names (`<tool>-cli.exe`).

## Verify Installation

```bash
confluence-cli --version
confluence-cli --help
confluence-cli auth status
```

If authentication is missing:

```bash
confluence-cli auth set-token <your-token>
confluence-cli space list --limit 5      # bounded real read; bare `space list` walks every space
confluence-cli config set space ENG
```

## Quick Start

```bash
# Read and search
confluence-cli page get 12345 --toon
confluence-cli page find 'deployment guide' --toon
confluence-cli page find --cql 'space="ENG" AND title~"API"' --json
confluence-cli page find --label documentation --space ENG --json

# Create or update
confluence-cli page create 'Feature Documentation' '# Overview'
confluence-cli page update 12345 '# Updated Content'
confluence-cli page ancestors 12345 --json

# Lifecycle / export
confluence-cli page export 12345 --output page.html
confluence-cli page archive 12345 --json
confluence-cli page restore-version 12345 --version 3 --json
```

- Root flags `--relative`, `--utc`, `--local`, and `--timezone` only affect human output; JSON/TOON
  output keeps the original API timestamps.
- Exact syntax and flags: `confluence-cli <command> --help`; full command surface:
  `confluence-cli --help`.
- For Jira work, use `managing-jira`.

## Workflows

- **Create Documentation** — [workflows/create-documentation.md](workflows/create-documentation.md)
- **Search and Export** — [workflows/search-and-export.md](workflows/search-and-export.md)
- **Page Lifecycle** — [workflows/manage-page-lifecycle.md](workflows/manage-page-lifecycle.md)

## Troubleshooting

- **Space key is required**: run `confluence-cli config set space <KEY>`
- **Authentication fails**: run `confluence-cli auth logout` then `confluence-cli auth set-token ...`
- **Page not found**: use `confluence-cli page find 'title text'` to locate the page ID
- **Search returns nothing**: broaden the query first, then add `--space`, `--cql`, or `--label`
