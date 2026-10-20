---
name: <Reproduce Redmine bug #NNNNN locally>
overview: <Given only a Redmine bug URL, recreate the regression's exact env and reproduce the SAME failure signature locally>
todos:
  - id: setup-dir
    content: Create the ticket dir /auto/fwgwork1/$USER/bugZilla/<ticket#>_<core> (references/ticket-documents.md §0) and save this plan there as Repro_<ticket#>.md
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
    content: 'While waiting for the box: copy templates/lab-box/ into tools/ and fill in lab.conf from the tarball data (Phase 9b); leave VERIFIED= empty until the first repro. Do NOT wait for a confirmed repro'
    status: pending
  - id: pin-repos
    content: 'In BOTH repos create a per-ticket worktree off the *2 clone on the pin branch <ticket#>_<topic> at the failing version (git -C <clone> worktree add -b <ticket#>_<topic> /auto/fwgwork1/$USER/golan_fw_<ticket#> or utopx_<ticket#> <sha>) — never a detached HEAD, never the clone''s own checkout; init submodules recursively; confirm with git branch --show-current + git describe --tags'
    status: pending
  - id: reproduce-ini
    content: Copy the regression-generated INI (not the release default) into regression_ini/ and diff it
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
    content: Confirm the failure reproduced (same signature) — or document how it diverged — in the Run log
    status: pending
  - id: recover-env
    content: If the box drifted (a regression ran since), rebuild + repin + reburn before trusting a result
    status: pending
  - id: log-investigation
    content: 'From the moment you start reading FW/tool source: append dated entries to the Investigation log below AS YOU GO (hypothesis, file:line evidence, git blame / git log --author attribution) - not reconstructed at the end. A wrong conclusion is struck through in place, never deleted'
    status: pending
  - id: verify-fix
    content: 'Once a candidate fix exists (golan_fw2 and/or utopx2 - never assume FW-only): build, deploy (reburn FW / rebuild+redeploy utopx), rerun the EXACT pinned command + seed, confirm the signature is gone AND the run ended cleanly, then run a control with the patch removed. Record the verdict in the Run log + Investigation log. Only a VERIFIED fix proceeds to commit-fix (Phase 9.5)'
    status: pending
  - id: write-rc
    content: 'Copy templates/Rc.md to Rc_<ticket#>.md in the ticket dir and fill it in: issue summary, branch/tag, root cause with code evidence + attribution, proposed fix (diff), verification results, next steps. Start it as soon as a root-cause hypothesis exists; MANDATORY deliverable whether or not commit-fix runs this session'
    status: pending
  - id: release-box
    content: 'Only when Peter says to release the box: jmake --reg-free <machine> (jk = jmake) after stopping your own watchdog / noga_wait for it. Never jmake --reg-cancel, which releases every box you hold'
    status: pending
  - id: commit-fix
    content: 'Commit the verified fix on the fix branch fix_<ticket#>_<topic>_<line> (Phase 11); write the commit message per skill gerrit-change; author Peter Xiang <pexiang@nvidia.com>. Commit/push only when the user asks'
    status: pending
isProject: false
---

# Redmine #<ticket#> — <short title>

> The plan, edited in place, then the Investigation log and the Run log, only appended. The
> conclusion is `Rc_<ticket#>.md`. Procedure: skill `regression-repro`,
> `references/procedure.md`.

## Goal

Reproduce the failure of [<ticket#>](https://redmine.nvidia.com/issues/<ticket#>) by recreating the regression run bit for bit: the same
server, FW build, INI, test-tool binary, command, scenario, iterations, environment, seed and
bring-up steps.

- Redmine: [<ticket#>](https://redmine.nvidia.com/issues/<ticket#>)
- Failure signature (verbatim): `<exact string from the subject, the FATAL or the verix log>`
- Success: the local run prints the same signature.

## Environment

Decoded from the ticket.

| Item | Value | Source |
|---|---|---|
| Test machine | <e.g. m-fwreg-029> | setup_id |
| Dev / build box | <e.g. m-fwdev-167> | — |
| Device family | <e.g. BRONCO (BF4)> | Chips, setup_id |
| MST device | <e.g. /dev/mst/mt41695_pciconf0> | attachment names, print_mst_devs log |
| FW at failure | <e.g. 82.48.1632> | flint_nv_dump_* attachment |
| Regression stream / branch | <e.g. FUR_2026_Jan_VR_Fractal_ES_from_48_0386> | subject |
| Test tool | <e.g. utopx → utopx.exe> | — |
| FW worktree | `/auto/fwgwork1/$USER/golan_fw_<ticket#>` off `golan_fw2`, branch `<ticket#>_<topic>` at `<sha>` | Phase 4 |
| Test-tool worktree | `/auto/fwgwork1/$USER/utopx_<ticket#>` off `utopx2`, branch `<ticket#>_<topic>` at `<sha>` | Phase 4 |
| MARS results root | <results_dir> | view_log URL |
| MARS coordinates | setup_id=<...> session_id=<...> key_id=<...> | view_log URL |

## Investigation log

### 1. <short title: what was found, a few words>

<YYYY-MM-DD HH:MM CST> — <what was asked or found, stated as a conclusion>

<Peter's instruction verbatim, when the entry starts from one>

- **Did**: <source read (`file:line`); commands; build (rc, `error:` count, image md5, log path)>
- **Result**: <the finding and its evidence — `git blame` / `git log --author` attribution, the
  verbatim signature, log paths; verdict: confirmed / refuted / open>
- **Next**: <one line>

## Run log

| # | Date | Box | FW / tool pin | Seed | Signature | Ended how | Log |
|---|---|---|---|---|---|---|---|
| 1 | <date> | <box> | <version / sha> | <seed> | <same / diverged / none> | <TEST FAILED / PASSED / VOID> | `<path>` |
