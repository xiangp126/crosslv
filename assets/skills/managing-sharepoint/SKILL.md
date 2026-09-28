---
name: managing-sharepoint
description: Search and retrieve SharePoint documents via MCP-backed CLI. Find files by keyword, download content, inspect metadata and permissions. Use when searching SharePoint files, reading document content, or checking file permissions.
---
<!--
Progressive Disclosure:
- Level 1 (YAML front matter): Skill metadata
- Level 2 (This file): Overview, quick start, key patterns
- Level 3: workflows/ for multi-step procedures

Related skills:
- managing-onedrive: For personal OneDrive files
- managing-confluence: For wiki content
-->

# SharePoint Management

Search and retrieve SharePoint documents via `sharepoint-cli` — find files by keyword, read content, and inspect metadata and permissions. **WSL note:** In WSL with Windows-installed binaries, append `.exe` to CLI names (`<tool>-cli.exe`).

`sharepoint-cli` connects to SharePoint through a MaaS MCP server, providing search and read access to documents across SharePoint sites.

## Verify Installation

```bash
sharepoint-cli --version
```

If command not found, see [installation page](https://outlook-cli-80d21a.gitlab-master-pages.nvidia.com/).

## Authentication

```bash
# Start agent / SSH / split-browser login
sharepoint-cli auth init

# After browser sign-in, complete with the full callback URL
sharepoint-cli auth complete '<callback-url>'

# Check status
sharepoint-cli auth status

# Log out
sharepoint-cli auth logout
```

Use `auth init` + `auth complete` for skill-driven workflows. `auth init` prints a browser URL without depending on a long-running local callback server.

## When to Use This Skill

- **Find documents**: Search across SharePoint sites by keyword
- **Read file content**: Retrieve document text for review or processing
- **Inspect metadata**: Check file owner, type, dates, and permissions
- **Check connectivity**: Verify MCP server health

For personal OneDrive files, see [managing-onedrive](../managing-onedrive/SKILL.md).

## Quick Start

### Search for Documents

```bash
# Search by keyword
sharepoint-cli search --query "quarterly report"

# Get more results per page
sharepoint-cli search --query "onboarding" --limit 10

# Paginate through results
sharepoint-cli search --query "engineering" --cursor <cursor-from-previous-result>

# JSON output for scripting
sharepoint-cli search --query "design doc" --output json
```

### Retrieve File Content

```bash
# Get file content by SharePoint URL
sharepoint-cli file get --file-url "https://nvidia.sharepoint.com/sites/team/Documents/report.pptx"

# Limit content length
sharepoint-cli file get --file-url <url> --max-length 5000
```

### Inspect File Metadata

```bash
# Get metadata (title, type, owner, dates, permissions)
sharepoint-cli file metadata --url "https://nvidia.sharepoint.com/sites/team/Documents/report.pptx"
```

### Check Server Health

```bash
sharepoint-cli health
```

Run `sharepoint-cli --help` for all commands. Run `sharepoint-cli <command> --help` for flags and examples.

## Key Patterns

### Finding a File URL

Search results include SharePoint URLs. Use these URLs with `file get` and `file metadata`:

```bash
# Search and extract URLs from JSON output
sharepoint-cli search --query "budget" --output json \
  | jq -r '.data.results[].url'

# Then retrieve content or metadata
sharepoint-cli file get --file-url <url-from-search>
sharepoint-cli file metadata --url <url-from-search>
```

### Search Pagination

Search returns a limited number of results per page. Use `--cursor` to paginate:

```bash
# First page
sharepoint-cli search --query "project plan" --output json > page1.json

# Extract cursor for next page
CURSOR=$(jq -r '.data.cursor' page1.json)

# Next page
sharepoint-cli search --query "project plan" --cursor "$CURSOR" --output json
```

## Workflows

1. **Document Discovery** ([workflows/find-documents.md](workflows/find-documents.md))
   - Search for files by keyword, retrieve content, inspect metadata

## Troubleshooting

**Authentication errors:** Run `sharepoint-cli auth init`, complete sign-in in a browser, then run `sharepoint-cli auth complete '<callback-url>'`.

**"server returned an error":** The MCP server may be temporarily unavailable. Check with `sharepoint-cli health`.

**Search returns no results:** Try broader keywords. The search indexes file names, content, and metadata across SharePoint sites you have access to.

**Broad queries fail:** Very common terms (e.g., "nvidia") may cause server-side timeouts. Use more specific search terms.
