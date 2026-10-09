---
name: ci-forensics
description: >-
  Trace a red CI job or bare verdict to its original MARS failure log (Jenkins build, session
  archive, bot mail) and tell environment from defect; also count occurrences in a session archive
  without the usual traps. Use when a CI build is red, a report only says "Failed: N", someone asks
  which case failed and why, or you need to count how often something happened in a regression log.
---

# Test & CI failure forensics

Failure triage is a three-skill chain. Go 1 → 2 → 3: leg 2 often ends the investigation, and one
log from leg 3 alone cannot tell a one-off from a month-old epidemic.

| Leg | Question it answers | Skill |
|---|---|---|
| 1 | Did anything fail last night, and where? | `regression-report-mail` (Outlook) |
| 2 | Is this failure new? How many setups? Which commit introduced it? | `fsearch-failures` (failure DB) |
| 3 | What exactly happened in that one run? | `ci-forensics` (Jenkins → MARS log) |

Use this skill when the upper layer reports only a verdict — Jenkins
`Completed golan_fw_minireg #N : FAILURE`, or a mail saying `Failed: 2` — with no case and no
cause. It works for any MARS session (minireg / DoA / regressions); all you need is the
session_id. Phase 1 gets the session_ids out of Jenkins, Phase 2 gets the raw log out of MARS.

## Phase 1 — a red job → session_ids

Do this in one pass: Jenkins keeps a fixed number of builds per job, so a busy job forgets sooner —
`golan_fw_minireg`, the DoA job that holds the session_ids, keeps about **a week**, `utopx_ci` about
two weeks. Record the session_ids — and, once fetched, their archive paths (Phase 2) — in your notes
immediately: the MARS archive sits on NFS and stays readable long after the build is purged. To measure a job's window, read
`api/json?tree=allBuilds[number,timestamp]`: the plain `builds` field stops at 100 entries, however
wide the `{0,N}` window, and fakes a short retention.

```bash
~/myGit/crosslv/assets/skills/ci-forensics/scripts/find_jenkins_build.sh --help
# builds have no stable name — find yours by a parameter value:
~/myGit/crosslv/assets/skills/ci-forensics/scripts/find_jenkins_build.sh \
    -j utopx_ci -p GERRIT_CHANGE_NUMBER -v 1467618 --blossom
```

Save the console at once, then read which stage failed and what ran downstream (`$J` = the URL of
the Jenkins instance hosting the job):

```bash
curl -s "$J/job/<job>/<build>/consoleText" -o logs/ci_<build>.log
grep -E 'Stage: ".*" Status:' logs/ci_<build>.log | grep -v 'Status: Success'
grep -oE '<downstream job> #[0-9]+' logs/ci_<build>.log | sort -u
```

`Failure_ignored` is routine (`Pre FC Validation`, `Macros Guard`) — not a real stage failure.

Two verdicts with nothing behind them to attribute:

- **ABORTED in `CI Execution Checkpoint`** — nothing compiled or ran: the concurrency cap was
  exceeded, or the branch is locked
  (`CI is DISABLED for project fw_ver/utopx, branch <branch>, because of ::: <project>/<branch> locked by <name> (<reason>) ::: Run aborted.`,
  followed by a bot `Verified-1`). Environmental by definition; the lock check and the rerun gate
  are in skill `utopx-ci-rerun`.
- **SUCCESS without a DoA** — on some branches the console says
  `Skipping micro-DoA. Missing stable seeds file or FW build reference.` and the green verdict
  covers the compile only. Say so when reporting it.

Pull the per-session verdicts out of the downstream console; this one grep tells you what failed
before you touch MARS:

```bash
grep -oE 'session_id [0-9]+ .-device [a-z0-9_]+ (.-branch [^ ]+ )?.-status [a-z]+' logs/<downstream>.log
```

Write `.-device`, never `--device`: grep/ugrep parses a leading `--` in the pattern as an option
and dies with `invalid option`. The arguments between `--device` and `--status` vary between
versions (current consoles put `--branch <branch>` there), and a pattern that does not allow for
them silently matches nothing — check the hit count against the `Successful sessions:` /
`Failed sessions:` lists printed just above.

Traps:

- **Do not window the build query** (`{0,40}`). Long builds and quickly-aborted ones interleave,
  so a windowed view under-reports badly.
- **The downstream job may live on another Jenkins instance with different auth.** A `Not Found`
  HTML page (anonymous) or a `401` (wrong credentials) looks exactly like "purged" and is not —
  try the other instance and the other credential before concluding the log is gone.
  `utopx_ci` = blossom/anonymous; `golan_fw_minireg` = internal/token.

## Phase 2 — session_id → the original log

```bash
~/myGit/crosslv/assets/skills/ci-forensics/scripts/mars_fetch.sh <session_id>
```

Three hops, no authentication at any step. What the script does (and what to do by hand):

1. `curl https://mars.nvidia.com/api/session/<session_id>` returns XML (the `/ui/...` web page
   needs an interactive login and 302s; the API does not). Take `<RESULT_DIR>` and `<SETUP_NAME>`
   from it. Check `PASSED`/`FAILED`/`IGNORED`/`NATIVE_STATUS` first to tell "ran and then failed"
   from "never got started". Both paths differ per session (different devices land in different
   setup sets) — read them for every session, never reuse the first one's.
   The API forgets a session after about two weeks — it then answers HTTP 200 with
   `Failed to get session <id> info` — while the archive stays on NFS for months. Record the
   archive path the script prints next to the session_id; later run
   `mars_fetch.sh <session_id> --tgz <path>`.
2. The full archive is `<RESULT_DIR>/<SETUP_NAME>/<session_id>/<session_id>.tgz`, readable
   directly over NFS. `SETUP_NAME` carries the parenthesised suffix you cannot guess (DoA:
   `mini_reg_SETUP_SET_<n>(<user>_<device>_<link>-CI_DOA_<n>-JK_BUILD_<n>)`, also listed in the
   DoA console's `Successful sessions:` / `Failed sessions:`). Build the path from the two values;
   do not `find` under `RESULT_DIR` — it can hold thousands of setup directories, and the scan
   takes minutes on NFS.
3. Unpack, then filter on `result:` in each `status.txt`: `0`=pass, `1`=fail, `2`=not executed.
   Parent nodes merely propagate failure upward. **A real case is a `result: 1` node with a
   sibling `log.txt`.** Do not search for "the deepest path" — the tree is uneven, and a
   depth-ranked search stops at an intermediate node while the real leaves sit far deeper.

   ```bash
   for f in $(grep -rl '^result: 1' <unpacked> --include=status.txt); do
     d=$(dirname $f); [ -f "$d/log.txt" ] && echo "$d"
   done
   ```

Each such `log.txt` holds the raw `UFATAL` / `Field mismatch: expected=X Actual=Y` /
`To rerun use seed N`.

No session_id yet? Take it from `--session_id N` in the upstream log, `Amonitor.php?session_id=N`,
or the table in the email report.

### Counting things in that log

When grepping the archive to answer "how often did X happen":

1. **`LOG_OP : <OP>` and `Executing operation <OP>` are different counts — sometimes by three
   orders of magnitude.** One BF-4 session:

   | op | `LOG_OP :` | `Executing operation` |
   |---|---|---|
   | `QUERY_EMULATED_FUNCTIONS_INFO` | 5 | 5 |
   | `QUERY_EMULATED_RESOURCES_INFO` | 47 | 15 |
   | `QUERY_HCA_CAP` | 14045 | 31 |
   | `MANAGE_PAGES` | 7506 | 20 |

   `LOG_OP` comes from one common sink (`UtopxOp.cpp:707`) and catches everything;
   `Executing operation` is printed by several executers (`CmdExecuter.cpp`,
   `ParallelDBExecuter.cpp`, `UtopxOpWrapper.cpp`) and only on some paths. Which one equals "how
   many really ran" is not settled — count both, put both in the report, and say which one you
   mean. Never quote a single number as "the" op count.
2. **One failure produces many lines**: the CMDIF syndrome summary, the `*_out` field dump, the
   `Status for command:` block, the `ContextChecker` FATAL and the `UtopxFatalHandler` re-report.
   So `grep -c <signature>` overcounts (syndrome `0xac5816`: **6** raw hits for **1** event;
   `0x3590f5`: 8 raw hits / 4 FATAL lines). Filter to `FATAL.*<signature>` and expect two lines
   per event (checker + handler).
3. **Identify a function by `TYPE=`, not by GVMI or BDF.** The log prints
   `VHCA=0x..:GVMI=0x..:TYPE=ECPF|PF|VF`. On Socket-Direct setups the same GVMI carries both an
   ECPF and a PF VHCA, and the "function N of the BDF" convention differs between setups — a GVMI
   or a trailing `.2` proves nothing on its own.
4. **Establish the denominator before reading a zero.** Before concluding "that capability bit is
   0", count how many times the block containing it was dumped at all — a field never printed and
   a field printed as 0 look identical to grep. A session can create objects without ever dumping
   the block (one BF-3 session: 35 object creations, zero capability dumps) — such a session is no
   control; using it as one inverts the conclusion.

`-B<N>` / `-A<N>` context grepping is not attribution: the surrounding lines belong to other
threads. Attribute an event by matching the thread id (`(EXE:0:16:45)`) and timestamp, or walk back
to the nearest line that carries the same thread id.

## Phase 3 — the bot mails, which carry things the console does not

When monitoring a change, polling Jenkins and the gerrit API is not enough — read the bot mails
too. Two different senders both render as "svc-sw-hca-bot"; do not conflate them:

| sender | address | carries |
|---|---|---|
| **Automation Bot** | `svc-sw-hca-bot@nvidia.com` | `PASSED/FAILED: CI_DOA_<n> <branch>` (per-device table: setup, pass %, session id, ran/passed/failed) · `nicx_minireg_doa #<n> - SUCCESS/FAILURE - UTOPX_CI_<n>` · the nightly regression / coverage reports |
| **svc-sw-hca-bot (Code Review)** | `git12023@mtl-git-gf-05.nvidia.com` | gerrit events: `doa #<n> FAILED - CI_DOA_<n>` · `Patch set N: <label> ±1` · `[S] Change in ...utopx[<branch>]: <title>` |

Information that exists only in the mail:

- A `PASSED: CI_DOA_<n> …` body can say *"Mini-Regression Passed, but failed in coverage"* while
  Jenkins says SUCCESS and gerrit voted `CI-Minireg+1` — neither shows the coverage tail.
- A `nicx_minireg_doa #<n> - SUCCESS - UTOPX_CI_<n>` body lists **`Ignored Failure Stages`** by
  name; they never surface as a stage failure anywhere else.

```
outlook_list_messages(query="from:svc-sw-hca-bot@nvidia.com", start_date="<today>", limit=15)
outlook_search_messages(query="CI_DOA_<n> OR UTOPX_CI_<n>", limit=15)
```

When you know the build number, default to the free-text search — it finds both senders at once.
`outlook_list_messages` takes KQL fields only; its traps are in skill `regression-report-mail`.

Outlook is MCP-only — there is no CLI for it (it is not among the ai-pim CLIs), so a background
bash watcher cannot poll mail; it reaches only Jenkins and the gerrit API. Let the watcher own
gerrit/Jenkins and check the mail yourself via MCP at every reporting step. A silent watcher does
not mean nothing happened.

## Attribution discipline

- Before calling a failure "environment" or "our code", find a control sample matching on
  **branch + mode + setup**: did someone else's change pass under identical conditions? Drop any
  one of the three and the conclusion can flip.
- Not valid evidence: log size; whether the node was taken offline (offlining is the system's
  generic response to any failure).
- "How often / since when / is it ours" → `fsearch`, but read skill `fsearch-failures` first: new
  path and Python 3.8 since 2026-09, and three traps that each flip the conclusion silently (dead
  old path that answers every query with zero rows, ~8-day retention that fakes a "first seen"
  date, `--datefrom`/`--dateto` accepted but ignored).
- Judge an empty fsearch result by a control query with a term you know exists, never by elapsed
  time. The old rule *"a real query takes 70–90 s; an instant return is a false negative"* is
  obsolete — Fsearch2 returns 32 rows in ~6 s.

## Related

- Failure history, frequency, and commit attribution: skill `fsearch-failures`.
- Re-triggering after you've decided it's environmental: skill `utopx-ci-rerun`.
- Reproducing it locally, bit-for-bit: skill `regression-repro`.
