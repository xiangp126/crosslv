# A ticket's documents — what each file holds, and when it changes

Every ticket directory, `/auto/fwgwork1/$USER/bugZilla/<ticket#>_<core>/`, holds **two
documents and nothing else of their kind**: `REPRO_<ticket#>.md` for the work and
`FINDINGS_<ticket#>.md` for the conclusion. The writing rules — language, links, code blocks,
dates, plain speech — are the ones feature work uses: skill `feature-delivery`,
`references/documents.md` §6. Every fact has one home; the other file links to it.

## 0. Setting up the directory

```bash
S=~/myGit/crosslv/assets/skills/regression-repro/templates
D=/auto/fwgwork1/$USER/bugZilla/<ticket#>_<core>
mkdir -p $D/regression_ini $D/tools $D/logs
cp $S/repro.md $D/REPRO_<ticket#>.md            # perf ticket: repro_perf_{local,remote}.md
cp $S/lab-box/* $D/tools/                       # then fill tools/lab.conf (Phase 9b)
```

`<core>` is at most two words of the issue's essence taken from the title, and side-agnostic —
never the test tool's name, because the root cause may be in FW or in the tool: #5090131
("[UTOPX] cmd_hca_cap actual < expected …") is `5090131_cap_mismatch`, not `5090131_utopx`.
Set up `tools/` as soon as Phases 1–2 are decoded, before the box is free, so the repro starts
the moment the lock lands; leave `VERIFIED=` empty until the first run reproduces the signature.
`FINDINGS_<ticket#>.md` is copied from `templates/findings.md` at the first root-cause hypothesis.

## 1. The files

| File | What it is | Reader | Created |
|---|---|---|---|
| `REPRO_<ticket#>.md` | the working document. On top, the plan — todo list, goal, the environment and pins decoded from the ticket — edited in place. Below, the Investigation log and the Run log, append-only | whoever works the ticket | step 0, `templates/repro.md` |
| `FINDINGS_<ticket#>.md` | the conclusion and the deliverable: status, the failure, where it happens, root cause, fix, verification, next steps; posted to Redmine and sent to the code owner, in plain English | Peter, the code owner, Redmine readers | at the first root-cause hypothesis, `templates/findings.md` |
| `regression_ini/` | the INI the regression burned, the release default, and their diff | — | Phase 5 |
| `tools/`, `logs/` | the lab-box scripts (`templates/lab-box/`); logs the documents cite | — | step 0 |
| `FIX_<topic>.patch`, `REJECTED_<vN>_<why>.patch` | the fix (exactly one) and every disproved candidate | — | as they happen |

A **performance-degradation** ticket keeps the same two documents, from other templates:
`REPRO_<ticket#>.md` from `templates/repro_perf_local.md` (runs need no power cycle; executed on
the test server) or `templates/repro_perf_remote.md` (runs need a power cycle; driven from the dev
box), and `FINDINGS_<ticket#>.txt` from the matching `templates/findings_perf_{local,remote}.txt`,
which is updated after every run.

## 2. What changes where

Update in the same step as the event:

| Event | `FINDINGS` | `REPRO` |
|---|---|---|
| Peter gives an instruction | — | log: his words, verbatim; plan: the todos or goal, when the plan changes |
| the ticket is decoded (Phases 1–2) | §1, §2 tables | plan: environment and pins; log: where each value came from |
| the box is locked, the environment rebuilt | — | log: box, lock, `env_rebuild` result and log path |
| a run | a §6 row for the runs that decide: repro, control, patched | Run log: every run — box, FW and tool pins, seed, signature yes / no, how it ended, log path |
| source read; a hypothesis formed or killed | — | log: `file:line`, attribution (`git blame`, `git log --author`), verdict |
| the root cause is accepted | §3 and the Status line | log: the deciding evidence |
| a hypothesis turns out wrong | §3 corrected; one §4 line pointing at the log entry | log: struck through in place, with the correction and its date |
| a fix is built, verified or rejected | §5, §6, the Status line | log: build result (rc, `error:` count, image md5); Run log: the runs |
| the fix is pushed or merged | §7 | log: the change as `[<num>](<URL>)`, patchset, CI and MARS ids |
| the session is interrupted | — | log: what is in flight, and the next step |

## 3. `FINDINGS`

- The mandatory deliverable. Start it (Status `IN PROGRESS`) at the first root-cause hypothesis;
  write it from the log, never from memory or a chat transcript.
- It states the current conclusion and is corrected in place; how the conclusion was reached
  lives in the log. A hypothesis that turned out wrong gets one §4 line ("looked like …; ruled out
  by …") naming its log entry.
- §2 holds real values — a vague `32.51.xxxx` is not an answer — and every path a reviewer needs
  to redo the work: official artifacts, worktrees and branches, local artifacts. Record the md5 of
  every built image: `jmake` always writes the same `<repo>/fw-<device>.mlx`, so save a named copy
  of each build or the control and the patched build overwrite each other.
- §6: the control differs from the patched run by exactly one variable — same tree, tag, configs,
  command and seed, patch removed. An even release tag is verified by building the next odd tag,
  and the control comes from that same tag. A run that scores zero on the signature and then
  crashes or stops at init is VOID, not a pass.
- §7 back-port range is measured, not estimated:
  `git tag --contains <bad-sha> | grep -E '^rel-' | sort -t_ -k2,2n -k3,3n | head -3` (first
  affected release), `git tag --contains <bad-sha> | grep -cE '^rel-'` (how many),
  `git branch -r --contains <bad-sha>` (which branches). fsearch cannot answer it: its ~8-day
  retention makes the oldest row look like a start date. Say whether "carries the defect" means
  "will fail": a config-gated bug is back-ported by which lines run that config.
- Patches are named by verdict: exactly one `FIX_<topic>.patch`; a disproved candidate becomes
  `REJECTED_<vN>_<why>.patch` the moment it is superseded, and is never deleted.
- Paths a reader copies stay in backticks: `FINDINGS` travels to Redmine and to HTML, where
  relative links break.
- External links are a short label linked to the full URL, never the URL itself:
  `[5298707](https://redmine.nvidia.com/issues/5298707)`, `[1530478](<gerrit change URL>)`,
  `[utopx_ci #25763](<Jenkins build URL>)`. Every mention of a change or ticket number is linked,
  in text and tables alike (feature-delivery `references/documents.md` §6). The plain-text
  `findings_perf_*.txt` are the exception: there a bare URL is the only clickable form.

## 4. `REPRO`

- The plan on top is edited in place and always shows the current plan.
- The Investigation log follows the rules of a feature's work log (`feature-delivery`
  `references/documents.md` §2): one entry per event, headed with its number and a short title,
  the date, time and one-line conclusion in the first line under it; Peter's words verbatim; Did / Result / Next; a wrong conclusion struck through in
  place with the correction; entries only appended, numbers only grow.
- The Run log is a table, one row per run, rows only appended.
- At the start of a session read the plan and the last few log entries, not the whole file.

## 5. What not to create

No second document for the ticket: no `repro_plan_*`, `ROOTCAUSE*`, `ROOT_CAUSE_*`, `ANALYSIS_*`,
`REPRO_STATUS`, `REPRO_RECORD_*`, `REPRO_AND_FIX`, `root_cause_report`, `regression_status`,
`README`, `INDEX_*` or `DUPLICATE_NOTE_*`. The conclusion and its status go into `FINDINGS`, the
steps into `REPRO`. An outgoing Redmine note or message is `msg_<who>_draft.txt` until it is
sent, then deleted.

## 6. A ticket inside a feature or a long task

That task's `TRACKING.md` lists this ticket's `FINDINGS` in its §6 and keeps the ticket's status
in its §3; this directory keeps everything else.

## 7. Moving an in-progress ticket to this set

1. Rename `repro_plan_<ticket#>.md` to `REPRO_<ticket#>.md`, and fix every link to the old name
   (`grep -rl repro_plan_<ticket#> /auto/fwgwork1/$USER/bugZilla`).
2. In `FINDINGS`, delete the writing rules the old template carried above §1; move the dated §3
   sub-investigations into the `REPRO` log when they are not there already, and keep the accepted
   root cause in §3 and one line per rejected hypothesis in §4.
3. Fold any file from §5 into `FINDINGS` or `REPRO`, then delete it.
