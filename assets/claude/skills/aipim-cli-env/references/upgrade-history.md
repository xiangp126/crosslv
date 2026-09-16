# ai-pim-utils 升级变更史

从 SKILL.md 移出(2026-09-16)。这是历史记录,不是操作规范——查"某版本改了什么"时读。

### 0.119.0 → 0.121.3 upgrade, done 2026-09-04 — what changed

**Nothing that affects us.** Recorded mainly so the next drift check has a baseline.

- ✅ **Credentials survive** the container recreate again (`$HOME` bind mount) —
  `Authenticated: true`, same token, env var still `CONFLUENCE_CLI_ACCESS_TOKEN`.
- ✅ `space list --limit 5` still the right smoke test, still ~seconds.
- ✅ **The write gate did NOT change.** `page create` from a non-interactive shell still exits
  **11 / CONFIRMATION_REQUIRED** on 0.121.3, exactly as on 0.119.0. The `confluence-update`
  raw-curl path stays the AI write route; do not re-litigate this per release.
- Build took ~2.5 min with `--no-cache` (apt layer 118 s + install layer 27 s).
- Rollback image kept as `ai-pim:0.119.0-rollback`.

### 0.99.3 → 0.119.0 upgrade, done 2026-08-27 — what changed

- ✅ **Credentials survive.** `~/.ai-pim-utils/tokens.toml` is on the bind-mounted `$HOME`;
  `confluence-cli auth status` still `Authenticated: true` with the same token afterwards.
- ⚠ **Env-var override renamed**: `CONFLUENCE_CLI_API_TOKEN` → **`CONFLUENCE_CLI_ACCESS_TOKEN`**.
  The persistent `tokens.toml` path is unchanged, so only scripts using the env var break.
- ⚠ **`confluence-cli space list` without `-l/--limit` now walks *every* space** in the instance
  and effectively hangs (0.99.3 stopped at 100). Use `space list --limit N` — `--limit 5`
  returns in ~2.4 s. Good smoke-test command after any upgrade.
- **`nvbugs-cli` command set unchanged** — still the same 21 groups; **no** `summarize` /
  `similar` equivalents were added, so those stay MCP-only (BugNeMo is server-side).

Sanity sequence after an upgrade (each step distinguishes a different failure):

```bash
docker exec -e AI_PIM_UTILS_TELEMETRY_DISABLED=1 pim <cli> --version        # new build in place?
docker exec -e AI_PIM_UTILS_TELEMETRY_DISABLED=1 pim confluence-cli auth status   # token survived?
docker exec -e AI_PIM_UTILS_TELEMETRY_DISABLED=1 -e AE=… -e AT=… pim \
    sh -c 'curl -s -o /dev/null -w "%{http_code}\n" -u "$AE:$AT" \
           https://nvidia.atlassian.net/wiki/rest/api/user/current'          # network+auth? want 200
docker exec -e AI_PIM_UTILS_TELEMETRY_DISABLED=1 pim confluence-cli space list --limit 5  # real read
```

⚠ In that curl, the `$AE`/`$AT` **must** be inside single quotes so they expand *in the
container*. Double-quoting expands them on the host (empty) and you get a misleading `401`.
