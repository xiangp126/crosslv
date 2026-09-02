---
name: regression-report-mail
description: Find the nightly UtopX / NICX regression reports and the functional-coverage mails in Outlook, and know what each one actually contains. Covers exact subjects and senders, the branch-pointer table that says which device runs which FW branch, and the hard limits of the Outlook MCP tools (get_message returns ECI 404; the real data is an .xlsx attachment, not the body). Use when asked to check the regression report, the daily/nightly report, regression pass rate, coverage degradation, or whether a feature was exercised by regression.
---

# Regression reports in Outlook — what exists, what's in them, what you can actually read

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

Human-written status mails (different senders, useful for pass rates):

| Subject | From |
|---|---|
| `Regression status <D.M> - version <ver> + master_rc` | Rami Salah |
| `P2 Regression status <D.M> - <branch> - <ver>` | Rami Salah |

Note "Criticial" is misspelled in the real subjects — search on `Coverage Degradation`, not the word.

## Finding them

`outlook_list_messages` takes **KQL field filters only** — plain text is rejected.

```
outlook_list_messages(query="subject:regression", start_date="2026-08-20", limit=25)
```

`outlook_search_messages` is the free-text one; use it when you don't know the subject.
Both return newest-first.

## ⚠ Hard limits — read before promising anything

1. **`outlook_get_message` returns `ECI API returned 404`** for these mails.
   Verified 2026-08-27: the *same* message_id works fine with `outlook_list_attachments`,
   so the ID is valid and the server is up — that one endpoint is what's blocked.
   **Don't conclude "the ID is stale" or "the mail server is down".**

2. **`outlook_list_messages` / `outlook_search_messages` / `outlook_get_conversation` return
   only `bodyPreview`** (~250 chars, truncated). None of them carry a `body` field.
   So the *most* body you can get is the first few lines — which happens to include the
   start of the branch-pointer table, and that is often all you need.

3. **The real report is an .xlsx attachment, not the body.**
   ```
   outlook_list_attachments(message_id=...)
     → UTOPX_REPORT_2026_08_27.xlsx        ~2.3 MB
     → STEERING_UL_REPORT_2026_08_27.xlsx  ~10 KB
   ```
   `outlook_get_attachment` returns base64 `contentBytes` with **no option to write to disk**.
   2.3 MB → ~3.1 MB of base64 → **do not pull it into context.** Its own docs also say a
   downloaded file must not be auto-processed without the user's explicit confirmation.
   → For the big xlsx, go to **V-DASH** or the functional-coverage website instead
   (both are linked from the mails; the report itself announces "Migrating Report to V-DASH").

## The branch-pointer table — usually the answer you actually want

The first lines of the body map **device family → FW branch**, one column per priority:

```
List of Branches Pointers
Device         P1                                          P2
cx7_BRANCH     master_rc                                   master_rc
cx9_BRANCH     FUR_2026_June_PRDMA_CSP_main_from_48_1642    FUR_2026_Jan_VR_Fractal_ES_from_48_0386
cx6l_BRANCH    ...
```

**This is what tells you whether a feature could have been exercised at all.**
Example (2026-08-27): `master_rc` sits on `cx7_BRANCH` — ConnectX-7. A DPU-only feature
(sat-PF, ECPF, emu-manager delegation) **cannot** run there; it needs a BlueField (MUSTANG/BF-3).
Pointers move day to day — on 08-26 `cx7_BRANCH` P1 was `FUR_2026_Aug_Anthropic_from_49_1118`.
**Always re-read the table for the day in question; never carry yesterday's mapping forward.**

## Cross-checking against the regression database

`fsearch` = `/mswg/projects/fw/fw_ver/mars_analytics/search.py`. **Run it with `/usr/bin/python3`** —
the default python on the dev host lacks `dateutil` and the script dies on import.

```bash
/usr/bin/python3 /mswg/projects/fw/fw_ver/mars_analytics/search.py \
    --branchlike master_rc --datefrom 2026-08-21 --countper device
```

Useful flags: `--branchlike/--branchexact/--branchnotlike`, `--devices`, `--testlike/--testexact`,
`--errlike/--errexact/--erregex`, `--countper`, `--regcycle`, `--session`, `--nodoa`, `--nomr`,
`--fatal`, `--cols`.

> ⚠ **fsearch only records failures.** A device missing from its output means
> "no failures recorded", **not** "did not run". Never use it alone to prove coverage —
> pair it with the branch-pointer table or the functional-coverage report.

## Answering "did regression exercise our feature?"

Three independent things, in increasing cost:

1. **Branch pointer** — is our branch even on a device family that has the hardware?
   (cheapest, and often decisive on its own)
2. **Functional coverage report / website** — the `Features Functional Coverage Status` mail
   links straight to the per-feature counters.
3. **MARS session grep** — pick a session and count the feature's own markers in the archive.
   For sat-PF emu-manager delegation the markers are `create_on_sat_pf`, `has_dpu_sat_pf`,
   `EMU-MGR`, `emulation_manager`. **`True=0 / False=0` means the path never ran**, which is a
   very different statement from "it ran and passed" — say which one you mean.
   See skill `ci-forensics` for getting from a session_id into the archive.
