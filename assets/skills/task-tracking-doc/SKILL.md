---
name: task-tracking-doc
description: >-
  Create and keep current TRACKING.md, the on-disk ledger of a long-running task - status board,
  per-object tables, evidence rows with controls, overturned conclusions kept in place. Use at the
  START of a task spanning sessions or several commits, branches, tickets, boxes or experiments;
  when resuming or handing it over or answering "where are we on X"; and whenever a build, push,
  CI verdict, merge, review comment or reversed judgement lands.
---

# TRACKING.md — the ledger for a long-running task

`TRACKING.md` is the task's memory on disk: an **append-only ledger, not a status report**. A
conclusion that turns out wrong is struck through and left where it is, never deleted.

One task, one directory named after the task, one file always named `TRACKING.md` (like
`README.md`). Never put the task in the filename: a descriptive name is outgrown once the file
also holds verdicts, CI history, review threads and lessons.

## 1. When to create one

Any **one** trigger is enough:

| Trigger | Why |
|---|---|
| Expected to span more than one work session | context is lost between sessions; this file is the only handover surface |
| Two or more objects advancing independently (commits, branches, tickets, boxes, experiment configs) | an N x M state matrix does not fit in anyone's head |
| An external async system answers later (CI, code review, regression, machine queue) | waiting is when things get forgotten |
| A judgement that could be overturned (attribution, root cause, "this branch does not need it") | an unrecorded reversal gets made twice |
| Evidence with an expiry (retention windows: §4c) | not written down in time = lost permanently |
| Someone will ask "where are we on X" | the answer must be copy-pasteable |

Do **not** create one for a one-off question, a single-file edit, or a single-ticket
investigation — that is skill `regression-repro`, which already has `repro_plan_<ticket>.md` +
`FINDINGS_<ticket>.md`; do not stack a third document on it.

## 2. Where it lives

- `<task dir>/TRACKING.md`. Every console capture and session archive goes in `<task dir>/logs/`;
  its path goes into the table next to the result it belongs to.
- **Never start a second file** — no `TRACKING_v2.md`, no split by time (`TRACKING_2026Q3.md`) or
  by status (`TRACKING_done.md`): one item's history would then span files. When the shape of the
  work changes, add a part (§7). Length is no reason to split; thousands of lines is normal.
- Split out a sub-document only when a block is self-contained **and** referenced on its own (a
  code-flow write-up, a handoff document, one independent investigation). A sub-document:
  - gets a lowercase descriptive name (`rebase_handoff.md`, `bf4_bringup_log.md`);
  - **must be registered in the sibling-documents table** at the top of `TRACKING.md` — an
    unregistered sub-document does not exist;
  - leaves a one-line summary plus a pointer in `TRACKING.md`, not a bare pointer.

## 3. Day 0 — written before the work starts

Copy `templates/TRACKING.md`. Its seven blocks are mandatory, in this order:

1. Title, one-line purpose, creation date, the words "kept current (updated in place, never start
   a new file)", `Last updated:`
2. **Status board** — milestone table, the index of the whole file; must fit one screen
3. Definition of done, plus decisions already locked
4. Constants — repo URL, gerrit/Jenkins prefixes, worktree paths, machine names
5. **The update-discipline table** — copied in verbatim
6. Writing conventions — ordering, greying-out, status legend, link rules
7. Sibling-documents table

Block 5 is load-bearing: the next session's agent may never load this skill, but it reads the
first screen of the document — the file carries its own enforcement.

**N objects x M channels** (commits x branches and the like): the per-channel ledger
(`templates/parts.md` part L) goes between blocks 1 and 2, at the very top — it answers the most
frequent question, "where is X on channel Y", so it must be on the first screen. When converting an
existing document to this skeleton, keep whatever its owner reads first at the front; never bury it
under the new header blocks.

## 4. The update contract

This is the part that fails. Four layers, in order of reliability.

**(a) An action = execute + record.** Update live, not as post-processing. An unrecorded action
**counts as not done**: do not proceed to the next one until the current result is recorded.

**(b) Event-driven, never periodic.** A periodic update needs a reminder that never comes; the
event itself is the trigger. Record in the same batch as the action:

| Event | Minimum to record |
|---|---|
| a long command / build finishes | SUCCESS or FAILED, elapsed, `error:` count, archived log path |
| push completed | change number, **new patchset number** (the next rebase starts from it), what the server echoed (`new:` / `updated:`) |
| CI verdict | build number, which stage failed, downstream job numbers, **session id** |
| merge / delivery landed | timestamp, and the **real SHA after landing** (a merge is usually rebased, so the pushed SHA does not exist on the branch) |
| review comment received or cleared | who raised it, which file and line, how it was resolved |
| experiment result | config, seed, **control group** (without one the result cannot be used for attribution), VERDICT |
| **any judgement overturned** | write "⚠ Correction" in place; **do not delete the old conclusion** (or it gets re-derived) |
| session interrupted | the in-flight item plus one line on the next step |

With a per-channel ledger, push, CI verdict and merge also update that object's row in it, in the
same batch.

**(c) Two companions.**
- **Archive the log before stating the conclusion.** Retention windows are hard limits: CI
  consoles one to two weeks (a fixed build count per job; the DoA job forgets first), failure DB
  ~8 days. `curl`/`cp` those into `logs/` first, then analyse. (MARS session archives,
  `/auto/sw_regression/host_fw/HCA_CORE_FWV/MARS/conf/results/[<setup set>/]<setup>/<sid>/<sid>.tgz`,
  are kept for months, but the MARS API that maps a session id to that path forgets it after about
  two weeks — record the archive path, not just the id.)
- **Write identifiers in full and name their kind.** These look alike but differ: the **local SHA
  before push**, the **patchset revision** on the review server, the **real SHA on the branch
  after landing**. A bare hash later yields a false "this commit does not exist". The landed SHA
  needs no fetch: the newest patchset of a merged gerrit change is the commit on the branch
  (`git ls-remote origin 'refs/changes/<last two digits>/<change>/*'`).

**(d) Mechanical backstop.** `scripts/tracking_lint.py` reports staleness: `Last updated` lagging
the newest artifact in the task directory is physical evidence of a missed update.

## 5. Session protocol

- **Opening**: read the status board and the in-flight rows only — not the whole file, it reaches
  thousands of lines. `python3 scripts/tracking_lint.py <file> --summary` prints exactly that.
- **Closing**: update the board row and `Last updated` as the last action of the session.
- **Interrupted**: one line on what is in flight and what comes next beats a complete narrative
  written later.
- Keep a standing item *update TRACKING.md* in the host's todo/plan mechanism; never check it off
  while the task is alive.

## 6. Writing rules that keep it worth reading

- **Headings are conclusions**, with a date and a verdict:
  `## 4.16 [2026-09-17] BF3 need not propagate to ES — root cause is on master only ★★★`. Never
  `## Analysis` or `## Investigation`.
- **Three independent status axes — do not mix them.** Progress `✅ 🟡 🔵 ⬜` (`⬜` = not
  applicable, *not* "missed"). Risk and disproof `⚠ 🔴 ❌`. Importance `★` x1–7.
- **`🔴` marks the one thing currently blocking you; at most one row carries it.** It is on the
  risk axis and answers "where does this stop today". Never substitute an arrow or bullet (`⬅`
  and friends render in body-text colour and vanish among rows). When the blocker moves, change
  the old row to what it became (`✅` fixed, `⚠` reassigned to another team, `⬜` overtaken) —
  never leave two.
- **Append, never delete.** `~~strikethrough~~` = void but retained, strictly distinct from
  deletion. **Results are not greyed out** — a merged change or a passing run is an outcome, not a
  retraction. When voiding, write three things: which part still holds, why it went wrong, the
  criterion to use next time. Forms: `templates/parts.md` part J.
- **Void in the file and in the live system in the same batch.** Writing "voided" without
  abandoning it in the system leaves the two out of sync.
- **Numbering only grows** — never renumber published sections. Insert as `1.5`, `4.16`, `7a`,
  `7b`, so an old cross-reference like `see §4.19` never silently points somewhere else (worse than
  no reference). Digits and plain letters only — never latin ordinals (`bis`, `ter`, `quater`):
  readers do not know them, `§7a` needs no explanation. The lint still accepts latin forms so
  existing documents keep validating; do not write new ones.
- **A `§` reference into another document names that document.** `see §12.10` reads as "section
  12.10 of this file"; write `` see `handoff.md` §12.10 ``. The lint flags bare `§` references
  matching no local section.
- **Every conclusion points at a control.** Evidence tables carry a control row; a conclusion
  without one is marked `🟡 unproven`. Not-disproved is not proved. Full evidence rules:
  `references/update-discipline.md`.
- **Diagnosis and disposition are separate.** Diagnose on your own; committing code, pushing,
  changing live-system state or sending external messages waits for an order. Proposals sit under
  `#### Proposed disposition (not executed, awaiting instruction)` until ordered, apart from
  completed records.
- **Distrust the file itself.** Patchset numbers, branch tips and ticket states recorded here are
  snapshots from the moment of writing. Re-query the live system before acting on them; if it
  differs, the live value wins — correct the file in place.
- **Register known violations.** A historical record that breaks today's rules and can no longer
  be changed (e.g. a missing mandatory footer) is registered with an explicit "not an example" —
  otherwise the next reader copies it.
- **Language**: keep the template's headings and markers exactly as in the template (English —
  the linter keys on them); write the body text in the task owner's working language (for Peter:
  Chinese). Never translate identifiers, log lines or error signatures. Outward deliverables
  (FINDINGS, commit messages, tickets) stay in English.
- **Formatting** follows the formatting rules at the top of
  `~/myGit/crosslv/assets/skills/regression-repro/templates/findings.md`: bare backticks for local
  paths (a markdown link breaks terminal click-through); **`http(s)` resources — gerrit, Jenkins,
  Redmine, MARS view_log — as bare full URLs, never behind a markdown label, including inside
  table cells**; code-fence language selection; the SUPERSEDED convention.

## 7. Picking parts

The skeleton is fixed; the body is assembled from `templates/parts.md`, and parts can be added at
any time (hence one template, not three).

| What the task looks like | Parts to fit |
|---|---|
| N objects x M channels (commit x branch, fix x platform) | **per-channel ledger at the top** (part L) + main ledger table + **alignment matrix** (measured, never copied from the ledger table) + archive fold |
| Linear, with milestones (bring-up, port, project) | status board + definition of done + timeline table |
| Problems keep surfacing | **numbered problem entries** (`## #N` with Symptom / Location / Action / Result and a status suffix) |
| Arguing an attribution or a root cause | **evidence table with a control row** + criteria table + experiment matrix ending in VERDICT |
| Waiting on CI or review | CI round table |

## 8. Health check

```bash
python3 scripts/tracking_lint.py <task dir>/TRACKING.md            # full report
python3 scripts/tracking_lint.py <task dir>/TRACKING.md --summary  # board + in-flight
```

Run it at session open, at session close, and after any large edit once the file passes ~500
lines. It checks table column alignment, staleness, stalled in-flight rows, numbering reuse,
deleted conclusions (gaps in `#N` problem-entry numbering), broken `§` cross-references, and — as
a hint only — verdict tables without a control row.

## 9. Relationship to `regression-repro`

- `regression-repro`: one ticket, investigated once, start to finish, delivering
  `FINDINGS_<ticket>.md`.
- `task-tracking-doc`: a task running for weeks across many objects whose conclusions get revised.
  No deliverable — it *is* the memory.

A long task can contain several tickets. Each runs `regression-repro` on its own; their `FINDINGS`
files are registered in the sibling-documents table of `TRACKING.md`.

## Related

- `references/update-discipline.md` — evidence rules: controls, criteria ranking, attribution, elimination
- `references/worked-examples.md` — layout patterns from the documents this format was distilled from
- `templates/TRACKING.md` — the skeleton to copy
- `templates/parts.md` — the parts library
- Single-ticket investigation: skill `regression-repro`
- Failure history and attribution: skill `fsearch-failures`
