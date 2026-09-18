---
name: <Reproduce Redmine bug #NNNNN locally>
overview: <Given only a Redmine bug URL, recreate the regression's exact env and reproduce the SAME failure signature locally>
todos:
  - id: setup-dir
    content: Create the per-ticket storage dir /auto/fwgwork1/$USER/bugZilla/<ticket#>_<core> and save the filled-in plan there
    status: pending
  - id: decode-ticket
    content: Decode the Redmine URL → failure signature, test tool, MARS coordinates (results_dir/setup_id/session_id/key_id), machine, device, MST dev, FW version
    status: pending
  - id: allocate-box
    content: malloc the SAME server from setup_id (jmake --reg-malloc <machine>); if busy, run the monitor script polling its lock every 15s and grab the instant it frees; --reg-extend to keep it, --reg-cancel when done. Never substitute a different host. Unknown command → ask Glean. Capture current FW as restore point
    status: pending
  - id: extract-regression
    content: From the MARS session tarball, read new_burn_fw + get_last_commit + run_case (FW/.mlx/INI/PSID + test-tool commit + exact command & seed) AND the session's own setup steps (clear_nv_data / SetMlxConfig / load_udriver / per-case Fwreset) — these are what the scripts must replay
    status: pending
  - id: write-scripts
    content: 'While waiting for the box: write tools/env_rebuild_<box>.sh + tools/per_run_reset.sh from the tarball data (Phase 9b). Mark both UNVERIFIED, make destructive paths opt-in, and gate both on Noga lock ownership. Do NOT wait for a confirmed repro'
    status: pending
  - id: pin-repos
    content: 'In BOTH repos create a named private branch from the failing version (git checkout -b <ticket#>_<topic>_<you> <sha>) — never a detached HEAD; init submodules recursively; confirm with git branch --show-current + git describe --tags'
    status: pending
  - id: reproduce-ini
    content: Copy the regression-generated INI (not the release default) and diff it
    status: pending
  - id: burn-fw
    content: Burn FW + INI to the device (rebuild only if you have source edits)
    status: pending
  - id: bringup
    content: Pivot FW into running memory, bind drivers, clear device state (match the regression's per-test setup)
    status: pending
  - id: run-repro
    content: Run the EXACT command + seed from run_case; watch for the same fatal/signature
    status: pending
  - id: confirm-repro
    content: Confirm the failure reproduced (same signature) — or document how it diverged — and log it
    status: pending
  - id: recover-env
    content: If the box drifted (a regression ran since), rebuild + repin + reburn before trusting a result
    status: pending
  - id: log-investigation
    content: 'From the moment you start reading FW/tool source: append DATED entries to the Investigation log section below AS YOU GO (hypothesis, file:line evidence, git blame / git log --author attribution) - not reconstructed at the end. Keep superseded conclusions, mark them SUPERSEDED, never delete'
    status: pending
  - id: verify-fix
    content: 'Once a candidate fix exists (golan_fw2 and/or utopx2 - never assume FW-only): build, deploy (reburn FW / rebuild+redeploy utopx), rerun the EXACT pinned command + seed, confirm the signature is gone AND the run ended cleanly, then run a control with the patch removed. Record verdict in Run log + Investigation log. Only a VERIFIED fix proceeds to commit-fix (Phase 9.5)'
    status: pending
  - id: write-findings
    content: 'Copy templates/findings.md to FINDINGS_<ticket#>.md in the ticket dir and fill it in: issue summary, branch/tag, root cause with code evidence + attribution, proposed fix (diff), verification results, next steps. Start it as soon as a root-cause hypothesis exists; MANDATORY deliverable regardless of whether commit-fix runs this session'
    status: pending
  - id: commit-fix
    content: 'Commit the fix in Gerrit format — title [Type][Subsystem] + numbered body + "Issue: <ticket#>" + "Reviewed By: AI, Yanku" + auto Change-Id; author Peter Xiang <pexiang@nvidia.com>. Commit/push only when the user asks'
    status: pending
isProject: false
---

# <Reproduce Redmine bug #NNNNN: short title>

NOTE: This template turns **a single Redmine bug URL** into a local reproduction of
      the **same failure**. It is feature/device-agnostic — every machine, device,
      MST node, FW version, INI, test-tool commit, command, and seed is *derived from
      the ticket*, not hardcoded. It targets NVIDIA FW-verification regression bugs
      (MARS-filed: tracker "Bug SW" or "Task" tagged `regression`, test tool = utopx /
      verix, device = ConnectX / BlueField). The success criterion for a BUG repro is
      **observing the same fatal/signature locally**, not a green test.

      A fully worked example (Redmine #5090131, BRONCO/BF4) is in the Appendix — read it
      alongside the phases; it shows exactly what each field/attachment yields.

> **SSH ACCESS:** read the current agent's `references/hosts/<runtime>.md` adapter before using
> the commands in this plan. Claude Code and Codex have different permission and long-process
> behavior; do not copy one runtime's workaround into the other.

## Step 0 — Create the storage destination for this ticket

Before anything else, create a per-ticket working dir and put your instantiated plan there:

```bash
mkdir -p /auto/fwgwork1/$USER/bugZilla/<ticket#>_<core>/regression_ini
mkdir -p /auto/fwgwork1/$USER/bugZilla/<ticket#>_<core>/tools
```
- **`<ticket#>`** = the Redmine number (e.g. `5090131`).
- **`<core>`** = ≤2 words of the issue's essence, taken from the title — and
  **side-agnostic**: do NOT name it after the test tool, because the root cause may turn out
  to be FW *or* tool. E.g. #5090131 ("[UTOPX] cmd_hca_cap actual < expected …") →
  `5090131_cap_mismatch` (the essence is the cap mismatch), **not** `5090131_utopx`.

Then, inside that dir:
1. Save your **filled-in (delegated) copy of this plan** — copy this template, replace every
   `<placeholder>` with the values you decode in Phase 1–2, and write it as
   `repro_plan_<ticket#>.md`.
2. Copy the regression's burned INI (and the release-default INI) into `regression_ini/`
   (Phase 5).
3. **As soon as Phase 1–2 are decoded — before the box is even free — write the two automation
   scripts** into `tools/` (Phase 9b): `tools/env_rebuild_<box>.sh` (runs from dev box) and
   `tools/per_run_reset.sh` (runs on reg box). The whole point is that the moment the lock lands
   you can start reproducing instead of starting to write. Everything they need (FW/INI/PSID, the
   mlxconfig set, the per-case reset command, the verbatim tool command + seed) is already in the
   session tarball — none of it requires the box. Mark both **UNVERIFIED** in their headers until
   the first run reproduces the signature, and keep every destructive path opt-in.

4. **Keep the `## Investigation log` section of this same file updated LIVE** as you read source
   and form hypotheses - that section, not the chat transcript, is the durable record of the
   root-cause work.
5. **Once a fix candidate exists, verify it on the box (Phase 9.5) before Gerrit** - build, deploy,
   rerun the pinned command + seed, confirm the signature is gone, and run a control with the patch
   removed.
6. **Copy `templates/findings.md` -> `FINDINGS_<ticket#>.md`** in this same dir as soon as a
   root-cause hypothesis exists, and finish it once verification lands. It is the mandatory
   deliverable (issue, root cause + evidence, fix, verification results, next steps) - not
   optional, and not deferred to a "write-up later".

This dir is the single home for everything about the repro (plan, INIs, run logs, scripts, notes,
the live investigation log, and the findings report).

## Goal

Reproduce the failure described in **<Redmine URL>** by recreating the regression run
**bit-for-bit**: the **same server** (from `setup_id`) + exact FW build + INI + test-tool
binary + **the exact command, scenario, iter/ops, env, seed, and bring-up steps** the
regression ran. Anything you change (host, command, iter count, bring-up shortcut) can hide
or fabricate the failure — so change nothing.

- Redmine: <URL>
- Failure signature (from the subject / Fatal message / verix log): `<paste the exact string>`
- **Repro = SUCCESS** when the local run prints the **same** signature. (For a bug, a
  PASS means you did NOT reproduce it — keep digging or note env divergence.)

## Environment (fill in after Phase 1 — all derived from the ticket)

- Test machine: <e.g. m-fwreg-029 — from setup_id>
- Dev/build box: <docker+toolchain box you build on, e.g. m-fwdev-167>
- DUT / device family: <e.g. BRONCO (BF4) — from Chips / setup_id>
- MST device: <e.g. /dev/mst/mt41695_pciconf0 — from attachment names / print_mst_devs log>
- Running FW at failure: <e.g. 82.48.1632 — from flint_nv_dump_* attachment filename>
- Regression stream / branch: <e.g. FUR_2026_Jan_VR_Fractal_ES_from_48_0386 — from subject>
- Test tool: <e.g. utopx → utopx.exe>
- FW source repo: **`/auto/fwgwork1/$USER/golan_fw2`** (the repro-dedicated clone — use this, not the main `golan_fw`)
- Test-tool repo + binary: **`/auto/fwgwork1/$USER/utopx2`** → `utopx.exe` (the repro-dedicated clone — use this, not the main `utopx`)

> **Repro uses the `2` clones** (`golan_fw2` / `utopx2`) — the designated repro/triage
> checkouts, kept apart from the primary feature repos (`golan_fw` / `utopx`). They may
> already be on another ticket's branch with uncommitted work, so Phase 4 does
> `git stash -u` before checking out the regression pin. All `<FW source repo>` /
> `<test tool repo>` placeholders below = these two paths.
- MARS results root (NFS): <results_dir from the ticket's view_log.php URL>
- MARS coordinates: setup_id=<...> session_id=<...> key_id=<...>

---


---

> **The phase-by-phase procedure is not in this file.** Copy this skeleton to
> `/auto/fwgwork1/$USER/bugZilla/<ticket#>_<core>/repro_plan_<ticket#>.md`, fill in the
> Environment table and the todos, and work through
> `~/myGit/crosslv/assets/skills/regression-repro/references/procedure.md` (Phases 1-11).
> Accumulated traps and a worked example: `references/key-learnings.md`.

---

## Investigation log (update LIVE, as you find things - NOT at the end)

> This is the durable record of root-cause work. The chat transcript is not a record - it is gone
> next session. Append a dated entry every time you read source, form or kill a hypothesis, or
> find attribution evidence. A dead end is worth recording: section 4 of the eventual
> `FINDINGS_<ticket#>.md` ("false positives / dead ends") is written from these entries.
>
> Keep superseded entries **in place**, marked `SUPERSEDED by <date> entry - <why>`. Deleting a
> wrong conclusion destroys the only evidence that it was already ruled out.

### <date> - <what you are investigating>
- **Reading:** `<file:line>` - <what the code does / what you expected>
- **Evidence:** `git blame` -> <commit, author, date>; `git log --author=<name> -- <path>` -> <context>
- **Finding / hypothesis:** <...>
- **Status:** <open | confirmed | refuted | superseded>

---

## Run log (update LIVE, every run)

| Date | Seed | Result | Reproduced signature? | FW / tool pin | Notes |
|---|---|---|---|---|---|
| <date> | <seed> | FAIL/PASS | ✅ same / ❌ diverged | <ver> | <observed signature or divergence> |

---
