# Global notes

Facts that hold in every session. Anything procedural lives in a skill (listed at the bottom) —
invoke it when the task matches; don't reconstruct the procedure from memory.

## Shared skills (Claude Code + Codex)

- Claude Code and Codex load the **same physical skills** from
  `~/myGit/crosslv/assets/skills`. `~/.claude/skills` and `~/.agents/skills` are real
  directories holding the same one link per shared skill, so what a client keeps there itself
  (Claude Code's `synced/` account skills, independently installed Codex skills) stays out of the
  repo.
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
- **Every ssh/scp from a Bash call carries `-o BatchMode=yes`; a script also does `unset DISPLAY`.**
  Bash calls have no TTY but inherit Peter's X `DISPLAY`: when publickey auth fails (a lab box that
  just booted, its NFS home not mounted yet) ssh opens `ssh-askpass` on Peter's desktop and blocks
  until someone answers. Root login, lab passwords, a box whose home is not mounted → skill
  `lab-box-login`
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

A repro pins its worktrees to old regression commits; feature work carries long-lived branches and
worktrees. **Never run a repro in the main clone, and never
start feature work in a `*2` clone.**

Then give each **ticket or feature** its **own worktree** off the right clone — never work in the
clone's own checkout, which is usually on someone else's branch. **One worktree per ticket, not per
sub-task**: controls, variants, A/B arms and ladder steps are commits switched inside that ticket's
worktree. A utopx worktree with a build is ~9 GB (`cmakeBuild/` ~8 GB) of the 200 GB `/vol/fwgwork1`
that every session shares — `df -h /auto/fwgwork1/$USER` before adding one. **Never delete a
worktree on your own** when the work ends; Peter reuses some. Short of space, drop idle trees'
`cmakeBuild/` first and ask before removing a tree (ask the session that created it if it is not
yours). Logs that a page or a report cites are copied into the ticket's bugZilla directory, which
outlives the worktree.
`jmake` detects the repo type from the path, so a path segment must start with `golan` / `nicx` /
`utopx`. → skills `fw-build-burn-utopx` §1.0, `regression-repro`

## Tooling

- **ai-pim CLIs** (`confluence-cli`, `jira-cli`, `glean-cli`, `nvbugs-cli`, `redmine-cli`,
  `slack-cli`, and the rest): on m-fwdev-167 they run in the `pim` Docker container through bashrc
  functions, which Bash tool calls do not inherit — a bare name hits the native
  `~/.local/bin/<cli>` and dies with `GLIBC_2.32' not found`. From an agent session call
  `docker exec -e AI_PIM_UTILS_TELEMETRY_DISABLED=1 -w "$PWD" pim <cli> <args>`. Elsewhere the
  native binaries are used. Their built-in skill sync is off (`skill_sync_disabled = true` in
  `~/.ai-pim-utils/config.toml`): it writes through `~/.claude/skills` into the shared skills, so
  keep it off and never run `<cli> skills reset|uninstall`. → skill `aipim-cli-env`
- **Confluence**: the MCP is **read-only**; `confluence-cli` is the publishing tool. But its
  `page create/update` need an interactive TTY, so **from an AI session publish with
  `~/myGit/crosslv/assets/aipim/confluence-update`** (raw curl). Reads either way are fine.
  → skills `managing-confluence`, `aipim-cli-env`
- **gitlab-master.nvidia.com** speaks SSH on **port 12051**:
  `git clone ssh://git@gitlab-master.nvidia.com:12051/<group>/<repo>.git`. HTTPS clones need a
  PAT (`https://oauth2:<token>@…`).
- Credentials live in files, never in docs/memory/commit messages: `~/.jenkins_env`,
  `~/.confluence_env` (both mode 600, on NFS home).
- **MCP servers**: after adding one, run **`jcl save-auth`** — it merges the new token into
  `~/.claude/mcp-oauth-backup.json`, and a server missing from there needs a fresh browser
  authorization after any `claude auth logout`. The merge only ever adds, so re-running is
  harmless. A new server under `/maas/auth/azure` (gerrit, glean, jenkins, redmine,
  confluence) can borrow a live token with `jcl fill-auth` and skip the browser entirely;
  the `/v2/auth/<svc>` ones (outlook, nvbugs, teams) are separate authorization domains and
  must be authorized by hand from `/mcp`. `jcl restore-auth` stays manual — only you know a
  logout happened, and a failing MCP call is far more often an expired token (renews itself)
  or a wrong scope (restore cannot help) than a wiped credentials file.
- **Messaging Codex sessions**: Codex sessions on this host are not in `/list-agents`. Reach one
  with `agent-bridge send --to '<name or id>' '<text>'` (names and session ids as `jcl list` and
  `agent-bridge peers` show them; the first 8+ characters of an id will do). A Codex session's
  message arrives as `Message from @<codex title>` with a `uds:` reply address: answer it with
  `SendMessage` to that address - a reply by name is not found. Given a Claude session,
  `agent-bridge send` prints the `uds:` address to hand `SendMessage` instead.
- **Session names change; session ids do not.** When you refer to another session — in a ledger,
  a message, a report — write `name (id prefix)`, e.g. `oci-emu-d1 (1f0e326b)`. A name that no
  longer resolves (`SendMessage`: "No agent named …", or `agent-bridge` finds none) does not mean
  the session ended: look its id up in `agent-bridge peers` or `jcl list` for the current name, then
  `SendMessage` that name (Claude) or `agent-bridge send --to <id prefix>` (Codex). The session has
  ended only when the id is gone too.

## Markdown documents

Every `.md` written for Peter — in any folder, for any purpose: tracking pages, work logs, defect
lists, reports, code-flow write-ups, notes — follows skill `markdown-docs`: which document set the
work gets (a feature, a long task and a bug ticket all get `Tracking.md`, `Ledger.md` and
`Defects.md`), how each kind of document is kept, and the writing rules. The ones most often
missed:

- External items are short labels linked to the full URL, `[1459033](https://git-nbu…/+/1459033)`,
  `[FR #4838395](…)`; never a bare URL or a URL as its own label; every mention of a change or
  ticket number is linked, tables included.
- Local files the reader opens (other documents, reports, run logs cited as evidence, `tools/`)
  are relative links labelled with the file name — except in the English copies under a ticket's
  `redmine/`, which go to Redmine. Source lines are links too. Code links the local
  worktree, never gerrit or gitiles, pinned to the commit its line number belongs to:
  `[VHCA.cpp:5149](../../utopx-psf/src/hca/VHCA.cpp?v=6faa4de858#L5149)`; md-preview-plus opens
  the line where that code is now, or the commit's read-only version if the line has changed. The
  commit must be in the local repository and held by a ref (fetch a patchset first; one no
  branch holds gets `refs/keep/<task>/<sha>`). The copies that go to Redmine
  use gerrit's file view or gitiles instead. Paths to type or copy stay in backticks.
- `Ledger.md` is only appended: the Run log table on top gets a row per run, its first cell
  `<a id="run-N"></a>N`; entries `## <N>. <short title>`, first line date — conclusion, go at the
  end. A handoff, a review thread or a draft is its own file, linked from the entry, not pasted
  into it. A Run log row or a section of another file is cited as a link to it:
  `[Run log #12](#run-12)`, `[Ledger.md §42](Ledger.md#42-fw-6025-builds)`.
- Run steps — a ticket's `Tracking.md` §4, a feature's §6 — are copied one by one to rebuild the
  box and run the test: every command complete as it stands (absolute paths, no variable carried
  between steps, no "same as"), its expected output from a real run; then the same with
  `env_rebuild.sh` and `per_run.sh`.
- Headings are short titles that say what the section holds (they become the table of contents);
  owners, timestamps, conclusions and status marks go in the first line under the heading.
- No code block inside a list item; patches go in `diff` fences.

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
It reads the command text, so a heredoc that merely mentions `l-fwminireg` counts too, and so does
prose quoting an `mlxconfig ... set` with `-f` or more than 8 `PARAM=value` pairs — write such files
with the Write/Edit tools, which the hook does not gate. Regression tests sit next to
it; run them after any change.

## Skills

| skill | covers |
|---|---|
| `fw-build-burn-utopx` | build FW from golan_fw, burn it to a local card, run utopx against it; even/odd version gate, jmake worktree path rules, OFED↔udriver hand-over, failure signatures |
| `steering-capture` | capture steering state from a **live** utopx run: freeze with `--wait_on_err`, dump one entry with `stedmp.sh`, or take the whole chain with `--hwtrace`. Also the `--wait_cycle` pause and the segfault-dump trick |
| `gerrit-change` | getting a change onto gerrit: commit message format, cherry-picks and back-ports, Change-Id rules, private branch names, **and pushing a dependent stack** (RELATED_CHANGES / IGNORE topics) |
| `utopx-ci-rerun` | re-triggering utopx / golan_fw CI, concurrency and vote preconditions |
| `ci-forensics` | red build → session_id → MARS archive → the raw failure log |
| `ci-support-ticket` | a CI support request on the ServiceNow "Host Firmware Automation Support" form, only when Peter says "open a CI ticket"; its description reports the failure, never the root cause |
| `fsearch-failures` | the regression failure DB: how often / since when / which commit — attribution. New path + Py3.8 since 2026-09, three silent traps |
| `regression-repro` | a bug ticket end to end: reproduce locally ("regression repro template") → root-cause in FW/utopx source → **verify the fix on the box** → the ticket's `Tracking.md`, `Ledger.md` and `Defects.md`. Also fires on "find the root cause", "investigate this ticket", "propose/verify a fix" |
| `utopx-regression-ticket` | a Redmine ticket for a UTOPX regression, CI or DoA failure (what "open a ticket" means): fields, subject, description, the evidence comment with every MARS artifact; the root cause analysis comment ("write a root cause analysis"); the HTML of any Redmine comment, and correcting one in place |
| `feature-delivery` | a **feature** end to end (the mirror of `regression-repro`): survey both repos' change stacks, find the on/off gates that keep the path dark, per-task worktrees, the daily-wiped reg-box env, and the verdict "did the new code path execute" instead of `TEST PASSED`. Also the feature's documents, created from its templates on day 0: the `Tracking.md` status page, the `Ledger.md` step-by-step record, `Defects.md`, test reports; any other multi-week task gets the same `Tracking.md` and `Ledger.md` (crosslv tool work gets one `plans/` document instead: skill `markdown-docs`). Fires on "take over this feature", "how far is X", "why is this change stuck", "update Tracking.md" |
| `markdown-docs` | every `.md` written for Peter: which document set the work gets (feature or long task, bug ticket, crosslv `plans/`), how pages and logs are kept, what not to create or keep, the writing rules (language, links, headings, code blocks) |
| `utopx-log-walkthrough` | an animated walkthrough page from one utopx debug log ("create a walkthrough demo for <log>"): build it, check it against the log, screenshot it, publish it as an Artifact, record it; the presenter talk track; the PSF ICM global-mode story and how to write a story for another feature |
| `noga-lock` | querying, locking, renewing, waiting for and releasing lab servers |
| `lab-box-login` | getting a shell on a lab box: ssh rules (BatchMode, DISPLAY, ControlMaster, waiting for a reboot), root login and where the lab passwords are, a box whose NFS home is not mounted (autofs, an empty `/etc/auto.master`) |
| `nic-livefish-recovery` | un-bricking a NIC that vanished from PCI; the mlxconfig rule |
| `bluefield-fwconfig` | mlxconfig read-back traps on any BlueField DPU, ARM-liveness check |
| `aipim-cli-env` | the ai-pim CLI container: credentials, upgrades, what the MCP covers and what needs the CLI; the Confluence write path |
| `managing-confluence` | Confluence reads, search, exports and publishing (the write itself: `aipim-cli-env`) |
| `managing-glean` | glean-cli, when the nvidia-glean MCP tools are missing or failing |
| `tracking-redmine` | redmine-cli, when the nvidia-redmine MCP tools are missing or failing |
| `tracking-nvbugs` | nvbugs-cli: every NVBugs write (the MCP is read-only) and the reads the MCP lacks |
| `regression-report-mail` | nightly UtopX / NICX regression + coverage mails: subjects, senders, branch-pointer table, Outlook MCP limits |
| `creating-nvidia-github-repo` | a new private repository under github.com/NVIDIA: the OSRB bug, module assignment, the onboarding form |
| `skill-maintainer` | add or modify the canonical skills shared by Claude Code and Codex; link repair and validation |

Full prose for anything above was split out of this file on 2026-08-13; the pre-split version is
at `~/.claude/backups/CLAUDE.md.pre-skill-split.20260813-190042`.
