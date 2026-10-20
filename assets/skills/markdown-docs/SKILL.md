---
name: markdown-docs
description: >-
  How to write and keep every markdown document for Peter - which document set a piece of work
  gets and where it lives (a feature or long task, a bug ticket, crosslv tool work), the writing
  rules (language by reader, links, headings, code blocks, dates, plain speech) and the rules every
  set shares (one home per fact, logs appended with wrong conclusions struck through, pages
  corrected in place, what not to create, deleting unused files). Use before creating, editing or
  reviewing any .md for Peter: a Tracking.md, Ledger.md, Defects.md or test report, a ticket's
  Repro or Rc, a crosslv plans/ document, notes, code-flow write-ups.
---

# Markdown documents for Peter

Every `.md` written for Peter, in any folder and for any purpose, follows this skill. It holds what
all documents share: which set a piece of work gets, how each kind of document changes, and the
writing rules. What a set contains — its files, templates and sections, and which event updates
which file — stays with the skill that runs that kind of work.

## 1. Pick the document set before writing anything

| Work | Documents | Directory | Defined in |
|---|---|---|---|
| a feature | `Tracking.md`, `Ledger.md`, `Defects.md`, one `report_<MMDD>_<box>_<sha>.md` per test campaign | `/auto/fwgwork1/$USER/bugZilla/<feature>/` | skill `feature-delivery`, "Documents" |
| another task that runs for weeks (branch propagation, a multi-ticket campaign) | `Tracking.md` and `Ledger.md`; `Defects.md` or reports only once it has defects or test campaigns | `/auto/fwgwork1/$USER/bugZilla/<task>/` | skill `feature-delivery`, `references/documents.md` |
| a bug ticket: a Redmine bug, a CI or DoA failure | `Repro_<ticket#>.md`, `Rc_<ticket#>.md` | `/auto/fwgwork1/$USER/bugZilla/<ticket#>_<core>/` | skill `regression-repro`, `references/ticket-documents.md` |
| a ticket worked inside a feature | the ticket's own `Repro` and `Rc`; the feature's `Tracking.md` lists the `Rc` (§6) and keeps the ticket's status (§3) | both directories | both skills |
| crosslv tools and configuration (a Cursor extension, `jcl`, `agent-bridge`), however long it runs | one `plans/<topic>.md` | `~/myGit/crosslv/plans/` | section 6 below |
| anything else, or not sure | ask Peter before creating a file | | |

A set belongs to its kind of work: crosslv tool work never gets a Tracking / Ledger / Defects set.

## 2. Three kinds of document

Every file of every set is one of three kinds, and the kind decides how it changes.

| Kind | Files | How it changes | A conclusion that turns out wrong |
|---|---|---|---|
| page | `Tracking.md`, `Defects.md`, `Rc`, the plan at the top of `Repro`, `plans/<topic>.md` | edited in place; it always shows the present | corrected in place, so it states only the current conclusion. A superseded conclusion stays only where the set's skill gives it a place — `Rc` §4, one line in a `Defects.md` root cause, the wrong turns in a plans document's history — as one short item. Rejected fixes in `Defects.md` are content, each with its diff |
| log | `Ledger.md`; the Investigation log and the Run log of `Repro` | entries only appended, never rewritten; the one edit allowed is turning a link to a deleted file into backticks | struck through in place (`~~…~~`), followed by the correction, its date and the criterion to use next time; the struck line stays, or the same mistake is made again |
| record | `report_*.md`, `handoff_from_<who>.md` | written once, never edited | corrected on the page, or in a new report |

### Log entries

- One entry per event. Heading: the entry number and a short title saying what happened,
  `## 42. FW 6025 builds` (inside `Repro`, one level lower: `### 42. …`). It is what the reader
  picks from the table of contents. Numbers only grow; never renumber.
- First line under it: date and time, then the conclusion in one sentence:
  `2026-10-16 14:05 CST — …`.
- Peter's instruction verbatim, in quotes, when the entry starts from one.
- **Did**: commands; SHAs with their kind; build result (rc, `error:` count, elapsed, log path);
  changes and CI builds as links; MARS session id and archive path. **Result**: the outcome, its
  evidence, the control it was compared with. **Next**: one line.
- A table log (the Run log of `Repro`) gets one row per run; rows are only appended.

## 3. Rules every set shares

- **Every fact has one home**; other files link to it and never copy it. Copies drift apart.
- **Record in the same step as the event**; an unrecorded action counts as not done. Write from
  the log and the live systems, never from memory or a chat transcript — the transcript is gone
  next session.
- **At the start of a session** read the page and the last few log entries, not the whole log.
  At the end of a session, or when interrupted, the last log entry says what is in flight and what
  comes next.
- **No rules for agents in a page or record meant for people** (`Tracking.md`, `Defects.md`, `Rc`,
  reports): rules live in skills.
- **Archive before concluding.** CI consoles live one to two weeks, the regression failure DB about
  eight days: copy what you cite from them into the task's `logs/` first. MARS archives are kept
  for months, but the API that maps a session id to its archive forgets it in about two weeks —
  record the path.
- **Write identifiers in full and name their kind**: the local SHA before push, the patchset
  revision, the SHA on the branch after landing. They differ, and a bare hash later reads as "this
  commit does not exist".
- **Distrust the file**: patchset numbers, tips and states written in a document are snapshots;
  re-query the live system before acting, and correct the file when it differs.
- **Diagnosis and disposition are separate**: diagnosing is the agent's job; committing, pushing,
  changing a box or sending a message waits for an order. A proposal is written down as a proposal
  — in a feature, a row of `Tracking.md` §1.5 — not carried out.

## 4. Files: what not to create, what to delete

- **No separate onboarding, handoff or environment-setup document**: the page already answers
  "where are we" and "how do I run it". A frozen handoff received from someone else may be kept as
  `handoff_from_<who>.md`.
- **No second document for content a file of the set owns**, and no ad-hoc names beside the set in
  a task directory (`ROOTCAUSE*`, `ANALYSIS_*`, `README`, `INDEX_*`, `*_STATUS`); each set's skill
  names the ones met there.
- **No `.bak` copies and no `archive_*` directories**: a replaced file is deleted, not kept.
- An outgoing message to people — mail, chat — is `msg_<who>_draft.txt` until it is sent, then
  deleted. A Redmine description or comment is drafted as skill
  `utopx-regression-ticket` says. Optional when the work needs one: `code_flow.md`, how the code
  works, with links to the source lines.
- **Delete what nothing uses, promptly**: logs no document cites (for a test campaign, once its
  report is written), scratch images, build logs, `.bak` copies, replaced documents and scripts.
  The set's skill says which citations keep a file. Before deleting, grep the remaining documents
  and `tools/` for the file name, and wait for a process still writing a file to stop. A worktree
  is deleted only when Peter agrees.
- **Moving an old set to a new one**: rename the files, repoint every link to the old names
  (`grep -rl '<old name>' <directories>`), fold stray files into the set, delete what was replaced.
  The set's skill has the specific steps.

## 5. Writing rules

### Language and wording

- **Language, by reader**: documents for Peter — `Tracking.md`, `Ledger.md`, `Defects.md`, a
  ticket's `Repro`, reports, `plans/*.md`, notes — in his working language, Chinese; documents that
  leave the team — a ticket's `Rc`, Redmine notes — in plain English. The templates are written in
  English; fill them in the document's language. Identifiers, log lines and error signatures are
  never translated.
- **Plain speech**: short sentences, no rhetoric. Explain a mechanism by what it is before what it
  does.
- **Failures** are described by where they stopped (the function and the source line), never with
  words like "dead" or "killed".
- **Dates** are absolute (`10-16`, `2026-10-16 14:05 CST`). Another session is written as
  `name (id prefix)` — names change, ids do not.

### Links

- **External resources** — gerrit change, Redmine ticket or FR, Jenkins build, MARS session,
  Confluence or SharePoint page — are markdown links whose label is the short name and whose
  target is the full URL. Never show the URL itself, and never use a URL as its own label.
  - Gerrit change `[1459033](https://git-nbu.nvidia.com/r/c/fw_ver/utopx/+/1459033)`; one patchset
    `[1519292 PS4](https://git-nbu.nvidia.com/r/c/golan_fw/+/1519292/4)`.
  - Redmine `[5298707](https://redmine.nvidia.com/issues/5298707)`, a Feature Request
    `[FR #4838395](https://redmine.nvidia.com/issues/4838395)`.
  - Jenkins `[utopx_ci #25763](https://nbuprod.blsm.nvidia.com/nbu-hca-fw-jenkins/job/utopx_ci/25763/)`;
    a page by its title, `[FWV uArch](https://nvidia.atlassian.net/wiki/spaces/FW/pages/3491039456)`.
  - MARS session `[session 11648317](https://mars.nvidia.com/ui/view/monitor/Amonitor.php?session_id=11648317)`;
    the log of one failing case: the `view_log` URL that skill `utopx-regression-ticket`, "Building
    the MARS link", builds.
  - **Every mention** of a change or ticket number is linked, in running text and in table cells
    alike — not only the first one, and not only its row in a commit table. A number inside a code
    span or a code block stays plain.
- **Local files the reader opens** — another document, a report or a run log cited as evidence (in
  text, tables and evidence lines alike), a file under `tools/` — depend on where the document is
  read:
  - Read on this machine, which is every document except the next case: relative links labelled
    with the file name — a file under `tools/` with that prefix — `[Defects.md](Defects.md)`,
    `[tools/env_rebuild.sh](tools/env_rebuild.sh)`,
    `[psf_seed902270181_1010_140805.log](logs/psf_seed902270181_1010_140805.log)`, so one click
    opens them. A page or a record cites the copy of a log in the task's own `logs/`, which
    outlives the worktree; a log entry may link a run's log where it lies.
  - Read elsewhere — a ticket's `Rc`, which goes to Redmine (attached, and as the source of the
    root-cause comment): the path in backticks, because relative links break there.
- **Source lines** — of code, or of a log — are links too, labelled with the file's base name and
  the line, so a click opens the file at that line. A range `<file>:<a>-<b>` links its first line;
  a further line of the same file may be labelled `:<line>` alone.
  - In a tree on this machine: the relative path with `#L<line>`,
    `[VHCA.cpp:3264](../../utopx-psf/src/hca/VHCA.cpp#L3264)`,
    `[psf_seed902270181_1010_154323.log:6960](logs/psf_seed902270181_1010_154323.log#L6960)`.
  - A line of a gerrit patchset, such as the line a review comment is on: gerrit's file view, with
    `#<line>` and no `L`,
    `[UtopxRandomTest.cpp:5720](https://git-nbu.nvidia.com/r/c/fw_ver/utopx/+/1530478/1/src/utopx_infra/UtopxRandomTest.cpp#5720)`.
  - In a ticket's `Rc`, only the gerrit form; any other source line stays in backticks.
- **Every link target must exist.** When a cited file is deleted, its links become backticks, in
  old log entries too.
- **Redmine descriptions and comments** are HTML, not markdown, with rules of their own: skill
  `utopx-regression-ticket`.
- **Paths to type or copy** (a command argument, a path on a lab box) stay in bare backticks.
- **Plain-text files** (`.txt`, such as a performance ticket's `Rc_<ticket#>.txt`): bare URLs, the
  only clickable form there.
- **A Confluence page source** (markdown carrying HTML and a `<!-- confluence-url: … -->` comment)
  keeps its HTML tags, attributes and comments untouched; only visible URLs get labels. A blanket
  URL rewrite breaks the HTML and the publishing tool's page id.
- **No inline HTML styling** such as `<span style="color:…">`: the viewer strips it.

### Structure

- **Headings are short titles that say what the section holds**: they become the table of
  contents, where the reader picks a section to jump to, so a title must tell them which one to
  pick in a few words. Owners, repositories, branches, timestamps, syndromes, status marks and
  ordering notes ("newest first") go in the first line under the heading, never in the heading; no
  links, code spans or emoji in headings.
- **A `§` reference into another file names the file**: `Ledger.md` §42, not "§42".
- **Code fences** carry a language: `text` for log lines, `diff` for patches, `cpp` / `c` for
  quoted source, `bash` for commands. Peter reads in VS Code's built-in Markdown preview with the
  `md-preview-plus` extension (`crosslv/assets/cursor/md-preview-plus/`), which colours `diff`
  lines the way the editor does.
- **A code block is never inside a list item**: Cursor's built-in markdown view drops the whole
  section that holds one, and every section after it. Put the block at top level, introduced by a
  bold lead line.

### Checks before handing a document over

- no `http` outside a link target (plain-text files excepted), and every 7-digit number outside
  code and headings is a link;
- every relative link target exists;
- every source line outside `Rc` is a link (in a log, in the new entries):
  `grep -nP '(?<!\[)\x60[\w./+-]+\.(?:[ch]|cc|[ch]pp|py|sh|js|adb|log|conf|md):\d+(?:-\d+)?\x60' <file>`
  prints nothing;
- no fence indented under a list item: `grep -nP '^\s+\x60{3}' <file>` prints nothing;
- no link, code span or emoji in a heading.

## 6. A crosslv plans document

One file per topic, `plans/<topic>.md`, such as `plans/md-preview-plus.md`. It is both the design
record and the handover for the next agent. It is a page — corrected in place — with no separate
log, defect list or tracking page beside it; options rejected go into the section on why it is
built this way, wrong turns into the history. The history is its record, written in the same step
as the event; when work stops half-way, the state in the summary table says what is in flight and
what comes next. It is written for the next agent as well as for Peter, so rules for changing the
code belong in it. The tool's own code directory may keep a README for its users (what it does,
how to install it) that links here for the rest.

1. Title `<name>: <what it is>`, then one paragraph: what it is for and where Peter uses it.
2. A summary table: the current state with its date, the versions installed, where the code is
   (relative links), the commits (linked).
3. Sections by topic, as the work needs: terms; why it is built this way, with the options
   rejected; what it does and how; each problem met, with its root cause; install, upgrade and
   reinstall; how to check it is working; how to test it (commands); rules for changing the code.
4. Last, the history: key steps only, and the wrong turns with what each one taught.
