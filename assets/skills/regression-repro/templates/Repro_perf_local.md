---
name: <Title of the investigation>
overview: <One-line summary of what this plan covers>
todos:
  - id: preflight
    content: Verify test environment (device, interfaces, docker image)
    status: pending
  - id: capture-preburn
    content: Capture current firmware state as restore point
    status: pending
  - id: test-baseline
    content: Test baseline (known working) firmware
    status: pending
  - id: test-regressed
    content: Test regressed (known bad) firmware
    status: pending
  - id: bisect
    content: Bisect the regression range to find first bad release
    status: pending
  - id: commit-level
    content: Build private images and identify the root cause commit
    status: pending
  - id: compare
    content: Fill consolidated comparison table
    status: pending
  - id: conclude
    content: State the root cause and next steps
    status: pending
isProject: false
---

# <Title of the Investigation>

NOTE: This is the LOCAL version -- execute directly on the test server.
      No SSH wrappers needed -- all commands run locally.
      Use this version when no power cycle is needed between test runs.
      If the test requires power cycling between runs, use the REMOTE version
      instead (execute from a dev machine, SSH into the test server).

## Goal

<Describe what regression you are investigating, what the expected outcome is,
and link to the Redmine/NVBugs ticket.>

Redmine: [<ticket#>](https://redmine.nvidia.com/issues/<ticket#>)

## Regression Info

- Reported version: <e.g. 28.49.0356>
- Last known working: <e.g. 28.48.1000>
- Regression range: <working> to <broken>
- Bisection result: <filled in during execution>
- Root cause commit: <filled in during execution>

## Environment

- Test machine: <hostname> (this machine)
- DUT: <device type, e.g. ConnectX-7 (Chimera)>
- MST device: <e.g. /dev/mst/mt4129_pciconf0>
- Interfaces: <e.g. eth22, eth23>
- DOCA/OFED: <version>
- MFT: <version>
- Host OS: <version>
- Docker image: <e.g. nvcr.io/nvstaging/doca/doca_firefly:latest-amd64-host-dev>
- Firmware workspace: <path to golan_fw repo>
- Private image archive: <path, e.g. /auto/fwgwork1/pexiang/mLX>
- Plan location: <path to this file>
- Report: `Rc_<ticket#>.txt` in the ticket dir, from `templates/Rc_perf_local.txt`

## Pre-burn: Capture Current Firmware State

Before burning any image, record the current firmware info as a restore point:

```bash
sudo flint -d <device> q full
```

## Release-Level Bisection

### Burn Commands

Official release:
```bash
jmake --burn-official <version> --device <device> --fw-reset
```

Private image (must specify -w for golan_fw directory):
```bash
jmake --burn --firmware <image_path> --device <device> --fw-reset -w <golan_fw_path>
```

### Per-Run Procedure

For each firmware version:

1. If the previous run left the device stuck, it needs a power cycle, which this server cannot do
   to itself and keep the session: continue with the REMOTE version (`Repro_perf_remote.md`).

2. Restart MST and verify device is healthy:

```bash
sudo mst restart
sudo flint -d <device> q | head -3
```

3. Burn the firmware image.

4. Verify the running firmware version matches expected:

```bash
sudo flint -d <device> q | head -3
```

5. Run the repro test.

6. After the test window, check for errors and device health:

```bash
sudo docker logs <container_id> 2>&1 | grep -iE "CRITICAL|ERROR|Failed|TIMEOUT"
sudo flint -d <device> q | head -3
```

7. Stop the container:

```bash
sudo docker stop <container_id>
```

8. Record the result in the report immediately.

### Repro Test Command

Start in detached mode for non-interactive testing:
```bash
sudo docker run --rm -d --privileged --net=host \
  <all repro flags here> \
  <docker_image> /entrypoint.sh
```

Or run interactively (Ctrl+C to stop):
```bash
sudo docker run --privileged --net=host \
  <all repro flags here> \
  -it <docker_image> /entrypoint.sh
```

<Paste the exact repro command here. Do not modify it across runs.>

### Pass/Fail Criteria

<Define what constitutes PASS and FAIL for this specific investigation.
Example:
- PASS: no error signatures in logs AND device remains accessible via flint
- FAIL: error signatures appear OR flint returns MFE_CMDIF_TIMEOUT_ERR
>

### Recovery After FAIL

If the test leaves the device stuck:

1. Confirm device is stuck:

```bash
sudo flint -d <device> q | head -3
```

2. It needs a power cycle, which this server cannot do to itself and keep the session: continue
   with the REMOTE version (`Repro_perf_remote.md`), which recovers it from the dev machine.

## Commit-Level Confirmation

### Build Workflow

Build must be done on a build machine with access to the golan_fw repo.
The built images are shared via NFS so the test server can access them.

For each commit under test:

1. Reset repo to clean base, then to commit:

```bash
cd <golan_fw_repo>
git checkout <working_branch>
git reset --hard <base_tag>
git reset --hard <commit_id>
```

2. Build:

```bash
jmake -m <target> --patch
```

3. Archive immediately (mv, not cp):

```bash
mv <build_output>.mlx <archive_dir>/fw-<device>-<commit_id>.mlx
```

4. Build one commit at a time. Do not batch builds.

Important: build in the ticket's own worktree off `golan_fw2` (skill
`regression-repro`, Phase 4), never in a clone's own checkout and never in /tmp
(limited space).

### Test Workflow

For each private image (run on the test server):

1. Burn the image:

```bash
sudo mst restart
jmake --burn --firmware <image_path> --device <device> --fw-reset -w <golan_fw_path>
```

2. Verify running firmware version:

```bash
sudo flint -d <device> q | head -3
```

3. Run the repro test.

4. Check results:

```bash
sudo docker logs <container_id> 2>&1 | grep -iE "CRITICAL|ERROR|Failed|TIMEOUT"
sudo flint -d <device> q | head -3
```

5. Record in report immediately before proceeding.

### Decision Rule

The root-cause commit is the first bad commit:
- If commit N is PASS and commit N+1 is FAIL, then N+1 is the root cause.

Shortcut: test the suspected commit and the one immediately before it first.
If suspect FAIL and previous PASS, confirmed. Then double-confirm with one
commit below and one above the boundary.

## Report Update Contract

The report must be updated live, not as a post-processing step.
After every single test run, record:
- Firmware version / commit tested
- PASS or FAIL
- Error signatures (if any)
- Whether power cycle was required
- Any anomalies

Do not proceed to the next test until the current result is documented.
