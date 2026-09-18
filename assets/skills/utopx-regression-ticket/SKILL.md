---
name: utopx-regression-ticket
description: Open a Redmine ticket for a UTOPX regression or CI failure — the default channel whenever Peter says "open a ticket". Covers the exact project/tracker/sprint/chips field set, the three-part description format (Fatal message / MARS view_log link / Root cause with confidence), how to build the MARS link, and when a firmware defect goes to the Design project instead. Use when asked to open a ticket, file a bug, or raise a Redmine issue for a regression, CI, DoA or MARS-session failure.
---

# Opening a Redmine ticket for a UTOPX regression failure

These are the **verification-side regression tickets** — one per distinct fatal signature found in a
nightly regression or CI DoA session. They are `Task`/`Story` in a Verification project, **not** bugs.

## The channel is set by Peter's wording, not by your judgement

| he says | you file |
|---|---|
| **"open a ticket"** (or anything short of the phrase below) | **a Redmine ticket — always, by default.** Do not reroute it because the problem looks like CI plumbing |
| **"open a CI ticket"** — explicitly | the ServiceNow request — see skill `ci-support-ticket` |

If a Redmine ticket looks like the wrong home for the finding, **say so in your reply and file the
Redmine ticket anyway** — the reroute is his call, not yours.

Within Redmine there is still one choice, by subject matter:

- **utopx test defect** (wrong expected value, bad model, a UFATAL in a case that ran) →
  project **5581 `ConnectX FW Core - Verification`**, Task/Story — the rest of this skill.
- **firmware defect** (FW returns the wrong cap/syndrome, the test is right) →
  project **5580 `ConnectX FW Core - Design`**, tracker **`Bug SW`**, with
  `Reported by Department` / `Detected In Version`.

## The field set

Canonical example to copy from: **[#5255514](https://redmine.nvidia.com/issues/5255514)**
(filed by Raz Gavrieli via the Orion auto-analyzer). One filed by hand from this skill:
**[#5257991](https://redmine.nvidia.com/issues/5257991)**.

| field | value | notes |
|---|---|---|
| tool | **`yai__create_task`**, or the REST fallback below if the MCP is down | NOT `create_bug` — that picks a Bug tracker the project may not enable |
| `project` | **`5581`** (`ConnectX FW Core - Verification`) | pass the numeric id |
| `tracker` | `Task` | |
| `scrum_type` | `Story` | required for it to land on the scrum board |
| `sprint_id` | see **Sprint lookup** below | |
| `priority` | **`P1: Critical` (id 6) — this is the default, use it** | Peter's rule 2026-09-15: these regression tickets go in as P1. Do not downgrade to P2 because the failure "only" kills one case — the judgement call is his, not yours |
| `assigned_to` | full name, e.g. `Peter Xiang`, or `me` | author is always the authenticated user |
| `target_version` | `9505` = `Host FW - 51.1000 GA Release (GA-October26)` | **pass the numeric id**; name resolution only checks the project's own versions |
| `custom_fields` | `{"Chips": "<id>"}` | **numeric chip id only** — `167` = Bronco (BF4), `84` = Mustang (BF3). The `"167=Bronco"` string form is rejected |
| `tags` | `["regression"]` | |
| `story_points` | `2` | typical for one signature |
| `Show Stopper` | defaults to `0` — leave it unless the failure really blocks a release | |

`start_date` / `due_date` are not create-time parameters; they come from the sprint window.

## When the redmine MCP is down

`yai__create_task` unavailable and `redmine-cli` broken by glibc? Use the REST API with the key
in `~/.redmine_env`. Field-name → numeric-id mapping, the id lookup endpoints, and the
"ask which sprint, don't infer it from the date" rule: **`references/rest-fallback.md`**.

## Sprint lookup — the sprint does NOT live in the ticket's project

Sprints are all in **project 103**, regardless of which project the ticket goes to:

Read the `redmine://projects/103/sprints` resource from server `nvidia-redmine`. Tool syntax
differs by runtime, so first read `references/hosts/claude.md` in Claude Code or
`references/hosts/codex.md` in Codex.

Match on `name` **and** `group_name` — several groups have a sprint literally named `26-09`.
Known ids: `MTBC_YL 26-06`=29881 · `MTBC_YL 26-07`=30226 · `MTBC_YL 26-08`=**30624** ·
`MTBC_YL 26-09`=30896.

> `redmine://projects/5581/sprints` returns `count: 0` — that is not "no sprints", it is the wrong
> project. Don't conclude the sprint doesn't exist.

⚠ Cross-project sprint assignment **has been rejected before** — on project **5580** (Design / Bug SW)
the MCP 422s and the sprint has to be set by hand on the UI scrum board. On **5581 with
`create_task` it works**; verify after creating (see below) and fall back to the UI if it didn't take.

## Subject

```
[UTOPX]<the fatal text, verbatim, one line>
```

Copy the message the test actually printed — including the odd double spaces. Reviewers and the
dedup tooling match on this string. Examples:

```
[UTOPX]status != OK is supported only in error test on command QUERY_EMULATED_RESOURCES_INFO syndrome : 0xe5dfad;query_emulated_resources_info: operation is not supported;
[UTOPX]cmd_hca_cap: general_obj_type_dpa_db_cq_mapping not greater than (or zero if expected) : expected= 0x0 Actual 0x1
```

## Description — keep it SHORT

**Peter's rule (2026-09-15): the description was too complex.** It is a landing page, not the
analysis. Look at [#5232246](https://redmine.mellanox.com/issues/5232246) — its description is the
fatal line plus the MARS link, nothing else.

Budget: **fatal message + MARS link + a Root cause paragraph of ~5 lines.** Everything longer —
the A/B evidence, per-branch SHAs, the candidate patch, the NOT-verified list — goes into the
**first comment**, with the full write-up as an **attachment**. A reader opening the ticket should
see what broke and where, and be able to choose whether to read further.

## Description — three parts, in this order

```
Fatal message:
<the UFATAL / FATAL lines, verbatim>

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

`scripts/mars_link.sh <setup_id> <session_id> <key_id> <test_name>` assembles it.

`key_id` is the node path inside the archive (`0.15.1.1.1.8.1.6.101.6.1`), i.e. the directory that
has `result: 1` **and** a sibling `log.txt`. Getting from a session id to that node is skill
`ci-forensics`.

> Note the URL takes `/auto/sw_regression/...` while the archive is mounted at
> `/.autodirect/sw_regression/...`. Both are correct in their own context — don't "fix" one to match
> the other.

### What the Root cause paragraph needs

In the **description**, keep it to the confidence word plus the mechanism in a few lines.
Everything below belongs in the **first comment**, not the description:

- **The suspect change**, as a gerrit URL + title + owner + merge date + per-branch SHAs.
- **A/B evidence over sessions**, not anecdotes: N sessions before with 0 occurrences vs M sessions
  after with K. Say explicitly if the test was already *running* before (field present in the
  expected-cap dump) — that rules out "it just wasn't exercised".
- **Scale and blast radius**: total occurrences, affected setups, affected branches, and which
  branches carry the code but don't run the case.
- **Impact in the reader's terms**: cases killed / total failing cases, whether it aborts the
  session, whether it gates CI, pass-rate delta.
- **Anything NOT verified, labelled as such.** Write "Leading hypothesis, NOT yet verified:" — a
  hypothesis presented as fact is the thing that gets a ticket bounced.
- **Whether reverting the suspect is an option**, if the suspect fixed something real.
- A pointer to the full local analysis file.

## Attachments

**Upload as much as you can — this is not optional.** The MARS per-case artifacts do not live
under the failing `key_id` (they sit in sibling nodes), the `.cap` files are MARS metadata rather
than the artifact, and your own A/B logs and patches belong on the ticket too.

Full procedure, naming convention, one-shot `tar` extraction and the two-step REST upload flow:
**`references/attachments.md`**.

## After creating — verify, don't assume

```
yai__get_tickets(ticket_ids=[<new id>], include="basic")
```

Check `author`, `assigned_to`, `priority`, `attachments`, `tag_list`, `story_points`,
`custom_fields[Chips]`, and
`start_date`/`due_date` — **the dates are the only visible proof the sprint took**, since the API
response has no sprint field. If they don't match the sprint window, set the sprint on the UI board.

## Related

- session_id → the archive → the actual UFATAL and node path: skill `ci-forensics`.
- If the MCP is down, `redmine-cli` fallback: skill `tracking-redmine`.
- Reporting a *firmware* defect instead: memory `reference_satpf_fw_wa_redmine_tickets`.

## Fields the REST API silently drops on this instance

Measured on #5273244 (2026-09-15): a `PUT` returns **204** but the value never lands for

| field | workaround |
|---|---|
| `story_points` | set it on the UI scrum board |
| `tags` / `tag_list` | set it on the UI |

`sprint_id`, `priority_id`, `fixed_version_id`, `assigned_to_id`, `custom_fields[Chips]` and
`uploads` all write fine. **Always read back after writing** — a 204 is not proof the value took.
For the sprint the only visible proof is `start_date`/`due_date` matching the sprint window
(`MTBC_YL 26-08` -> 2026-08-01 .. 2026-08-31).
