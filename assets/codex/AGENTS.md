# Global preferences

- Respond in Simplified Chinese by default, including progress updates and final answers.
- Preserve the original language for code, commands, identifiers, file paths, logs, error
  messages, and technical terms when translation would reduce precision.
- Follow the user's explicit language request when they ask for another language.

# Global engineering notes

Facts that hold in every session live here. Procedures live in the corresponding skill under
`~/.agents/skills`; load the matching skill instead of reconstructing a workflow from memory.

## Shared skills (Claude Code + Codex)

- Claude Code and Codex load the **same physical skills** from
  `~/myGit/crosslv/assets/skills`. `~/.claude/skills` is a tree link; shared entries under
  `~/.agents/skills` are per-skill links so independently installed Codex skills remain intact.
- Whenever the user asks to add, modify, synchronize, or repair a skill, invoke
  `skill-maintainer` and edit the canonical path returned by `jskill path <name>`. Never maintain
  a Claude copy and a Codex copy.
- Keep shared behavior in `SKILL.md` and common resources. Put only runtime-specific tool syntax
  in `references/hosts/claude.md` or `references/hosts/codex.md`; when present, read the Codex
  adapter before invoking tools.
- Finish skill changes with `jskill sync` and `jskill check`. Start a new session when validating
  discovery of a new skill or changed frontmatter metadata.

## Shell and local tools

- `jk` is an alias for `jmake` (`$HOME/.usr/bin/jmake`). Use `jmake` directly in Codex shell
  calls because aliases and interactive shell functions are not guaranteed to load.
- Use the shell tool's working-directory option when available. If a command must change
  directory internally, use an explicit `cd /path && ...`.
- `code` is a bash function. Source `$HOME/Templates/code-function.sh` before using it.
- Do not rename or wrap a denied command to bypass Codex permissions. Request approval for the
  exact operation or a suitably narrow reusable prefix.
- FW reset goes through `jmake --fw-reset --device <dev>`, not bare `mlxfwreset`. Every test run
  gets its own reset. See skill `fw-build-burn-utopx`.

## Tooling

- ai-pim CLIs (`confluence-cli`, `jira-cli`, `glean-cli`, `nvbugs-cli`, `redmine-cli`,
  `slack-cli`, and the rest) are interactive bash functions on `m-fwdev-167`. From Codex, use
  the explicit `docker exec ... pim <cli>` form documented by skill `aipim-cli-env`.
- The active Codex MCP set is maintained in `~/.codex/config.toml`. MCP tools can be deferred;
  use tool search before concluding that a configured tool is unavailable.
- Confluence prose discovery uses Glean MCP. Exact page metadata uses `confluence-cli` reads.
  Codex page writes use `~/myGit/crosslv/assets/aipim/confluence-update` because the CLI write
  commands require an interactive TTY. See skills `managing-confluence` and `aipim-cli-env`.
- `gitlab-master.nvidia.com` uses SSH port 12051:
  `git clone ssh://git@gitlab-master.nvidia.com:12051/<group>/<repo>.git`.
- Credentials stay in their mode-600 files, never in documentation, memory, command output, or
  commits. Relevant files include `~/.jenkins_env` and `~/.confluence_env`.

## Hard rules

1. **Never touch `l-fwminireg-*`.** Do not lock, SSH into, burn, run `mlxconfig`, or reset these
   dedicated CI/DoA machines. NOGA can report them free during a live CI session. See skill
   `regression-repro`.
2. **Never bulk-apply an `mlxconfig` dump.** Change only the few relevant parameters, read back
   Next Boot after each change, and verify Current after the cold boot. See skill
   `nic-livefish-recovery`.
3. **A green run is not a reproduction.** Reproduction succeeds only when the same failure
   signature appears locally. See skill `regression-repro`.
4. **Even SUBMINOR is official-build-only; local builds use the next odd SUBMINOR.** If the
   bit-exact release is required, burn the official release image instead of rebuilding it. See
   skill `fw-build-burn-utopx`.
5. **Never reboot or power-cycle `m-fwdev-167` without Peter's explicit approval.** This covers
   `jmake --power-cycle`, `reboot`, `shutdown`, IPMI power operations, and `mlxfwreset -l 4`.
   Device-level resets such as `mlxfwreset -l 3` and `jmake --fw-reset` are allowed. Other lab
   machines may be rebooted when the authorized workflow requires it.
6. **When something passed before and fails now, run the known-good control first.** Re-burn or
   re-check out the last passing artifact and use the same seed before theorizing or changing NV.
   See skill `fw-build-burn-utopx`, section 7b.

Claude's PreToolUse guard enforces parts of rules 1 and 2 only inside Claude Code. It does not
intercept Codex commands. Codex must enforce every hard rule before constructing or executing a
command.

## Skill routing

| Skill | Use it for |
|---|---|
| `fw-build-burn-utopx` | Build FW, burn a local card, bring drivers up, and run utopx |
| `steering-capture` | Freeze a live utopx run and capture STE / steering-chain state (`--wait_on_err`, `stedmp.sh`, `--hwtrace`). |
| `gerrit-change` | Commit-message format, Change-Id rules, cherry-picks and backports |
| `utopx-ci-rerun` | Re-trigger utopx/golan_fw CI with vote and concurrency checks |
| `ci-forensics` | Jenkins failure to session id, MARS archive, and raw failure log |
| `ci-support-ticket` | Prepare the ServiceNow CI-support form when explicitly requested |
| `fsearch-failures` | Query regression failure history and attribute occurrences to commits |
| `regression-repro` | Reproduce a regression locally from Redmine/MARS coordinates |
| `noga-lock` | Query, reserve, renew, wait for, and release lab servers |
| `nic-livefish-recovery` | Recover a NIC missing from PCI and avoid unsafe bulk NV writes |
| `bluefield-fwconfig` | BlueField mlxconfig read-back and ARM-liveness traps |
| `aipim-cli-env` | ai-pim CLI container, credentials, upgrades, and MCP/CLI split |
| `regression-report-mail` | Nightly regression and coverage reports in Outlook |
| `managing-confluence` | Confluence discovery, exact reads, exports, and publishing |
| `tracking-redmine` | redmine-cli fallback when nvidia-redmine MCP is unavailable |
| `utopx-regression-ticket` | File the standard Redmine ticket for a regression failure |
| `skill-maintainer` | Add or modify canonical skills shared with Claude; repair and check links |
