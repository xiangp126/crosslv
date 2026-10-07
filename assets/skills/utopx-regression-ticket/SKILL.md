---
name: utopx-regression-ticket
description: Open a Redmine ticket for a UTOPX regression or CI failure — the default channel whenever Peter says "open a ticket". Covers the exact project/tracker/sprint/chips field set, the three-part description format (Fatal message / MARS view_log link / Root cause with confidence), how to build the MARS link, and when a firmware defect goes to the Design project instead. Also the formatting rules for ANY text written to Redmine (descriptions and comments: textile, not HTML) and how to correct a posted comment in place. Use when asked to open a ticket, file a bug, or raise a Redmine issue for a regression, CI, DoA or MARS-session failure, and whenever posting or editing a Redmine comment.
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
| **utopx test defect** — wrong expected value, bad model, a UFATAL in a case that ran | **5581** `ConnectX FW Core - Verification` | Task/Story — the rest of this skill |
| **firmware defect** — FW returns the wrong cap/syndrome, the test is right | **5580** `ConnectX FW Core - Design` | **`Bug SW`**, with `Reported by Department` / `Detected In Version` |

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
| `priority` | **`P1: Critical` (id 6)** — the default, use it | do not downgrade (e.g. to P2 because the failure "only" kills one case); priority is Peter's call |
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
[UTOPX]<the fatal text, verbatim, one line>
```

Copy the message the test actually printed, including the odd double spaces: reviewers and the
dedup tooling match on this string. Examples:

```
[UTOPX]status != OK is supported only in error test on command QUERY_EMULATED_RESOURCES_INFO syndrome : 0xe5dfad;query_emulated_resources_info: operation is not supported;
[UTOPX]cmd_hca_cap: general_obj_type_dpa_db_cq_mapping not greater than (or zero if expected) : expected= 0x0 Actual 0x1
```

## Writing to Redmine — format, posting, correcting

Applies to descriptions and comments.

### Format: textile

Redmine renders content that contains HTML as HTML, and textile inside it stays literal. Anything
else is rendered as textile. The MCP appends a textile footer
(`%{font-size:smaller}via YAI Redmine MCP […]%`) to everything it writes, so write the body in
textile.

| element | textile |
|---|---|
| heading | `h3. Title`, `h4. Title` |
| bold | `*text*` |
| field names, identifiers, hex | `@pci_switch=0x1@` |
| fatal lines, logs | `<pre>` and `</pre>` on their own lines |
| lists | `* item`, `# item` |
| table | see the example below |
| link | `"text":https://…` or a bare URL |

Table example:

```
|_. Run |_. FW |_. Result |
| A | 82.48.6150 | FAIL |
```

- Put every hex value, `->` and `'` inside `@…@` or `<pre>`. Outside them textile renders `0x0` as
  `0×0`, `->` as `→` and `'` as `’`.
- Do not put `@` right before a word or number outside a code span: `@6148` opens one.

### Posting

1. Draft locally (`/auto/fwgwork1/$USER/bugZilla/<ticket#>_<core>/*_redmine.textile`) and show
   it to Peter.
2. After he approves, post the approved text unchanged, with the same wording and format. Take any
   change back to him first.
3. Post a new comment with `yai__update_ticket(ticket_id=<id>, notes=<textile>)` and no other
   fields.
4. Re-read the ticket. The stored note must equal what you sent, plus the MCP footer.

Do not state how something renders without seeing it. Ask Peter for a screenshot, or compare with
a note he confirms displays correctly.

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
- In a note that went out as HTML the MCP footer shows raw. Replace that line with
  `<p><span style="font-size:smaller">via YAI Redmine MCP […]</span></p>`.

## Description — three parts, kept short

The description is a landing page, not the analysis: a reader sees what broke and where, and
chooses whether to read further. Template: [#5232246](https://redmine.nvidia.com/issues/5232246)
— the fatal line plus the MARS link, nothing else.

Budget: **fatal message + MARS link + a Root cause paragraph of ~5 lines** (the confidence word
plus the mechanism). Everything longer — the A/B evidence, per-branch SHAs, the candidate patch,
the NOT-verified list — goes into the **first comment**, with the full write-up as an
**attachment**.

In this order:

```
Fatal message:
<pre>
<the UFATAL / FATAL lines, verbatim>
</pre>

<MARS view_log URL>

Root cause (<HIGH|MEDIUM|LOW> confidence): <the analysis>
```

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
- A pointer to the full local analysis file.

## Attachments

Required: attach as much as you can. The MARS per-case artifacts sit in sibling nodes of the
failing `key_id`, not under it; the `.cap` files are MARS metadata, not the artifact; your own A/B
logs and patches go on the ticket too. Procedure, naming convention, one-shot `tar` extraction and
the two-step REST upload flow: **`references/attachments.md`**.

## After creating — verify, don't assume

```
yai__get_tickets(ticket_ids=[<new id>], include="basic")
```

Check `author`, `assigned_to`, `priority`, `attachments`, `tag_list`, `story_points`,
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

## Firmware defect tickets (project 5580)

- Project **5580** `ConnectX FW Core - Design`, tracker **`Bug SW`** (id 28) — not 5581, not 5574.
- Required custom fields: `Reported by Department` = `R&D`; `Detected In Version` = the gerrit
  URL of the FW change that introduced the defect (or the FW version); `Chips` = the numeric chip
  id (`"84"`, not `"84=..."`).
- `target_version`: pass the numeric id. FW versions often live in project 5574 and are shared to
  5580; name resolution only searches the ticket's own project.
- Sprint and `scrum_type` Story: the MCP rejects a sprint from another project, and Story without a
  sprint returns 422 — set both on the Redmine UI scrum board.
- MCP limits on `yai__update_ticket`: it cannot move a ticket to another project (UI only);
  `is_private` is not settable; `assigned_to` cannot be empty; status `Rejected` on `Bug SW`
  requires custom field 46 `Rejected reason` from its fixed list (`Other`; `Duplicate issue`
  needs a real "duplicates" relation).

## Related

- session_id → the archive → the actual UFATAL and node path: skill `ci-forensics`.
- If the MCP is down, `redmine-cli` fallback: skill `tracking-redmine`.
