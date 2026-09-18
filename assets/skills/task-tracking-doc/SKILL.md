---
name: task-tracking-doc
description: >-
  Create and then continuously maintain TRACKING.md — the single on-disk ledger for a long-
  running task: status board, per-object tables, evidence rows with controls, and overturned
  conclusions kept in place instead of deleted. Use at the START of any task that will span
  more than one session or touch more than one commit, branch, ticket, lab box or experiment;
  when resuming such a task after days away; when handing it over or answering "where are we
  on X"; and every time a build, push, CI verdict, merge, review comment or reversed judgement
  lands and the record must be brought up to date.
---

# TRACKING.md — the ledger for a long-running task

`TRACKING.md` is the task's memory on disk. It is an **append-only ledger, not a status
report**: a conclusion that turns out wrong is struck through and left where it is, never
deleted. One task directory, one `TRACKING.md`, same filename every time — like `README.md`.

A fixed name is deliberate. The document this skill is distilled from was called
`branch_propagation_ledger.md` and outgrew that name within weeks (it ended up holding
attribution verdicts, CI history, review threads and methodology lessons). Name the
directory after the task; never the file.

## 1. When to create one

Any **one** of these triggers it. Do not deliberate.

| Trigger | Why |
|---|---|
| Expected to span more than one work session | context is lost between sessions; this file is the only handover surface |
| Two or more objects that advance independently (commits, branches, tickets, boxes, experiment configs) | an N x M state matrix does not fit in anyone's head |
| An external async system will answer later (CI, code review, regression, machine queue) | you will wait, and waiting is when things get forgotten |
| A judgement that could be overturned (attribution, root cause, "this branch does not need it") | reversals must be recorded or you will make the same one twice |
| Evidence with an expiry (Jenkins purges builds in ~12 days; the failure DB keeps ~8) | not written down at the time is lost permanently |
| Someone will ask "where are we on X" | the answer must be copy-pasteable |

**Do not create one** for: a one-off question; a single-file edit; a single-ticket
investigation — that is skill `regression-repro`, which already has
`repro_plan_<ticket>.md` + `FINDINGS_<ticket>.md`. Do not stack a third document on it.

## 2. Where it lives

- `<task dir>/TRACKING.md`. One task, one directory, named after the task.
- Sub-documents get lowercase descriptive names (`rebase_handoff.md`, `bf4_bringup_log.md`)
  and **must be registered in the sibling-documents table** at the top of `TRACKING.md`.
  An unregistered sub-document does not exist.
- `logs/` under the same directory holds every console capture and session archive; the
  path goes into the table next to the result it belongs to.
- **Never start a second file.** When the shape of the work changes, add a part
  (section 7), do not create `TRACKING_v2.md`.

## 3. Day 0 — written before the work starts

Copy `templates/TRACKING.md`. Its seven blocks are mandatory, in this order:

1. Title, one-line purpose, creation date, the words "持续更新,不另起新文件", `Last updated:`
2. **Status board** — milestone table that is the index for the whole file. Must fit one screen.
3. Definition of done, plus decisions already locked
4. Constants — repo URL, gerrit/Jenkins prefixes, worktree paths, machine names
5. **The update-discipline table** — copied in verbatim
6. Writing conventions — ordering, greying-out, status legend, link rules
7. Sibling-documents table

Block 5 is the load-bearing one. **The discipline table is copied into the product, not
just kept in this skill.** The next session's agent may never load this skill; it will
still be constrained by the first screen of the document it opens. The file carries its
own enforcement.

## 4. The update contract

This is the part that fails. Four layers, in order of reliability.

**(a) Definition.** An action is *execute + record*. An action that is not recorded
**counts as not done**, and you do not move to the next one. Inherited verbatim in spirit
from the oldest ancestor of this format: *"Do not proceed to the next test until the
current result is documented."*

**(b) Event-driven, never periodic.** Periodic updates are always missed.

| Event | Minimum to record |
|---|---|
| a long command / build finishes | SUCCESS or FAILED, elapsed, `error:` count, archived log path |
| push completed | change number, new patchset number, what the server echoed (`new:` / `updated:`) |
| CI verdict | build number, which stage failed, downstream job numbers, **session id** |
| merge / delivery landed | timestamp, and the **real SHA after landing** (a merge is usually rebased, so it differs from what you pushed) |
| review comment received or cleared | who raised it, which file and line, how it was resolved |
| experiment result | config, seed, **control group**, VERDICT |
| **any judgement overturned** | write "⚠ 更正" in place; **do not delete the old conclusion** |
| session interrupted | the in-flight item plus one line on the next step |

**(c) Two companions.** Archive the log before stating the conclusion — retention windows
are hard limits. Write identifiers in full and say which kind they are ("local SHA before
push" vs "SHA on the branch after landing"); those two differ and confusing them has cost
real time.

**(d) Mechanical backstop.** `scripts/tracking_lint.py` reports staleness: when
`Last updated` lags the newest artifact in the task directory, that is physical evidence
of a missed update, not an opinion.

## 5. Session protocol

- **Opening**: read the status board and the in-flight rows — **not the whole file**, it
  will reach thousands of lines. `python3 scripts/tracking_lint.py <file> --summary` prints
  exactly that.
- **Closing**: update the board row and `Last updated`. This is the last action of the
  session, not something to catch up on later.
- **Interrupted**: one line on what is in flight and what comes next beats a complete
  narrative written later.
- Put a standing item in whatever todo/plan mechanism your host gives you: *update
  TRACKING.md*. It should never be checked off while the task is alive.

## 6. Writing rules that keep it worth reading

- **Headings are conclusions**, with a date and a verdict:
  `## 4.16 【2026-09-17】BF3 不需要传播到 ES —— 根因只在 master ★★★`.
  Never `## 分析` or `## 调查`.
- **Three independent status axes — do not mix them.**
  Progress `✅ 🟡 🔵 ⬜` (`⬜` = not applicable, which is *not* the same as "missed").
  Risk and disproof `⚠ 🔴 ❌`. Importance `★` x1–7.
- **Append, never delete.** `~~strikethrough~~` means void-but-retained and is strictly
  distinct from deletion. **Results are not greyed out** — a merged change or a passing run
  is an outcome, not a retraction. When voiding something, always write three things: which
  part still holds, why it went wrong, and the criterion to use next time.
- **Numbering only grows.** Insert as `1.5`, `4.16`, `7bis`, `7ter` so that an old
  cross-reference like `见 §4.19` never silently points somewhere else.
- **A `§` reference into another document must name that document.** `见 §12.10` reads as
  "section 12.10 of this file"; write `` 见 `handoff.md` §12.10 `` instead. The lint flags
  bare `§` references that match no local section — that check found nine of them in the
  first real document written from this template.
- **Every conclusion must point at a control.** Evidence tables carry a control row; a
  conclusion without one is marked `🟡 未证实`. Not-disproved is not the same as proved.
- **Diagnosis and disposition are separate.** Proposals sit under
  `#### 处置建议(未执行,等指令)` until ordered.
- **Distrust the file itself.** Patchset numbers and branch tips recorded here are
  snapshots from the moment of writing. Re-query the live system before acting on them.
- **Language**: `TRACKING.md` is written in the language the task owner works in (Chinese
  here — all three real-world ancestors are). Identifiers, log lines and error signatures
  are never translated. Outward deliverables (FINDINGS, commit messages, tickets) stay in
  English.
- **Formatting rules are not repeated here.** Bare backticks for local paths (wrapping
  them in a markdown link breaks terminal click-through), code-fence language selection,
  and the SUPERSEDED convention all live in
  `~/myGit/crosslv/assets/skills/regression-repro/templates/findings.md` lines 1-40.
  Follow that. One complement to it: **`http(s)` resources — gerrit, Jenkins, Redmine,
  MARS view_log — are always full clickable links, including inside table cells.**

## 7. Picking parts

The skeleton is fixed; the body is assembled from `templates/parts.md`. Parts can be
added at any time — that is why there is one template and not three.

| What the task looks like | Parts to fit |
|---|---|
| N objects x M channels (commit x branch, fix x platform) | main ledger table + **alignment matrix** (measured, never copied from the ledger table) + archive fold |
| Linear, with milestones (bring-up, port, project) | status board + definition of done + timeline table |
| Problems keep surfacing | **numbered problem entries** (`## #N` with 现象/定位/处置/结果 and a status suffix) |
| Arguing an attribution or a root cause | **evidence table with a control row** + criteria table + experiment matrix ending in VERDICT |
| Waiting on CI or review | CI round table |

## 8. Health check

```bash
python3 scripts/tracking_lint.py <task dir>/TRACKING.md            # full report
python3 scripts/tracking_lint.py <task dir>/TRACKING.md --summary  # board + in-flight
```

Run it at session open, at session close, and after any large edit once the file passes
~500 lines. It checks table column alignment, staleness, stalled in-flight rows, deleted
conclusions, numbering reuse and broken `§` cross-references.

## 9. Relationship to `regression-repro`

> `regression-repro` is one ticket, investigated once, start to finish, delivering
> `FINDINGS_<ticket>.md`.
> `task-tracking-doc` is a task that runs for weeks across many objects whose conclusions
> get revised. It has no deliverable — it *is* the memory.

A long task can contain several tickets. Each ticket runs `regression-repro` on its own;
their `FINDINGS` files are registered in the sibling-documents table of `TRACKING.md`.

## Related

- `references/update-discipline.md` — the contract in full, plus the evidence rules
- `references/worked-examples.md` — three real documents dissected
- `templates/TRACKING.md` — the skeleton to copy
- `templates/parts.md` — the parts library
- Single-ticket investigation: skill `regression-repro`
- Failure history and attribution: skill `fsearch-failures`
