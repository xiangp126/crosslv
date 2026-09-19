## Key learnings (carry forward)

- **A regression bug ticket carries its own repro coordinates**: the `view_log.php` URL
  (`results_dir`/`setup_id`/`session_id`/`key_id`) + the `run_case`/`flint_nv_dump`
  attachments. Decode those first; everything else (machine, device, MST, FW, command,
  seed) follows.
- **Repro success = same signature, not a green run.** A PASS means you did not reproduce.
- **Reproduce on the SAME server, with the SAME command/env/steps/seed — bit-for-bit.**
  Use the `<machine>` from `setup_id`; never substitute another host or trim the command.
  Reserve it with `jmake --reg-malloc <machine>`, keep it alive with `jmake --reg-extend`,
  and **release it with `jmake --reg-cancel` when done**. If it's busy, **monitor its lock
  and grab it the instant it frees** (don't switch boxes). **Unknown reg/lab command → ask
  Glean (`glean_search`/`glean_chat`) before guessing.**
- **Three-way match or it's not a repro**: FW build + burned INI + test-tool *binary*.
- **The box drifts daily** — read the ticket's session, verify running FW with `flint q`.
- **`git checkout` doesn't touch the compiled binary** — after drift, rebuild; verify mtime.
- **Burn the regression-*generated* INI, not the release default**; cross-check vs the
  ticket's `dump_nv_data` attachment. Don't add your own nvconfig rows.
- **Pin `--seed`** from `run_case`; a pass on one seed ≠ pass on the next.
- **Reset between every run** (`jmake --fw-reset`); device/emulation state leaks.
- **One command per ssh**, reuse one SSH connection, drop the ControlMaster socket after
  any reboot. **Always fetch tags first.**
- **Some reg boxes aren't in the malloc pool.** `jmake --reg-malloc`/`--reg-mine` only see
  boxes labeled `HCA_FW_ALLOCATION_POOL_HOST`; dedicated BRONCO/BF boxes may carry only
  `PARTITION_NOGA_ALLOC_reg`. Lock those directly: `noga_manage.py -l -t server -n <box> -L
  <hours> -N "…"` (the `-t server` is mandatory), and confirm ownership via
  `noga_manage.py -q` — sqme won't show it.
- **Reuse the deployed binary.** The regression leaves its exact prebuilt `utopx.exe` + configs
  in `/tmp/mars_tests/<test-DB>/tests/` on the box — use it in place (no build) and confirm the
  commit via the run's "tarball git tag is: <describe>" line. Local build repos: `golan_fw2` /
  `utopx2` (never the active `[USE_THIS_WORKSPACE]` clone).
- **Commit convention** (Phase 11, Gerrit format): title `[<Type>][<Subsystem>] <summary>`,
  numbered-list body (`1.` `2.` `3.`; refactor → item 1 = "No logic change."), `Issue: <ticket#>`,
  `Reviewed By: AI, Yanku`, and an auto `Change-Id` from the commit-msg hook (never hand-written).
  Author **Peter Xiang `<pexiang@nvidia.com>`**. Commit/push only when the user asks.
- **Kill stale daemons before resetting.** A box out of rotation may still run a prior
  `utopx.exe --daemon` holding `/dev/udriver_*`; it makes fw_reset fail "Device is busy". Find
  via `fuser`/`ps`, kill, retry.
- **Same-PSID substitution is allowed ONLY with explicit user approval** — match the PSID
  (board), not just the family; verify the substitute is idle + healthy (last session Burn RC=0)
  and, ideally, already shows the signature in its own latest regression (§3b-bis).
- **Find same-PSID boxes via Noga, not MARS INI names.** The board PSID lives on the **NIC**
  resource (`Setup Automation.psid`); one query lists every board with it:
  `noga_manage.py -q -t nic -e "psid:<PSID>"` (e.g. `psid:MT_0000000704`). MARS-results/INI-name
  scans only see boxes that ran this suite and will FALSELY report "no other same-PSID box." A
  `mars_reg` lock on a box that is **down/unreachable** is a stale reservation, not a live run —
  verify with `ssh <box> hostname` (using the runtime adapter) + newest real session mtime. A same-PSID substitute often
  still needs its own `topology_<mode>.xml` authored (per-box entry_points/IPs) — see §3b-bis.
- **Some boxes are in a Noga partition `jmake --reg-malloc` refuses** ("Server is in partition
  virtio, allowed partitions are: e2e,mpi,automation,dev,perf,reg,userdev"). Lock those directly:
  `noga_manage.py -l -t server -n <box> -L <hours> -N "…"`; confirm with `noga_manage.py -q`.
- **Noga REST can be down (504) for hours** — malloc/minfo/`noga_manage -q` all share that
  backend. Probe `api_cmd=get_teams` with curl; wait it out in the background; never read a
  504 traceback as "box locked". `lock_time_out` is Israel time and auto-release lags — watch
  the `Status.status` flip, not the clock. (STM-only fallback: Noga's direct Oracle DB API.)
- **Health-check a substitute before grabbing it**: burn-step `status.txt` (RC) +
  `summary_results.json` (PASSED count) from its recent status-only tgz archives; the
  ini_files filename gives session→FW-version/PSID with no tarball at all. A box that can't
  burn FW is useless no matter how well its PSID/mode match.
- **A different fatal can be the same bring-up bug** at a different device state (`cmd_hca_cap`
  caps=0 vs `VerifyHealthBuffer` FW assert `ext_synd 0x817e`). Read the VHCA HCA_STAGE dump;
  re-burn fresh + regression fw_reset to chase the exact signature. **DPU/BF: never power-cycle**
  (breaks BareMetal ArmAgent) — memory utopx-bf3-repro-use-regression-fwreset.
- **Write env_rebuild + per_run_reset right after decoding the ticket (Phase 9b) — NOT after the
  first repro.** Waiting for a contended box takes hours; build the scripts in that window so the
  lock lands on a ready harness. Guard against false confidence with an `!!! UNVERIFIED !!!`
  banner, opt-in destructive paths, and warn-only gates that have no grounded baseline yet — not
  by delaying. The split is deliberate: `tools/env_rebuild_<box>.sh` (from dev box) handles slow
  one-time setup (burn, mlxconfig, verify); `tools/per_run_reset.sh` (on reg box) runs the
  per-attempt loop (mst start → FW gate → PCI gate → ARM → baseline Fwreset → buggy tool →
  post-run Fwreset → verdict). Both use `FORCE=1` guards and color-coded output. `chmod +x` both.
- **A MARS helper's `--session_id` can select CACHED STATE from the original run, not just label
  the log.** `Fwreset.py` caches the resolved FW version in
  `/tmp/fwreset_wrapper_<session_id>__dev_mst_<dev>.txt` and **reuses the file if it exists**. On a
  box whose `/tmp` survives reboots (many do — check for files older than `uptime`), passing the
  ticket's session id in the name of bit-for-bit fidelity makes the helper re-apply **that day's**
  FW assumption to **today's** device: it invoked the `rel-…_0098` reset script against a
  `32.51.0100` card → `version is not supported` → `could not obtain tools semaphore` →
  `-ERROR- Fwreset failed!!`, which the baseline gate correctly scored as an abort rather than a
  repro. Fix: give helper tools a **repro-specific session id** and **purge their cache before every
  run**; keep the original id only where it is genuinely part of the command under test (e.g.
  utopx's own `--seed`/`--session_id`). Fidelity means the *command under test*, not every
  incidental id you can copy.
- **Every script that touches the box must first verify `Status.lock_owner == $USER` via Noga.**
  `hostname` is not a guard: the nightly regression runs on that same box, so an `mst start`,
  `modprobe`, or `Fwreset` fired while `mars_reg` holds the lock silently corrupts a live session
  (and the session you are corrupting is usually the one you are waiting on). Refuse and exit
  non-zero unless the owner is you.
  Key lesson: **SSH ControlMaster** (`-o ControlMaster=auto -o ControlPath=<mux> -o
  ControlPersist=28800`) in env_rebuild is mandatory — NFS-home auth fails for ~30 s after
  power-cycle; a single authenticated master socket avoids all subsequent auth races.
- **A single-signal verdict will eventually lie to you — require CORE evidence + a passing
  baseline.** Decide on the defect's *direct effect* (a before/after state diff you captured),
  not on a downstream symptom like "the next script failed". Hard-gate the baseline; a warning
  that execution continues past is worthless. Also assert the tool binary is the **pre-fix**
  commit, and emit `RUN VOID` when the tool never initialised instead of scoring it as a repro.
  (#5138907 declared success while the baseline was already failing, the tool had never started,
  and the syndrome count was zero.)
- **An env-setup side effect can perfectly mimic the ticket's signature.** #5138907's signature
  was "PCI address changed"; the address really did move 81→83 — because `mlxconfig` enabled the
  emulated PCIe switch, inserting bridges at 81/82 and shifting endpoints to 83. Capture the
  baseline **after env_rebuild, immediately before the tool runs**, and observe the expected
  topology rather than reasoning it out — a gate written from the pre-mlxconfig layout aborts
  100% of runs.
- **The box is re-provisioned DAILY by the regression — script the rebuild (Phase 9b-bis).** A
  repro env is rebuilt every session, not built once. And a ticket's steps assume an
  already-provisioned box, so "I followed them exactly and it still fails" usually means a
  missing prerequisite the reporter never had to think about. Recover the real list from the
  session tarball's `install_Tools` step, then capture it in `tools/provision_<box>.sh`.
- **Snapshot the evidence AFTER the post-run reset, not right after the tool.** Emulated-device
  topology changes only materialise when fwreset does its PCI remove/rescan; a snapshot taken
  at tool-exit is empty and scores a real repro as `PARTIAL` (happened on #5138907). Also mine
  the reset log itself for a direct statement of the change (`Rshim BDF changed to …`).
- **Run the reporter's documented steps VERBATIM before your own script.** Dropping one setup
  step (`clear_nv_data`) changed the starting topology enough that the bug could not present;
  adding `--timeout`/`--case_name` to the recorded tool command was another silent divergence.
  Diff before assuming: two INI files with different names were byte-identical.
- **Branch from the failing version FIRST (Phase 4) — then the working tree is authoritative.**
  Create a named private branch in *each* repo (`git checkout -b <ticket#>_<topic>_<you> <sha>`),
  never a detached HEAD. A repro clone inherits the *previous* ticket's detached HEAD, which is
  unlabelled and usually a different release family — on #5184928 the clone sat detached from
  `rel-12_48_1633` while the ticket was the **51** line, so the first discovery greps read the
  wrong tree entirely (the key function was a `static inline` in `include/hca_cap.h` there vs a
  real function in `src/main/hca_cap.c` at the correct tag). Branch first and this whole class of
  error disappears — plus the fix has a place to live.
- **Grep the RELEASE TAG's tree, not your clone's HEAD** — the fallback when you have not branched
  yet (discovery greps, or a quick cross-version check like "is this still broken at `rel-…_0101`?").
  Reading the wrong tree is how #5138907 got a fabricated root cause ("virtio path is missing a
  bounds check") when the real check was on the common pre-execution path at
  `cmdif_checks_rdma.c:1261` in `rel-12_50_0402`. Use `git grep <pat> <tag> -- 'src/*.c'` and
  `git show <tag>:<file>`; resolve product→source family first (`24.50.0402` → `rel-12_50_0402`,
  `32.51.0098` → `rel-12_51_0098`). **Discovery may grep anywhere; every published CLAIM must be
  re-verified against the correct tree.** Cheap self-check that the verification was real: if the
  file path or line numbers you cite differ between clone and tag, you genuinely read the tag.
- **Moving tags lie — branch from the SHA and confirm with `git describe`.** A run log's
  `regression_stable_tag-0-g<sha>` records where that *moving* tag pointed on the day of the
  regression; your local copy can be months stale (#5184928: local `regression_stable_tag` →
  2026-05-31, the regression's `3207d90` → 2026-08-01). Branch from the SHA, then
  `git describe --tags <sha>` — it returned `host_fwv_20260801_FW_version_51_0098_branch_master`,
  independently confirming both date and FW line. Also verify the FW tag↔version mapping the same
  way: `git log -1 rel-12_51_0098` → `"Updated version 12.51.0098"` dated 2 h before the MARS burn.
- **RegTools (`check_arm_agent.py`, `Fwreset.py`) need `sudo -E`** — they read `/dev/rshim0/misc`
  (`crw------- root root`). Unprivileged, every Fwreset fails permanently, which is precisely how
  a "post-run Fwreset failed" verdict becomes a false positive. If a gate fails identically both
  before and after your trigger, it is environment, not the bug.
- **Some reg boxes net-boot a fresh image every reboot**: MFT vanishes, `/tmp` is wiped, boot
  takes 10-19 min. Re-ensure MFT after every power-cycle, log to NFS not `/tmp`, and size
  `wait_host` for the slow case. `clear_nv_data` + a reboot that loses MFT strands the card in
  **Livefish**; recovery is the **HCA System Service** tool (its Enable/Disable-Livefish steps are
  what manual flashing lacks) — blind `mlxburn`/`flint` burns and power cycles do NOT work, and a
  full generic-`.mlx` write risks clobbering `DEV_INFO` (board GUID/MAC). See Phase 9c.
- **A test-tool "fix" that pins a parameter is a workaround, not a root cause.** utopx `388d923`
  pins `total_vf=0` so utopx stops emitting the illegal value — the FW gap it exposed is
  untouched and still reachable by any other caller. When a ticket is closed by a constraint
  change in the test tool, ask what the tool was *provoking* and whether that defect was fixed.
  Repro of the underlying defect then REQUIRES the pre-fix tool binary.
- **Repeated IPMI power-cycles can permanently kill a DPU's ARM boot** (abrupt cuts on a running
  ARM Linux → dirty eMMC/fs → sshd never comes up again; the OOB name may still resolve+ping — that
  can be the integrated BMC, not the ARM: check **port 22**, not ping). Before blaming a FW version
  for "ARM won't boot after I burned X", run the **restore-control test**: burn back the previous
  FW + power-cycle — if ARM is still dead, the board is broken, not the FW. A DPU-mode utopx repro
  is DEAD without the ARM (ArmAgent StartSession is the first step) — verify ARM health early, and
  prefer boards whose recent regression sessions show real PASSes (0-PASS-for-weeks ≈ broken ARM).
- **BF4 (no rshim!) ARM recovery is BMC-only — host IPMI power-cycle is NOT a DPU reset.** BF3's
  rshim tricks (`/dev/rshim0/boot` BFB push, `rshim0/console`, DROP_MODE) do not exist on BF4;
  management moved to the DPU-BMC on the 1GbE OOB (`<box>-bf4-oob`). ARM-only reset: Redfish
  `POST {"ResetType":"ArmReset"}` to `https://<dpu-bmc>/redfish/v1/Chassis/BlueField_0/Actions/Oem/
  NvidiaChassis.Reset` (authenticate with the QA-standard BMC credentials — get them from the team password store), or `gpioset gpiochip0 56=0` → `=1`
  on the BMC shell; console = SOL via the DPU-BMC (`obmc-console-client` / `ipmitool -C 17 -I
  lanplus ... sol activate`). To fix a HOST-side wedge (flint D-state) prefer **host warm reboot**
  (card keeps aux power, ARM unaffected); FW pivot via the regression fwreset.py, not power cuts.
  If the OOB endpoint itself vanishes (NXDOMAIN + all mgmt ports closed) the DPU is off the network
  entirely → lab hands required. (Sources: "BlueField-4 Troubleshooting", "BF4 QA One Stop Shop",
  "Serial over LAN" Confluence pages, 2026-07.)
- **BF4 boot chain: DPU-BMC gates Grace — if BOTH ARM and DPU-BMC are off the net, it is NOT
  host-recoverable.** POR order (BF4 reset-flow HLD): DPU-BMC boots first (its EROT auths BMC FW &
  releases BMC reset) → BMC asserts `BMC_BOOT_DONE` → CPLD releases Grace EROT + Grace. Therefore
  **DPU-BMC down ⇒ it de-asserts BMC_BOOT_DONE ⇒ Grace (ARM) is HELD in reset + CX-9 affected** —
  exactly the "ARM sshd never comes up AND `<box>-bf4-bmc`/`-bf4-oob` are NXDOMAIN/all-ports-closed"
  picture. Root cause is a wedged/failed DPU-BMC, not the ARM.
  - **Why your host IPMI power-cycles don't fix it:** `ipmitool power cycle` / jmake --power-cycle
    cut RUN power only; the DPU-BMC reset is **latched** and rides on AUX/standby power, so it stays
    wedged across every host power-cycle (confirmed: 4 cycles + FW restore-control, no change).
  - **The only things that reset a wedged DPU-BMC:** (a) **AUX/standby power removal** — real AC/PDU
    cut, or on VR platforms `stbypowerctrl.sh aux_cycle` from the *platform* BMC (not the DPU-BMC,
    not the host); (b) **platform-BMC forced full-card reset** / `DPU_BMC_RESET_RELEASE` (needs a
    platform BMC + MCU wired up — BF4.1 MCM, not most BF4.0 ES fwreg boxes); (c) SMBus/USB DPU-BMC
    recovery — physical. All are **lab-hands / platform operations**, not host-side scriptable.
  - **Host in-band recovery for a BF4 with OOB down is an explicitly UNSOLVED FR** (QA One Stop Shop:
    "how to recover grace without rshim, in case oob not connected?"; RSHIM-replacement host↔ARM
    virtual-ethernet is FR #4563650, still BETA). So do NOT burn more time hunting a host path.
  - **Escalation:** open a lab/HW ticket for an AC/aux power cycle (or reseat) of the specific fwreg
    box; hold the Noga lock while it's investigated so a regression doesn't reclaim a dead board.
    (Sources: Confluence "BF4 reset flow" 2830130924, "Reset flows via DPU BMC Redfish" 3064582957,
    "[HLD][BF4] Reset flow - full reset" 2830145665, "BF4.1 Arch options" SharePoint, 2026-07.)
- **The flint end-of-burn segfault** (image writes 100% + "Restoring signature - OK", then flint
  segfaults, exit 139, device access wedges in D-state) is **intermittent** and host-side
  (IOMMU `intel_unmap` trace at burn time). The image usually DID take — verify with `flint q`
  after recovering (host warm reboot; if D-state persists → power-cycle). `flint -d <dev> v`
  cannot verify FS5/PQC encrypted flash — its scary message is a tool limitation, not corruption.
- **BF4 boxes that hosted QS/PLDM firmware-update testing can be left triple-broken** (seen on
  m-fwreg-017, 2026-07-10):
  1. **ARM `ubuntu` password changed** — utopx HARDCODES the Bronco ARM credentials in
     `src/arm_agent_api/ArmAgentApiOS.cpp` (`GetArmUserName()` / `GetArmPassword()`, a
     `IsBronco(device) ? ... : ...` pair — Bronco and non-Bronco differ). Symptom = ArmAgent scp
     fails 60 attempts. Fix: the `root` account usually still works → `echo 'ubuntu:<password>'
     | chpasswd` on the ARM, restoring what utopx expects.
     Values: see `lab-credentials.md` in this directory (local, gitignored — copy
     `lab-credentials.md.example` if you do not have it); the source file above is authoritative.
  2. **DPU-BMC stuck in OpenBMC first-login state** — Redfish returns 403 for
     `admin:0penBmc` (OpenBMC's upstream factory default, not a secret) and 401 for everything
     else. **403-not-401 is the tell**: the password is right, a first-login password change is
     simply pending. Fix: `PATCH /redfish/v1/AccountService/Accounts/admin
     {"Password":"<the value utopx expects — see ArmAgentApiOS.cpp>"}` with
     `-u admin:0penBmc`, then full Redfish access. BMC name:
     `<box>-bf4-bmc` (separate from `-bf4-oob` = ARM). Manager id e.g. `BlueField_BMC_0`;
     `GracefulRestart` may not really reboot — use `ForceRestart` and CONFIRM port 443 drops.
  3. **Flash semaphore held PERMANENTLY by the running QS FW** (stuck PLDM/MCC session inside
     FW): `-clear_semaphore` + immediate burn, `--no_fw_ctrl` direct burn, burning inside a
     verified BMC-reboot window, ARM-side mstflint — ALL fail at lock. It's a chicken-and-egg
     (new FW needs a burn, burn needs the lock) → the box needs QA/lab restore; the nightly
     regression on it fails the same way (session = all NOT_EXECUTED). Diagnose by elimination:
     host `pgrep flint|mlxburn`, ARM procs, SD-pair host, then burn inside a BMC-down window —
     if still locked, it's the FW itself.

---

## Appendix — Worked example: Redmine #5090131 (BRONCO / BF4)

Input (the only thing the session was given):
`https://redmine.mellanox.com/issues/5090131`

After `yai__get_tickets([5090131], include="full")`, Phase 1 yields:

- **Subject / Fatal:** `[UTOPX] actual cap field can't be less than expected ; cmd_hca_cap ; FUR_2026_Jan_VR_Fractal_ES_from_48_0386 DEVICE_NAME_LIKE[BRONCO]`
  → tool = **utopx**; **signature to reproduce** = `actual cap field can't be less than
  expected` on `cmd_hca_cap` (a utopx cap-prediction vs FW-actual mismatch); regression
  stream = `FUR_2026_Jan_VR_Fractal_ES_from_48_0386`.
- **MARS URL in description**, parsed:
  - `results_dir` = `/auto/sw_regression/host_fw/HCA_CORE_FWV/MARS/conf/results`
  - `setup_id`   = `BRONCO_FW-m-fwreg-029_DPU_MODE_P1` → machine **m-fwreg-029**, device
    **BRONCO (BF4)**, **DPU mode**, P1 suite
  - `session_id` = `11125573` → tarball
    `/auto/sw_regression/host_fw/HCA_CORE_FWV/MARS/conf/results/BRONCO_FW-m-fwreg-029_DPU_MODE_P1/11125573/11125573.tgz`
  - `key_id`     = `0.24.1.1.1.10.1.10.6.10.1` → failing step (matches every attachment suffix)
  - `name=traffic_test_error`, `status=Failed` → a **traffic test**, failed.
- **Device / MST / FW** from attachment names:
  - `flint_nv_dump_mt41695_pciconf0_82.48.1632_0x03e80000_0` → MST = **`/dev/mst/mt41695_pciconf0`**,
    running FW = **82.48.1632** (BF4 = `mt41695`).
  - `Chips` custom field = **Bronco (BF4)** (id 167); `fixed_version` = **Host FW - 50.1000 GA Release (GA-July26)**.
- **Exact command + env** from attachments (download via `content_url`, or read the same
  files from the tarball): `run_case_0.24.1.1.1.10.1.10.6.10.1.log` (command + seed +
  scenario), `dump_nv_data_*` (NVconfig to match), `fw_reset_*` / `modprobe_udriver_*` /
  `print_mst_devs_*` (bring-up sequence).
- **History:** auto-filed by Raz Gavrieli (duty scrum), reassigned to Yong Liang by Jerry
  Jia on 2026-06-17; an Orion AI-overview link is in the description.

From here the session proceeds Phase 2→8: pull `new_burn_fw`/`get_last_commit` from the
`11125573.tgz`, **`jmake --reg-malloc m-fwreg-029`** (the exact box from `setup_id` — wait
for it if locked, monitor+grab if busy), pin **`utopx2`** to its `get_last_commit` tag (FW
burns from the official `.mlx`, no `golan_fw2` build needed here), copy the regression INI, burn to
`mt41695_pciconf0`, bring up **exactly** per the attached `fw_reset`/`modprobe_udriver`/
`print_mst_devs` logs, then run the `run_case` command **verbatim** (`traffic_test_error.conf
--iter=150 --ops_per_it=100 --case_name utopx_6_traffic_test_error`) with its pinned seed
`1753076298` and confirm the `cmd_hca_cap` "actual < expected" fatal reproduces. Release
with `jmake --reg-cancel` when done.
