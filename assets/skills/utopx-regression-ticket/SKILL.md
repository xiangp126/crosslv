---
name: utopx-regression-ticket
description: Open a Redmine ticket for a UTOPX regression or CI failure (the default channel when Peter says "open a ticket"), modelled on ticket 5273909 - field set, subject from the MAIN_FATAL line, a short description, a first comment carrying the evidence with every MARS per-case artifact attached, and the analysis attachment. Also the root cause analysis comment for an existing ticket (what Peter means by "write a root cause analysis"), the HTML format for ANY Redmine description or comment, and how to correct a posted comment in place. Use when opening a ticket or filing a bug for a regression, CI, DoA or MARS-session failure, when asked to write a root cause analysis (RCA) for a ticket, when moving a misfiled ticket to another project or tracker, and whenever posting or editing a Redmine comment.
---

# Opening a Redmine ticket for a UTOPX regression failure

Scope: verification-side regression tickets, one per distinct fatal signature found in a nightly
regression or CI DoA session. They are `Task`/`Story` in a Verification project, not bugs.

## Channel: Peter's wording decides, not your judgement

| Peter says | you file |
|---|---|
| **"open a ticket"** (or anything short of the phrase below) | **a Redmine ticket, always.** Do not reroute it because the problem looks like CI plumbing |
| **"open a CI ticket"**, explicitly | the ServiceNow request — skill `ci-support-ticket` |

If Redmine looks like the wrong home for the finding, say so in your reply and file the Redmine
ticket anyway; the reroute is Peter's call.

Within Redmine, pick the project by subject matter:

| finding | project | tracker |
|---|---|---|
| **utopx defect** — wrong expected value, bad model, a UFATAL in a case that ran, or a draw/config that keeps a feature path from running (coverage gap) | **5581** `ConnectX FW Core - Verification` | **`Task`**, scrum type Story — the rest of this skill |
| **firmware defect** — FW returns the wrong cap/syndrome, the test is right | **5580** `ConnectX FW Core - Design` | **`Bug SW`**, with `Reported by Department` / `Detected In Version` |

- A utopx-side ticket is never `Bug SW`, although 5581 enables that tracker: utopx tickets are
  `Task`, like the ones the regression team opens.
- A ticket found in the wrong project or tracker is moved, not re-filed: "Moving a ticket to
  another project or tracker".

## The ticket, end to end — template [#5273909](https://redmine.nvidia.com/issues/5273909)

Open [#5273909](https://redmine.nvidia.com/issues/5273909) and copy its shape: subject, description,
first comment, attachments, analysis comment. A ticket is not opened until all of these are on it:

| # | part | content | section |
|---|---|---|---|
| 1 | subject | `[UTOPX]` + the quoted MAIN_FATAL message | Subject |
| 2 | description | MAIN_FATAL line, MARS URL, Root cause paragraph, "See the first comment for …" — nothing else | Description |
| 3 | first comment | the evidence in `== … ==` sections, **with every MARS per-case artifact attached in the same journal** (10 files) plus your own repro logs, probe scripts and candidate patch | What the first comment needs, Attachments |
| 4 | analysis comment | one line pointing at the analysis, with `Rc_<ticket#>.md` attached under the name `ROOTCAUSE_analysis.md` | Attachments |

Draft all four locally, show them to Peter, and post them together after he approves:

1. `scripts/mars_artifacts.sh` — the MARS per-case artifacts and their manifest (Attachments).
2. `yai__create_task` — the ticket with the field set below.
3. `scripts/post_ticket.py desc`, then `note` twice — description, first comment with its uploads,
   analysis comment (Posting).
4. "After creating" — fields, sprint dates, attachment count.

## The field set

Templates: **[#5255514](https://redmine.nvidia.com/issues/5255514)** (canonical; filed by Raz
Gavrieli via the Orion auto-analyzer) and **[#5257991](https://redmine.nvidia.com/issues/5257991)**
(filed by hand from this skill).

| field | value | notes |
|---|---|---|
| tool | **`yai__create_task`**; the REST fallback below if the MCP is down | not `create_bug` — it picks a Bug tracker the project may not enable |
| `project` | **`5581`** (`ConnectX FW Core - Verification`) | pass the numeric id |
| `tracker` | `Task` | |
| `scrum_type` | `Story` | required for the ticket to land on the scrum board |
| `sprint_id` | see **Sprint lookup** below | |
| `priority` | **`P1: Critical` (id 6)** — the default, use it | P1 = it costs regression: a failing case, or coverage the regression no longer gets (a coverage gap is P1); P2 = an impact outside regression; P3 = no impact, an optimization. Do not downgrade (e.g. to P2 because the failure "only" kills one case); priority is Peter's call |
| `assigned_to` | full name, e.g. `Peter Xiang`, or `me` | the author is always the authenticated user |
| `target_version` | `9505` = `Host FW - 51.1000 GA Release (GA-October26)` | **pass the numeric id**; name resolution only checks the project's own versions |
| `custom_fields` | `{"Chips": "<id>"}` | **numeric chip id only** — `167` = Bronco (BF4), `84` = Mustang (BF3). The `"167=Bronco"` string form is rejected |
| `tags` | `["regression"]` | |
| `story_points` | `2` | typical for one signature |
| `Show Stopper` | defaults to `0` | leave it unless the failure really blocks a release |

`start_date` / `due_date` are not create-time parameters; they come from the sprint window.

## When the redmine MCP is down

If `yai__create_task` is unavailable, use the REST API with the key in `~/.redmine_env`: it needs
no login, while `redmine-cli` (pim container) is not logged in there. Field-name → numeric-id
mapping and the id lookup endpoints: **`references/rest-fallback.md`**.

## Sprint lookup — the sprint does NOT live in the ticket's project

All sprints are in **project 103**, whichever project the ticket goes to. Read the
`redmine://projects/103/sprints` resource from server `nvidia-redmine`. The tool syntax differs by
runtime: first read `references/hosts/claude.md` in Claude Code or `references/hosts/codex.md` in
Codex.

- Match on `name` **and** `group_name` — several groups have a sprint literally named `26-09`.
- Known ids: `MTBC_YL 26-06`=29881 · `MTBC_YL 26-07`=30226 · `MTBC_YL 26-08`=**30624** ·
  `MTBC_YL 26-09`=30896.
- `redmine://projects/5581/sprints` returns `count: 0` because it is the wrong project, not
  because there are no sprints. Do not conclude the sprint doesn't exist.
- Ask Peter which sprint if he has not said; do not infer it from the date. The sprint follows the
  team's planning board, not the calendar month: a mid-month ticket can belong to the previous
  month's sprint (`MTBC_YL 26-08`, not `26-09`).
- Cross-project sprint assignment: on project **5580** (Design / Bug SW) the MCP returns 422 and
  the sprint has to be set by hand on the UI scrum board. On **5581 with `create_task`** it works;
  verify after creating (below) and fall back to the UI if it didn't take.

## Subject

```
[UTOPX]<the message inside the quotes of the MAIN_FATAL line>
```

Take it from the run log's `MAIN_FATAL:` line (`grep -a MAIN_FATAL <run_case log>`), which reads
`<file>:<line>, in Func <Func>. "<message>"`. Copy the message verbatim, including the odd double
spaces: reviewers and the dedup tooling match on this string. Join a multi-line message with single
spaces. A cap mismatch prints the full expected and received cap dumps between the message head and
its closing `Field mismatch:  DETAILS: …` line: keep the head and that line, drop the dumps. Examples:

```
[UTOPX]QUERY_EMULATED_FUNCTIONS_INFO mismatch of num_emulated_functions DETAILS: expected:0x61 actual:0x2
[UTOPX]actual cap fields can't be less than expected cap (or zero) Field mismatch:  DETAILS: cmd_hca_cap: general_obj_type_dpa_db_cq_mapping not  greater than (or zero if expected)   : expected= 0x0 Actual 0x1
```

Not the `Field mismatch` line alone and not the `general_layout.cpp:365 … FATAL :` block: both drop
part of the MAIN_FATAL message.

## Writing to Redmine — format, posting, correcting

Applies to descriptions and comments.

### Which path writes: MCP or REST

| use | for |
|---|---|
| the MCP (`yai__*`) | reads, searches, `create_task`, field and status changes through `update_ticket`: it acts under the user's SSO identity, resolves and validates names (`P1: Critical`, `Fixed`, `me`), writes the plugin fields REST drops (`story_points`, `tags`), and its footer marks the change as AI-made |
| REST (key in `~/.redmine_env`) | what the MCP cannot do: moving a ticket to another project or tracker, editing an existing journal, a note with several uploads in one journal; and posting a drafted description or comment with `post_ticket.py`, which compares the read-back (Posting) |

- Every MCP write adds a journal carrying the textile footer; a status or field change gets a
  journal whose note is the footer alone. Replace it with its HTML form in place (see
  "Correcting").
- A REST write carries no AI marker: the history shows it as the user's own change.
- Read the ticket back after every write: a REST `204` is not proof the value took.
- Every write — note, field, status, move — needs Peter's go-ahead first.

### Format: HTML, the way the web editor stores it

The web editor on redmine.nvidia.com stores descriptions and comments as HTML (`<p>…</p>`,
`<br />`, CRLF line ends). Content that contains HTML renders as HTML; anything else goes through
textile, and on this instance textile output gets large vertical gaps: a single line break inside
a paragraph shows as an extra empty line, every list item takes two lines, and a textile table is
preceded by a large empty block. Write descriptions and comments in HTML.

| element | HTML |
|---|---|
| paragraph | `<p>…</p>`, one per paragraph; no line breaks inside it |
| heading | `<h3>Title</h3>`, `<h4>Title</h4>` |
| bold | `<strong>text</strong>` |
| field names, identifiers, hex | `<code>pci_switch=0x1</code>` |
| fatal lines, logs | `<pre>…</pre>` |
| list | `<ul><li>…</li></ul>`, `<ol><li>…</li></ol>` |
| link | `<a href="https://…">text</a>` |
| table | `<table border="1" cellpadding="4" cellspacing="0"><tbody>`, a `<tr><th>…</th></tr>` header row, then `<tr><td>…</td></tr>` rows |

- Escape `&`, `<` and `>` in text and inside `<pre>` (`&amp;`, `&lt;`, `&gt;`).
- Tables in the form above render on this instance (bordered, header row bold).
- The MCP appends its footer in textile (`%{font-size:smaller}via YAI Redmine MCP […]%`), which
  shows raw in an HTML note. Right after posting, replace that line in place (see "Correcting")
  with `<p><span style="font-size:smaller">via YAI Redmine MCP […]</span></p>`, keeping the text
  inside the brackets unchanged.

### Posting

1. Draft locally in `/auto/fwgwork1/$USER/bugZilla/<ticket#>_<core>/`: the description and each
   comment as an `.html` file, the uploads of a comment as a manifest `.tsv`. Show them to Peter.
2. After he approves, post the approved files unchanged. Take any change back to him first.
3. Post with `scripts/post_ticket.py` (REST, key from `~/.redmine_env`). Run every step with
   `--dry-run` first; every real write is read back and compared with the file:

   ```bash
   P=$(jskill path utopx-regression-ticket)/scripts/post_ticket.py
   $P desc --ticket <id> --subject '<subject>' --description <dir>/TICKET_<id>_description.html
   $P note --ticket <id> --note <dir>/NOTE_<id>_first_comment.html --manifest <dir>/attach/manifest.tsv
   $P note --ticket <id> --note <dir>/NOTE_<id>_analysis.html --manifest <dir>/analysis.tsv   # new ticket
   $P note --ticket <id> --note <dir>/redmine/NOTE_<id>_rootcause.html     # root cause analysis: no uploads
   ```

   - `desc` replaces subject and description and keeps the footer that `yai__create_task` put on
     the ticket, converted to its HTML form.
   - `note` uploads every manifest row and attaches them to the comment in **one journal**.
     Manifest rows: `<file><TAB><description>[<TAB><upload name>]`, paths relative to the
     manifest. Upload `Rc_<ticket#>.md` as `ROOTCAUSE_analysis.md` with the third column.
   - Notes posted this way carry no MCP footer.
   - `verify --ticket <id> [--subject …] [--description <file>] [--journal <id> --note <file>]`
     re-checks a posted ticket read-only.
   - Exit code 0 only when everything stored equals what was sent.
4. A later short comment without uploads may go through `yai__update_ticket(ticket_id=<id>,
   notes=<html>)`; then replace the MCP footer with its HTML form (see Format) and re-read the
   ticket.

Do not state how something renders without seeing it. Ask Peter for a screenshot, or compare with
a note he confirms displays correctly. Never try out a layout on a live ticket: every edit is
visible to all readers. If a layout is not proven on this instance, let Peter check the draft in
the editor's preview first; if an edit renders badly, restore the approved version at once.

### Correcting a posted comment: edit it in place, never post a new one

The MCP has no journal edit, and `update_ticket(notes=…)` adds a comment. Use REST with the key
from `~/.redmine_env` (`references/rest-fallback.md`):

```bash
curl -sk -X PUT -H "X-Redmine-API-Key: $K" -H 'Content-Type: application/json' \
     --data-binary @payload.json "$U/journals/<journal_id>.json"    # {"journal":{"notes":"…"}}
```

- `204` means done. Re-read `issues/<id>.json?include=journals`: the journal count must be
  unchanged, and only that journal's notes may differ.
- `GET /journals/<id>.json` returns 404 because there is no show route; PUT still works.
- After posting an HTML note through the MCP, this PUT is also how the footer gets its HTML form
  (see Format).

## Root cause analysis — one comment on the ticket

When Peter asks for a root cause analysis (RCA) for a ticket, write one comment in this shape.
Template: `assets/root_cause_analysis.html`. Reference:
[#5258246 note-23](https://redmine.nvidia.com/issues/5258246#note-23); also the RCA comments on
#5342762 and #5342798.

| part | HTML | content |
|---|---|---|
| title | `<h3>Root cause analysis — <session or event> (<branch>, FW <ver>, <setup>)</h3>` | |
| Summary | `<p><strong>Summary:</strong> …</p>` | one paragraph: first what it is not (a FW defect, a FW regression, the problem this ticket was opened for), then what it is and what exposed it; when fixed, the box it was verified on and the gerrit URL |
| 1. Failure | `<h4>1. Failure</h4>`, `<pre>`, `<ul>` | the FATAL line(s) verbatim from the case log, timestamp columns dropped; then Branch (FW and utopx versions), Setup (chip, PSID, box, mode, which functions exist), Where (case, seed, iteration:op, command, VHCA/GVMI, how many failing cases in which sessions or the fsearch count), Example (the MARS view_log URL, written out in full as the link text) |
| 2. Root cause | `<h4>2. Root cause</h4>`, `<ol>` | the causal chain, one item per link, each opening with `<strong>Label (qualifier).</strong>`: Trigger (regression config, utopx generation, a scenario); FW behaviour (by design, or unchanged/changed between versions, quoted from the FW source with file:line); utopx expectation or ordering (file:line, ending in the check that fails). Fields, functions and file:line go in `<code>` |
| 3. Evidence | `<h4>3. Evidence (<box>, <FW + INI>, <utopx>, <case>, seed <n>, <starting state>; one variable changed per run)</h4>`, a table, `<ul>` | one row per run (reproduction, controls, fix runs), one column per variable changed, a Result column; under the table the repro rate, corroboration from the regression archives (counts over sessions, setups, branches), and what rules out each remaining variable |
| 4. What this is not | `<h4>4. What this is not</h4>`, `<ul>` | each plausible wrong reading, with the run or fact that rules it out |
| 5. Ownership and next steps | `<h4>5. Ownership and next steps</h4>`, `<ul>` | one item per owner, opening with `<strong>Owner (scope):</strong>` — utopx, regression config, FW / architecture: the fix with its gerrit URL, or the concrete ask; "FW: nothing needed" when so |

- No attachments, and no second comment carrying files: the gerrit and MARS links are the trail.
  The attachment rules further down apply to opening a new ticket only.
- Write it from the ticket's `Rc_<ticket#>.md` (skill `regression-repro`), not from memory.
  Every number and timing comes from the logs and is checked on every run it is claimed for. Repro
  rates count only local runs from the case's starting state; a priming run is listed apart.
- Mark anything inferred from source but not run as "(from code, not run)".
- No internal process: no agent or session names, review history, local paths or chat quotes.
- Flow: draft `<ticket dir>/redmine/NOTE_<id>_rootcause.html` from the template; show Peter the
  full text in the reply, rendered readably; after his approval post it unchanged with
  `post_ticket.py note --ticket <id> --note <file>` (no manifest) and confirm the read-back.

## Description — four parts, kept short

The description is a landing page, not the analysis: a reader sees what broke and where, and
chooses whether to read further. Template: [#5273909](https://redmine.nvidia.com/issues/5273909).

Budget: **MAIN_FATAL line + MARS URL + a Root cause paragraph of 5–8 lines + a pointer to the first
comment.** Everything else — log excerpts, code paths, session lists, per-branch SHAs, the
candidate patch, the NOT-verified list — goes into the **first comment**, with the full write-up as
an **attachment**.

In this order:

```html
<p>Fatal message:<br />
<file>:<line>, in Func <Func>. &quot;<message>&quot;</p>

<p><a href="<MARS view_log URL>"><MARS view_log URL></a></p>

<p>Root cause (<HIGH|MEDIUM|LOW> confidence): <the mechanism, plain prose></p>

<p>See the first comment for <what it holds>.</p>
```

- **Fatal message**: the MAIN_FATAL line on one line, as in the subject (head + `DETAILS:` line,
  dumps dropped). Not a `<pre>` block of the multi-line FATAL output.
- **MARS URL**: shown as itself — the link text is the URL, not a label such as "MARS log".
- **Root cause**: the confidence word, then what the test does, what FW reports and why, what
  utopx expects and why, and why it is intermittent if it is. Plain prose: no `<code>` markup,
  session lists, SHAs or patch.
- **Pointer**: one sentence naming what the first comment holds.
- HTML entities as the web editor stores them: `&quot;`, `&#39;`, `&amp;` in the URL; keep the
  message's double spaces as `&nbsp; `.

### Building the MARS link

```
https://mars.mellanox.com/web/server/php/view_log.php
  ?results_dir=/auto/sw_regression/host_fw/HCA_CORE_FWV/MARS/conf/results
  &name=<test name, no utopx_NN_ prefix>
  &setup_id=<setup dir name>
  &session_id=<session id>
  &key_id=<archive node path>
  &status=Failed
```

`scripts/mars_link.sh <setup_id> <session_id> <key_id> [test_name]` assembles it. Omit
`test_name` and it is derived from the node's `log.txt` when the archive is reachable.

- `key_id` is the node path inside the archive (`0.15.1.1.1.8.1.6.101.6.1`): the directory that
  has `result: 1` **and** a sibling `log.txt`. Getting from a session id to that node: skill
  `ci-forensics`.
- The URL takes `/auto/sw_regression/...` while the archive is mounted at
  `/.autodirect/sw_regression/...`. Both are correct in their own context — don't "fix" one to
  match the other.

### What the first comment needs

Post it right after the description, with every attachment of the "Attachments" section in the
**same journal**. Layout of [#5273909](https://redmine.nvidia.com/issues/5273909): one intro line,
then `== <title> ==` sections, prose plus `<pre>` blocks for log and code excerpts:

| section | holds |
|---|---|
| `== The failing check (session, setup, branch, FW) ==` | case, seed, conf; the ops around the fatal; the expected vs received values that matter |
| `== Where FW's <value> comes from (<FW tag>, <sha>) ==` | the FW call chain, `file:line` per step |
| `== Where utopx's <value> comes from (<utopx tag>, <sha>) ==` | the utopx call chain, `file:line`; the change that introduced it |
| `== Occurrences ==` | A/B over sessions, scale, recent sessions, branches that carry the code but do not show it |
| `== Fix ==` | the candidate patch and why it matches FW; say whether it has run |
| `== Not related ==` | look-alike tickets or changes, and why they are different |
| `== Not verified ==` | every open point |

The full root cause goes into the first comment, not the description:

- **The suspect change**: gerrit URL + title + owner + merge date + per-branch SHAs.
- **A/B evidence over sessions**, not anecdotes: N sessions before with 0 occurrences vs M sessions
  after with K. Say explicitly if the test was already *running* before (field present in the
  expected-cap dump) — that rules out "it just wasn't exercised".
- **Scale and blast radius**: total occurrences, affected setups, affected branches, and which
  branches carry the code but don't run the case.
- **Impact in the reader's terms**: cases killed / total failing cases, whether it aborts the
  session, whether it gates CI, pass-rate delta.
- **Anything NOT verified, labelled as such**: write "Leading hypothesis, NOT yet verified:". A
  hypothesis presented as fact gets the ticket bounced.
- **Whether reverting the suspect is an option**, if the suspect fixed something real.
- A pointer to the full analysis, `Rc_<ticket#>.md`, which the analysis comment attaches.

## Attachments

Required: attach as much as you can. The MARS per-case artifacts sit in sibling nodes of the
failing `key_id`, not under it; the `.cap` files are MARS metadata, not the artifact; your own A/B
logs and patches go on the ticket too. Procedure, naming convention and the REST upload flow:
**`references/attachments.md`**.

```bash
S=$(jskill path utopx-regression-ticket)/scripts
$S/mars_artifacts.sh <setup_id> <session_id> <key_id> <dir>/attach
# then append your own rows to <dir>/attach/manifest.tsv: <file><TAB><description>
```

- With the first comment, in one journal: all ten MARS per-case artifacts (`custom_post_checker`,
  `dmesg`, `dump_file`, `fw_reset`, `mstdump_1..3`, `oplist`, `query_mlxconfig`, `run_case`), then
  your repro logs, probe scripts and candidate patch. [#5273909](https://redmine.nvidia.com/issues/5273909)
  carries twelve.
- Then a separate comment, one line pointing at the analysis, with `Rc_<ticket#>.md` attached as
  `ROOTCAUSE_analysis.md` (the upload name only; no local file has that name). A corrected version
  goes up later as `ROOTCAUSE_analysis_v2.md`.
- Every upload gets a `description`.
- A ticket with zero attachments is not opened yet.

## After creating — verify, don't assume

```
yai__get_tickets(ticket_ids=[<new id>], include="basic")
```

Check `author`, `assigned_to`, `priority`, `attachments` (at least the ten MARS artifacts), `tag_list`, `story_points`,
`custom_fields[Chips]`, and `start_date`/`due_date`. The dates are the only visible proof the
sprint took (the API response has no sprint field): they must match the sprint window, e.g.
`MTBC_YL 26-08` -> 2026-08-01 .. 2026-08-31. If they don't, set the sprint on the UI board.

### Fields the REST API silently drops on this instance

A `PUT` returns **204** but the value never lands for:

| field | workaround |
|---|---|
| `story_points` | set it on the UI scrum board |
| `tags` / `tag_list` | set it on the UI |

`sprint_id`, `priority_id`, `fixed_version_id`, `assigned_to_id`, `custom_fields[Chips]` and
`uploads` all write fine. Always read back after writing — a 204 is not proof the value took.

## Moving a ticket to another project or tracker

`yai__update_ticket` cannot change the project; use REST once Peter has approved the move.

1. Save the ticket as it is into the ticket directory:
   `GET {U}/issues/<id>.json?include=journals` — the record of what the move discards.
2. Check that the target enables the tracker: `GET {U}/projects/<target>.json?include=trackers`.
3. Move and set the fields in one `PUT {U}/issues/<id>.json`, e.g.
   `{"issue":{"project_id":5581,"tracker_id":9,"priority_id":6}}` → `204`.
4. Read it back and expect two side effects:
   - the status falls back to the new tracker's default when the old status is not in its
     workflow (`Bug SW` `Assigned` becomes `Task` `New`);
   - custom fields the target project or tracker does not enable are dropped (from `Bug SW`:
     `Reported by Department`, `Detected In Version`, `Found on Cluster`, `Review Status`, the AI
     showstopper fields).
5. Set the status Peter wants in a second write through the MCP, so the change carries the AI
   marker, then replace its footer (see "Which path writes").

The move writes one journal of field changes and no note. Ids: `references/rest-fallback.md`.

## Firmware defect tickets (project 5580)

- Project **5580** `ConnectX FW Core - Design`, tracker **`Bug SW`** (id 28) — not 5581, not 5574.
- Required custom fields: `Reported by Department` = `R&D`; `Detected In Version` = the gerrit
  URL of the FW change that introduced the defect (or the FW version); `Chips` = the numeric chip
  id (`"84"`, not `"84=..."`).
- `target_version`: pass the numeric id. FW versions often live in project 5574 and are shared to
  5580; name resolution only searches the ticket's own project.
- Sprint and `scrum_type` Story: the MCP rejects a sprint from another project, and Story without a
  sprint returns 422 — set both on the Redmine UI scrum board.
- MCP limits on `yai__update_ticket`: it cannot move a ticket to another project (move it over
  REST, see "Moving a ticket to another project or tracker");
  `is_private` is not settable; `assigned_to` cannot be empty; status `Rejected` on `Bug SW`
  requires custom field 46 `Rejected reason` from its fixed list (`Other`; `Duplicate issue`
  needs a real "duplicates" relation).

## Related

- session_id → the archive → the actual UFATAL and node path: skill `ci-forensics`.
- If the MCP is down: the REST fallback above (`references/rest-fallback.md`), not the `redmine-cli`
  path of skill `tracking-redmine`.
