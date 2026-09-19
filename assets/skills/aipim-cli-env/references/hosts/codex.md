# Codex adapter

The active Codex MCP configuration is `~/.codex/config.toml`, normally linked to
`~/myGit/crosslv/assets/codex/config.toml`. Inspect that file and live tool discovery instead of
relying on a saved server count or list; Codex may expose configured tools lazily.

For NVIDIA MaaS HTTP servers, Codex uses `http_headers_helper` with
`~/.codex/bin/claude-mcp-headers`. The helper stores no credential and has no server allowlist: it
discovers Claude Code's authenticated `nvidia-*` entries dynamically, validates the MaaS URL,
and emits the current access-token header. Claude Code remains the credential owner and performs
refresh, avoiding two clients rotating copies of one refresh token. Inspect eligible names with
`claude-mcp-headers --list`; it does not print token values.

Refresh is on demand, not periodic. If a credential has 15 minutes or less remaining, the first
helper invocation takes a cross-process lock and waits for `claude mcp list`; concurrent MCP
connections wait for that same refresh, re-read the credential file, and return only after the
new expiry is verified. A refresh failure returns no stale token. Codex sets
`mcp_optional_startup_grace_ms = 0`, so a new session waits for each server's configured startup
timeout instead of freezing the initial tool catalogue after the default one-second grace.

To adopt another server, authenticate it in Claude Code first, then add this shape and restart
Codex:

```toml
[mcp_servers.nvidia-<name>]
url = "https://maas.prd.astra.nvidia.com/maas/<name>/mcp"
http_headers_helper = "/labhome/pexiang/.codex/bin/claude-mcp-headers nvidia-<name>"
startup_timeout_sec = 70
```

Do not copy the full MaaS catalogue into Codex, and do not hard-code its current active list into
the helper. Add only authenticated servers with a concrete use, then verify tool discovery.
