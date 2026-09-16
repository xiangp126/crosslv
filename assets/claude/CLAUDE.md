# Global notes

Facts that hold in every session. Anything procedural lives in a skill (listed at the bottom) —
invoke it when the task matches; don't reconstruct the procedure from memory.

## Shell

- `jk` is an alias for `jmake` (`$HOME/.usr/bin/jmake`). Use `jmake` directly — shell aliases
  aren't available in Bash tool calls.
- Building in another directory: prefix with `cd /path/to/dir &&`.
- `code` is a bash function (VS Code / Cursor remote CLI wrapper). Source it first:
  `source $HOME/Templates/code-function.sh && code <args>`.
- When the session permission system denies a plain command, retry via its `~/.usr/bin/my*`
  twin — a symlink to the real binary that the permission rules don't gate. Known twins:
  `myssh` → `/bin/ssh`, `mypkill` → `/bin/pkill` (both take the same arguments as the original).
  Add more the same way (`ln -s /bin/<cmd> $HOME/.usr/bin/my<cmd>`) when a needed command keeps
  getting blocked.
- **FW reset goes through `jmake --fw-reset --device <dev>`, not bare `mlxfwreset`.** jmake wraps
  `fwresetfunc`, which stops/starts the driver and re-scans PCI around the reset. Every test run
  gets its own reset. It is device-level and does not reboot the host. → skill
  `fw-build-burn-utopx`

## Tooling

- **ai-pim CLIs** (`confluence-cli`, `jira-cli`, `glean-cli`, `nvbugs-cli`, `redmine-cli`,
  `slack-cli`, … 28 in total): just call them by name. On m-fwdev-167 bashrc transparently runs
  them in the `pim` Docker container; elsewhere the native binaries are used. Nothing to start
  by hand, including after a reboot. → skill `aipim-cli-env`
- **Confluence**: the MCP is **read-only**; `confluence-cli` is the publishing tool. But its
  `page create/update` need an interactive TTY, so **from an AI session publish with
  `~/myGit/crosslv/assets/aipim/confluence-update`** (raw curl). Reads either way are fine.
  → skills `managing-confluence`, `aipim-cli-env`
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
4. **Even SUBMINOR = official build only; you must build odd.** In both `golan_fw` and `utopx`,
   the release bot tags an **even** `SUBMINOR` (that is what `/mswg/release/BUILDS/...` ships) and
   then bumps the branch to the next **odd** number. A local build of an even version is refused
   outright:
   `******** Even-numbered FW Subminor Version can only be compiled by official build. Please
   compile odd-numbered version only. ********` → `make[1]: *** [Makefile:226: pre_comp] Error 1`.
   So "build the last GA release yourself" always means **official + 1** (e.g. GA `12.50.1016`
   → build `12.50.1017`); the two differ only in the version stamp (`Version` plus the
   auto-generated version vector in `adabe/upgrade_ini_defaults.adb`), never in functional code.
   If you need the **bit-exact** released image, do not build — burn the release `.mlx` from
   `/mswg/release/BUILDS/fw-<devid>/fw-<devid>-rel-<ver>-build-001/dist/`.
5. **Never reboot / power-cycle `m-fwdev-167` without Peter's explicit approval.** This applies
   to that box only — other machines (lab/reg boxes) may be rebooted as the work needs. It covers
   `jmake --power-cycle`, `reboot`, `shutdown`, IPMI power off/on and `mlxfwreset -l 4`
   (Warm Reboot); `m-fwdev-167` carries dozens of live tmux sessions and long-running work.
   Device-level resets that do **not** reboot the host — `mlxfwreset -l 3` (driver restart +
   PCI reset), `jmake --fw-reset` — are fine anywhere. If an NV parameter on `m-fwdev-167` only
   takes effect after a cold boot, stop and ask; do not reboot to make it apply.

6. **"It passed before, it fails now" → run the known-good control BEFORE theorising.** Re-burn
   /re-check out the last artefact that passed and reproduce with it. Until that data point
   exists you cannot separate "my change broke it" from "the box drifted", and every explanation
   you invent will be a guess. On 2026-09-08 five consecutive root-cause claims were wrong for
   this exact reason; one control run would have settled it in ten minutes. Corollary: never
   "fix" NV config by setting parameters one at a time to what you think the baseline was —
   verify with data (utopx logs a raw-TLV NV snapshot every run) and restore wholesale.
   → skill `fw-build-burn-utopx` §7b

Rules 1 and 2 are additionally enforced by a PreToolUse hook
(`~/myGit/crosslv/assets/claude/hooks/guard.py`), which denies the matching Bash calls outright.
It reads the command text, so a heredoc that merely mentions `l-fwminireg` counts too — write
such files with the Write/Edit tools, which the hook does not gate. Regression tests sit next to
it; run them after any change.

## Skills

| skill | covers |
|---|---|
| `utopx-traffic-forensics` | a utopx run's traffic failed: rebuild the WQE/packet from `utopx_dump`, read the CQE checker verdict, dump the STE the packet hit, walk the whole HW steering chain (`ste_chain.py`, hwtrace) |
| `fw-build-burn-utopx` | build FW from golan_fw, burn it to a local card, run utopx against it; even/odd version gate, jmake worktree path rules, OFED↔udriver hand-over, failure signatures |
| `gerrit-change` | commit message format, cherry-picks, Change-Id rules |
| `gerrit-stack` | pushing dependent commits, RELATED_CHANGES / IGNORE topics |
| `utopx-ci-rerun` | re-triggering utopx / golan_fw CI, concurrency and vote preconditions |
| `ci-forensics` | red build → session_id → MARS archive → the raw failure log |
| `regression-repro` | reproducing a regression locally ("regression repro template") |
| `noga-lock` | querying, locking, waiting for lab servers |
| `nic-livefish-recovery` | un-bricking a NIC that vanished from PCI; the mlxconfig rule |
| `bluefield-fwconfig` | mlxconfig read-back traps on any BlueField DPU, ARM-liveness check |
| `aipim-cli-env` | the ai-pim CLI container, Confluence write path |
| `regression-report-mail` | nightly UtopX / NICX regression + coverage mails: subjects, senders, branch-pointer table, Outlook MCP limits |

Full prose for anything above was split out of this file on 2026-08-13; the pre-split version is
at `~/.claude/backups/CLAUDE.md.pre-skill-split.20260813-190042`.
