# Claude Code adapter

Claude Code has two MCP views with different purposes:

- `~/.claude/settings.json` may contain the broad MaaS catalogue. Listed does not mean usable.
- `~/.claude.json` top-level `mcpServers` is the curated, authenticated set loaded by sessions.

Inspect both live files instead of relying on a saved count or list. To adopt a server, add the
standard HTTP entry to the active set, restart Claude Code, complete that server's authorization,
and verify its tools. A configuration edit does not activate tools in an existing session.

Do not bulk-copy catalogue entries into the active set; it creates unauthenticated servers and
unnecessary discovery cost.
