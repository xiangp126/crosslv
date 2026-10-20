# The feature's documents — what each file holds, and when it changes

`SKILL.md` "Documents" gives the file set, the copy commands and the event table. This file is the
detail behind them, and holds only what is particular to the feature's set. How every document is
written and kept — one home per fact, how a page and a log change, the writing rules, what not to
create, what to delete — is skill `markdown-docs`. In its terms `Tracking.md` and `Defects.md` are
pages, `Ledger.md` is a log, and a report is a record.

## 1. `Tracking.md` — the feature's status page (for people)

Readers: Peter, the owners, the reviewers. It answers "where is this feature, what is it waiting
for, what changed". It is a **current-state** page: edit it in place, keep it short (one or two
screens before §2), put the most important content first. It holds no rules for agents, no
step-by-step record and no history of SHAs.

| Section | Holds | Rules |
|---|---|---|
| header | name, Last updated, owners, 2-4 sentences on what the feature is | Last updated changes with every edit |
| §1 one-sentence verdict + status table | one row per part (test tool, FW, gates, device verification, requirements) | the verdict is the first thing a reader sees; rewrite it whenever the situation changes |
| §1.1 / §1.2 commits | per repository: not merged, then merged | **owners only** — the feature's owners on each side, current and former; other people's commits in the same area are not this feature's. "Not merged" is the owner's current plan (their own list, a message, the stack they are assembling), not every open change in gerrit: stale and abandoned changes are left out. Merged dates come from the gerrit submit approval (`gerrit query --all-approvals`, type `SUBM`), not from commit dates. Every change is its number linked to its gerrit URL (skill `markdown-docs`, "Links") |
| §1.2 tail | the FW image under test | base SHA and version + which changes and patchsets + image path and md5 |
| §1.3 waiting for | one line per person or team | name who, what, since when, and where the draft or message is |
| §1.4 next steps | short list | |
| §1.5 decisions for Peter | question + background | a decision taken moves out of this table; the ledger keeps the record |
| §1.6 requirements | one row per Req of the Feature Request | the "Verified?" column is only ✅ when an assertion that can fail exists and a run passed it |
| §2 test campaigns | one row per campaign, newest first | links the frozen report |
| §3 defects | one row per defect: one-line problem, side, **status** | the only place the feature keeps a defect's status; a defect worked as a ticket also has its `Rc`, whose Status line says how far the investigation got |
| §4 timeline | one line per day, newest first | what changed for the feature, not what the agent did |
| §5 environment and how to run | boxes, FW/INI/NV, code paths, the two commands | the procedure that executes is `tools/`; this section only points to it |
| §6 documents | one row per local file, its relative link `[name](path)` in the left column (files under `tools/` too, as `tools/<file>`); external documents as `[short name](URL)` | one click opens each file; the links line up |

Status marks, one meaning each: ✅ done · 🟡 partial or worked around · 🔵 in progress or waiting ·
🔴 blocked · ⬜ not started or not hit.

## 2. `Ledger.md` — the step-by-step record (for whoever continues)

The feature's log: its entries, and how a wrong conclusion is struck through, follow skill
`markdown-docs`, "Log entries". What each event records here, next to what it changes in
`Tracking.md`: the event table in `SKILL.md`, "Documents". At the start of a session read
`Tracking.md` §1 and the last few ledger entries.

## 3. `Defects.md` — defects and fixes (for Peter, owners and reviewers)

One section per defect, in the order a run from the starting baseline hits them; §0 is that
reproduction ladder (step, code under test, parameters, which defect, where it stops). Each section
holds: side, fix (linked change number), how to hit it, what happens (verbatim, in a `text`
block), root cause (with links to its source lines), the final diff, why it works and what it
deliberately leaves out, rejected alternatives with their diffs, the evidence (runs before and
after, the control), open questions.

- **No status in this file** — it lives in `Tracking.md` §3.
- **Reviewer-safe from day 1**: no reviewer names, no internal process (who asked what, session
  names, the order in which the agent tried things). Owners appear only on the side line.
- Fixes found while testing someone else's change start as `[Local-Only]` commits; their section here
  is the review material for the fix commit when Peter decides to push it.
- A defect that stops appearing moves to "Defects no longer seen", with what removed it.
- A superseded root cause stays only when it helps the reader, as one line: "first thought …; it
  turned out …".
- Failures that are not this feature's (the same failure exists in the regression DB on boxes
  without it) go to "Pre-existing issues", with the regression-DB hit.

## 4. `report_<MMDD>_<box>_<sha>.md` — one test campaign (for people)

Written when a campaign ends and not edited afterwards. Conclusion first (n of m, attribution of
every failure, what the new path did, what it proves and what it does not), then the setup with
identities (FW image md5, test-tool tree and binary md5), one row per run with the feature's
fingerprints as columns, the failures with verbatim lines and attribution, what was not covered,
environment problems. Every run and every failure gets a row; nothing is summarised away.

## 5. `tools/` and `logs/`

- `tools/` is skill `regression-repro`'s `templates/lab-box/` with `MODE=feature`: fill `lab.conf`
  only; change a script only when no hook can express the need, and record why in `Ledger.md`. A
  control or a second box gets its own small conf that sources `lab.conf`.
- Run logs stay in the tested worktree's `logs/`; logs a page or a report cites are copied to the
  task's `logs/`, so deleting a worktree never deletes evidence. A `Ledger.md` entry may link the
  run's log in the worktree.
- FW images go to the worktree's `logs/`, and only the one under test stays.
- Deleting follows skill `markdown-docs`, "Files". A path cited only in `Ledger.md` does not keep a
  file: once a campaign's report is written, its logs that neither the report, `Defects.md` nor
  `Tracking.md` cites are deleted.

## 6. What not to create

The rules are skill `markdown-docs`, "Files". In a feature directory they mean in particular: no
separate workaround or review document next to `Defects.md`, and no second status page — §1 and §5
of `Tracking.md` already answer "where are we" and "how do I run it".

## 7. Moving an old document set to this one

1. Rename the old append-only ledger to `Ledger.md`, unchanged, with one line on top saying
   it is the old ledger.
2. Write `Tracking.md` from the template, from the live state (gerrit, boxes) — not by trimming the
   old ledger.
3. Merge overlapping defect and review documents into `Defects.md`.
4. Delete every replaced file and every log the new documents do not cite; repoint references in the
   remaining documents.

## 8. Other long tasks and tickets inside a feature

- A long task that is not a feature (branch propagation, a multi-ticket campaign) starts with
  `Tracking.md` and `Ledger.md` from this skill's templates; `Defects.md`, reports and `tools/` are
  added once it has defects, test campaigns or lab runs. In `Tracking.md`, §1.1 / §1.2 become one
  commit table per target branch, and what does not apply (the Gates row, §1.6) is left out.
- A bug ticket worked inside a feature runs skill `regression-repro` in its own directory, with its
  own worktrees off the `*2` clones and its own `Repro_<ticket#>.md` and `Rc_<ticket#>.md`. The
  feature's `Tracking.md` lists the `Rc` in §6 and keeps the ticket's status in §3; its `Ledger.md`
  records only what changes the feature (the ticket opened, its status, its fix landing).
