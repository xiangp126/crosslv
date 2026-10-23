# The feature's documents — what each file holds, and when it changes

`SKILL.md` "Documents" gives the file set, the copy commands and the event table. This file is the
detail behind them, and holds only what is particular to the feature's set. How every document is
written and kept — one home per fact, how a page and a log change, the writing rules, what not to
create, what to delete — is skill `markdown-docs`. In its terms `Tracking.md` and `Defects.md` are
pages, `Ledger.md` is a log, and a report is a record.

## 1. `Tracking.md` — the feature's status page

It answers "where is this feature, what is it waiting for, what
changed". It is a **current-state** page: edit it in place, most important content first, the
verdict and the status table of §1 on the first screen. It holds no rules for agents, no
step-by-step record and no history of SHAs. A status lives in one row: a change's in §1.1,
a Redmine ticket's in §1.5, a defect's in §3; §1.2 and §1.3 say what is to be done and point to
that row.

| Section | Holds | Rules |
|---|---|---|
| header | name, Last updated, owners, 2-4 sentences on what the feature is | Last updated changes with every edit |
| §1 one-sentence verdict + status table | one row per part (test tool, FW, gates, device verification, requirements) | the verdict is the first thing a reader sees; rewrite it whenever the situation changes |
| §1.1 commit status | §1.1.1 FW commit, then §1.1.2 Utopx commit: a line with the repository, branch and owners (and any change in another repository, such as `hca_fw/udriver`), then not merged, then merged — every table with the same five columns, Change, Content, Now, Version under test, Status | **owners only** — the feature's owners on each side, current and former; other people's commits in the same area are not this feature's. "Not merged" is the owner's current plan (their own list, a message, the stack they are assembling), not every open change in gerrit: stale and abandoned changes are left out. **Content** is the change's gerrit title verbatim — the subject after `Title:`, type tags, spelling and final period as they are, a `<TAG>` in backticks so the preview shows it; what the change does goes in Status, never in place of the title. **Now** is the current patchset and its date; once merged, the merged patchset and the date of the gerrit submit approval (`gerrit query --all-approvals`, type `SUBM`, not commit dates), and the patchset it has the same content as when the later ones keep the code (gerrit kinds `TRIVIAL_REBASE`, `TRIVIAL_REBASE_WITH_MESSAGE_UPDATE`, `NO_CODE_CHANGE`, `NO_CHANGE`; walk back to the last `REWORK`). **Version under test** is the patchset that ran on the box with its local SHA and the Run log rows, and whether it has the same code as Now — a tested patchset older than the merged code says so. A change that is not in the tree or image under test says that instead, and whether it matters; look it up by Change-Id in the tested commit's history (`git -C <tree> log --grep="Change-Id: <id>" <tested commit>`), not by subject or date. A result that needed something on the other side (a local FW image, a carry) names it, so nobody reads a pass on a local image as a pass on the official one. **Status** is what the change does or fixes (defect numbers, linking §3), its unresolved comments, and Code-Review and CI while open. The SHA a change landed as goes in `Ledger.md`, not here. Every change is its number linked to its gerrit URL (skill `markdown-docs`, "Links") |
| §1.1.1 tail | the FW image under test | base SHA and version + which changes and patchsets + image path and md5 |
| §1.2 waiting for | one line per person or team | name who, what, since when, and where the draft or message is |
| §1.3 next steps | short list | |
| §1.4 decisions for Peter | question + background | a decision taken moves out of this table; the ledger keeps the record |
| §1.5 Redmine tickets | §1.5.1 FW and §1.5.2 Utopx: one row per ticket — the feature's own tickets first, then tickets others opened that the work touched — with title, opened by / assigned to, date, status, sprint, and the Defects.md / Ledger.md section, linked; the Feature Request in the line above | the only place a ticket's status is kept; refreshed from Redmine when it changes, with the time it was checked |
| §1.6 requirements | one row per Req of the Feature Request | the "Verified?" column is only ✅ when an assertion that can fail exists and a run passed it |
| §2 test campaigns | one row per campaign, newest first | links the frozen report |
| §3 defects | one row per defect: one-line problem, side, **status** | the only place the feature keeps a defect's status; for a defect worked as a ticket the row links the ticket's `Tracking.md`, which keeps it |
| §4 timeline | one line per day, newest first | what changed for the feature, not what the agent did |
| §5 environment | one table with the columns Item, Value and Source, like a ticket's §3: the box and when mars_reg takes it back, the dev box, card and PSID, MST device, MARS setup id, FW image (path, md5, FW Release Date), INI and NV, the test-tool and FW trees with their commits, the feature gate, the reference run's seed and arguments, where the logs go | every row says where it was checked; corrected in the same step as the box, the image or a tree changes |
| §6 test steps | flat steps 6.1 … like a ticket's §4 reproduction steps: an opening paragraph (where and as whom the commands run, copied top to bottom, about how long), lock, the checks before touching the box, one step per rebuild step in the order `env_rebuild.sh` runs them, one run with the feature on, the control run with it off, the result check, the build when the code changed, and last the same steps with `env_rebuild.sh` and `per_run.sh` | written as skill `markdown-docs`, "Run steps", says: copying the commands one by one rebuilds the box and runs the test; each step's "Expected" is a verbatim line from a real run with its log linked. Corrected in the same step as a command changes |
| §7 documents | one row per local file, its relative link `[name](path)` in the left column (files under `tools/` too, as `tools/<file>`); external documents as `[short name](URL)` | `Defects.md` and `Ledger.md` are the first two rows; one click opens each file; the links line up |

Status marks, one meaning each: ✅ done · 🟡 partial or worked around · 🔵 in progress or waiting ·
🔴 blocked · ⬜ not started or not hit.

## 2. `Ledger.md` — the step-by-step record

The feature's log: the Run log table at the top, one row per device run (time, box, FW, test-tool
tree and binary md5, seed and arguments, the `per_run.sh` verdict, the log), then the entries.
Rows, entries, and how a wrong conclusion is struck through follow skill `markdown-docs`, "Log
entries". What each event records here, next to what it changes in `Tracking.md`: the event table
in `SKILL.md`, "Documents". At the start of a session read `Tracking.md` §1 and the last few
ledger entries.

## 3. `Defects.md` — defects and fixes

One section per defect, in the order a run from the starting baseline hits them; §0 is that
reproduction ladder (step, code under test, parameters, which defect, where it stops). Each section
holds: side, fix (linked change number), how to hit it, what happens (verbatim, in a `text`
block), root cause (with links to its source lines), the final diff, why it works and what it
deliberately leaves out, rejected alternatives with their diffs, the evidence (runs before and
after, the control), open questions.

- **No status in this file** — it lives in `Tracking.md` §3.
- **How the work went belongs in `Ledger.md`**: no session names, and no account of the order in
  which things were tried. A reviewer's request that shaped a fix is stated with a link to the
  comment.
- Fixes found while testing someone else's change start as `[Local-Only]` commits; their section
  here is what the fix commit's message is written from when Peter decides to push it.
- A defect that stops appearing moves to "Defects no longer seen", with what removed it.
- A superseded root cause stays only when it helps the reader, as one line: "first thought …; it
  turned out …".
- Failures that are not this feature's (the same failure exists in the regression DB on boxes
  without it) go to "Pre-existing issues", with the regression-DB hit.

## 4. `reports/report_<MMDD>_<box>_<sha>.md` — one test campaign

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
- FW images a run burns go to the task's `fw/`, one `fw_archive_<MMDD>_<sha>/` per build, never to
  a worktree's `logs/`; only those a conf or a cited run uses stay. `lab.conf`'s `FW_MLX` points
  there.
- A run on a tree with uncommitted changes gets its `git diff` in `patches/`, named after the run's
  log (skill `markdown-docs`, "Log entries"). The other directories — `reports/`, `drafts/`, the
  subdirectories of `logs/` — follow skill `markdown-docs`, "Task directory layout".
- A run that confirms or refutes a fix has its log copied to the task's `logs/` in the same step
  and cited in the defect's evidence in `Defects.md`; a run log the ledger alone cites lives in the
  worktree until the campaign ends.
- Deleting follows skill `markdown-docs`, "Files". A path cited only in `Ledger.md` does not keep a
  file: once a campaign's report is written, its logs that neither the report, `Defects.md` nor
  `Tracking.md` cites are deleted.

## 6. What not to create

The rules are skill `markdown-docs`, "Files". In a feature directory they mean in particular: no
separate workaround or review document next to `Defects.md`, and no second status page — §1 and §6
of `Tracking.md` already answer "where are we" and "how do I run it".

## 7. Moving an old document set to this one

1. Rename the old append-only ledger to `Ledger.md`, unchanged, with one line on top saying
   it is the old ledger. New entries continue its numbering and its heading format. Its sections
   that were pages — a status board, a todo list, a change table — get one line under their
   heading: stopped on `<date>`, the current state is in `Tracking.md`. The Run log table goes
   right below the old header, before its first section.
2. Write `Tracking.md` from the template, from the live state (gerrit, boxes) — not by trimming the
   old ledger.
3. Merge overlapping defect and review documents into `Defects.md`.
4. Delete every replaced file and every log the new documents do not cite; repoint references in the
   remaining documents.

## 8. Other long tasks and tickets inside a feature

- A long task that is not a feature (branch propagation, a multi-ticket campaign) starts with
  `Tracking.md` and `Ledger.md` from this skill's templates; `Defects.md`, reports and `tools/` are
  added once it has defects, test campaigns or lab runs. In `Tracking.md`, §1.1 holds one commit
  table per target branch, and what does not apply (the Gates row, §1.6) is left out.
- A bug ticket worked inside a feature runs skill `regression-repro` in its own directory, with its
  own worktrees off the `*2` clones and its own `Tracking.md`, `Ledger.md` and `Defects.md`. The
  feature's `Tracking.md` links the ticket's `Tracking.md` from its §3 row instead of copying the
  status, and lists the ticket's `Defects.md` in §7; its `Ledger.md` records only what changes the
  feature (the ticket opened, its fix landing).
