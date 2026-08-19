# Global notes

Facts that hold in every session. Anything procedural lives in a skill (listed at the bottom) —
invoke it when the task matches; don't reconstruct the procedure from memory.

## Shell

- `jk` is an alias for `jmake` (`$HOME/.usr/bin/jmake`). Use `jmake` directly — shell aliases
  aren't available in Bash tool calls.
- Building in another directory: prefix with `cd /path/to/dir &&`.
- `code` is a bash function (VS Code / Cursor remote CLI wrapper). Source it first:
  `source $HOME/Templates/code-function.sh && code <args>`.
- If an `ssh` command is denied by the session permission system, use `myssh` with the same
  arguments (`$HOME/.usr/bin/myssh`, a symlink to /bin/ssh).

## Tooling

- **ai-pim CLIs** (`confluence-cli`, `jira-cli`, `glean-cli`, `nvbugs-cli`, `redmine-cli`,
  `slack-cli`, … 28 in total): just call them by name. On m-fwdev-167 bashrc transparently runs
  them in the `pim` Docker container; elsewhere the native binaries are used. Nothing to start
  by hand, including after a reboot. → skill `aipim-cli-env`
- **Writing to Confluence**: use `~/myGit/crosslv/assets/aipim/confluence-update` (raw curl).
  Never `confluence-cli page create/update` — those need an interactive TTY that an AI session
  cannot provide. Reads are fine. → skill `aipim-cli-env`
- **gitlab-master.nvidia.com** speaks SSH on **port 12051**:
  `git clone ssh://git@gitlab-master.nvidia.com:12051/<group>/<repo>.git`. HTTPS clones need a
  PAT (`https://oauth2:<token>@…`).
- Credentials live in files, never in docs/memory/commit messages: `~/.jenkins_env`,
  `~/.confluence_env` (both mode 600, on NFS home).

## Hard rules

1. **Never touch `l-fwminireg-*`** — dedicated CI/DoA machines. Do not lock, ssh into, burn,
   mlxconfig or fw-reset them. NOGA reports them free while a live CI session is running on
   them. → skill `regression-repro`
2. **Never bulk-apply an mlxconfig dump.** A few parameters at a time, read back Next Boot after
   each, verify Current after the cold boot. A 457-parameter `set` took out three cards in one
   day. → skill `nic-livefish-recovery`
3. **A green run is not a reproduction.** For any repro, success means the *same failure
   signature* appears locally. → skill `regression-repro`

Rules 1 and 2 are additionally enforced by a PreToolUse hook
(`~/myGit/crosslv/assets/claude/hooks/guard.py`), which denies the matching Bash calls outright.
It reads the command text, so a heredoc that merely mentions `l-fwminireg` counts too — write
such files with the Write/Edit tools, which the hook does not gate. Regression tests sit next to
it; run them after any change.

## Skills

| skill | covers |
|---|---|
| `gerrit-change` | commit message format, cherry-picks, Change-Id rules |
| `gerrit-stack` | pushing dependent commits, RELATED_CHANGES / IGNORE topics |
| `utopx-ci-rerun` | re-triggering utopx / golan_fw CI, concurrency and vote preconditions |
| `ci-forensics` | red build → session_id → MARS archive → the raw failure log |
| `regression-repro` | reproducing a regression locally ("regression repro template") |
| `noga-lock` | querying, locking, waiting for lab servers |
| `nic-livefish-recovery` | un-bricking a NIC that vanished from PCI; the mlxconfig rule |
| `satpf-171` | sat-PF env on l-fwreg-171, BlueField mlxconfig read-back traps |
| `aipim-cli-env` | the ai-pim CLI container, Confluence write path |

Full prose for anything above was split out of this file on 2026-08-13; the pre-split version is
at `~/.claude/backups/CLAUDE.md.pre-skill-split.20260813-190042`.
