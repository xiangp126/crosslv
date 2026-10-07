---
name: regression-report-mail
description: >-
  Find the nightly UtopX / NICX regression reports and functional-coverage mails in Outlook and
  read them correctly - the data is an .xlsx attachment (get_message returns ECI 404), coverage
  numbers live in a SQLite DB, and a branch-pointer table maps devices to FW branches. Use for the
  nightly or daily regression report, pass rate, coverage degradation, or whether regression
  exercised a feature.
---

# Regression reports in Outlook — what exists, what's in them, what you can actually read

Failure triage is a three-skill chain. Go 1 → 2 → 3: leg 2 often ends the investigation, and one
log from leg 3 alone cannot tell a one-off from a month-old epidemic.

| Leg | Question it answers | Skill |
|---|---|---|
| 1 | Did anything fail last night, and where? | `regression-report-mail` (Outlook) |
| 2 | Is this failure new? How many setups? Which commit introduced it? | `fsearch-failures` (failure DB) |
| 3 | What exactly happened in that one run? | `ci-forensics` (Jenkins → MARS log) |

## The mails, by exact subject

All from `svc-sw-hca-bot@nvidia.com` ("Automation Bot") to `NBU-HCA-Core-FWV`, one set per day.

| Subject | Cadence | Contains |
|---|---|---|
| `UTOPX Regression Report (DD_MM_YYYY)` | several per day (re-sent as the day fills in) | **branch-pointer table** in the body; full data in `UTOPX_REPORT_<date>.xlsx` |
| `[V5] UTOPX Regression Report (DD_MM_YYYY)` | same, V5 variant | same shape |
| `NICX Regression Report (DD/MM/YYYY)` | daily (+ `[V5]`) | NICX side |
| `P1 all - UTOPX Features Functional Coverage Status in REGRESSION - <Mon D>` | daily | **feature coverage** — links into the functional-coverage website |
| `P1 all - UTOPX Criticial Coverage Degradation in REGRESSION - <Mon D>` | daily | buckets that dropped vs the 3-week max |
| `P1 MTBC - UTOPX Criticial Coverage Degradation in REGRESSION` | daily | MTBC-scoped variant |
| `UtopX Anomalies Report (DD/MM/YYYY)` | daily | **new first-time failures** in the last 7 days |

Human-written status mails (not from the bot; useful for pass rates):

| Subject | From |
|---|---|
| `Regression status <D.M> - version <ver> + master_rc` | Rami Salah |
| `P2 Regression status <D.M> - <branch> - <ver>` | Rami Salah |

"Criticial" is misspelled in the real subjects — search on `Coverage Degradation`, not that word.

## Finding them

- `outlook_list_messages` takes **KQL field filters only** — plain text is rejected:

  ```
  outlook_list_messages(query="subject:regression", start_date="2026-08-20", limit=25)
  ```

- `outlook_search_messages` is the free-text one; use it when you don't know the subject.
- Both return newest-first.

## Hard limits — check before promising anything

1. **`outlook_get_message` returns `ECI API returned 404`** for these mails. The same message_id
   works with `outlook_list_attachments`, so the ID is valid and the server is up — only that one
   endpoint is blocked. Do not conclude "the ID is stale" or "the mail server is down".
2. **`outlook_list_messages` / `outlook_search_messages` / `outlook_get_conversation` return only
   `bodyPreview`** (~250 chars, truncated); none carries a `body` field. That preview includes the
   start of the branch-pointer table, which is often all you need.
3. **The real report is an .xlsx attachment, not the body:**

   ```
   outlook_list_attachments(message_id=...)
     → UTOPX_REPORT_2026_08_27.xlsx        ~2.3 MB
     → STEERING_UL_REPORT_2026_08_27.xlsx  ~10 KB
   ```

   `outlook_get_attachment` returns base64 `contentBytes` with no option to write to disk; 2.3 MB
   becomes ~3.1 MB of base64 — **do not pull it into context.** Its own docs also say a downloaded
   file must not be auto-processed without the user's explicit confirmation. Instead:
   - the big xlsx → **V-DASH** or the functional-coverage website (both linked from the mails; the
     report itself announces "Migrating Report to V-DASH");
   - functional coverage numbers → the SQLite DB directly (see "Functional coverage: read the DB,
     not the mail" below).

## The branch-pointer table — usually the answer you actually want

The first lines of the body map **device family → FW branch**, one column per priority:

```
List of Branches Pointers
Device         P1                                          P2
cx7_BRANCH     master_rc                                   master_rc
cx9_BRANCH     FUR_2026_June_PRDMA_CSP_main_from_48_1642    FUR_2026_Jan_VR_Fractal_ES_from_48_0386
cx6l_BRANCH    ...
```

It tells you whether a feature could have been exercised at all: e.g. `master_rc` on
`cx7_BRANCH` runs on ConnectX-7, where a DPU-only feature (sat-PF, ECPF, emu-manager delegation)
**cannot** run — that needs a BlueField (MUSTANG/BF-3).

Pointers move day to day (`cx7_BRANCH` P1 went from `FUR_2026_Aug_Anthropic_from_49_1118` to
`master_rc` overnight). **Re-read the table for the day in question; never carry an earlier day's
mapping forward.**

## Cross-checking against the regression database

Run fsearch only as skill `fsearch-failures` says — path, interpreter, flags and traps all live
there and are deliberately not duplicated here. The old `/mswg/...` copy is frozen and answers
"No records found" for every query, which looks like "the failure DB does not index syndromes". It
does.

> **fsearch only records failures.** A device missing from its output means "no failures
> recorded", **not** "did not run". Never use it alone to prove coverage — pair it with the
> branch-pointer table or the coverage DB below.

## Functional coverage: read the DB, not the mail

The coverage mails are unreadable from an agent session (404 + truncated preview, above), and the
numbers are not in the MARS session archive either (it holds no coverage files). The real store is
a **SQLite database**:

| what | path |
|---|---|
| **read this** | `/mswg/projects/fw/fw_ver/regression_db/coverage_dbs/coverage_backup.db` |
| live original | `l-fwvrt-06:/functional_coverage/utopx_func_coverage.db` |
| schema + tools | `/auto/sw/work/hca_fw/projects/fw_automations/coverage/` |

The backup is ~2.3 GB and refreshes daily around 08:00. Open it read-only:

```python
import sqlite3
c = sqlite3.connect('file:/mswg/projects/fw/fw_ver/regression_db/coverage_dbs/'
                    'coverage_backup.db?mode=ro', uri=True)
c.row_factory = sqlite3.Row
rows = c.execute("""select name, parent_name, branch, fw_version, date,
                           mustang_count, mustang_max, argaman_count, argaman_max
                    from Results
                    where name = :bucket and domain = 'regression' and date >= :since""",
                 {'bucket': 'create_on_sat_pf', 'since': '2026-09-18'}).fetchall()
```

Table `Results`: one row per bucket per branch per day, with a `<device>_count` /
`<device>_max` pair per device. `type` is one of `coverage` / `group` / `item` / `bucket`;
`domain` is `regression` / `sw_regression` / `minireg` / `pld`.

Traps:

1. **Device columns are chip code names, not machine or family names.** BF-3 = `mustang`,
   **BF-4 = `argaman`**. There is no `bronco` column — grepping for one returns nothing while the
   data sits right there. Full list in `device_catalog.json`; `enums.py` has `REG_DEVS`.
2. **A column aggregates a whole device type.** `argaman_count` merges every BF-4 setup
   (016 / 017 / 018 / …), so it cannot answer "which machine hit it" — for that, go back to the
   session log and bucket by DBDF.
3. **`max` = the largest count seen on that branch**, not a target. Read `0/1` as "zero today,
   this branch hit it once before".
4. **A missing day is not a miss.** Branches drop out of the DB for days at a time, even on days
   when the session log shows the feature firing. Check that the row exists before reading a 0 as
   evidence.

To find your feature's bucket names, grep the test source for the coverage macros
(`COVER_ITEM_BOOL`, `COVER_ITEM`, `COVER_ITEM_OCCURRED`). The group name is the enclosing class's
`GetName()`, and the DB's `parent_name` is that group.

## Answering "did regression exercise our feature?"

Three independent checks, cheapest first:

1. **Branch pointer** — is our branch even on a device family that has the hardware? Often
   decisive on its own.
2. **The coverage DB** (above) — per-feature counters, queryable, no website needed; the cheapest
   *quantitative* answer, covering every branch and device at once.
3. **MARS session grep** — pick a session and count the feature's own markers in the archive
   (session_id → archive: skill `ci-forensics`). For sat-PF emu-manager delegation the markers are
   `create_on_sat_pf`, `has_dpu_sat_pf`, `EMU-MGR`, `emulation_manager`. **`True=0 / False=0`
   means the path never ran** — a different statement from "it ran and passed"; say which one you
   mean.
