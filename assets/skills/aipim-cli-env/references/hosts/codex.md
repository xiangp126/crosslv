# Codex adapter

Codex's `~/.codex/config.toml` is normally linked to
`~/myGit/crosslv/assets/codex/config.toml`. Its configured MCP server list is
separate from Claude Code's active list. Update the Codex entries explicitly
when adding or removing a Claude server, then restart Codex. Inspect live tool
discovery because Codex may expose configured tools lazily.

The Codex config contains server names, HTTPS URLs, tool policies, and an
`http_headers_helper` command, but no credential values. The helper
`~/.codex/bin/claude-mcp-headers` reads OAuth access tokens from Claude Code's
`~/.claude/.credentials.json` and static HTTP headers from the active server's
entry in `~/.claude.json`. It checks the exact server name and URL before
returning headers. NVIDIA MaaS names have an additional URL-pattern check.
`claude-mcp-headers --list` prints active HTTP server names without tokens.

Claude Code remains the credential owner. OAuth refresh starts in the
background when a token has 15 minutes or less remaining because Codex gives
the header helper only a short execution window. An already expired token can
make that server unavailable for a session while Claude refreshes it; start a
new Codex session after the refresh. The refresh log is
`~/.claude/.codex-mcp-refresh.log`.

If a server is added in Claude, authenticate and verify it there before adding
its URL and header-helper command to Codex. Do not paste secrets into Codex
config. Confirm `codex mcp list` plus live tool discovery. Do not bulk-copy the
MaaS catalogue.
