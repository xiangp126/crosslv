# The feature's documents — what each file holds, and when it changes

`SKILL.md` "Documents" gives the file set, the copy commands and the event table. This file is the
detail behind them. One rule decides everything below: **every fact has exactly one home**; other
files link to it and never copy it. Copies drift — the same defect list kept in seven files ended
with three different merge dates and a review document that still said "nothing pushed" after the
push.

## 1. `Tracking.md` — the feature's status page (for people)

Readers: Peter, the owners, the reviewers. It answers "where is this feature, what is it waiting
for, what changed". It is a **current-state** page: edit it in place, keep it short (one or two
screens before §2), put the most important content first. It holds no rules for agents, no
step-by-step record and no history of SHAs.

| Section | Holds | Rules |
|---|---|---|
| header | name, Last updated, owners, 2-4 sentences on what the feature is | Last updated changes with every edit |
| §1 one-sentence verdict + status table | one row per part (test tool, FW, gates, device verification, requirements) | the verdict is the first thing a reader sees; rewrite it whenever the situation changes |
| §1.1 / §1.2 commits | per repository: not merged, then merged | **owners only** — the feature's owners on each side, current and former; other people's commits in the same area are not this feature's. "Not merged" is the owner's current plan (their own list, a message, the stack they are assembling), not every open change in gerrit: stale and abandoned changes are left out. Merged dates come from the gerrit submit approval (`gerrit query --all-approvals`, type `SUBM`), not from commit dates. Every change is its number linked to its gerrit URL (§6 Links) |
| §1.2 tail | the FW image under test | base SHA and version + which changes and patchsets + image path and md5 |
| §1.3 waiting for | one line per person or team | name who, what, since when, and where the draft or message is |
| §1.4 next steps | short list | |
| §1.5 decisions for Peter | question + background | a decision taken moves out of this table; the ledger keeps the record |
| §1.6 requirements | one row per Req of the Feature Request | the "Verified?" column is only ✅ when an assertion that can fail exists and a run passed it |
| §2 test campaigns | one row per campaign, newest first | links the frozen report |
| §3 defects | one row per defect: one-line problem, side, **status** | the only place a defect's status lives |
| §4 timeline | one line per day, newest first | what changed for the feature, not what the agent did |
| §5 environment and how to run | boxes, FW/INI/NV, code paths, the two commands | the procedure that executes is `tools/`; this section only points to it |
| §6 documents | one row per local file, its relative link `[name](path)` in the left column (files under `tools/` too, as `tools/<file>`); external links as bare URLs | one click opens each file; the links line up |

Status marks, one meaning each: ✅ done · 🟡 partial or worked around · 🔵 in progress or waiting ·
🔴 blocked · ⬜ not started or not hit.

## 2. `Ledger.md` — the step-by-step record (for whoever continues)

Append-only, in time order, never rewritten. One entry per event: the heading is the entry number
and a short title naming what happened (it is what the reader picks from the table of contents);
the first line under it holds the date and time and the one-sentence conclusion; then Peter's
instruction verbatim when the entry starts from one. A
conclusion that turns out wrong is struck through in place, followed by the correction, its date
and the criterion to use next time — the struck line stays, or the same mistake is re-derived.
Entry numbers only grow; never renumber.

What each event records here, next to what it changes in `Tracking.md`: the event table in
`SKILL.md`, "Documents".

At the start of a session read `Tracking.md` §1 and the last few ledger entries, not the whole ledger; at
the end, or when interrupted, the last entry says what is in flight and what comes next.

Two companions:
- **Archive before concluding.** CI consoles live one to two weeks, the regression failure DB about
  eight days. Copy what you cite into the task's `logs/` first. MARS archives are kept for months,
  but the API that maps a session id to the archive forgets it in about two weeks — record the path.
- **Write identifiers in full and name their kind**: the local SHA before push, the patchset revision,
  the SHA on the branch after landing. They differ, and a bare hash later reads as "this commit does
  not exist".

## 3. `Defects.md` — defects and fixes (for owners and reviewers)

One section per defect, in the order a run from the starting baseline hits them; §0 is that
reproduction ladder (step, code under test, parameters, which defect, where it stops). Each section
holds: side, fix (linked change number), how to hit it, what happens (verbatim, in a `text` block), root cause
(`file:line`), the final diff, why it works and what it deliberately leaves out, rejected
alternatives with their diffs, the evidence (runs before and after, the control), open questions.

- **No status in this file** — it lives in `Tracking.md` §3.
- **Reviewer-safe from day 1**: no reviewer names, no internal process (who asked what, session
  names, the order in which the agent tried things). Owners appear only on the side line.
- Fixes found while testing someone else's change start as `[Local-Only]` commits; their section here
  is the review material for the fix commit when Peter decides to push it.
- A defect that stops appearing moves to "Defects no longer seen", with what removed it.
- A superseded root cause stays only when it helps the reader, as one line: "first thought …; it
  turned out …".
- Failures that are not this feature's (the same failure exists in the regression DB on boxes
  without it) go to "Pre-existing issues met", with the regression-DB hit.

## 4. `report_<MMDD>_<box>_<sha>.md` — one test campaign (for people)

Written when a campaign ends and not edited afterwards. Conclusion first (n of m, attribution of
every failure, what the new path did, what it proves and what it does not), then the setup with
identities (FW image md5, test-tool tree and binary md5), one row per run with the feature's
fingerprints as columns, the failures with verbatim lines and attribution, what was not covered,
environment problems. Every run and every failure gets a row; nothing is summarised away.

## 5. `tools/` and `logs/`

- `tools/` is skill `regression-repro`'s `templates/lab-box/` with `MODE=feature`: fill `lab.conf`
  only; change a script only when no hook can express the need, and record why in the ledger. A
  control or a second box gets its own small conf that sources `lab.conf`.
- Run logs stay in the tested worktree's `logs/`; logs a document cites are copied to the task's
  `logs/`, so deleting a worktree never deletes evidence.
- **Delete what nothing uses, promptly** — not into an archive: a test log that neither a report,
  `Defects.md` nor `Tracking.md` cites (once the campaign's report is written), scratch images, build
  logs, `.bak` copies, replaced documents and scripts. A path cited only in `Ledger.md` does not
  keep a file. A worktree itself is deleted only when Peter agrees.

## 6. Writing rules for every file

These rules hold for every markdown file written for Peter, in any folder and for any purpose —
this document set, a ticket's `Repro` and `Rc` (skill `regression-repro`,
`references/ticket-documents.md`), reports, notes, code-flow write-ups. The global instructions
(`CLAUDE.md`, `AGENTS.md`) point here.

- **Language**, by reader: documents for Peter — `Tracking.md`, `Ledger.md`, a ticket's
  `Repro`, reports to him — in his working language, Chinese; documents that leave the team — a
  ticket's `Rc`, Redmine notes — in plain English. Identifiers, log lines and error
  signatures are never translated.
- **Plain speech**: short sentences, no rhetoric. Explain a mechanism by what it is before what it
  does.
- **Failures** are described by where they stopped (`<function>`, `file:line`), never with words
  like "dead" or "killed".
- **Links**: every external resource (gerrit change, Redmine ticket or FR, Jenkins build, MARS
  session, Confluence or SharePoint page) is a markdown link whose label is its short name and whose
  target is the full URL. Never show the URL itself, and never use a URL as its own label.
  - Gerrit change `[1459033](https://git-nbu.nvidia.com/r/c/fw_ver/utopx/+/1459033)`; one patchset
    `[1519292 PS4](https://git-nbu.nvidia.com/r/c/golan_fw/+/1519292/4)`.
  - Redmine `[5298707](https://redmine.nvidia.com/issues/5298707)`, a Feature Request
    `[FR #4838395](https://redmine.nvidia.com/issues/4838395)`.
  - Jenkins `[utopx_ci #25763](https://nbuprod.blsm.nvidia.com/nbu-hca-fw-jenkins/job/utopx_ci/25763/)`;
    a page by its title, `[FWV uArch](https://nvidia.atlassian.net/wiki/spaces/FW/pages/3491039456)`.
  - **Every mention** of a change or ticket number is linked, in running text and in table cells
    alike — not only its first one, and not only its row in the commit table — so any number the
    reader sees opens with one click. A number inside a code span or a code block stays plain.
  - Check: no `http` outside a link target, and every 7-digit number outside code is a link.
  - A Confluence page source (markdown carrying HTML and a `<!-- confluence-url: … -->` comment)
    keeps its HTML tags, attributes and comments untouched; only visible URLs get labels. A blanket
    URL rewrite breaks the HTML and the publishing tool's page id.
- **Local files the reader opens** — the §6 document table, another document of the set, a report
  or a run log cited as evidence (in text, tables and evidence lines alike, also logs under a
  worktree's `logs/`), each file under `tools/` — are relative markdown links labelled with the file
  name, `[Defects.md](Defects.md)`, `[env_rebuild.sh](tools/env_rebuild.sh)`,
  `[psf_seed902270181_1010_140805.log](../../utopx-psf/logs/psf_seed902270181_1010_140805.log)`, so
  one click opens them. Check that every target exists; a cited file that is gone stays in
  backticks. A path given to type or copy (a command argument, a path on a lab box) and a source
  location (`file:line`) stay in bare backticks. No inline HTML styling such as `<span style="color:…">`: the viewer strips it.
- **Headings are short titles that say what the section holds**: they become the table of
  contents, where the reader picks a section to jump to, so a title must tell them which one to
  pick in a few words. Owners, repositories, branches, timestamps, syndromes, status marks and
  ordering notes ("newest first") go in the first line under the heading, never in the heading;
  no links, code spans or emoji in headings.
- **Code fences**: `text` for log lines, `diff` for patches, `cpp` / `c` for quoted source, `bash`
  for commands. Peter reads in VS Code's built-in Markdown preview with the `md-preview-plus`
  extension (`crosslv/assets/cursor/md-preview-plus/`), which colours `diff` lines the way the
  editor does (added light green, removed orange, no row background).
- **A code block is never inside a list item.** Cursor's built-in markdown view drops the whole
  section that holds one, and every section after it. Put the block at top level, introduced by a
  bold lead line.
- **Dates** absolute (`10-16`, `2026-10-16 14:05 CST`); another session is written as
  `name (id prefix)` — names change, ids do not.
- **A `§` reference into another file names the file**: `Ledger.md` §42, not "§42".
- **Distrust the file**: patchset numbers, tips and states written here are snapshots; re-query the
  live system before acting, and correct the file when it differs.
- **Diagnosis and disposition are separate**: diagnosing is the agent's job; committing, pushing,
  changing a box or sending a message waits for an order. A proposal goes into §1.5 of
  `Tracking.md`, not into action.

## 7. What not to create

- Onboarding, handoff or environment-setup documents: §1 and §5 of `Tracking.md` already answer
  "where are we" and "how do I run it". A frozen handoff received from someone else may be kept as
  `handoff_from_<who>.md`.
- A second document for content one of the files above owns (a separate workaround or review
  document next to `Defects.md`; a second status page).
- `.bak` copies or `archive_*` directories: a replaced file is deleted, not kept. FW images go to the
  worktree's `logs/`, and only the one under test stays.
- Optional when the feature needs one: `code_flow.md` (how the code works, with `file:line`) and
  `msg_<who>_draft.txt` (an outgoing message until it is sent).

## 8. Moving an old document set to this one

1. Rename the old append-only ledger to `Ledger.md`, unchanged, with one line on top saying
   it is the old ledger.
2. Write `Tracking.md` from the template, from the live state (gerrit, boxes) — not by trimming the
   old ledger.
3. Merge overlapping defect and review documents into `Defects.md`.
4. Delete every replaced file and every log the new documents do not cite; repoint references in the
   remaining documents.

## 9. Other long tasks and tickets inside a feature

- A long task that is not a feature (branch propagation, a multi-ticket campaign) uses the same
  `Tracking.md` template: §1.1 / §1.2 become one commit table per target branch.
- A bug ticket worked inside a feature runs skill `regression-repro` and keeps its own
  `Rc_<ticket>.md`; list it in §6 of the feature's `Tracking.md`.
