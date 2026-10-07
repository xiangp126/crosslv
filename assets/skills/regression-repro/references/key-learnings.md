# Key learnings (carry forward)

Traps beyond the must-fire rules in `SKILL.md`. Phase and § numbers refer to `procedure.md`.

## Decoding the ticket and pinning versions

- **A regression bug ticket carries its own repro coordinates:** the `view_log.php` URL
  (`results_dir`/`setup_id`/`session_id`/`key_id`) + the `run_case`/`flint_nv_dump` attachments.
  Decode those first; machine, device, MST, FW, command and seed follow (Phase 1; worked example
  in the Appendix).
- **Pin `--seed`** from `run_case`; a pass on one seed ≠ a pass on the next.
- **Grep the RELEASE TAG's tree, not your clone's HEAD**, whenever you have not branched yet
  (discovery greps, or a quick cross-version check like "is this still broken at `rel-…_0101`?").
  Reading the wrong tree yields fabricated root causes (e.g. a "virtio path is missing a bounds
  check" when the real check sat on the common pre-execution path at `cmdif_checks_rdma.c:1261`
  in `rel-12_50_0402`).
  - Use `git grep <pat> <tag> -- 'src/*.c'` and `git show <tag>:<file>`.
  - Resolve product version → source family first: `24.50.0402` → `rel-12_50_0402`,
    `32.51.0098` → `rel-12_51_0098`.
  - Discovery may grep anywhere; re-verify every published CLAIM against the correct tree.
    Self-check: if the file path or line numbers you cite differ between clone and tag, you
    genuinely read the tag.
- **Branch from the failing version FIRST (Phase 4) — then the working tree is authoritative.**
  In *each* repo, pin in a per-ticket worktree off the `*2` clone, on the named pin branch
  `<ticket#>_<topic>` (`git -C <clone> worktree add -b <ticket#>_<topic> <worktree> <sha>`,
  worktree `/auto/fwgwork1/$USER/golan_fw_<ticket#>` / `utopx_<ticket#>`) — never a detached
  HEAD, never the clone's own checkout. That checkout carries the *previous* ticket's detached
  HEAD, which is unlabelled and usually a different release family (e.g. detached from
  `rel-12_48_1633` while the ticket was on the **51** line: the key function was a
  `static inline` in `include/hca_cap.h` there, a real function in `src/main/hca_cap.c` at the
  correct tag). Branching first removes this class of error and gives the fix a place to live.
- **Moving tags lie — branch from the SHA and confirm with `git describe`.** A run log's
  `regression_stable_tag-0-g<sha>` records where that *moving* tag pointed on the day of the
  regression; your local copy can be months stale. Branch from the SHA, then
  `git describe --tags <sha>` — it prints e.g. `host_fwv_20260801_FW_version_51_0098_branch_master`,
  independently confirming the date and the FW line. Verify the FW tag↔version mapping the same
  way: `git log -1 rel-12_51_0098` → `"Updated version 12.51.0098"`; compare its date with the
  MARS burn.
- **A test-tool "fix" that pins a parameter is a workaround, not a root cause.** E.g. utopx
  `388d923` pins `total_vf=0` so utopx stops emitting the illegal value; the FW gap it exposed is
  untouched and still reachable by any other caller. When a ticket is closed by a constraint change
  in the test tool, ask what the tool was *provoking* and whether that defect was fixed.
  Reproducing the underlying defect then REQUIRES the pre-fix tool binary.

## Allocating the box; substitutes

- **Box lifecycle:** reserve the `<machine>` from `setup_id` with `jmake --reg-malloc <machine>`
  (never substitute another host or trim the command), keep it alive with `jmake --reg-extend`,
  **release it with `jmake --reg-cancel` when done**. If it is busy, monitor its lock and grab it
  the instant it frees (§3b) — do not switch boxes. **Unknown reg/lab command → ask Glean
  (`glean_search` / `glean_chat`) before guessing.**
- **Some reg boxes are outside the malloc pool.** `jmake --reg-malloc` / `--reg-mine` only see
  boxes labelled `HCA_FW_ALLOCATION_POOL_HOST`; dedicated BRONCO/BF boxes may carry only
  `PARTITION_NOGA_ALLOC_reg`, and some sit in a partition malloc refuses ("Server is in partition
  virtio, allowed partitions are: e2e,mpi,automation,dev,perf,reg,userdev"). Lock those directly:
  `noga_manage.py -l -t server -n <box> -L <hours> -N "…"` (the `-t server` is mandatory), and
  confirm ownership via `noga_manage.py -q` — sqme won't show it.
- **Noga REST can be down (504) for hours** — malloc / minfo / `noga_manage -q` all share that
  backend. Probe `api_cmd=get_teams` with curl and wait it out in the background; never read a 504
  traceback as "box locked". `lock_time_out` is UTC and auto-release lags — watch the
  `Status.status` flip, not the clock. (STM-only fallback: Noga's direct Oracle DB API.)
- **Same-PSID substitution** (approval rule: `SKILL.md`; procedure: §3b-bis): match the PSID
  (board), not just the family; verify the substitute is idle + healthy (last session Burn RC=0)
  and, ideally, already shows the signature in its own latest regression.
- **Find same-PSID boxes via Noga, not MARS INI names.** The board PSID lives on the **NIC**
  resource (`Setup Automation.psid`); one query lists every board with it:
  `noga_manage.py -q -t nic -e "psid:<PSID>"` (e.g. `psid:MT_0000000704`). MARS-results /
  INI-name scans only see boxes that ran this suite and FALSELY report "no other same-PSID box".
- **A `mars_reg` lock on a box that is down/unreachable is a stale reservation, not a live run** —
  verify with `ssh <box> hostname` (using the runtime adapter) + the newest real session mtime.
- **Health-check a substitute before grabbing it:** burn-step `status.txt` (RC) +
  `summary_results.json` (PASSED count) from its recent status-only tgz archives; the ini_files
  filename gives session → FW version / PSID with no tarball at all. A box that cannot burn FW is
  useless no matter how well its PSID/mode match.
- **Check the box-specific `topology_<mode>.xml` BEFORE locking.** A same-PSID substitute often
  still needs its own authored (per-box entry_points/IPs, §3b-bis). Verify topology first (e.g.
  `topology_eth_arm_agent.xml`), lock second.
- **Every script that touches the box must first verify `Status.lock_owner == $USER` via Noga**;
  refuse and exit non-zero unless the owner is you. `hostname` is not a guard: the nightly
  regression runs on that same box, so an `mst start`, `modprobe` or `Fwreset` fired while
  `mars_reg` holds the lock silently corrupts a live session (usually the one you are waiting on).

## Environment, burn, bring-up, reset

- **The box drifts daily** — read the ticket's session; verify the running FW with `flint q`.
- **`git checkout` doesn't touch the compiled binary** — after drift, rebuild and verify the mtime.
- **Burn the regression-*generated* INI, not the release default**; cross-check it against the
  ticket's `dump_nv_data` attachment. Don't add your own nvconfig rows.
- **Reset between every run** (`jmake --fw-reset`); device/emulation state leaks (NV clearing:
  Phase 10).
- **One command per ssh**, reuse one SSH connection, drop the ControlMaster socket after any
  reboot. **Always fetch tags first.**
- **SSH ControlMaster is mandatory in `env_rebuild`**
  (`-o ControlMaster=auto -o ControlPath=<mux> -o ControlPersist=28800`): NFS-home auth fails for
  ~30 s after a power-cycle; one authenticated master socket avoids every later auth race.
- **Reuse the deployed binary.** The regression leaves its exact prebuilt `utopx.exe` + configs in
  `/tmp/mars_tests/<test-DB>/tests/` on the box — use it in place (no build; read-only, see
  `SKILL.md`) and confirm the commit via the run's "tarball git tag is: <describe>" line. Local
  builds: a per-ticket worktree off `golan_fw2` / `utopx2` (Phase 4), never a clone's own
  checkout.
- **Kill stale daemons before resetting.** A box out of rotation may still run a prior
  `utopx.exe --daemon` holding `/dev/udriver_*`; fw_reset then fails "Device is busy". Find it via
  `fuser` / `ps`, kill, retry.
- **A MARS helper's `--session_id` can select CACHED STATE from the original run, not just label
  the log.** `Fwreset.py` caches the resolved FW version in
  `/tmp/fwreset_wrapper_<session_id>__dev_mst_<dev>.txt` and **reuses the file if it exists**. On a
  box whose `/tmp` survives reboots (check for files older than `uptime`), passing the ticket's
  session id re-applies **that day's** FW assumption to **today's** device — e.g. the
  `rel-…_0098` reset script against a `32.51.0100` card → `version is not supported` →
  `could not obtain tools semaphore` → `-ERROR- Fwreset failed!!` (an abort, not a repro). Give
  helper tools a **repro-specific session id** and **purge their cache before every run**; keep the
  original id only where it is genuinely part of the command under test (e.g. utopx's own
  `--seed` / `--session_id`). Fidelity means the *command under test*, not every incidental id.
- **RegTools (`check_arm_agent.py`, `Fwreset.py`) need `sudo -E`** — they read
  `/dev/rshim0/misc` (`crw------- root root`). Unprivileged, every Fwreset fails permanently, which
  turns a "post-run Fwreset failed" verdict into a false positive. If a gate fails identically both
  before and after your trigger, it is environment, not the bug.
- **Run the reporter's documented steps VERBATIM before your own script.** Dropping one setup step
  (`clear_nv_data`) changes the starting topology enough that the bug cannot present; adding
  `--timeout` / `--case_name` to the recorded tool command is another silent divergence. Diff
  before assuming a difference matters: two INI files with different names can be byte-identical.
- **The box is re-provisioned DAILY by the regression — script the rebuild (Phase 9b-bis).** A
  repro env is rebuilt every session, not built once. A ticket's steps assume an
  already-provisioned box, so "I followed them exactly and it still fails" usually means a missing
  prerequisite the reporter never had to think about. Recover the real list from the session
  tarball's `install_Tools` step and capture it in `tools/provision_<box>.sh`.
- **Some reg boxes net-boot a fresh image every reboot:** MFT vanishes, `/tmp` is wiped, boot
  takes 10-19 min. Re-ensure MFT after every power-cycle, log to NFS not `/tmp`, and size
  `wait_host` for the slow case. `clear_nv_data` + a reboot that loses MFT strands the card in
  **Livefish**; recover fully remotely with skill `nic-livefish-recovery` (relay_controller.py +
  IPMI), or with the **HCA System Service** tool (its Enable/Disable-Livefish steps are what manual
  flashing lacks). Blind `mlxburn` / `flint` burns and power cycles do NOT work, and a
  full generic-`.mlx` write risks clobbering `DEV_INFO` (board GUID/MAC). See Phase 9c.
- **A different fatal can be the same bring-up bug** at a different device state (`cmd_hca_cap`
  caps=0 vs a `VerifyHealthBuffer` FW assert `ext_synd 0x817e`). Read the VHCA HCA_STAGE dump;
  re-burn fresh + regression fw_reset to chase the exact signature.
- **DPU/BF: never power-cycle to recover a wedged run or to pivot between runs** — use
  `jmake --fw-reset --device <dev>` (or the regression's own per-test reset; on BlueField
  `*_ARM_AGENT_*` setups the regression's own reset is required — procedure Phase 7). A power-cycle boots
  the ARM from eMMC into DOCA, and on ARM-agent setups utopx's BareMetal ArmAgent then times out
  before the first op (`ArmAgentApiBareMetal.cpp:20 Bare metal arm agent timeout`). Power-cycle
  only for a pending NV change that needs a cold boot (`mlxfwreset -d <dev> q` answers
  `There is no supported reset-level`), then confirm the ARM is alive before running (skill
  `bluefield-fwconfig`). Full rule: Phase 7.
- **`/dev/rshim*` disappears after `clear_nv_data` + reburn + `--fw-reset`** (BF-3 sat-PF boxes),
  while `systemctl status rshim` still reports `active` and `tmfifo_net0` is UP. Symptom:
  `Rshim is not enabled!`. Fix: `systemctl restart rshim` — make it a step in the per-run reset
  script.
- **The flint end-of-burn segfault** (image writes 100% + "Restoring signature - OK", then flint
  segfaults, exit 139, device access wedges in D-state) is intermittent and host-side (IOMMU
  `intel_unmap` trace at burn time). The image usually DID take — verify with `flint q` after
  recovering (host warm reboot; if D-state persists → power-cycle a non-DPU NIC box; a
  DPU/BlueField box: Phase 7).
- **Encrypted flash (FS5/PQC, CX9 secure-fw) cannot be read back.** `flint -d <dev> v` cannot
  verify it — its scary message is a tool limitation, not corruption. `flint -d <dev> dc` (dump the
  burned INI) fails with `Operation not supported on an encrypted flash`, also with `-no_fw_ctrl`.
  Prove which INI went on by logging its md5 when you burn it, then check what is visible through
  `mlxconfig -e q` after the reset.

## Repro harness and verdicts (Phase 9b)

- **Write env_rebuild + per_run_reset right after decoding the ticket — NOT after the first
  repro.** Waiting for a contended box takes hours; build the scripts in that window so the lock
  lands on a ready harness. Guard against false confidence with an `!!! UNVERIFIED !!!` banner,
  opt-in destructive paths, and warn-only gates where no grounded baseline exists yet — not by
  delaying.
  - `tools/env_rebuild_<box>.sh` (from the dev box): slow one-time setup — burn, mlxconfig, verify.
  - `tools/per_run_reset.sh` (on the reg box): the per-attempt loop — mst start → FW gate → PCI
    gate → ARM → baseline Fwreset → buggy tool → post-run Fwreset → verdict.
  - Both use `FORCE=1` guards and color-coded output; `chmod +x` both.
- **A single-signal verdict will eventually lie — require CORE evidence + a passing baseline.**
  Decide on the defect's *direct effect* (a before/after state diff you captured), not on a
  downstream symptom like "the next script failed". Hard-gate the baseline; a warning that
  execution continues past is worthless. Assert the tool binary is the **pre-fix** commit, and
  emit `RUN VOID` when the tool never initialised instead of scoring it as a repro. Each of these
  alone voids a "success": baseline already failing, tool never started, syndrome count zero.
- **An env-setup side effect can perfectly mimic the ticket's signature.** E.g. "PCI address
  changed" (81→83) was caused by `mlxconfig` enabling the emulated PCIe switch, which inserts
  bridges at 81/82 and shifts endpoints to 83. Capture the baseline **after env_rebuild,
  immediately before the tool runs**, and observe the expected topology rather than reasoning it
  out — a gate written from the pre-mlxconfig layout aborts 100% of runs.
- **Snapshot the evidence AFTER the post-run reset, not right after the tool.** Emulated-device
  topology changes only materialise when fwreset does its PCI remove/rescan; a snapshot taken at
  tool exit is empty and scores a real repro as `PARTIAL`. Also mine the reset log itself for a
  direct statement of the change (`Rshim BDF changed to …`).
- **A constant in the test conf can lock out half the state space.** If a precondition is constant
  in the conf, the other half has probability zero, not low probability — more rounds and more
  seeds cannot reach it. Tell: a dedicated validation env with zero hits over hundreds of
  rounds/seeds while the nightly regression hits the same bug daily on the same chip (e.g.
  `scenario_dpa_emu.conf` always performs the delegation step, so the "delegation has NOT
  happened" path is unreachable there; it validates the feature enabled, never misbehaviour when
  it is not). When a feature has an enable/delegate/provision step, the negative case is a separate
  test-matrix axis, not a seed outcome: ask which conf exercises the state *before* the step.
- **Find the randomised variable that gates the bug, and pin the seed.** E.g. `num_sat_pf` is
  generated by `.Gen()` under a `[0-1]` constraint, so the nightly hit the bug ~half the time;
  pinning the seed turned that 50% flake into a 3/3 reproduction. Without a pinned seed such a bug
  is not reproducible on demand.

## Evidence discipline — the two ways a root cause goes wrong

Shape of both: a fact about the code turned into a claim about runtime without checking runtime.

- **Reading code cannot tell you whether a behaviour is a bug or by design.** Tell: the analysis
  read source and never the HLD/Arch doc. E.g. a refusal path that visibly ignored `cap_type`
  while a neighbouring file dispatched on it looked like a defect; the HLD says a satellite PF
  starts least-privileged, so refusing before delegation is correct.
  ⇒ **Before claiming "FW is wrong", find the design document, or ask the architect.** Escalate
  architecture questions early: a quotable verdict from the architect can close the FW side
  permanently (and rule out loosening FW to accommodate the tool); more code reading does not get
  there.
- **A parameter existing in a signature is not evidence it is used that way.**
  `check_query_hca_cap_opmode(gvmi, uid, input_gvmi, …)` has two gvmi params, which suggested
  "some privileged function must be querying the sat-PF"; the log said `other_function : 0x0` —
  the sat-PF was querying **itself**.
  ⇒ **For any "who did what, when" claim, grep the log first.**
- **The same failure mode applies to rules.** Before citing a rule — especially before telling
  someone else they broke one — open the file and quote it; a misremembered rule propagates as
  false correction.

### When a peer or another session hands you an analysis, verify before adopting

Adopt the mechanism; re-derive the specifics against your own tree and your own logs. Typical
wrong details in an otherwise correct analysis:

- a function name that **does not exist** (`is_esw_gvmi_dpu_pf` vs the real
  `is_esw_gvmi_dpu_sat_pf`, which is much narrower: vport type must be exactly
  `VPORT_TYPE_DPU_SAT_PF`);
- line numbers off by 300-1200 lines, because the author read a different baseline;
- an identifier that differs per run and per environment (`GVMI=0x7` vs `0x5`);
- an absence claim ("zero hits on platform X") that a direct query contradicts.

Record which claims you verified and which you took on trust; when a number came from someone
else's baseline, say so instead of quoting it as yours. Mirror case: when a peer's static reading
says YOUR fix is broken, check the runtime evidence before conceding (e.g. a peer's airtight-looking
analysis of `RunSanityCheck` missed that the call happens later in bring-up than the code it
worried about; the measured run showed zero fatals).

### Reading a cap-mismatch FATAL: two VHCAs on one GVMI are one gen + its checker

A cap-mismatch log often shows the same GVMI under two VHCA numbers. Both print
`Setting Expected CAP`; the second is followed by
`FATAL : actual cap fields can't be less than expected cap`. That is **not** two instances judged
differently: the first is the gen VHCA, the second its checker clone (`UtopxRandomTest.cpp`:
`checker_vhca = gen_vhca->Clone(GetCheckerDB())`), whose log line is `VHCA.cpp:… vhca Type <T>`
with no DBDF/HIX/PORT. The gen side only builds the expected list and **never compares**;
comparison happens only on the checker path (`ContextChecker` → `VHCA::VerifyQuery` →
`VerifyQueryHcaCap` → `FailOnDiffWithCheckList`).

- So "same GVMI, one passes, one FATALs" is not a control pair. Before using it as evidence, look
  for `Adding <T> VHCA=X` followed by the clone line `VHCA=Y … vhca Type`.
- For emulation-manager caps (`device_object`, `dpa_db_cq_mapping`, `*_emulation_manager`), the
  function that fails is the one `IsDefaultDeviceEmulationManager()` picks: the lowest-GVMI PF in
  NIC mode, the lowest-GVMI ECPF in ECPF mode. Each case dies at that function's first
  `QUERY_HCA_CAP`, so the other PFs/ECPFs are never checked in that run. "The others would pass"
  is a reading of the code, not something the run showed.

## Which binary you are actually running

### `utopx.exe` is a shell — the code you changed lives in `libhca.so`

The md5 of `utopx.exe` does NOT tell you which version of the logic you are running. From
`build.ninja`:

```text
build .../utopx.exe: CXX_EXECUTABLE_LINKER__utopx.2eexe_ CMakeFiles/utopx.exe.dir/src/main.cpp.o
    ... artifacts/lib/.../libhca.so
```

The executable links `main.cpp.o` plus shared libraries. `VHCA.cpp`, `HcaCaps.cpp`,
`CmdSetHcaCap.cpp` — everything you normally patch — compile into **`libhca.so`**; change any of
them and `utopx.exe` stays **byte-identical** (two builds with different `VHCA.cpp.o` give the same
`utopx.exe` while `libhca.so` differs — not a broken deterministic build, not NFS).

- **Archive and diff `libhca.so`, not `utopx.exe`.** An archived `.exe` alone does not pin a
  version and cannot be used to re-run an old build later.
- A header-only change (adding a declaration) *can* move `utopx.exe`, because units compiled
  directly into the exe include that header — so the exe md5 changing sometimes, and not others,
  is itself misleading. Infer nothing from it.
- Running via `cd <worktree> && ./utopx.exe` picks up that worktree's `libhca.so`, so an in-place
  run is correctly paired. It is the **archived copies** that silently decouple.
- Each module builds its own library (`src/nv_config/*` → `libnv_config.so`, …), found through a
  **relative** RUNPATH (`./artifacts/lib/ninja/.../Legacy:./steering_ul/lib:…`, resolved against
  the cwd). So `cp utopx.exe utopx_unpatched.exe` is **not** a control: the copy loads the same
  patched libraries. Control = revert the patch and rebuild in the same tree, or use a separate
  worktree. Prove the patch is in or out with
  `strings -n 6 artifacts/lib/.../lib<module>.so | grep <a literal the patch adds>`.
- To prove a change reached the binary, go to the object/library level:
  `nm -CD libhca.so | grep <symbol>`, or `objdump -dr <file>.o` and read the relocation targets (a
  `callq` in a `.o` is an unrelocated `e8 00 00 00 00` placeholder — the symbol name is only in the
  reloc entry, never in the disassembly).
- **"Same md5" is an ambiguous signal, not a verdict.** It can mean "my change did not take", "the
  two versions really are equivalent", or "I hashed a file that does not carry the change". Resolve
  it one level down — object files and libraries — before theorising about the build system.

### Other ways to check the wrong file

- **Stripped binaries defeat `strings` / `nm` / `grep`.** Verifying "did my change get into this
  `.exe`" that way returns nothing — and a control test on an identifier that *is* present also
  returns nothing, so the method cannot even be sanity-checked. Use mtime + build log + a runtime
  probe instead.
- **NFS caches between the dev box and the reg box.** After a `cp` on the dev box the reg box can
  read a **stale** binary while `md5sum` on each host separately looks fine — a false "the fix
  does not work". Take the md5 **on the reg box**, the machine that will execute it, and delete
  old artifacts before rebuilding.

## DPU / BlueField: ARM and DPU-BMC recovery

- **Repeated IPMI power-cycles can permanently kill a DPU's ARM boot**: abrupt cuts on a running
  ARM Linux → dirty eMMC/fs → sshd never comes up again. The OOB name may still resolve and ping —
  that can be the integrated BMC, not the ARM: check **port 22**, not ping.
  - Before blaming a FW version for "ARM won't boot after I burned X", run the
    **restore-control test**: burn back the previous FW and pivot it per Phase 7; if the ARM is
    still dead, the board is broken, not the FW.
  - A DPU-mode utopx repro is DEAD without the ARM (ArmAgent StartSession is the first step):
    verify ARM health early, and prefer boards whose recent regression sessions show real PASSes
    (0-PASS-for-weeks ≈ broken ARM).
- **BF4 (no rshim!) ARM recovery is BMC-only — a host IPMI power-cycle is NOT a DPU reset.** BF3's
  rshim tricks (`/dev/rshim0/boot` BFB push, `rshim0/console`, DROP_MODE) do not exist on BF4;
  management moved to the DPU-BMC on the 1GbE OOB (`<box>-bf4-oob`).
  - ARM-only reset: Redfish `POST {"ResetType":"ArmReset"}` to
    `https://<dpu-bmc>/redfish/v1/Chassis/BlueField_0/Actions/Oem/NvidiaChassis.Reset`
    (authenticate with the QA-standard BMC credentials — get them from the team password store),
    or `gpioset gpiochip0 56=0` → `=1` on the BMC shell.
  - Console: SOL via the DPU-BMC (`obmc-console-client` /
    `ipmitool -C 17 -I lanplus ... sol activate`).
  - HOST-side wedge (flint D-state): prefer a **host warm reboot** (the card keeps aux power, ARM
    unaffected). FW pivot via the regression fwreset.py, not power cuts.
  - OOB endpoint gone (NXDOMAIN + all mgmt ports closed) → the DPU is off the network entirely →
    lab hands required.
  - Refs (Confluence): "BlueField-4 Troubleshooting", "BF4 QA One Stop Shop", "Serial over LAN".
- **BF4 boot chain: the DPU-BMC gates Grace — if BOTH ARM and DPU-BMC are off the net, it is NOT
  host-recoverable.** POR order (BF4 reset-flow HLD): DPU-BMC boots first (its EROT authenticates
  BMC FW and releases BMC reset) → BMC asserts `BMC_BOOT_DONE` → CPLD releases Grace EROT + Grace.
  So a down DPU-BMC de-asserts `BMC_BOOT_DONE` ⇒ Grace (ARM) is HELD in reset + CX-9 affected —
  the "ARM sshd never comes up AND `<box>-bf4-bmc` / `-bf4-oob` are NXDOMAIN/all-ports-closed"
  picture. Root cause: a wedged/failed DPU-BMC, not the ARM.
  - Host IPMI power-cycles do not fix it: `ipmitool power cycle` / jmake --power-cycle cut RUN
    power only; the DPU-BMC reset is **latched** and rides on AUX/standby power, so it stays wedged
    across every host power-cycle.
  - The only things that reset a wedged DPU-BMC — all **lab-hands / platform operations**, not
    host-side scriptable: (a) **AUX/standby power removal** — a real AC/PDU cut, or on VR platforms
    `stbypowerctrl.sh aux_cycle` from the *platform* BMC (not the DPU-BMC, not the host);
    (b) **platform-BMC forced full-card reset** / `DPU_BMC_RESET_RELEASE` (needs a platform BMC +
    MCU wired up — BF4.1 MCM, not most BF4.0 ES fwreg boxes); (c) SMBus/USB DPU-BMC recovery —
    physical.
  - Host in-band recovery for a BF4 with OOB down is an explicitly UNSOLVED FR (QA One Stop Shop:
    "how to recover grace without rshim, in case oob not connected?"; the RSHIM-replacement
    host↔ARM virtual-ethernet is FR #4563650, still BETA). Do not spend time hunting a host path.
  - Escalation: open a lab/HW ticket for an AC/aux power cycle (or reseat) of the specific fwreg
    box; hold the Noga lock meanwhile so a regression does not reclaim a dead board.
  - Refs: Confluence "BF4 reset flow" 2830130924, "Reset flows via DPU BMC Redfish" 3064582957,
    "[HLD][BF4] Reset flow - full reset" 2830145665; SharePoint "BF4.1 Arch options".
- **BF4 boxes that hosted QS/PLDM firmware-update testing can be left triple-broken** (e.g.
  m-fwreg-017):
  1. **ARM `ubuntu` password changed.** utopx HARDCODES the Bronco ARM credentials in
     `src/arm_agent_api/ArmAgentApiOS.cpp` (`GetArmUserName()` / `GetArmPassword()`, a
     `IsBronco(device) ? ... : ...` pair — Bronco and non-Bronco differ). Symptom: ArmAgent scp
     fails 60 attempts. Fix: the `root` account usually still works →
     `echo 'ubuntu:<password>' | chpasswd` on the ARM, restoring what utopx expects. Values:
     `lab-credentials.md` in this directory (local, gitignored — copy `lab-credentials.md.example`
     if you do not have it); the source file above is authoritative.
  2. **DPU-BMC stuck in OpenBMC first-login state.** Redfish returns 403 for `admin:0penBmc`
     (OpenBMC's upstream factory default, not a secret) and 401 for everything else.
     **403-not-401 is the tell**: the password is right, a first-login password change is pending.
     Fix: `PATCH /redfish/v1/AccountService/Accounts/admin
     {"Password":"<the value utopx expects — see ArmAgentApiOS.cpp>"}` with `-u admin:0penBmc`,
     then full Redfish access. BMC name: `<box>-bf4-bmc` (separate from `-bf4-oob` = ARM). Manager
     id e.g. `BlueField_BMC_0`; `GracefulRestart` may not really reboot — use `ForceRestart` and
     CONFIRM port 443 drops.
  3. **Flash semaphore held PERMANENTLY by the running QS FW** (stuck PLDM/MCC session inside
     FW): `-clear_semaphore` + immediate burn, `--no_fw_ctrl` direct burn, burning inside a
     verified BMC-reboot window, ARM-side mstflint — ALL fail at the lock. Chicken-and-egg (new FW
     needs a burn, the burn needs the lock) → the box needs QA/lab restore; its nightly regression
     fails the same way (session = all NOT_EXECUTED). Diagnose by elimination: host
     `pgrep flint|mlxburn`, ARM procs, SD-pair host, then a burn inside a BMC-down window — if
     still locked, it is the FW itself.

## Commit convention

Write the commit message per skill `gerrit-change`; commands: Phase 11. `Change-Id` comes from the
commit-msg hook (never hand-written). Author **Peter Xiang `<pexiang@nvidia.com>`**. Commit/push
only when the user asks.

---

## Appendix — Worked example: Redmine #5090131 (BRONCO / BF4)

What each field and attachment yields in Phase 1. Input: `https://redmine.nvidia.com/issues/5090131`
→ `yai__get_tickets([5090131], include="full")`.

| Source | Value | Yields |
|---|---|---|
| Subject / Fatal | `[UTOPX] actual cap field can't be less than expected ; cmd_hca_cap ; FUR_2026_Jan_VR_Fractal_ES_from_48_0386 DEVICE_NAME_LIKE[BRONCO]` | tool = **utopx**; **signature to reproduce** = `actual cap field can't be less than expected` on `cmd_hca_cap` (a utopx cap-prediction vs FW-actual mismatch); regression stream = `FUR_2026_Jan_VR_Fractal_ES_from_48_0386` |
| MARS URL `results_dir` | `/auto/sw_regression/host_fw/HCA_CORE_FWV/MARS/conf/results` | NFS results root |
| `setup_id` | `BRONCO_FW-m-fwreg-029_DPU_MODE_P1` | machine **m-fwreg-029**, device **BRONCO (BF4)**, **DPU mode**, P1 suite |
| `session_id` | `11125573` | tarball `/auto/sw_regression/host_fw/HCA_CORE_FWV/MARS/conf/results/BRONCO_FW-m-fwreg-029_DPU_MODE_P1/11125573/11125573.tgz` |
| `key_id` | `0.24.1.1.1.10.1.10.6.10.1` | failing step (matches every attachment suffix) |
| `name`, `status` | `name=traffic_test_error`, `status=Failed` | a **traffic test**, failed |
| attachment name | `flint_nv_dump_mt41695_pciconf0_82.48.1632_0x03e80000_0` | MST = **`/dev/mst/mt41695_pciconf0`**, running FW = **82.48.1632** (BF4 = `mt41695`) |
| custom field `Chips` | **Bronco (BF4)** (id 167) | device family |
| `fixed_version` | **Host FW - 50.1000 GA Release (GA-July26)** | target release |
| attachments (via `content_url`, or the same files from the tarball) | `run_case_0.24.1.1.1.10.1.10.6.10.1.log`; `dump_nv_data_*`; `fw_reset_*` / `modprobe_udriver_*` / `print_mst_devs_*` | command + seed + scenario; NVconfig to match; bring-up sequence |
| `journals` | auto-filed by the duty scrum, then reassigned to a developer; an Orion AI-overview link is in the description | when real triage started |

Phases 2→8 for this ticket: pull `new_burn_fw` / `get_last_commit` from `11125573.tgz`;
**`jmake --reg-malloc m-fwreg-029`** (the exact box from `setup_id` — wait for it if locked,
monitor + grab if busy); pin a per-ticket worktree off **`utopx2`** to its `get_last_commit` tag
(FW burns from the official `.mlx`, no `golan_fw2` build needed); copy the regression INI and burn
to `mt41695_pciconf0`; bring up **exactly** per the attached `fw_reset` / `modprobe_udriver` /
`print_mst_devs` logs; run the `run_case` command **verbatim** (`traffic_test_error.conf --iter=150 --ops_per_it=100 --case_name
utopx_6_traffic_test_error`) with its pinned seed `1753076298`; confirm the `cmd_hca_cap`
"actual < expected" fatal reproduces. Release with `jmake --reg-cancel` when done.
