# A ticket's documents — what each file holds, and when it changes

A ticket gets the same three documents as a feature, with sections of its own: `Tracking.md`, the
status page; `Ledger.md`, the Run log and the step-by-step record; `Defects.md`, the root cause and
the fix. How they are written and kept — language, links, log entries, corrections, what not to
create, what to delete — is skill `markdown-docs`. All three are in Chinese; what goes to Redmine
is written from them in English, under `redmine/` (section 3).

## 0. Setting up the directory

```bash
S=~/myGit/crosslv/assets/skills/regression-repro/templates
D=/auto/fwgwork1/$USER/bugZilla/<ticket#>_<core>
mkdir -p $D/{tools,ini,reports,drafts,patches,fw} $D/logs/{env_rebuild,ci,fwtrace,lock,build}
cp $S/{Tracking.md,Ledger.md,Defects.md} $D/
cp $S/lab-box/* $D/tools/                       # then fill tools/lab.conf (Phase 9b)
```

`<core>` is at most two words of the issue's essence taken from the title, and side-agnostic —
never the test tool's name, because the root cause may be in FW or in the tool: #5090131
("[UTOPX] cmd_hca_cap actual < expected …") is `5090131_cap_mismatch`, not `5090131_utopx`.
Set up `tools/` as soon as Phases 1–2 are decoded, before the box is free, so the repro starts
the moment the lock lands; leave `VERIFIED=` empty until the first run reproduces the signature.

A performance-degradation ticket uses the same three documents and the procedure of
`perf-bisect.md`, which says what goes where.

## 1. The files

| File | What it is | Created |
|---|---|---|
| `Tracking.md` | the status page: the status sentence, waiting for, next steps, decisions needed from Peter; the goal and the environment decoded from the ticket; the reproduction steps as this ticket does them, each with its status; the list of files. Edited in place | step 0 |
| `Ledger.md` | the log: the Run log table on top, one row per run; the entries below, one per event — source read, hypotheses formed and killed, builds, Peter's instructions verbatim | step 0 |
| `Defects.md` | the conclusion: the failure, where it happens, root cause, rejected hypotheses, fix, verification, next steps. Edited in place | step 0; filled from the first root-cause hypothesis |
| `ini/` | the INI the regression burned, the release default, and their diff | Phase 5 |
| `reports/` | `report_<MMDD>_<box>_<sha>.md`, one per test campaign, written once (template: skill `feature-delivery`, `templates/report.md`) | end of each campaign |
| `tools/`, `logs/`, `fw/`, `drafts/` | the lab-box scripts (`templates/lab-box/`); logs the documents cite; FW images a run burns; outgoing text until it is sent (skill `markdown-docs`, "Task directory layout") | step 0 |
| `patches/` | `FIX_<topic>.patch`, the fix (exactly one); `REJECTED_<vN>_<why>.patch`, every disproved candidate; the `git diff` of a tree with uncommitted changes that a run used | as they happen |
| `attach/` | the MARS artifacts uploaded to the ticket, with `manifest.tsv` (skill `utopx-regression-ticket`) | when the ticket gets them |
| `redmine/` | what goes to Redmine, in English: drafts of the description and comments, `ROOTCAUSE_analysis.md` (skill `utopx-regression-ticket`) | when something is posted |

`Tracking.md` §4 holds the run steps, written as skill `markdown-docs`, "Run steps", says: copying
its commands one by one reproduces the failure. They are the box lock and the checks before
touching it, the session's own setup steps in the session's order, the per-case reset, the
start-state check, the case command, the signature check and the fix verification, then the same
steps with the scripts.

## 2. What changes where

Update in the same step as the event:

| Event | `Tracking.md` | `Ledger.md` | `Defects.md` |
|---|---|---|---|
| Peter gives an instruction | the next steps, when they change | an entry: his words, verbatim | — |
| the ticket is decoded (Phases 1–2) | §2 goal, §3 environment, §4 from the session's steps | an entry: where each value came from | — |
| the box is locked, the environment rebuilt | §4, when a command had to change | an entry: box, lock, `env_rebuild` result and log path | — |
| a run | the status, when the run changes it; §4, when a command had to change | a Run log row: box, FW and tool pins, seed, signature yes / no, how it ended, log | §6, for the runs that decide: repro, control, patched |
| source read; a hypothesis formed or killed | — | an entry: the source lines read, linked; attribution (`git blame`, `git log --author`); verdict | §4 gets the killed hypothesis as one line |
| the root cause is accepted | the status | an entry: the deciding evidence | §3 |
| a hypothesis turns out wrong | — | struck through in place, with the correction, its date and the criterion for next time | §3 corrected; one §4 line pointing at the entry |
| a fix is built, verified or rejected | the status | an entry: build result (rc, `error:` count, image md5); Run log rows | §5, §6 |
| the fix is pushed or merged | the status: the change as `[<num>](<URL>)`, patchset | an entry: patchset, CI and MARS ids | §5 Gerrit line |
| something waits for a person; a decision is needed | waiting for; decisions needed from Peter | — | — |
| the session is interrupted | — | an entry: what is in flight, and the next step | — |

## 3. `Defects.md` and what goes to Redmine

- `Defects.md` is the deliverable, the source of everything said about the ticket. It states the
  current conclusion and is corrected in place; how the conclusion was reached lives in
  `Ledger.md`. A hypothesis that turned out wrong gets one §4 line ("looked like …; ruled out by
  …") naming its entry.
- §2 holds real values — a vague `32.51.xxxx` is not an answer — for what decides whether the bug
  fires; the whole environment is `Tracking.md` §3, not copied. Record the md5 of every built
  image: `jmake` always writes the same `<repo>/fw-<device>.mlx`, so save a named copy of each
  build or the control and the patched build overwrite each other.
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
- Patches live in `patches/` and are named by verdict: exactly one `FIX_<topic>.patch`; a
  disproved candidate becomes `REJECTED_<vN>_<why>.patch` the moment it is superseded, and is never
  deleted.
- A second, independent defect found in the same ticket gets its own section after §7,
  `## 8. <one line: the second defect>`, with the same parts as bold lead lines; when it deserves
  its own ticket, it gets one.
- **What goes to Redmine** is written from `Defects.md` and `Tracking.md` §3 in plain English,
  under `redmine/`, when it is posted: the root-cause comment (`NOTE_<id>_rootcause.html`) and, for
  a new ticket, `ROOTCAUSE_analysis.md` from skill `utopx-regression-ticket`'s
  `assets/ROOTCAUSE_analysis.md`. Local paths and lines of a local tree stay in backticks there; a
  source line the server has links gerrit's file view or gitiles. Once posted, a file there is not
  edited; a correction goes up as `_v2`.

## 4. `Ledger.md`

- The Run log sits on top, under the header; rows are appended at its end, one per run, before the
  next run starts. Entries are appended at the end of the file, `## <n>. <short title>`, first line
  date and conclusion (skill `markdown-docs`, "Log entries").
- At the start of a session read `Tracking.md` and the last few entries, not the whole file.

## 5. Files: what to keep, what not to create

- Logs: a run's log stays in the worktree's `logs/` and the Run log row links it there; a run
  that decides something — the repro, the control, the patched run — has its log copied to the
  ticket's `logs/` in the same step and cited from `Defects.md` §6. Once the fix is verified, logs
  in the ticket's `logs/` that neither `Defects.md` nor `Tracking.md` cites are deleted.
- FW images: in the ticket's `fw/`, one `fw_archive_<MMDD>_<sha>/` per build, never in a
  worktree's `logs/`. Keep only those `Defects.md` §6 cites — the control and the final patched
  build — with their md5; a disproved candidate keeps only its `.patch`, in `patches/`.
- The other directories — `drafts/`, `patches/`, the subdirectories of `logs/` — follow skill
  `markdown-docs`, "Task directory layout".
- No second document for the ticket (skill `markdown-docs`, "Files"): no `repro_plan_*`,
  `REPRO_*`, `FINDINGS_*`, `Repro_*`, `Rc_*`, `ROOTCAUSE*` outside `redmine/`, `ROOT_CAUSE_*`,
  `ANALYSIS_*`, `REPRO_STATUS`, `REPRO_RECORD_*`, `REPRO_AND_FIX`, `root_cause_report`,
  `regression_status`, `README`, `INDEX_*` or `DUPLICATE_NOTE_*`. The conclusion goes into
  `Defects.md`; the status and the reproduction steps into `Tracking.md`; what was done, step by
  step, into `Ledger.md`.

## 6. A ticket inside a feature or a long task

The ticket keeps its own three documents in its own directory and its own worktrees off the `*2`
clones. That task's `Tracking.md` links this ticket's `Tracking.md` from its defect row (§3)
instead of copying the status, lists this ticket's `Defects.md` in its §7, and its `Ledger.md`
records only what changes that task.

## 7. Moving an older ticket directory to this set

When a ticket is worked again and its directory still has the older documents —
`Repro_<ticket#>.md` and `Rc_<ticket#>.md`, or before them `repro_plan_<ticket#>.md`,
`REPRO_<ticket#>.md`, `FINDINGS_<ticket#>.md` (a performance ticket's `.txt`):

1. Ask the sessions that write the directory to stop until the move is done.
2. `Tracking.md` from the template, written from the live state (gerrit, the box, the lock) and
   the old plan's goal and environment — not by trimming the old file. §4 is written from the
   commands the scripts in `tools/` and the log entries show were actually run.
3. `Ledger.md`: the old Run log becomes the Run log table; the old investigation entries become
   entries, in time order, numbered from 1, each headed by a short title with the date in its first
   line, struck-through lines kept as they are. Material pasted into the old log — a handoff, a
   review thread, a Redmine draft — moves to its own file (`<kind>_from_<who>.md`, `redmine/`) and
   the entry keeps a line with the link. Every entry's content is kept.
4. `Defects.md` from the template, written in Chinese from the old conclusion document; the
   environment it carried goes to `Tracking.md` §3.
5. Fold any file from section 5 into the three, repoint every link to the old names
   (`grep -rlE 'Repro_<ticket#>|Rc_<ticket#>|repro_plan_<ticket#>|REPRO_<ticket#>|FINDINGS_<ticket#>' /auto/fwgwork1/$USER/bugZilla`),
   then delete the old files.
