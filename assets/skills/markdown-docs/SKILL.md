---
name: markdown-docs
description: >-
  How to write and keep every markdown document for Peter - which document set a piece of work
  gets and where it lives (a feature or long task, a bug ticket, crosslv tool work), the writing
  rules (language by reader, links, headings, code blocks, dates, plain speech) and the rules every
  set shares (one home per fact, logs appended with wrong conclusions struck through, pages
  corrected in place, what not to create, deleting unused files). Use before creating, editing or
  reviewing any .md for Peter: a Tracking.md, Ledger.md, Defects.md or test report of a feature, a
  long task or a bug ticket, a crosslv plans/ document, notes, code-flow write-ups.
---

# Markdown documents for Peter

Every `.md` written for Peter, in any folder and for any purpose, follows this skill. It holds what
all documents share: which set a piece of work gets, how each kind of document changes, and the
writing rules. What a set contains — its files, templates and sections, and which event updates
which file — stays with the skill that runs that kind of work.

## 1. Pick the document set before writing anything

| Work | Documents | Directory | Defined in |
|---|---|---|---|
| a feature | `Tracking.md`, `Ledger.md`, `Defects.md`, one `reports/report_<MMDD>_<box>_<sha>.md` per test campaign | `/auto/fwgwork1/$USER/bugZilla/<feature>/` | skill `feature-delivery`, "Documents" |
| another task that runs for weeks (branch propagation, a multi-ticket campaign) | `Tracking.md` and `Ledger.md`; `Defects.md` or reports only once it has defects or test campaigns | `/auto/fwgwork1/$USER/bugZilla/<task>/` | skill `feature-delivery`, `references/documents.md` |
| a bug ticket: a Redmine bug, a CI or DoA failure | `Tracking.md`, `Ledger.md`, `Defects.md`, one `reports/report_<MMDD>_<box>_<sha>.md` per test campaign; what goes to Redmine, in English, under `redmine/` | `/auto/fwgwork1/$USER/bugZilla/<ticket#>_<core>/` | skill `regression-repro`, `references/ticket-documents.md` |
| a ticket worked inside a feature | the ticket's own set in its own directory; the feature's `Tracking.md` links the ticket's `Tracking.md` from its §3 row instead of copying the status, and lists the ticket's `Defects.md` in §7 | both directories | both skills |
| crosslv tools and configuration (a Cursor extension, `jcl`, `agent-bridge`), however long it runs | one `plans/<topic>.md` | `~/myGit/crosslv/plans/` | section 6 below |
| anything else, or not sure | ask Peter before creating a file | | |

The three names mean the same in every set: `Tracking.md` is the status page, `Ledger.md` the log,
`Defects.md` the defects with their root causes and fixes. The table of documents in `Tracking.md`
lists `Defects.md` and `Ledger.md` first. The sections inside them differ by kind
of work and are set by the skill that runs it. A set belongs to its kind of work: crosslv tool work
never gets a Tracking / Ledger / Defects set.

### Task directory layout

Every task directory — a feature, a long task, a ticket — keeps its files by kind:

| Directory | Holds |
|---|---|
| top level | the set's documents (`Tracking.md`, `Ledger.md`, `Defects.md`), text received from someone else (`<kind>_from_<who>.md`), an optional `code_flow.md` |
| `reports/` | `report_<MMDD>_<box>_<sha>.md`, one per test campaign |
| `drafts/` | outgoing text until it is sent, `<what>_<to whom>_draft.txt` (section 4) |
| `patches/` | the `git diff` of a tree with uncommitted changes that a run used (section 2, "Log entries"); a ticket's fix, `FIX_<topic>.patch`, and its disproved candidates, `REJECTED_<vN>_<why>.patch` |
| `fw/` | FW images a run burns, one `fw_archive_<MMDD>_<sha>/` per build — here, not in a worktree, which may be deleted |
| `logs/` | run logs at its top; `env_rebuild/` (environment setup), `ci/` (CI consoles), `fwtrace/`, `lock/` (`noga_watchdog.sh` output), `build/` |
| `tools/`, `ini/` | the lab scripts and their configuration; INI files — a feature's own INI; a ticket's INI the regression burned, the release default and their diff |
| `redmine/`, `attach/` | a ticket only: what goes to Redmine; the MARS artifacts uploaded to the ticket, with `manifest.tsv` |

The set's skill creates them on day 0; a command or script that writes into one runs `mkdir -p` on
it first.

## 2. Three kinds of document

Every file of every set is one of three kinds, and the kind decides how it changes.

| Kind | Files | How it changes | A conclusion that turns out wrong |
|---|---|---|---|
| page | `Tracking.md`, `Defects.md`, `plans/<topic>.md` | edited in place; it always shows the present | corrected in place, so it states only the current conclusion. A superseded conclusion stays only where the set's skill gives it a place — the rejected hypotheses of a ticket's `Defects.md`, one line in a feature defect's root cause, the wrong turns in a plans document's history — as one short item. Rejected fixes in `Defects.md` are content, each with its diff |
| log | `Ledger.md`: its Run log table and its entries | rows and entries only appended, never rewritten; the only edits allowed are to links, with the wording untouched: a link follows its target when the target is renamed, moved or renumbered, and becomes backticks when the target is deleted | struck through in place (`~~…~~`), followed by the correction, its date and the criterion to use next time; the struck line stays, or the same mistake is made again |
| record | `reports/report_*.md`; text received from someone else, `<kind>_from_<who>.md`; what was posted to Redmine (a ticket's `redmine/`) | written once, never edited | corrected on the page, or in a new report or a new upload (`_v2`) |

### Log entries

- One entry per event, appended at the end of the file. Heading: the entry number and a short
  title saying what happened, `## 42. FW 6025 builds`. It is what the reader picks from the table
  of contents. Numbers only grow; never renumber.
- First line under it: date and time, then the conclusion in one sentence:
  `2026-10-16 14:05 CST — …`.
- Peter's instruction verbatim, in quotes, when the entry starts from one.
- **Did**: commands; SHAs with their kind; build result (rc, `error:` count, elapsed, log path);
  changes and CI builds as links; MARS session id and archive path. **Result**: the outcome, its
  evidence, the control it was compared with. **Next**: one line.
- **Run log**: a table at the top of `Ledger.md`, under its header, one row per run — box, FW,
  test-tool tree or pin (with its patch link when the tree had uncommitted changes), seed, outcome,
  the log as a link — appended before the next run starts. The first cell of a row is its number
  with an anchor, `<a id="run-12"></a>12`, so a row can be linked. An entry about runs says why
  they ran and what they showed, and names the rows as links instead of repeating them:
  `[Run log #12–#14](#run-12)`; from another file `[Ledger.md Run log #12](Ledger.md#run-12)`.
- **A run on a tree with uncommitted changes**: save the `git diff` taken right before the build
  as `patches/<run log stamp>.diff`, so the patch and the run's log share a name, and link it from
  the Run log row and the entry. Where the entry names a changed line, link that line in the patch
  (`#L<n>`), not the worktree, which changes later. Paste the diff into the entry in a `diff` fence
  only when it is small; a large one is linked, not pasted.
- **Not in a log**: long material — a handoff, a review thread, someone else's analysis, a Redmine
  draft — is saved as its own file (`<kind>_from_<who>.md`, or the ticket's `redmine/`), and the
  entry gives what in it matters, in a line, with the link. Events that do not change the work — a
  box lease ticking over, documents moved or renamed — get one line at most.

## 3. Rules every set shares

- **Every fact has one home**; other files link to it and never copy it. Copies drift apart.
- **Record in the same step as the event**; an unrecorded action counts as not done. Write from
  the log and the live systems, never from memory or a chat transcript — the transcript is gone
  next session.
- **At the start of a session** read the page and the last few log entries, not the whole log.
  At the end of a session, or when interrupted, the last log entry says what is in flight and what
  comes next.
- **Several sessions may write the same file.** Re-read the end of a log right before appending,
  and take the entry or row number at that moment. Change a file with local edits anchored on its
  current text; never rewrite a whole file another session may be writing.
- **A status is kept in one place**: a change's in its row of the commit table, a defect's in its
  row of `Tracking.md`'s defect table, a bug ticket's in its own `Tracking.md` §1, a Redmine
  ticket a feature opened or depends on in the feature's `Tracking.md` §1.5. Other sections say what
  is to be done and point to that row; they do not restate the state.
- **Copy the evidence when a run decides something.** A run that confirms or refutes a fix or a
  root cause: copy its log into the task's `logs/` in the same step and cite it from `Defects.md`.
  A log cited only in `Ledger.md` is not kept (section 4).
- **No rules for agents in `Tracking.md`, `Defects.md` or a report**: rules live in skills.
- **Archive before concluding.** CI consoles live one to two weeks, the regression failure DB about
  eight days: copy what you cite from them into the task's `logs/ci/` first. MARS archives are kept
  for months, but the API that maps a session id to its archive forgets it in about two weeks —
  record the path.
- **Write identifiers in full and name their kind**: the local SHA before push, the patchset
  revision, the SHA on the branch after landing. They differ, and a bare hash later reads as "this
  commit does not exist".
- **Distrust the file**: patchset numbers, tips and states written in a document are snapshots;
  re-query the live system before acting, and correct the file when it differs.
- **Diagnosis and disposition are separate**: diagnosing is the agent's job; committing, pushing,
  changing a box or sending a message waits for an order. A proposal is written down as a proposal
  — an item of "Decisions needed from Peter" in `Tracking.md` — not carried out.

## 4. Files: what not to create, what to delete

- **No separate onboarding, handoff or environment-setup document**: the page already answers
  "where are we" and "how do I run it". Text received from someone else — a handoff, a review, an
  analysis — may be kept as written, named `<kind>_from_<who>.md` (`handoff_from_wenda_0915.md`).
- **No second document for content a file of the set owns**, and no ad-hoc names beside the set in
  a task directory (`ROOTCAUSE*` outside a ticket's `redmine/`, `ANALYSIS_*`, `README`, `INDEX_*`,
  `*_STATUS`); each set's skill names the ones met there.
- **No `.bak` copies and no `archive_*` directories**: a replaced file is deleted, not kept.
- Outgoing text — mail, chat, a gerrit reply, a channel post — is drafted in `drafts/` as
  `<what>_<to whom>_draft.txt` (`fw_questions_to_shuaijie_draft.txt`,
  `gerrit_1530478_ps1_replies_draft.txt`) until it is sent, then deleted. Redmine descriptions and
  comments are drafted under the ticket's `redmine/`, as skill `utopx-regression-ticket` says.
  Optional when the work needs one: `code_flow.md`, how the code works, with links to the source
  lines.
- **Delete what nothing uses, promptly**: scratch images, build logs, `.bak` copies, replaced
  documents and scripts, and logs that no page or record cites once the work they belong to is
  concluded — a test campaign when its report is written, a ticket's runs when its fix is
  verified. A citation in `Ledger.md` alone does not keep a file. Before deleting, grep the
  remaining documents and `tools/` for the file name, and wait for a process still writing a file
  to stop. A worktree is deleted only when Peter agrees.
- **Moving an old set to a new one**: rename the files, repoint every link to the old names
  (`grep -rl '<old name>' <directories>`), fold stray files into the set, delete what was replaced.
  The set's skill has the specific steps.

## 5. Writing rules

### Language and wording

- **Language, by reader**: documents for Peter — `Tracking.md`, `Ledger.md`, `Defects.md`,
  reports, `plans/*.md`, notes — in his working language, Chinese; text that leaves the team —
  what a ticket's `redmine/` holds, Redmine notes — in plain English. The templates are written in
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
  - Read elsewhere — the English copies in a ticket's `redmine/`, which go to Redmine: the path in
    backticks, because relative links break there.
- **Source lines** — of code, or of a log — are links too, labelled with the file's base name and
  the line, so a click opens the file at that line. A range `<file>:<a>-<b>` links its lines,
  `#L<a>-L<b>`; a further line of the same file may be labelled `:<line>` alone.
  - **Code links the local worktree, never gerrit or gitiles**, pinned to the commit its line
    number belongs to: the relative path, `?v=<commit>` (10 hex digits), `#L<line>`,
    `[VHCA.cpp:5149](../../utopx-psf/src/hca/VHCA.cpp?v=6faa4de858#L5149)`. md-preview-plus opens
    the worktree file at the line where that code is now, however the worktree has moved or been
    edited since; when that line itself has been changed or deleted, it opens the file as of the
    commit, read-only. The commit is the one the text is about: the tree's HEAD when the line was
    read, a patchset's revision (`git -C <tree> ls-remote origin refs/changes/<NN>/<change>/<ps>`),
    a release tag's commit. It must exist in the local repository: fetch a patchset or a tag with
    `git -C <tree> fetch origin <ref>` and no destination, which changes only that worktree's
    `FETCH_HEAD` and the object store. It must also stay there: `git gc` deletes a commit that no
    ref holds within weeks, and the link then falls back to the line number in the file as it is
    now. So every commit a link pins gets a ref outside branches and tags, in the same step,
    `git -C <tree> update-ref refs/keep/<task>/<10-digit SHA> <commit> ""`; it changes no branch
    or worktree, and keeps only the files that commit changed, a few MiB. A line of an
    uncommitted edit links the run's saved diff in `patches/` (section 2, "Log entries").
  - Logs: the relative path with `#L<line>`,
    `[psf_seed902270181_1010_154323.log:6960](logs/psf_seed902270181_1010_154323.log#L6960)`; a log
    does not change, so it needs no commit.
  - In a copy that goes to Redmine, where a local path means nothing: gerrit's file view of a
    patchset (`…/+/<change>/<ps>/<path>#<line>`, no `L`) or gitiles at a commit or tag (a SHA in
    full); a line no server has stays in backticks, `<file>:<line>` and its short SHA.
- **Every link target must exist.** When a cited file is deleted, its links become backticks, in
  old log entries too.
- **Redmine descriptions and comments** are HTML, not markdown, with rules of their own: skill
  `utopx-regression-ticket`.
- **Paths to type or copy** (a command argument, a path on a lab box) stay in bare backticks.
- **Plain-text files** (`.txt`, such as a `*_draft.txt`): bare URLs, the only clickable form
  there.
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
- **A `§` reference into another file is a link to that section's heading**, labelled with the file
  and the section: `[Ledger.md §42](Ledger.md#42-fw-6025-builds)`, not `[Ledger.md](Ledger.md) §42`,
  which opens the file at the top. A range links its first section,
  `[Ledger.md §40–§42](Ledger.md#40-…)`; each further item of a list gets its own link,
  `[§45](Ledger.md#45-…)`. The part after `#` is the id the preview gives the heading: its text
  lowercased, each run of whitespace turned into `-`, ASCII and full-width punctuation dropped,
  everything else kept, Chinese included; a later heading with the same text gets `-1`, `-2`. A log
  entry's heading never changes, so links to it hold; when a page's heading is renamed or its
  sections are renumbered, every link to them and every plain mention (`Tracking §1.5`) in every
  file of the set is corrected in the same step — in a log entry too, label and anchor only. A
  reference inside the same file may link the same way,
  `[§42](#42-fw-6025-builds)`.
- **A page's header carries `Last updated: <YYYY-MM-DD HH:MM CST>`**, changed with every edit. A
  log or a record carries none: its entries and its header date say when.
- **Code fences** carry a language: `text` for log lines, `diff` for patches, `cpp` / `c` for
  quoted source, `bash` for commands. Peter reads in VS Code's built-in Markdown preview with the
  `md-preview-plus` extension (`crosslv/assets/cursor/md-preview-plus/`), which colours `diff`
  lines the way the editor does.
- **A code block is never inside a list item**: Cursor's built-in markdown view drops the whole
  section that holds one, and every section after it. Put the block at top level, introduced by a
  bold lead line.

### Run steps

The steps that rebuild a box and run the test on it — a ticket's `Tracking.md` §4, a feature's
`Tracking.md` §6 — are written so that copying the commands one by one, top to bottom, does the
job:

- Every command is complete as it stands: absolute paths, the box and the user written out, no
  shell variable carried from one step to the next, no "same as step <n>" — a step done twice is
  written out twice. Logs go to the task's `logs/` by absolute path.
- Each step says where it runs and what output to expect, as a line from a real run, verbatim.
- Every command is the one actually run, taken from the scripts and the logs, not written from
  memory.
- Credentials stay in their files: a step that needs them calls the script that holds them.
- The manual steps come first; the same steps with the scripts close the section — the rebuild
  script and the per-run script (`env_rebuild.sh` and `per_run.sh` of skill `regression-repro`'s
  `templates/lab-box/`, or the task's own), each invocation copyable as it stands, which manual
  steps it covers, the lines and exit codes it prints.
- When a command changes — another box, image or tree, a step that needs a wait — the steps are
  corrected in the same step.

### Checks before handing a document over

- no `http` outside a link target (plain-text files excepted), and every 7-digit number outside
  code and headings is a link;
- every relative link target exists;
- every source line is a link (in a log, in the new entries; not in a copy that goes to
  Redmine):
  `grep -nP '(?<!\[)\x60[\w./+-]+\.(?:[ch]|cc|[ch]pp|py|sh|js|adb|log|conf|md):\d+(?:-\d+)?\x60' <file>`
  prints nothing;
- every code link carries `?v=<commit>`, a ref holds the commit
  (`git -C <tree> for-each-ref --contains <commit> --count=1` prints a line), and no code line links gerrit or gitiles outside
  a copy for Redmine: `grep -nP 'gitiles/|/\+/\d+/\d+/[^)]*#\d+\)' <file>` prints nothing;
- run steps: every `bash` block passes `bash -n`, every command sent over ssh passes `bash -n -c`,
  and every path in them exists;
- every `Run log #<n>` outside code is a link to its row: `grep -nP '(?<!\[)Run log #\d' <file>`
  prints nothing, and every Run log row starts with its `<a id="run-<n>"></a>` anchor;
- every `§` reference into another file is a link to its heading:
  `grep -nP '\]\([^)]+\.md\) ?§' <file>` and
  `grep -nP '(?<![\[\w/])(?:Tracking|Ledger|Defects)(?:\.md)?:? ?§' <file>` print nothing, and every
  `#` anchor names a heading or an `id` that exists in its file;
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
