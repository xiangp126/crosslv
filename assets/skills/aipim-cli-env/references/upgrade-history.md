# ai-pim-utils upgrade history

What each past upgrade changed — read when you need to know what a version changed. The upgrade
procedure and the post-upgrade sanity sequence are in `../SKILL.md` → "Versions and upgrades".

### 0.119.0 → 0.121.3 upgrade, done 2026-09-04

Nothing that affects us.

- **Credentials survive** the container recreate (`$HOME` bind mount): `Authenticated: true`,
  same token, env var still `CONFLUENCE_CLI_ACCESS_TOKEN`.
- `space list --limit 5` is still the right smoke test, still ~seconds.
- **The write gate did NOT change.** `page create` from a non-interactive shell still exits
  **11 / CONFIRMATION_REQUIRED** on 0.121.3, exactly as on 0.119.0.
- The build took ~2.5 min with `--no-cache` (apt layer 118 s + install layer 27 s).
- Rollback image kept as `ai-pim:0.119.0-rollback`.

### 0.99.3 → 0.119.0 upgrade, done 2026-08-27

- **Credentials survive.** `~/.ai-pim-utils/tokens.toml` is on the bind-mounted `$HOME`;
  `confluence-cli auth status` still `Authenticated: true` with the same token afterwards.
- **Env-var override renamed**: `CONFLUENCE_CLI_API_TOKEN` → **`CONFLUENCE_CLI_ACCESS_TOKEN`**.
  The persistent `tokens.toml` path is unchanged, so only scripts using the env var break.
- **`confluence-cli space list` without `-l/--limit` now walks *every* space** in the instance
  and effectively hangs (0.99.3 stopped at 100). Use `space list --limit N` — `--limit 5`
  returns in ~2.4 s. Good smoke-test command after any upgrade.
- **`nvbugs-cli` command set unchanged** — still the same 21 groups; **no** `summarize` /
  `similar` equivalents were added, so those stay MCP-only (BugNeMo is server-side).
