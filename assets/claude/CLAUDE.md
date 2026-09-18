# Global notes

Facts that hold in every session. Anything procedural lives in a skill (listed at the bottom) —
invoke it when the task matches; don't reconstruct the procedure from memory.

## Shared skills (Claude Code + Codex)

- Claude Code and Codex load the **same physical skills** from
  `~/myGit/crosslv/assets/skills`. `~/.claude/skills` is a tree link; shared entries under
  `~/.agents/skills` are per-skill links so unrelated Codex skills are preserved.
- When asked to add, modify, synchronize, or repair a skill, invoke skill `skill-maintainer` and
  edit the canonical path returned by `jskill path <name>`. Never create separate Claude and
  Codex copies.
- Put common behavior in `SKILL.md` and shared resources. Put only genuine runtime differences
  in `references/hosts/claude.md` and `references/hosts/codex.md`; when those files exist, read
  the adapter for the current agent before invoking tools.
- Finish skill changes with `jskill sync` and `jskill check`. A running client may need a new
  session to refresh discovery or changed frontmatter metadata.

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

## Repos — which clone, decided by the kind of work

Two clone pairs exist, and mixing them up wrecks someone's tree. Pick by what the work *is*,
never by which one happens to be checked out already:

| Kind of work | FW source | Test-tool source |
|---|---|---|
| **Task / feature** — a feature you own, a gerrit change you drive | `/auto/fwgwork1/$USER/golan_fw` | `/auto/fwgwork1/$USER/utopx` |
| **Regression / bug investigation** — Redmine ticket, CI or DoA failure, MARS session | `/auto/fwgwork1/$USER/golan_fw2` | `/auto/fwgwork1/$USER/utopx2` |

A repro pins repos to an old regression commit and may `git stash -u` whatever it finds; feature
work carries long-lived branches and worktrees. **Never run a repro in the main clone, and never
start feature work in a `*2` clone.**

Then give each task its **own worktree** off the right clone — never work in the clone's own
checkout, which is usually on someone else's branch. `jmake` detects the repo type from the path,
so a path segment must start with `golan` / `nicx` / `utopx`. → skills `fw-build-burn-utopx` §1.0,
`regression-repro`

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
| `fw-build-burn-utopx` | build FW from golan_fw, burn it to a local card, run utopx against it; even/odd version gate, jmake worktree path rules, OFED↔udriver hand-over, failure signatures |
| `steering-capture` | capture steering state from a **live** utopx run: freeze with `--wait_on_err`, dump one entry with `stedmp.sh`, or take the whole chain with `--hwtrace`. Also the `--wait_cycle` pause and the segfault-dump trick |
| `gerrit-change` | getting a change onto gerrit: commit message format, cherry-picks, Change-Id rules, **and pushing a dependent stack** (RELATED_CHANGES / IGNORE topics) |
| `utopx-ci-rerun` | re-triggering utopx / golan_fw CI, concurrency and vote preconditions |
| `ci-forensics` | red build → session_id → MARS archive → the raw failure log |
| `fsearch-failures` | the regression failure DB: how often / since when / which commit — attribution. New path + Py3.8 since 2026-09, three silent traps |
| `regression-repro` | a bug ticket end to end: reproduce locally ("regression repro template") → root-cause in FW/utopx source → **verify the fix on the box** → `FINDINGS_<ticket>.md`. Also fires on "find the root cause", "investigate this ticket", "propose/verify a fix" |
| `feature-delivery` | a **feature** end to end (the mirror of `regression-repro`): survey both repos' change stacks, find the on/off gates that keep the path dark, per-task worktrees, the daily-wiped reg-box env, and the verdict "did the new code path execute" instead of `TEST PASSED`. Fires on "take over this feature", "how far is X", "why is this change stuck" |
| `task-tracking-doc` | a task that spans sessions or touches several commits/branches/tickets/boxes: build `TRACKING.md` and keep it current — update contract, evidence rows with a control, overturned conclusions struck through not deleted. **Reach for it at the START of such a task** |
| `noga-lock` | querying, locking, waiting for lab servers |
| `nic-livefish-recovery` | un-bricking a NIC that vanished from PCI; the mlxconfig rule |
| `bluefield-fwconfig` | mlxconfig read-back traps on any BlueField DPU, ARM-liveness check |
| `aipim-cli-env` | the ai-pim CLI container, Confluence write path |
| `regression-report-mail` | nightly UtopX / NICX regression + coverage mails: subjects, senders, branch-pointer table, Outlook MCP limits |
| `skill-maintainer` | add or modify the canonical skills shared with Codex; link repair and validation |

Full prose for anything above was split out of this file on 2026-08-13; the pre-split version is
at `~/.claude/backups/CLAUDE.md.pre-skill-split.20260813-190042`.
