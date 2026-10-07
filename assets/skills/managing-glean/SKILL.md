---
name: managing-glean
description: >-
  Fallback path for Glean, used only when the nvidia-glean MCP tools are missing or failing -
  prefer them whenever the session has them (Claude Code may list them as deferred tools to load
  first). Then use glean-cli to search enterprise content across all datasources, ask Glean AI
  questions, and read document content.
---
<!--
Progressive Disclosure:
- Level 1 (YAML front matter): Skill metadata
- Level 2 (This file): Overview, quick start, key patterns
- Level 3: workflows/ for multi-step procedures

Related skills:
- managing-sharepoint: For SharePoint documents
- managing-confluence: For Confluence wiki pages
-->

# Glean Enterprise Search

> **Use the `nvidia-glean` MCP first.** When it is connected, its `glean_search`, `glean_chat`
> and `glean_get_file` tools cover everything below without a container or a TTY; this CLI is
> the fallback for when they are missing or failing.

`glean-cli` connects to Glean through a MaaS MCP server: search across all connected datasources
(Google Drive, Confluence, Slack, Jira, etc.), Glean AI chat, file content by URL, file metadata,
and MCP server health. **WSL note:** In WSL with Windows-installed binaries, append `.exe` to CLI
names (`<tool>-cli.exe`).

For Confluence pages, see [managing-confluence](../managing-confluence/SKILL.md).

## Verify Installation

```bash
glean-cli --version
```

If command not found, see [installation page](https://outlook-cli-80d21a.gitlab-master-pages.nvidia.com/).

## Authentication

Check the status before any other call. Read its text: it exits 0 even when not authenticated.

```bash
glean-cli auth status
```

If it reports `Not authenticated`, stop and ask Peter to sign in — the login and the browser
sign-in are his steps. The flow for an agent / SSH / split-browser login is `auth init` +
`auth complete`: `auth init` prints a browser URL without depending on a long-running local
callback server.

```bash
# Start the login: prints the browser URL
glean-cli auth init

# After browser sign-in, complete with the full callback URL
glean-cli auth complete '<callback-url>'

# Log out
glean-cli auth logout
```

## Enterprise Search & Retrieval

Search results span all connected sources; retrieve a result's content with `get-file`. Add
`--output json` for scripting. Run `glean-cli --help` for all commands and
`glean-cli <command> --help` for flags and examples.

`get-file` and `get-metadata` need `--system`, set to the result's `datasource` field (e.g.
`confluence`, `gdrive`, `o365sharepoint`, `onedrive`, `jira`). `--help` does not mark the flag
required, but the Glean MCP server behind the CLI requires `system` for both calls.

```bash
# Search by keyword
glean-cli search --query "quarterly report"

# More results per page
glean-cli search --query "onboarding" --limit 10

# Paginate through results
glean-cli search --query "engineering" --cursor <cursor-from-previous-result>

# JSON output; extract results
glean-cli search --query "design doc" --output json
glean-cli search --query "release process" --output json \
  | jq -r '.data.results[]'

# Get file content by URL (e.g. a URL from search); --system = the result's datasource
glean-cli get-file --file-url "https://docs.google.com/document/d/..." --system gdrive

# Limit content length
glean-cli get-file --file-url <url> --system <datasource> --max-length 5000

# Get metadata (properties, attributes)
glean-cli get-metadata --url "https://docs.google.com/document/d/..." --system gdrive

# Check MCP server health
glean-cli health
```

## Glean AI Chat

Use `chat` for natural-language questions; answers are grounded in enterprise content.

```bash
# Ask a question
glean-cli chat --message "What is our PTO policy?"

# Continue a conversation
glean-cli chat --message "Tell me more about that" --chat-id <id-from-previous-response>

# JSON output
glean-cli chat --message "How do I request a new VM?" --output json
```

## Troubleshooting

- **Authentication errors:** check `glean-cli auth status`; if it reports `Not authenticated`,
  ask Peter to sign in again (`glean-cli auth init`, browser sign-in, then
  `glean-cli auth complete '<callback-url>'`).
- **"server returned an error":** The MCP server may be temporarily unavailable. Check with
  `glean-cli health`.
- **Search returns no results:** Try broader keywords.
