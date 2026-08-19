---
name: managing-confluence
description: Manage Confluence pages, spaces, search, comments, labels, attachments, and exports via confluence-cli. Use when working with Confluence wiki pages, documentation lookup, page publishing, or content lifecycle tasks.
---

# Confluence Content Management

Use `confluence-cli` for Confluence documentation workflows. **WSL note:** In WSL with Windows-installed binaries, append `.exe` to CLI names (`<tool>-cli.exe`).

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
