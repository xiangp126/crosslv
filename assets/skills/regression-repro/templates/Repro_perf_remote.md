---
name: <Title of the investigation>
overview: <One-line summary of what this plan covers>
todos:
  - id: preflight
    content: Verify test environment (machine, device, interfaces, docker image)
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

NOTE: This is the REMOTE version -- execute from a local dev machine, SSH into
      the test server. Use this version when the test requires power cycling
      the server between runs (you cannot power cycle from the server itself
      and maintain the session).
      If no power cycle is needed between runs, use the LOCAL version instead.

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

- Test machine: <hostname>
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
- Report: `Rc_<ticket#>.txt` in the ticket dir, from `templates/Rc_perf_remote.txt`

## SSH Session Management

Establish a persistent SSH control socket once, then reuse for all commands:

```bash
# Open persistent connection (run once at start)
ssh -fNM -S /tmp/<hostname>.sock pexiang@<hostname>

# All subsequent commands use the control socket
ssh -S /tmp/<hostname>.sock pexiang@<hostname> '<command>'

# Close when done
ssh -S /tmp/<hostname>.sock -O exit pexiang@<hostname>
```

Note: If the server is power-cycled, the control socket will break.
Re-establish it after the server comes back online.

## Pre-burn: Capture Current Firmware State

Before burning any image, record the current firmware info as a restore point:

```bash
ssh -S /tmp/<hostname>.sock pexiang@<hostname> 'sudo flint -d <device> q full'
```

Note: `sudo` is required for `flint` and all firmware operations.

## Release-Level Bisection

### Burn Commands

Official release:
```bash
ssh -S /tmp/<hostname>.sock pexiang@<hostname> \
  '$HOME/.usr/bin/jmake --burn-official <version> --device <device> --fw-reset'
```

Private image:
```bash
ssh -S /tmp/<hostname>.sock pexiang@<hostname> \
  '$HOME/.usr/bin/jmake --burn --firmware <image_path> --device <device> --fw-reset -w <golan_fw_path>'
```

### Per-Run Procedure

For each firmware version:

1. If previous run left device stuck, power cycle first:

```bash
ssh -S /tmp/<hostname>.sock pexiang@<hostname> 'sudo ipmitool power cycle'
```

Wait for server to come back, then verify uptime to confirm reboot.

2. Re-establish SSH control socket if power-cycled.

3. Verify device is healthy:

```bash
ssh -S /tmp/<hostname>.sock pexiang@<hostname> \
  'uptime && sudo mst restart && sudo flint -d <device> q | head -3'
```

4. Burn the firmware image.

5. Verify the running firmware version matches expected:

```bash
ssh -S /tmp/<hostname>.sock pexiang@<hostname> 'sudo flint -d <device> q | head -3'
```

6. Run the repro test.

7. After the test window, check for errors and device health.

8. Record the result in the report immediately.

9. Power cycle the server before the next test.

### Repro Test Command

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
ssh -S /tmp/<hostname>.sock pexiang@<hostname> 'sudo flint -d <device> q | head -3'
```

2. Power cycle:

```bash
ssh -S /tmp/<hostname>.sock pexiang@<hostname> 'sudo ipmitool power cycle'
```

3. Wait for server, verify uptime confirms actual reboot.

4. Re-establish SSH control socket.

5. Verify device is accessible before proceeding.

## Commit-Level Confirmation

### Build Workflow

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

Important: Do not use /tmp or create separate worktrees for builds. Always
build in the current golan_fw working directory. /tmp may have limited space
and worktrees add unnecessary complexity.

### Test Workflow

For each private image:

1. Power cycle the server (fresh boot for every test).
2. Burn the image.
3. Verify running firmware version.
4. Run the repro test.
5. Check results.
6. Record in report immediately before proceeding.

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
