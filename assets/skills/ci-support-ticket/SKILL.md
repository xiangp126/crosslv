---
name: ci-support-ticket
description: Open a CI support request with the nbu-fw_automation_team — the ServiceNow "Networking SW - Host Firmware Automation Support" form. Covers which fields Service Type=CI expands, the two checkbox assertions you must verify first, and the one rule that keeps getting broken — the Description reports the failure only, never your root-cause analysis. Use ONLY when Peter explicitly says "open a CI ticket"; a plain "open a ticket" means Redmine.
---

# Opening a CI ticket (nbu-fw_automation_team)

## When — only on the explicit words

| Peter says | file |
|---|---|
| **"open a CI ticket"** | this form |
| **"open a ticket"**, or anything else | **Redmine** — skill `utopx-regression-ticket`. Do not reroute here because the failure looks like CI plumbing |

If Redmine looks like the wrong home, **say so in your reply and open the Redmine ticket anyway.**
The reroute is his call. (2026-09-07: an ES-branch DoA that could not dispatch was routed here on
my own judgement and the Redmine ticket had to be closed again.)

**There is no CLI or MCP for this form.** Produce the field values; Peter pastes and submits.

## The form

ServiceNow → **"Networking SW - Host Firmware Automation Support"**, owned by
`nbu-fw_automation_team`. Blurb: *"Support for automations like: CI, regression, mini-regression,
DoA, FW builds, PSC etc."*

Picking **Service Type = `CI`** expands it. All `*` are required:

| field | value |
|---|---|
| Is this request for yourself or someone else | `Yourself` |
| Watch List | optional — reviewers who should follow it |
| **Service Type** \* | `CI` |
| **Branch** \* | the gerrit branch, e.g. `FUR_2026_Jan_VR_Fractal_ES_from_48_0386` |
| **Gerrit Link** \* | full change URL |
| **Stage** \* | the failing stage **verbatim**, e.g. `Micro-DoA: gfw:BUILDER` — copy it out of `Stage: "<name>" failed` in the utopx_ci console, do not write it from memory |
| ☐ *I checked in "known rerun issues" and it's not part of them* \* | verify — see below |
| ☐ *I am updated on the latest issues in "Golan FW" and it's not part of them* \* | verify — see below |
| **Description** \* | see below |

Other Service Type values expand different field sets; re-read the form rather than assuming.

## The two checkboxes are assertions — verify before telling him to tick

- **known rerun issues** — run
  `~/myGit/crosslv/assets/skills/utopx-ci-rerun/scripts/ci_rerun.sh --reasons` and
  check every entry against this failure. The list is edited over time (dated entries get added and
  removed), so **read it now**; do not rely on a remembered list.
- **latest issues in "Golan FW"** — read the current "Known Issues" / "Golan_CI Updates" notice and
  establish why it does not apply. Compare on **job** (NICX Mini-Regression vs golan_fw_minireg
  Micro-DoA), **branch**, and **which test**.

State both comparisons in your reply, so he ticks them knowing they were actually checked.

## Description — what happened, nothing else

**Root-causing the failure is the automation team's job.** The Description is a report, not a
diagnosis. Facts you can point at in a log; no inference, no conclusions, no consequences.

Include:

1. Which build failed at which stage.
2. Which downstream job it dispatched, and how that job ended.
3. Any directly observable fact about the outcome (e.g. "none of the ten setups reported a device
   status") — readable straight off the log, not derived.
4. The build link.
5. "Could you take a look?"

**Leave out — all of it, however solid:**

| leave out | it is |
|---|---|
| the resolving code path (`file:line`), the missing directory or config | their diagnosis to make |
| a passing control run, A/B comparisons, per-branch state tables | analysis |
| "I reran it twice, identical output, not transient" | analysis |
| "another author's change fails the same way", "nothing has merged since <date>" | analysis |
| "so this is not a test failure", "the DoA aborted during setup" | conclusion |
| "the change can never get a Verified vote" | consequence |

Worked example — the whole Description, for a Micro-DoA that never dispatched:

```
utopx_ci #24693 failed at stage "Micro-DoA: gfw:BUILDER".

The stage dispatched golan_fw_minireg #147055, which ended with
"Mini-regression failed". None of the ten setups reported a device status.

https://nbuprod.blsm.nvidia.com/nbu-hca-fw-jenkins/job/utopx_ci/24693/

Could you take a look?
```

> ⚠ **This took four corrections on 2026-09-07 to get right**, each cutting more:
> ~60 lines with every run number and vote history → *"too complex"*; then still led with
> `BurnFwUsingMfa.py:100` and a three-directory comparison → *"you don't need to find the root
> cause"*; then still carried the rerun note and the other-author note → *"delete that"*; then
> still ended with "so this is not a test failure / the change can't get Verified" → *"do not add
> any analysis from you, just tell the CI owner what happened"*.
>
> **Keep doing the investigation** — it is what tells you the failure is not yours and stops
> pointless reruns. Park it in the local analysis md. The ticket is not where it goes.

## Related

- Redmine tickets (the default channel): skill `utopx-regression-ticket`.
- Getting the stage name, downstream job and log facts: skill `ci-forensics`.
- Checking rerun reasons and concurrency before a rerun: skill `utopx-ci-rerun`.
