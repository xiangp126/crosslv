---
name: managing-confluence
description: >-
  Read, search, export, create, and update Confluence content. Use the runtime's available MCP for
  indexed prose discovery, confluence-cli for exact page metadata and exports, and the raw-curl
  helper for agent writes because CLI write commands require an interactive TTY. **This is the
  entry point for all Confluence content work** — lookup, search, export, page creation and
  updates, comments, labels, attachments. Skill `aipim-cli-env` covers only the case where the
  CLI container itself is broken.
---

# Confluence Content Management

**Which tool does what:**

| Need | Use |
|---|---|
| broad prose discovery / search | the current runtime's MCP route; read the host adapter below |
| exact page id, version, hierarchy, labels, attachments, or export | `confluence-cli` read commands |
| create / update from an interactive human terminal | `confluence-cli page create/update` |
| create / update from an agent | `~/myGit/crosslv/assets/aipim/confluence-update` (raw curl); CLI writes are TTY-gated and exit 11 before reaching the API |

Before MCP discovery or invocation, read `references/hosts/claude.md` in Claude Code or
`references/hosts/codex.md` in Codex. Do not assume that a catalogued MCP is active. Glean can
return indexed prose but not authoritative page ids or versions, so use the CLI before a write.

The CLI itself is not read-only: it is the interactive human publishing tool. An agent cannot
drive its typed confirmation gate, hence the raw-curl helper. Details and measured evidence:
skill `aipim-cli-env`.

Use `confluence-cli` for Confluence documentation workflows. **WSL note:** In WSL with Windows-installed binaries, append `.exe` to CLI names (`<tool>-cli.exe`).

> ## ⚠ Read this first in an agent session
>
> Everything below is written for a **human at an interactive terminal**. Two things change
> for an agent, both measured on 2026-09-04 — see skill `aipim-cli-env` for the full record:
>
> 1. **The CLI is not on your PATH the way it looks.** The 28 `*-cli` names are bashrc shell
>    functions; a non-interactive shell falls through to the native binary and dies on glibc.
>    Spell out the container call the wrapper would have made:
>
>    ```bash
>    docker exec -e AI_PIM_UTILS_TELEMETRY_DISABLED=1 -w "$PWD" pim confluence-cli <args>
>    ```
>
> 2. **The write subcommands are the right tool for a human, but an agent cannot drive them.**
>    `page create` and `page update` both sit behind a
>    typed-confirmation gate that needs stdin *and* stderr to be TTYs; from an agent they exit
>    **11 / CONFIRMATION_REQUIRED** without reaching the API. Do not look for a `--yes` or
>    `--force` flag — there is none, and the exit-code table's wording ("destructive operation")
>    misleadingly suggests page creation is exempt. It is not.
>
>    **AI writes go through `~/myGit/crosslv/assets/aipim/confluence-update`** (raw curl, runs
>    natively on the host, no container). It does GET page → `version+1` → PUT, so it needs a
>    page id and version — get those with the read commands below.
>
> The read commands (`page get`, `page find`, `page ancestors`, `page export`, `space get`, CQL
> search) all work fine as an agent. Prefer `space get <KEY>` over `space list` as a liveness
> check — `space list` enumerates every space and can exceed a 120 s timeout.

## Verify Installation

```bash
confluence-cli --version
confluence-cli --help
confluence-cli auth status
```

If authentication is missing:

```bash
confluence-cli auth set-token <your-token>
confluence-cli space list
confluence-cli config set-space ENG
```

## When to Use This Skill

- Read page content by ID or title
- Search pages by text, CQL, or labels
- Create, update, export, archive, or restore documentation pages
- Manage comments, labels, attachments, and page hierarchy
- Work with space-level page listings or page lifecycle tasks

For Jira work, use `managing-jira`.

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

**Timestamp note:** Root flags like `--relative`, `--utc`, `--local`, and `--timezone` only affect human output. JSON/TOON output keeps original API timestamps.

Use `confluence-cli <command> --help` for exact syntax and flags.

## Workflows

- **Create Documentation** — [workflows/create-documentation.md](workflows/create-documentation.md)
- **Search and Export** — [workflows/search-and-export.md](workflows/search-and-export.md)
- **Page Lifecycle** — [workflows/manage-page-lifecycle.md](workflows/manage-page-lifecycle.md)

## Troubleshooting

- **Space key is required**: run `confluence-cli config set-space <KEY>`
- **Authentication fails**: run `confluence-cli auth logout` then `confluence-cli auth set-token ...`
- **Page not found**: use `confluence-cli page find 'title text'` to locate the page ID
- **Search returns nothing**: broaden the query first, then add `--space`, `--cql`, or `--label`

Run `confluence-cli --help` for the full command surface.
