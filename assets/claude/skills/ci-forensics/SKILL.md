---
name: ci-forensics
description: Get from a red CI job or a bare test verdict down to the original failure log — Jenkins build to session_id to the MARS archive to status.txt/log.txt with the UFATAL or field mismatch. Covers minireg, DoA and regression sessions, and the attribution discipline for calling a failure environmental vs a real defect. Use when a CI build went red, an email report says "Failed: N" with no detail, or when asked why a test failed, which case failed, or whether a failure is ours.
---

# Test & CI failure forensics

Symptom: the upper layer reports only a verdict — Jenkins
`Completed golan_fw_minireg #N : FAILURE`, or an email report saying `Failed: 2` — with no hint
of which case failed or why.

Applies to any MARS session (minireg / DoA / regressions); all you need is the session_id. Two
phases: get the session_ids out of Jenkins, then get the raw log out of MARS.

## Phase 1 — a red job → session_ids

Do this **in one pass**: Jenkins purges builds in roughly **12 days**, and once the console is
gone you are reverse-engineering from source. Record the session_ids in your notes immediately —
they outlive the Jenkins console, because the MARS archive sits on NFS and stays readable long
after the build is purged.

```bash
~/.claude/skills/ci-forensics/scripts/find_jenkins_build.sh --help
# find your build by a parameter value (builds have no stable name):
~/.claude/skills/ci-forensics/scripts/find_jenkins_build.sh \
    -j utopx_ci -p GERRIT_CHANGE_NUMBER -v 1467618 --blossom
```

Then save the console immediately and read which stage failed and what ran downstream:

```bash
curl -s "$J/job/<job>/<build>/consoleText" -o logs/ci_<build>.log
grep -E 'Stage: ".*" Status:' logs/ci_<build>.log | grep -v 'Status: Success'
grep -oE '<downstream job> #[0-9]+' logs/ci_<build>.log | sort -u
```

Distinguish `Failure_ignored` (routine — `Pre FC Validation`, `Macros Guard`) from a real stage
failure.

Pull the per-session verdicts out of the downstream console — that single grep tells you what
failed before you touch MARS:

```bash
grep -oE 'session_id [0-9]+ .-device [a-z0-9]+ .-status [a-z]+' logs/<downstream>.log
```

⚠ Write `.-device`, **never** `--device`: grep/ugrep parses a leading `--` in the pattern as an
option and dies with `invalid option`.

Two traps in this phase:

- **Do NOT window the build query** (`{0,40}`). Long builds and quickly-aborted ones interleave,
  so a windowed view under-reports badly.
- **The downstream job may live on a different Jenkins instance with different auth.** A
  `Not Found` HTML page (anonymous) or a `401` (wrong credentials) **looks exactly like "purged"
  and is not** — try the other instance and the other credential before concluding the log is
  gone. (`utopx_ci` = blossom/anonymous; `golan_fw_minireg` = internal/token.)

## Phase 2 — session_id → the original log

Three hops, **no authentication needed at any step**:

```bash
~/.claude/skills/ci-forensics/scripts/mars_fetch.sh <session_id>
```

What it does, and why each step matters:

1. `curl https://mars.nvidia.com/api/session/<session_id>` returns XML. (The `/ui/...` web page
   requires interactive login and 302s; the API does not.) Take `<RESULT_DIR>` from it. It also
   reports `PASSED`/`FAILED`/`IGNORED`/`NATIVE_STATUS` — check these first to tell "ran and then
   failed" from "never got started".
   **`RESULT_DIR` differs per session** (different devices land in different setup sets) — read
   it for each session, never reuse the first one.
2. `<RESULT_DIR>/<setup name>(...)/<session_id>/<session_id>.tgz` is the full archive, readable
   directly over NFS. Locate it with
   `find <RESULT_DIR> -maxdepth 3 -name "<session_id>.tgz"` — the setup directory carries a
   parenthesised suffix you will not guess.
3. Unpack, then filter on `result:` in each `status.txt`: `0`=pass, `1`=fail, `2`=not executed.
   Parent nodes merely propagate failure upward. **A real case is a `result: 1` node that has a
   sibling `log.txt`** — do NOT search for "the deepest path"; the tree is uneven and a
   depth-ranked search stops at an intermediate node while the real leaves sit far deeper.

   ```bash
   for f in $(grep -rl '^result: 1' <unpacked> --include=status.txt); do
     d=$(dirname $f); [ -f "$d/log.txt" ] && echo "$d"
   done
   ```

Each `log.txt` holds the raw `UFATAL` / `Field mismatch: expected=X Actual=Y` /
`To rerun use seed N`.

Where to get a session_id if you don't have one: `--session_id N` in the upstream log,
`Amonitor.php?session_id=N`, or the table in the email report.

## Attribution discipline

Before calling a failure "environment" or "our code", find a **control sample matching on
branch + mode + setup**: did someone else's change pass under identical conditions? Drop any one
of those three dimensions and the conclusion can flip.

**Not valid evidence**: log size; whether the node was taken offline (node offlining is the
system's generic response to *any* failure).

`fsearch` only records **case-level** failures — anything dying in setup/init never reaches it.
It also **returns 0 rows silently when a parameter value is invalid**, so judge by elapsed time:
a real query takes 70–90 s; an instant return is a false negative.

## Related

- Re-triggering after you've decided it's environmental: skill `utopx-ci-rerun`.
- Reproducing it locally, bit-for-bit: skill `regression-repro`.
