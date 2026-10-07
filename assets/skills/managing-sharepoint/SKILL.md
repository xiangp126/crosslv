---
name: managing-sharepoint
description: Search and retrieve SharePoint documents via MCP-backed CLI. Find files by keyword, download content, inspect metadata and permissions. Use when searching SharePoint files, reading document content, or checking file permissions.
---

# SharePoint Management

`sharepoint-cli` connects to SharePoint through a MaaS MCP server: search and read access to
documents across SharePoint sites — find files by keyword, read content, inspect metadata and
permissions.

- **WSL:** with Windows-installed binaries, append `.exe` to CLI names (`<tool>-cli.exe`).
- Wiki content: skill `managing-confluence`.

## Setup

```bash
sharepoint-cli --version
```

If the command is not found, see the [installation page](https://outlook-cli-80d21a.gitlab-master-pages.nvidia.com/).

Authenticate with `auth init` + `auth complete` (agent / SSH / split-browser login): `auth init`
prints a browser URL without depending on a long-running local callback server.

```bash
sharepoint-cli auth init                         # prints the sign-in URL
sharepoint-cli auth complete '<callback-url>'    # after browser sign-in, the full callback URL
sharepoint-cli auth status
sharepoint-cli auth logout
```

## Commands

All commands: `sharepoint-cli --help`; flags and examples: `sharepoint-cli <command> --help`.

### Search

```bash
sharepoint-cli search --query "quarterly report"
sharepoint-cli search --query "onboarding" --limit 10      # more results per page (default 3)
sharepoint-cli search --query "design doc" --output json   # JSON for scripting
```

Search indexes file names, content (Office docs and PDFs, not just file names) and metadata across
the SharePoint sites you have access to.

Pagination — each page returns a cursor; pass it back with the same query:

```bash
sharepoint-cli search --query "project plan" --output json > page1.json
CURSOR=$(jq -r '.data.cursor' page1.json)
sharepoint-cli search --query "project plan" --cursor "$CURSOR" --output json
```

### Read content and metadata

Search results include the SharePoint URL; pass it to `file get` and `file metadata`:

```bash
sharepoint-cli search --query "budget" --output json | jq -r '.data.results[].url'

sharepoint-cli file get --file-url "https://nvidia.sharepoint.com/sites/team/Documents/report.pptx"
sharepoint-cli file get --file-url <url> --max-length 5000     # limit content length
sharepoint-cli file metadata --url "https://nvidia.sharepoint.com/sites/team/Documents/report.pptx"
```

`file metadata` returns title, type, owner, created/updated dates, and the permission breakdown:
**Owners** (full control), **Contributors** (edit access), **Viewers** (read-only access).

### Server health

```bash
sharepoint-cli health
```

## Workflow

**Document Discovery** — [workflows/find-documents.md](workflows/find-documents.md): search,
pick the file, check its metadata, read its content.

## Troubleshooting

- **Authentication errors:** run `sharepoint-cli auth init`, complete sign-in in a browser, then
  `sharepoint-cli auth complete '<callback-url>'`.
- **"server returned an error":** the MCP server may be temporarily unavailable — check with
  `sharepoint-cli health`.
- **Search returns no results:** try broader keywords.
- **Broad queries fail:** very common terms (e.g., "nvidia") may cause server-side timeouts — use
  more specific search terms.
