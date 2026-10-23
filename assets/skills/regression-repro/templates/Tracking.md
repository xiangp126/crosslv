# Redmine #<ticket#> — <short title>

> Last updated: <YYYY-MM-DD HH:MM CST> · [<ticket#>](https://redmine.nvidia.com/issues/<ticket#>)
> The ticket's status page. Every run and the step-by-step record: [Ledger.md](Ledger.md). Root cause and fix: [Defects.md](Defects.md).

## 1. Status

**Status**: `<IN PROGRESS | ROOT-CAUSE FOUND | FIX VERIFIED | COMMITTED | VOID>` — <one sentence: where the ticket stands and what it waits for; the change as [<num>](https://git-nbu.nvidia.com/r/c/<project>/+/<num>) PS<n> once pushed>

- **Waiting for**: <who, what, since when; the path of the draft or message>
- **Next steps**: <action — who>
- **Decisions needed from Peter**: <question; the facts and the options>

## 2. Goal

Reproduce the failure of [<ticket#>](https://redmine.nvidia.com/issues/<ticket#>) by recreating the regression run bit for bit: the same
server, FW build, INI, test-tool binary, command, scenario, iterations, environment, seed and
bring-up steps.

- Failure signature (verbatim): `<exact string from the subject, the FATAL or the verix log>`
- Success: the local run prints the same signature.

## 3. Environment

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

## 4. Reproduction steps

<Where the commands run (the dev box, which user); the same steps with the scripts are the last
subsection.>

### 4.1 Lock the box

```bash
~/myGit/crosslv/assets/skills/noga-lock/scripts/noga_watchdog.sh <box> --until-locked
python3 /.autodirect/sw_tools/Internal/Noga/RELEASE/latest/cli/noga_manage.py -q -t server -n <box> | grep lock_owner
```

Expected: `LOCK_ACQUIRED <time>` (or `ALREADY_OURS <time>`), then `Status.lock_owner = <user>`.
While someone else holds the box, the first command waits for it, checking every 15 s; it never
locks over a live lease.

Right after the lock, the renewal watchdog:

```bash
mkdir -p <ticket dir>/logs/lock
nohup bash ~/myGit/crosslv/assets/skills/noga-lock/scripts/noga_watchdog.sh <box> >> <ticket dir>/logs/lock/watchdog_<box>.log 2>&1 &
```

Expected: <the watchdog's first heartbeat line in its log>.

### 4.2 Check the box before touching it

```bash
ls -td /auto/sw_regression/host_fw/HCA_CORE_FWV/MARS/conf/results/<setup_id>/*/ | head -1 | xargs -I{} sh -c 'echo {}; ls {}*.tgz'
ssh -o BatchMode=yes <user>@<box> 'ps -eo cmd | grep -cE "[u]topx\.exe|[R]egTools|[m]ars_tests|[F]wreset|[m]lxburn"'
ssh -o BatchMode=yes <user>@<box> 'md5sum <deployed test tree>/<binary>'
ssh -o BatchMode=yes <user>@<box> 'sudo mst start >/dev/null; sudo flint -d <MST device> q full' > <ticket dir>/logs/flint_before_manual.log
```

Expected: <the setup's newest MARS session has its `.tgz` — without it the session is still running
and the box is not touched, whatever NOGA shows; 0 processes; the md5 of the binary that will run;
what to do when it differs>.

### 4.3 <The session's first setup step>

<One subsection per setup step of the session, in the session's order — reboots, burn, NV clear,
mlxconfig, agents — each with the regression step's name, its full command and the expected
output. A step done twice is written out twice.>

```bash
<full command>
```

Expected: <the line that shows the step worked, verbatim>.

### 4.<n> Per-case reset and start state

```bash
<the regression's per-case reset, full command>
<the full command that prints the start state the case needs, such as the NV checksum>
```

Expected: <the value the failing case started from>; anything else stops here.

### 4.<n+1> Run the case

```bash
ssh -o BatchMode=yes <user>@<box> "cd <test tree> && <the case command from run_case>" > <ticket dir>/logs/<label>.log 2>&1; echo "rc=$?"
```

<Each difference from the regression's command, and why.>

### 4.<n+2> Check the signature

```bash
sed 's/\x1b\[[0-9;]*m//g' <ticket dir>/logs/<label>.log | grep -a -m1 'FATAL :'
```

Expected, timestamps aside:

```text
<the first FATAL of the reproducing run, verbatim>
```

### 4.<n+3> Verify the fix

<Apply the fix to a build of the same commit and build it; run the reset, the case and the check
from that tree; then the control with the fix removed; then restore the tree. Full commands, as
above.>

### 4.<n+4> The same steps with the scripts

<Which manual steps the rebuild script and the per-run script cover, and which they leave out.>

```bash
bash <ticket dir>/tools/env_rebuild.sh --burn --yes
ssh -o BatchMode=yes <user>@<box> 'bash <ticket dir>/tools/per_run.sh --seed <N>'
```

Expected: <the last lines each script prints, verbatim; the verdict and its exit code; where each
run's files and the summary go>.

## 5. Documents

| File | Content |
|---|---|
| [Defects.md](Defects.md) | the failure, its root cause, the fix and its verification |
| [Ledger.md](Ledger.md) | the Run log and the step-by-step record |
| [tools/lab.conf](tools/lab.conf) | the box, image, INI, NV recipe and hooks of this ticket |
| [ini/](ini/) | the INI the regression burned, the release default, their diff |
| [report_<MMDD>_<box>_<sha>.md](reports/report_<MMDD>_<box>_<sha>.md) | one test campaign each |
| [FIX_<topic>.patch](patches/FIX_<topic>.patch) | the fix |
| [attach/](attach/) | the MARS artifacts for the ticket, with `manifest.tsv` |
| [redmine/](redmine/) | what goes to Redmine, in English |

Directories: run logs in [logs/](logs/), with the environment, CI, fwtrace, lock and build logs in
[logs/env_rebuild/](logs/env_rebuild/), [logs/ci/](logs/ci/), [logs/fwtrace/](logs/fwtrace/),
[logs/lock/](logs/lock/), [logs/build/](logs/build/); FW images in [fw/](fw/); patches — the fix,
rejected candidates, diffs of uncommitted trees — in [patches/](patches/); reports in
[reports/](reports/); drafts in [drafts/](drafts/).
