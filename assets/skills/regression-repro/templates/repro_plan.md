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
    content: malloc the SAME server from setup_id (jmake --reg-malloc <machine>); if busy, run the monitor script polling its lock every 15s and grab it the instant it frees; --reg-extend to keep it; never release it without Peter's explicit permission. Never substitute a different host. Unknown command → ask Glean. Capture the current FW as a restore point
    status: pending
  - id: extract-regression
    content: From the MARS session tarball, read new_burn_fw + get_last_commit + run_case (FW/.mlx/INI/PSID + test-tool commit + exact command & seed) AND the session's own setup steps (clear_nv_data / SetMlxConfig / load_udriver / per-case Fwreset) — the scripts must replay these
    status: pending
  - id: write-scripts
    content: 'While waiting for the box: write tools/env_rebuild_<box>.sh + tools/per_run_reset.sh from the tarball data (Phase 9b). Mark both UNVERIFIED, make destructive paths opt-in, gate both on Noga lock ownership. Do NOT wait for a confirmed repro'
    status: pending
  - id: pin-repos
    content: 'In BOTH repos create a per-ticket worktree off the *2 clone on the pin branch <ticket#>_<topic> at the failing version (git -C <clone> worktree add -b <ticket#>_<topic> /auto/fwgwork1/$USER/golan_fw_<ticket#> or utopx_<ticket#> <sha>) — never a detached HEAD, never the clone''s own checkout; init submodules recursively; confirm with git branch --show-current + git describe --tags'
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
    content: 'From the moment you start reading FW/tool source: append DATED entries to the Investigation log below AS YOU GO (hypothesis, file:line evidence, git blame / git log --author attribution) - not reconstructed at the end. Keep superseded conclusions, mark them SUPERSEDED, never delete'
    status: pending
  - id: verify-fix
    content: 'Once a candidate fix exists (golan_fw2 and/or utopx2 - never assume FW-only): build, deploy (reburn FW / rebuild+redeploy utopx), rerun the EXACT pinned command + seed, confirm the signature is gone AND the run ended cleanly, then run a control with the patch removed. Record the verdict in Run log + Investigation log. Only a VERIFIED fix proceeds to commit-fix (Phase 9.5)'
    status: pending
  - id: write-findings
    content: 'Copy templates/findings.md to FINDINGS_<ticket#>.md in the ticket dir and fill it in: issue summary, branch/tag, root cause with code evidence + attribution, proposed fix (diff), verification results, next steps. Start it as soon as a root-cause hypothesis exists; MANDATORY deliverable whether or not commit-fix runs this session'
    status: pending
  - id: commit-fix
    content: 'Commit the verified fix on the fix branch fix_<ticket#>_<topic>_<line> (Phase 11); write the commit message per skill gerrit-change; author Peter Xiang <pexiang@nvidia.com>. Commit/push only when the user asks'
    status: pending
isProject: false
---

# <Reproduce Redmine bug #NNNNN: short title>

NOTE: This plan turns **a single Redmine bug URL** into a local reproduction of the **same
      failure**. It is feature/device-agnostic: every machine, device, MST node, FW version, INI,
      test-tool commit, command and seed is *derived from the ticket*, never hardcoded. Scope:
      NVIDIA FW-verification regression bugs filed by MARS (tracker "Bug SW" or "Task" tagged
      `regression`; test tool utopx / verix; device ConnectX / BlueField). Success for a BUG repro
      = **the same fatal/signature observed locally**, not a green test.

      Worked example of what each field/attachment yields (Redmine #5090131, BRONCO/BF4): the
      Appendix of `~/myGit/crosslv/assets/skills/regression-repro/references/key-learnings.md`.

> **SSH ACCESS:** before using the commands in this plan, read the current agent's adapter,
> `~/myGit/crosslv/assets/skills/regression-repro/references/hosts/<runtime>.md`. Claude Code and
> Codex differ in permissions and long-process behavior; never copy one runtime's workaround into
> the other.

## Step 0 — Create the storage destination for this ticket

First, create the per-ticket working dir:

```bash
mkdir -p /auto/fwgwork1/$USER/bugZilla/<ticket#>_<core>/regression_ini
mkdir -p /auto/fwgwork1/$USER/bugZilla/<ticket#>_<core>/tools
```
- **`<ticket#>`** = the Redmine number (e.g. `5090131`).
- **`<core>`** = ≤2 words of the issue's essence, taken from the title, and **side-agnostic**:
  never the test tool's name, because the root cause may turn out to be FW *or* tool. E.g.
  #5090131 ("[UTOPX] cmd_hca_cap actual < expected …") → `5090131_cap_mismatch` (the essence is
  the cap mismatch), **not** `5090131_utopx`.

Then, inside that dir:
1. Save this plan with every `<placeholder>` replaced by the values decoded in Phases 1–2, as
   `repro_plan_<ticket#>.md`.
2. Copy the regression's burned INI (and the release-default INI) into `regression_ini/`
   (Phase 5).
3. **As soon as Phases 1–2 are decoded — before the box is free — write the two automation
   scripts** into `tools/` (Phase 9b): `tools/env_rebuild_<box>.sh` (runs from the dev box) and
   `tools/per_run_reset.sh` (runs on the reg box), so you start reproducing the moment the lock
   lands. Everything they need (FW/INI/PSID, the mlxconfig set, the per-case reset command, the
   verbatim tool command + seed) is in the session tarball; none of it needs the box. Mark both
   **UNVERIFIED** in their headers until the first run reproduces the signature; keep every
   destructive path opt-in.
4. **Update the `## Investigation log` section of this file LIVE** as you read source and form
   hypotheses — it, not the chat transcript, is the durable record of the root-cause work.
5. **Verify a fix candidate on the box (Phase 9.5) before Gerrit:** build, deploy, rerun the
   pinned command + seed, confirm the signature is gone, and run a control with the patch removed.
6. **Copy `templates/findings.md` → `FINDINGS_<ticket#>.md`** into this dir as soon as a
   root-cause hypothesis exists; finish it once verification lands. It is the mandatory
   deliverable (issue, root cause + evidence, fix, verification results, next steps) — never
   deferred to a later write-up.

This dir is the single home for everything about the repro: plan, INIs, run logs, scripts, notes,
the live investigation log, and the findings report.

## Goal

Reproduce the failure described in **<Redmine URL>** by recreating the regression run
**bit-for-bit**: the **same server** (from `setup_id`) + exact FW build + INI + test-tool binary +
**the exact command, scenario, iter/ops, env, seed, and bring-up steps** the regression ran. Any
change (host, command, iter count, bring-up shortcut) can hide or fabricate the failure — change
nothing.

- Redmine: <URL>
- Failure signature (from the subject / Fatal message / verix log): `<paste the exact string>`
- **Repro = SUCCESS** when the local run prints the **same** signature. (For a bug, a PASS means
  you did NOT reproduce it — keep digging or note the env divergence.)

## Environment (fill in after Phase 1 — all derived from the ticket)

- Test machine: <e.g. m-fwreg-029 — from setup_id>
- Dev/build box: <docker+toolchain box you build on, e.g. m-fwdev-167>
- DUT / device family: <e.g. BRONCO (BF4) — from Chips / setup_id>
- MST device: <e.g. /dev/mst/mt41695_pciconf0 — from attachment names / print_mst_devs log>
- Running FW at failure: <e.g. 82.48.1632 — from flint_nv_dump_* attachment filename>
- Regression stream / branch: <e.g. FUR_2026_Jan_VR_Fractal_ES_from_48_0386 — from subject>
- Test tool: <e.g. utopx → utopx.exe>
- FW source repo: worktree **`/auto/fwgwork1/$USER/golan_fw_<ticket#>`** off the repro-dedicated clone `golan_fw2` (not the main `golan_fw`)
- Test-tool repo + binary: worktree **`/auto/fwgwork1/$USER/utopx_<ticket#>`** off the repro-dedicated clone `utopx2` → `utopx.exe` (not the main `utopx`)

> **Repro uses the `2` clones** (`golan_fw2` / `utopx2`), the designated repro/triage clones,
> kept apart from the primary feature repos (`golan_fw` / `utopx`). Their own checkouts may be on
> another ticket's branch with uncommitted work, so Phase 4 never checks out inside them: it pins
> each repo in a per-ticket worktree. Every `<FW source repo>` / `<test tool repo>` placeholder
> means these two worktrees.
- MARS results root (NFS): <results_dir from the ticket's view_log.php URL>
- MARS coordinates: setup_id=<...> session_id=<...> key_id=<...>

---


---

> **The phase-by-phase procedure is not in this file.** Copy this skeleton to
> `/auto/fwgwork1/$USER/bugZilla/<ticket#>_<core>/repro_plan_<ticket#>.md`, fill in the
> Environment table and the todos, and work through
> `~/myGit/crosslv/assets/skills/regression-repro/references/procedure.md` (Phases 1-11).
> Accumulated traps and the worked example:
> `~/myGit/crosslv/assets/skills/regression-repro/references/key-learnings.md`.

---

## Investigation log (update LIVE, as you find things - NOT at the end)

> The durable record of root-cause work; the chat transcript is gone next session. Append a dated
> entry every time you read source, form or kill a hypothesis, or find attribution evidence.
> Record dead ends too: section 4 of `FINDINGS_<ticket#>.md` ("false positives / dead ends") is
> written from these entries.
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
