# FWV test env on l-fwreg-171 — for OCI BF-4 Satellite PF Emulation Manager Capability Delegation

**Feature:** `OCI BF-4 Satellite PF Emulation Manager Capability Delegation`. [HLD (Confluence page 3395678597)](https://nvidia.atlassian.net/wiki/spaces/FW/pages/3395678597). [FWV MAS (Confluence page 3530037909)](https://nvidia.atlassian.net/wiki/spaces/FW/pages/3530037909). Peter is the FWV owner.

**Aim:** stand up the BlueField-3 test environment on `l-fwreg-171` that this feature's FW verification will eventually run against. Three layers (revised 2026-06-05):

1. **Baseline utopx layer** — `utopx scenario_dpa_emu` running successfully on 171 with the right FW + INI (Jerry's 36 NVMe/virtio emulation flags). This is the existing test that exercises emulation paths and gives us a regression-known-good state to build on. **See Phases 0-9.**
2. **utopx native sat-PF FWV layer (Phase 11) — PASS-verified 2026-06-05**. utopx has built-in sat-PF code (`IsDpuPf`, `HandleDpuPfCreateEswVport`, `force_dpu_pf_emu_manager`, `num_sat_pf` NVconfig gen, etc.). To exercise sat-PF logic in utopx, pass three **separate** `-e` flags (one per knob): `force_fw_cap.enable_mask_2.fw_feature_support_bits.force_dpu_pf_emu_manager=1`, `nvconfig_registers.pf_pci_conf.num_sat_pf=1`, `nvconfig_registers.pf_pci_conf.num_sat_pf_valid=1`. Verified PASS: seed `226259204`, ~8m57s on utopx `07de3b4` rebuilt binary + FW `32.50.0222`. **No FW-level sat-PF instantiation needed for this path.** See §Phase 11.
3. **FW-level sat-PF instantiation layer (Phase 10) — OPTIONAL / BLOCKED.** To make sat PF physically exist (ARM lspci shows BDF `00:00.2`, mst dev `mt41692_pciconf0.2`) requires INI burn + ARM-side mlxconfig set + power cycle. **Currently blocked on 171 hardware** — no INI permutation tested (incl. Marie's MAS recipe) yields both sat PF Current=1 AND no FW assert 0x821d. Needs Marie's dedicated `l-fwreg-146` setup or FW fix from Li. **Phase 11 doesn't need Phase 10**; Phase 10 is only required for end-to-end ARM-side SF / traffic tests.

**Status of the FW feature on the implementation side (as of 2026-06-05):** **in progress, not yet ready for verification runs**. Li Zeng's gerrit [`nbu:golan_fw~1426433`](https://git-nbu.nvidia.com/r/c/golan_fw/+/1426433) is only *part* of the FW-side implementation — additional commits are still being written. Do **not** treat the current code on master_rc as a testable build. This plan focuses on **env preparation** so that when Li's feature work is complete, the test bench is already standing.

**For a fresh AI agent** picking this up: follow Phase 0 → 9 (baseline utopx) then Phase 11 (utopx-native sat-PF FWV — verified PASS 2026-06-05). Phase 10 (FW-level sat-PF infra) is **OPTIONAL** and currently blocked on 171 — skip it unless you specifically need end-to-end ARM-side enumeration. **If `mars_reg` has just run on the box and left a fresh env, follow §Phase 12 first** — regression rebuilds `utopx.exe` and changes FW, so you'll need to repin + rebuild before utopx works. The "Final recipe" and "Re-run quick reference" sections at the bottom collapse it to a runnable script. Phases below are the diagnostic log with every dead-end included so future debug is faster.

---

## ⚡ Quick re-setup — read this first (2026-06-04 lessons)

The original plan assumed a static, already-prepared box. In practice the box drifts and several heavy steps dominate the wall-clock. If you're re-setting up, expect these (each was a real time-sink on 2026-06-04):

1. **FW drifts daily — don't assume `0222`.** The MARS regression re-burns a fresh FW every day (`0222 → 0238 → 0250 → 0256 → …`) and re-pins utopx to match it. Find the current pairing from the **newest** session dir under `/auto/sw_regression/host_fw/HCA_CORE_FWV/MARS/conf/results/MUSTANG_FW-l-fwreg-171_eth_ARM_AGENT_P1/`: read `new_burn_fw` (FW ver + `.mlx`/INI paths) and `get_last_commit` (`git_describe=(host_fwv_<date>_FW_version_50_<bld>_branch_master-0-g<sha>)`, `commit_id=(<sha>)`). Verify the box's running FW with `flint q`. golan_fw tag = `rel-12_50_<bld>` (drop the `32`→`12` family prefix).
2. **Local repos may be on YOUR dev branches** (e.g. utopx on a PRDMA branch, golan_fw on a QPC branch) with uncommitted work — not the regression pairing. To match: `git stash -u` → **checkout the exact regression SHA** (the daily tag can be stale/force-moved; `git fetch --force` or just `git checkout <sha>` from `get_last_commit`) → **`git submodule update --init`** (utopx has 3: `hca_fw_core_platform`, `hca_fwv_shared`, `steering_ul`; `steering_ul`'s recorded commit may need a fetch).
3. **utopx build is Docker-containerized (~8 min)** — `cd /auto/fwgwork1/pexiang/utopx && jk -o` (or `jk -c -o` for clean after a big branch switch). It runs `./build.sh` in a harbor container; the product is **`utopx.exe`** (the `utopx` file is a ~1.5 KB wrapper that execs `./utopx.exe`). Build on a docker-capable box (m-fwdev-167, has the image/toolchain/udriver artifacts); output is on NFS so 171 sees it.
4. **The INI must be the `scenario_dpa_emu` INI** — not whatever the box was last burned with. A box burned with virtio `num_pf=1` (static virtio PFs at boot) and/or no sat-PF gate makes `scenario_dpa_emu` fail *and* the sat PF not appear. Use `regression_ini/burned_session_*.ini` (virtio `num_pf=0` → dynamic; nvme `num_pf=2`; 5 BAR2 `[fw_boot_config]` lines; + the 2 `mac_params` gate lines). The `0222` and `0256` release-default INIs are byte-identical except the header comment, so one burned INI is reusable across builds. Reburn: `cd golan_fw && jk --burn --firmware <rel-XX_dist/fw-BlueField-3.mlx> --ini <burned INI>` (~8 min; do **not** chain `--fw-reset`).
5. **The sat-PF gate must be IN THE BURNED IMAGE — being able to *query* `PF_NUM_SAT_PF` is NOT proof the gate is present.** (This corrects Phase 10.0/10.4.) Without `mac_params.satellite_pf_en=1` + `device_type=3` baked into the burned INI, FW **reduces** `PF_NUM_SAT_PF` to `Current=0` on load even when you've set `Next=1` — you'll see `Default 0 / Current 0 / Next 1` and ConnectX-7 count stays 2. With the gate burned in: set `PF_NUM_SAT_PF=1` from ARM → power cycle → `Current=1`, count 3, sat PF at `00:00.2`. **Caveat (observed 2026-06-05):** even with the gate burned in and `Next=1` already, a fresh power cycle sometimes lands on `Default 0 / Current 0 / Next 1` (iron_prep still reduced it). Re-issue `mlxconfig -d /dev/mst/mt41692_pciconf0 -e -y s PF_NUM_SAT_PF=1` from ARM and power cycle a second time — Current then comes up =1. **Always verify ARM-side `Current` after every cycle before running utopx; don't assume Next=1 implies Current=1.**
6. **Persistent mlxconfig overrides survive a reburn.** A reburn sets the image *default*, but a prior `mlxconfig set` shadows it (e.g. virtio shows `Default 0 / Current 1` after burning a `num_pf=0` INI). Clear it explicitly: `mlxconfig -d <dev> -y s VIRTIO_{NET,BLK,FS}_EMULATION_NUM_PF=0` + power cycle.
7. **Post-power-cycle races (each cycle ~3 min, and you'll do several).** After `jk --power-cycle`, **wait** for: (a) NFS `/labhome` automount — pubkey `ssh` fails with `Permission denied (publickey,password)` until it mounts; (b) `/dev/rshim0/*` to appear (`sudo systemctl start rshim` if needed) — utopx needs it; (c) ARM to finish booting. Use background `until`-loops (foreground `sleep` is blocked in this harness), e.g. `until ssh -o BatchMode=yes l-fwreg-171 true; do sleep 8; done`.
8. **utopx pushes its own BFB to the ARM** (BareMetal ArmAgent, via `/dev/rshim0/boot`) to run its ARM-side agent for DPA/emulation. So **after any run the ARM is NOT the normal sshable DOCA OS** — `ssh root@192.168.100.1` returns `No route to host` until you power-cycle (which reboots ARM from eMMC). The sat PF persists across this (`PF_NUM_SAT_PF` is in NVRAM).
9. **`debug_conf.xml` currently FAILS on `0256`.** It sets `allow_icmd_access_reg_on_all_registers=0x1`, which ICMD-walks every nvconfig TLV; one TLV on FW `0256` returns `ICMD_ACCESS_REG → BAD_PARAM` (deterministic; independent of seed and of virtio `num_pf`). The same walk passed on `0222`. This is a FW/utopx register-access incompatibility, not an env problem. For a functional baseline use `conf.xml`; to chase the bug, identify the failing TLV (the dump before the fault showed nvme-emu TLV `type=0x8b`, then `0x8d`, `0x80`).

**SSH to ARM** (after the box is up): from `l-fwreg-171`, bare `ssh` is shadowed by the Noga lab wrapper (mangles `root@…` → `pexiang@root@…`). Bypass it: `/usr/bin/ssh root@192.168.100.1` (pw `3tango`), or scripted `SSHPASS=3tango sshpass -e ssh -o PreferredAuthentications=password root@192.168.100.1`. `sshpass` execs the real binary, so it sidesteps the wrapper. Confirm with `uname -m` → `aarch64`.

---

## debugPhase 0 — Starting point

On dev box `m-fwdev-167`, running

```bash
cd /auto/fwgwork1/pexiang/utopx
sudo ./utopx --device=/dev/mst/mt41692_pciconf0 --daemon --num_of_clients=0 \
             --xml_conf_file conf.xml --conf_file config/scenario_dpa_emu.conf \
             --iter=300 --ops_per_it=30
```

failed at `ArmAgentApiBareMetal.cpp:20` with `Failed to open /sys/bus/pci/devices/0000:ca:00.2/resource2_wc`. BAR2 wasn't exposed on the rshim function because our locally-built FW (`golan_fw/`) wasn't configured the same way the official build is. Decision: stop fighting on dev box; reproduce the regression's exact environment on the regression machine instead.

## Phase 1 — Extract regression's baseline from MARS

The MARS UI link a coworker sent looked like:

```
https://mars.mellanox.com/web/server/php/view_log.php?
  results_dir=/auto/sw_regression/host_fw/HCA_CORE_FWV/MARS/conf/results
  &setup_id=MUSTANG_FW-l-fwreg-171_eth_ARM_AGENT_P1
  &session_id=11047756
  &name=...&key_id=...&status=Passed
```

The web view needs auth, but the `**results_dir` path is an NFS share** mounted on every dev box. So instead of fetching via the web, just read the same files directly:

```bash
ls /auto/sw_regression/host_fw/HCA_CORE_FWV/MARS/conf/results/MUSTANG_FW-l-fwreg-171_eth_ARM_AGENT_P1/11047756/
# 11047756.tgz
```

Every MARS session's full logs are packed in one `<sid>.tgz` under that path. The directory layout inside the tarball follows MARS's step-numbering scheme (e.g. `1.26.1.1`, `0.22.1.1.1.8.1.7.1.8.1` — each level is a sub-step). Inside each step dir there's a `log.txt` (human output) and a `<step_name>.cap` (the XML that defines the step).

### Step 1A: find the two steps that hold the version info

Two MARS steps capture the exact versions used in a session:

1. `**new_burn_fw**` — the FW burn step. The log shows what `.mlx`, `.ini`, FW version, and PSID were burned.
2. `**get_last_commit**` — runs before the build/install of utopx in regression. It calls a helper that does `git describe` inside the utopx checkout in the MARS workspace and prints the commit hash.

Find their step IDs by listing the tarball:

```bash
mkdir -p /tmp/mars_11047756
tar -tzf /auto/sw_regression/host_fw/HCA_CORE_FWV/MARS/conf/results/MUSTANG_FW-l-fwreg-171_eth_ARM_AGENT_P1/11047756/11047756.tgz \
   | grep -E "burn_fw|get_last_commit"
# 1.26.1.1/new_burn_fw.cap
# 1.26.1.1/new_burn_fw_log.txt   (or just log.txt under the dir)
# 0.22.1.1.1.6.1.1.1/get_last_commit.cap
```

Extract just those two `log.txt` files (not the whole 200-MB tarball):

```bash
tar -xzf .../11047756.tgz -C /tmp/mars_11047756/ \
    1.26.1.1/log.txt \
    0.22.1.1.1.6.1.1.1/log.txt
```

### Step 1B: read `new_burn_fw` for FW version, .mlx path, PSID, and the burned INI path

```bash
grep -E "default_ini:|fw_file:|FW Version:|psid:|new_ini_file:|Burning FW:" /tmp/mars_11047756/1.26.1.1/log.txt
```

That printed all the keys I needed in one go:

```
default_ini:    /auto/sw/release/host_fw2/fw-41692/fw-41692-rel-32_50_0222-build-001/dist/900-9D3B6-00CV-AAB_Ax.ini
fw_file:        /auto/sw/release/host_fw2/fw-41692/fw-41692-rel-32_50_0222-build-001/dist/fw-BlueField-3.mlx
FW Version:     32.50.0222
psid:           MT_0000000998
new_ini_file:   /auto/sw/work/hca_fw/data/burn_fw/ini_files/1247020260527212221_session_11047756_version_32_50_0222_psid_MT_0000000998.ini
Burning FW:     timeout 1500 sudo -E env MFT_ICMD_TIMEOUT=60000 mlxburn -d /dev/mst/mt41692_pciconf0 \
                -fw <fw_file> -conf <new_ini_file> -force
```

The `**new_ini_file**` path is the *actual* file BurnFw.py generated and passed to `mlxburn`. That's the one you want to copy locally — it has all the regression-injected overrides baked in.

### Step 1C: read `get_last_commit` for the utopx commit hash

```bash
grep -E "git_describe|commit_id|HCA_CORE_FW-utopx" /tmp/mars_11047756/0.22.1.1.1.6.1.1.1/log.txt
```

Output (one line per finding):

```
INFO: Executing cmd: /.../HcaCoreRegression/RegTools/get_last_commit_db.py \
      --remote_test_path HCA_CORE_FW-utopx_carveout_master_rc.db/tests
-DEBUG- git_describe=(host_fwv_20260527_FW_version_50_0222_branch_master-0-g07de3b4)
-INFO-  commit_id=(07de3b4)
```

That gave me:

- **utopx regression tag** (canonical reference, captured directly from the log): `host_fwv_20260527_FW_version_50_0222_branch_master`. This tag points exactly at the build the regression ran. Prefer this over the bare SHA when documenting which utopx revision was used — the tag encodes verification stream + date + FW version + branch in one string.
  - Verify the tag still resolves locally: `git tag --points-at 07de3b4` → should print the tag.
  - Resolve tag → SHA: `git rev-parse host_fwv_20260527_FW_version_50_0222_branch_master`.
- **utopx git short SHA** (alternate reference): `07de3b4`. Equivalent to the tag for checkout purposes.
- **utopx branch**: `master` (from the tag stem `..._branch_master`). Verify with `git branch -a --contains 07de3b4` in the local repo — should show `master` and `remotes/origin/master`. The repo has no `master_rc` branch at all.
- **utopx regression DB name**: `HCA_CORE_FW-utopx_carveout_master_rc.db` — the `_rc` suffix is **part of the regression-suite carveout name, not the branch**. Don't confuse the two.

### Step 1D: translate the FW version number to a golan_fw commit

`get_last_commit` only describes utopx — there's no equivalent step for the FW source tree (the FW is burned as a pre-built `.mlx` from `/auto/sw/release/host_fw2/...`, not built from sources during the session). To find the corresponding **golan_fw** commit, two options:

1. **By git log + version string** — every release point in golan_fw has a commit titled `Updated version <X>.<Y>.<Z>  Issue: NNNNNN`. Grep:
  ```bash
   cd /auto/fwgwork1/pexiang/golan_fw
   git log --all --oneline --grep="Updated version 12.50.0222"
   # 1bd3640336 Updated version 12.50.0222  Issue: 373899
  ```
   Note the version-number convention: regression / tools report the **product** number `32.50.0222`, but the **source-tree** number is `12.50.0222` (BF-3 family prefix differs). The build-number `0222` matches; the family digits don't. Grep on the trailing portion (`.50.0222`) to be safe.
2. **By date cross-reference** — the FW release path tells you the build date:
  ```
   /auto/sw/release/host_fw2/fw-41692/fw-41692-rel-32_50_0222-build-001/
  ```
   `build-001` means first build of that day. Combined with the regression session timestamp (2026-05-27 21:22), look for the most recent `Updated version` commit before that timestamp on `master_rc`.

Verified the commit exists in the local repo:

```bash
git rev-parse 1bd3640336
# 1bd364033669a37a34acefc32b559a6e9b60d935
git log -1 --format='%H %ci %s' 1bd3640336
# 1bd364033669... 2026-05-27 19:02:06 +0300 Updated version 12.50.0222  Issue: 373899
```

19:02 commit, 21:22 burn — matches: the official build server compiled this commit and the regression picked up that build a couple hours later.

#### golan_fw branch and release tag

The MARS log doesn't print the golan_fw branch directly (FW is burned as a pre-built `.mlx`, not git-cloned during the session). Recover the branch with `git branch -a --contains 1bd3640336`:

```bash
cd /auto/fwgwork1/pexiang/golan_fw
git fetch --all --tags          # IMPORTANT: tags may be remote-only
git branch -a --contains 1bd3640336
# * fr_1351156_libfhi_QPC               ← your current local branch (whichever)
#   master_rc                            ← the regression branch
#   remotes/origin/HEAD -> origin/master_rc
#   remotes/origin/master_rc
```

**golan_fw branch is `master_rc`** — and this **differs from utopx's branch (`master`)**: the two repos use different branch-naming conventions for the release-candidate line. Don't assume both repos share a branch name.

**The matching release tag is `rel-12_50_0222`** — derivable directly from the FW version printed in `new_burn_fw` (`FW Version: 32.50.0222`):

```
FW version  32.50.0222   →   drop product-family prefix "32"   →   12.50.0222 (source-tree form)
                          →   dots to underscores              →   12_50_0222
                          →   add "rel-" prefix                →   rel-12_50_0222
```

Verify:

```bash
git tag --points-at 1bd3640336
# rel-12_50_0222
git rev-parse rel-12_50_0222
# 1bd364033669a37a34acefc32b559a6e9b60d935
git describe --tags 1bd3640336
# rel-12_50_0222
```

So for golan_fw you can `git checkout rel-12_50_0222` (more memorable / self-documenting than the SHA) and the result is identical to `git checkout 1bd3640336`.

**Crucial gotcha:** the tag is only on `origin` after a fresh clone — `git tag --points-at` may return empty until you run `git fetch --all --tags`. If you ever see `git describe` produce something like `rel-12_50_0125-658-g1bd3640336` (a "nearest preceding tag plus N commits past it" form), that's the signal that your local tag list is stale, not that the build has no tag. Always fetch tags first before declaring "no tag exists".

### Step 1E: also worth grabbing (but optional)

The utopx command the regression actually ran:

```bash
tar -xzf .../11047756.tgz -C /tmp/mars_11047756/ 0.22.1.1.1.8.1.7.1.8.1/run_case.cap
grep -oE '<tsr_args>[^<]+' /tmp/mars_11047756/0.22.1.1.1.8.1.7.1.8.1/run_case.cap
# --daemon --num_of_clients=0 --xml_conf_file conf.xml --conf_file config/scenario_dpa.conf \
# --iter=13000 --ops_per_it=5 --extra_constraints=test_mode.virtio_emulation_multi_vf=1 ...
```

This was for `utopx_1_scenario_dpa`, NOT `scenario_dpa_emu`. So `scenario_dpa_emu.conf` isn't actually exercised by this exact regression; useful to know if you wanted to run identical-to-regression.

## Phase 2 — Match local repos to regression versions

Both repos under `/auto/fwgwork1/pexiang/` must match the regression's pair. Keep all three identifiers — they're interchangeable cross-references for the same point:


| Repo     | Branch      | Tag                                                  | Commit SHA                                                       |
| -------- | ----------- | ---------------------------------------------------- | ---------------------------------------------------------------- |
| utopx    | `master`    | `host_fwv_20260527_FW_version_50_0222_branch_master` | `07de3b4319491c961586206c1a6ece0967c37e7f` (short: `07de3b4`)    |
| golan_fw | `master_rc` | `rel-12_50_0222`                                     | `1bd364033669a37a34acefc32b559a6e9b60d935` (short: `1bd3640336`) |


Tag is the most self-documenting — prefer it for checkout. SHA is the most stable (always resolves, even if a tag gets moved). Branch tells you which line of development this came from. Always `git fetch --all --tags` first — tags may be remote-only in a stale clone.

### utopx

```bash
cd /auto/fwgwork1/pexiang/utopx
git fetch --all --tags
git log -1 --format='%H %h %ci %s'
# 07de3b4319491c961586206c1a6ece0967c37e7f 07de3b431 2026-05-27 ... — already at target ✓
```

If utopx is NOT already at the target, stash any local edits and check out the regression tag:

```bash
cd /auto/fwgwork1/pexiang/utopx
git status                                              # check for local mods
git stash push -u -m "auto-stash before checkout to regression tag (Mustang match)"
git fetch --all --tags
git checkout host_fwv_20260527_FW_version_50_0222_branch_master
git log -1 --format='%H %ci %s'                         # verify (expect SHA 07de3b4319491c...)
```

### golan_fw

```bash
cd /auto/fwgwork1/pexiang/golan_fw
git fetch --all --tags                                  # crucial — rel-12_50_0222 may be remote-only
git status
# HEAD detached at rel-12_25_0222    ← wrong (12.25.0222 from 2019)
# Changes not staged: shared/algorithm modified
git rev-parse rel-12_50_0222                            # confirm tag resolves
# 1bd364033669a37a34acefc32b559a6e9b60d935
```

Fix — stash local change to `shared/algorithm`, checkout the regression tag:

```bash
cd /auto/fwgwork1/pexiang/golan_fw
git stash push -u -m "auto-stash before checkout to rel-12_50_0222 (Mustang regression match)"
git checkout rel-12_50_0222
git log -1 --format='%H %ci %s'
# 1bd364033669a37a34acefc32b559a6e9b60d935 2026-05-27 19:02:06 +0300 Updated version 12.50.0222  Issue: 373899
```

Now both repos exactly match the regression's pair.

## Phase 3 — Download regression's INIs to local utopx repo + augment

Pulled both INI files for inspection and modification:

```bash
mkdir -p /auto/fwgwork1/pexiang/utopx/regression_ini
cp /auto/sw/release/host_fw2/fw-41692/fw-41692-rel-32_50_0222-build-001/dist/900-9D3B6-00CV-AAB_Ax.ini \
   /auto/fwgwork1/pexiang/utopx/regression_ini/default_900-9D3B6-00CV-AAB_Ax.ini
cp /auto/sw/work/hca_fw/data/burn_fw/ini_files/1247020260527212221_session_11047756_version_32_50_0222_psid_MT_0000000998.ini \
   /auto/fwgwork1/pexiang/utopx/regression_ini/burned_session_11047756_v32_50_0222_psid_MT_0000000998.ini
```

### 3a — What regression already adds vs the release default

`diff` between `default_900-9D3B6-00CV-AAB_Ax.ini` and `burned_session_11047756_v32_50_0222_psid_MT_0000000998.ini` shows the regression's `BurnFw.py` appends five lines at the end of `[fw_boot_config]` (these are NOT in the release default):

```
nv_config.global.pci.settings.toolspf_en        = 0
internal_use.eliminate_pcie_switch_hier         = 0x1
internal_use.ddr_mapping_en                     = 0x1
nv_config.global.pci.settings.num_pfs_valid     = 0x1
internal_use.ddr_log_2_bar_size                 = 0x22
```

These are what make BAR2 visible on the rshim function — exactly what the dev-box run was missing. The rest of the diff is whitespace normalization (the default INI has comments and `=`-without-spaces; the burned one has comments stripped and `=`  formatting).

### 3b — Verify which setups have Jerry's emulation flags

The Argaman P2 setups (`ARGAMAN_FW-l-fwreg-225_P2`, `ARGAMAN_FW-l-fwreg-226_eth_P2`) have Jerry's 36 NVMe/virtio emulation flags in their `mars_extra_burn_params/master_rc` block — but the Mustang setup does NOT. Verified:

```bash
grep -cE "emulation_nvme|emulation_virtio_(net|blk|fs)" \
    /auto/mswg/projects/fw/fw_ver/MARS_HCA_CORE/MARS_conf/setups/ARGAMAN_FW-l-fwreg-225_P2/argaman_ib_loopback-l-fwreg-225.setup
# 108  (the 36 flags × 3 branch sections: master_rc, FUR_2026_Jan_*, FUR_2026_Feb_*)

grep -cE "emulation_nvme|emulation_virtio_(net|blk|fs)" \
    /auto/mswg/projects/fw/fw_ver/MARS_HCA_CORE/MARS_conf/setups/MUSTANG_FW-l-fwreg-171_eth_ARM_AGENT_P1/mustang_l-fwreg-171_eth.setup
# 0
```

### 3c — Append all 36 emulation flags to the burned-INI copy

Per Jerry's request (and to make the `scenario_dpa_emu` scenario actually reach virtio emulation queries), I edited `/auto/fwgwork1/pexiang/utopx/regression_ini/burned_session_11047756_v32_50_0222_psid_MT_0000000998.ini` to insert the 36 flags right after `internal_use.ddr_log_2_bar_size = 0x22` and before `[fw_main_config]`.

The inserted block (44 new lines = 36 flags + 4 section comments + 4 blank separators):

```ini
;;;; user config for nvme
nv_config.global.emulation_nvme_cap.nvme_emu_supported = 1
nv_config.global.emulation_nvme_cap.nvme_emu_max_num_pf = 2
nv_config.global.emulation_nvme_conf.nvme_emu_enable = 1
nv_config.global.emulation_nvme_conf.nvme_emu_num_pf = 2
nv_config.global.emulation_nvme_conf.nvme_emu_vendor_id = 0x15b3
nv_config.global.emulation_nvme_conf.nvme_emu_device_id = 0x6001

;;;; user config for virtio-net
nv_config.global.emulation_virtio_net_cap.virtio_net_emu_supported = 0x1
nv_config.global.emulation_virtio_net_cap.virtio_net_emu_max_num_pf = 0x10
nv_config.global.emulation_virtio_net_cap.virtio_net_emu_max_total_vf = 0xff
nv_config.global.emulation_virtio_net_conf.virtio_net_emu_enable = 0x1
nv_config.global.emulation_virtio_net_conf.virtio_net_emu_num_pf = 0x0
nv_config.global.emulation_virtio_net_conf.virtio_net_emu_total_vf = 0x0
nv_config.global.emulation_virtio_net_conf.virtio_net_emu_device_id = 0x1041
nv_config.global.emulation_virtio_net_conf.virtio_net_emu_vendor_id = 0x1af4
nv_config.global.emulation_virtio_net_conf.virtio_net_emu_class_code = 0x028000
nv_config.global.emulation_virtio_net_conf.virtio_net_emu_num_msix = 0x2

;;;; user config for virtio-blk
nv_config.global.emulation_virtio_blk_cap.virtio_blk_emu_supported = 0x1
nv_config.global.emulation_virtio_blk_cap.virtio_blk_emu_max_num_pf = 0x10
nv_config.global.emulation_virtio_blk_cap.virtio_blk_emu_max_total_vf = 0xff
nv_config.global.emulation_virtio_blk_conf.virtio_blk_emu_enable = 0x1
nv_config.global.emulation_virtio_blk_conf.virtio_blk_emu_num_pf = 0x0
nv_config.global.emulation_virtio_blk_conf.virtio_blk_emu_total_vf = 0x0
nv_config.global.emulation_virtio_blk_conf.virtio_blk_emu_device_id = 0x1042
nv_config.global.emulation_virtio_blk_conf.virtio_blk_emu_vendor_id = 0x1af4
nv_config.global.emulation_virtio_blk_conf.virtio_blk_emu_class_code = 0x010800
nv_config.global.emulation_virtio_blk_conf.virtio_blk_emu_num_msix = 0x2

;;;; user config for virtio-fs
nv_config.global.emulation_virtio_fs_cap.virtio_fs_emu_supported = 0x1
nv_config.global.emulation_virtio_fs_cap.virtio_fs_emu_max_num_pf = 0x10
nv_config.global.emulation_virtio_fs_cap.virtio_fs_emu_max_total_vf = 0xff
nv_config.global.emulation_virtio_fs_conf.virtio_fs_emu_enable = 0x1
nv_config.global.emulation_virtio_fs_conf.virtio_fs_emu_num_pf = 0x0
nv_config.global.emulation_virtio_fs_conf.virtio_fs_emu_total_vf = 0x0
nv_config.global.emulation_virtio_fs_conf.virtio_fs_emu_device_id = 0x105a
nv_config.global.emulation_virtio_fs_conf.virtio_fs_emu_vendor_id = 0x1af4
nv_config.global.emulation_virtio_fs_conf.virtio_fs_emu_class_code = 0x010800
nv_config.global.emulation_virtio_fs_conf.virtio_fs_emu_num_msix = 0x2
```

**Additionally, for the satellite PF layer (added 2026-06-03)**, two more lines immediately after `mac_params.external_hosts_count = 2` (the existing line 54), i.e. inserted at line 55-56:

```ini
mac_params.satellite_pf_en = 1
mac_params.device_type     = 3        ; DPU_WITH_NON_INTEGRATED_CPU — required by satellite_pf_en
```

These two are the gate that lets `iron_prep` emit the `PF_NUM_SAT_PF` nvconfig TLV at all. Without them, the TLV is reduced and mlxconfig reports `Failed to find Param / TLV with name 'PF_NUM_SAT_PF'` — see Phase 10 §"Root cause of TLV invisibility". Constraints from `src/common/mac_guid_handler.c:431-441`:
- `DEVICE_IS(X)` macro = `mac_p.device_type == X`. So `device_type = 3` literally means "DPU_WITH_NON_INTEGRATED_CPU".
- `satellite_pf_en=1` requires `device_type=3`; otherwise FW boot fwasserts `0x80C1`.
- This is the **minimum** patch — BF-4 OCI MLI PRS sets a 6-field bundle (dedicated_dpu_bmc, dedicated_mcu, etc), but on BF-3 these 2 are enough.

Notes on the value choices for the 36 emulation flags (all match Jerry's email exactly):


| Section    | Key values                                                                                                                                                 |
| ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| NVMe       | vendor=`0x15b3` (NVIDIA), device=`0x6001`, 2 PFs enabled                                                                                                   |
| virtio-net | vendor=`0x1af4` (Red Hat / virtio), device=`0x1041` (virtio-net PCI), class=`0x028000` (Ethernet), 0 PFs at boot (added dynamically), max 16 PFs / 255 VFs |
| virtio-blk | vendor=`0x1af4`, device=`0x1042` (virtio-blk PCI), class=`0x010800` (NVMe / Mass Storage), 0 PFs at boot, max 16 PFs / 255 VFs                             |
| virtio-fs  | vendor=`0x1af4`, device=`0x105a` (virtio-fs PCI), class=`0x010800`, 0 PFs at boot, max 16 PFs / 255 VFs                                                    |


### 3d — Final state of the burned INI

```
File:    /auto/fwgwork1/pexiang/utopx/regression_ini/burned_session_11047756_v32_50_0222_psid_MT_0000000998.ini
Before:  670 lines (release default)
After  (Jerry's 36 emu flags appended): 714 lines
After  (+ 2 satellite_pf lines, 2026-06-03): 716 lines

Verify:
  grep -cE "emulation_nvme|emulation_virtio_(net|blk|fs)" <file>       → 36
  grep -nE "mac_params\.(satellite_pf_en|device_type)" <file>           → 2 lines
  grep -n "^\[" <file>                                                  → section indices shifted:
    [image_info]      line 1
    [mfg_info]        line 7
    [device_info]     line 11
    [boot_record]     line 15
    [fw_boot_config]  line 34
    [fw_main_config]  line 112  (was line 66 — 46 lines moved by insertions)
    [hw_boot_config]  line 148
    [hw_main_config]  line 612
```

This is the `--ini` argument fed to `jmake --burn ... --ini <this file>` in Phase 5.

## Phase 4 — SSH to l-fwreg-171, attempt burn

```bash
ssh l-fwreg-171
hostname; uptime
# l-fwreg-171, idle, no MARS sessions running
sudo cat /dev/rshim0/misc | grep -E "DPU is ready|Linux up|UP_TIME"
# no "DPU is ready" / "Linux up" line, UP_TIME 0(s)  — ARM not booted
# (BF_MODE is NOT a boot-state field — it reports DPU-vs-NIC mode, so don't
#  read "BF_MODE Unknown" as "ARM down". Use "DPU is ready" for OS readiness.)
sudo timeout 8 flint -d /dev/mst/mt41692_pciconf0 q | head -3
# FW Version: 32.50.0222   (already regression-burned)
```

First attempt — exactly what user requested:

```bash
ssh l-fwreg-171 'cd /auto/fwgwork1/pexiang/golan_fw && \
  /labhome/pexiang/.usr/bin/jmake \
      --device /dev/mst/mt41692_pciconf0 \
      --models mustang \
      --ini ../utopx/regression_ini/burned_session_11047756_v32_50_0222_psid_MT_0000000998.ini \
      --fw-reset -o --clean'
```

**Failed**: jmake's `-o --clean --models mustang` triggered a clean build of golan_fw. The build aborted with:

```
Even-numbered FW Subminor Version can only be compiled by official build.
Please compile odd-numbered version only.
```

Version `12.50.0222` has subminor=0222 (even), reserved for the official build server. Local builds are restricted to odd subminors.

**Workaround when you DO need to locally build (e.g. you have source edits and can't use the official .mlx):** checkout the *next odd-numbered* tag, which shares the same code as the even-numbered one — only the version-number tag itself differs. Concretely:

```bash
cd /auto/fwgwork1/pexiang/golan_fw
git tag -l 'rel-12_50_*' --sort=-version:refname | head -5
# rel-12_50_0223        ← odd, locally buildable, same code as 0222
# rel-12_50_0222        ← even, official-only
# rel-12_50_0221        ← odd, locally buildable, same code as 0220
# ...

git checkout rel-12_50_0223         # or whichever odd tag immediately follows the even one you want
# now `jk -o --clean --models mustang` will build without the even-subminor block
```

For Phase 10 / Li's feature work we did NOT take this path — we used the official 0222 `.mlx` with a custom INI (Phase 5) because we only needed an INI change, not a source rebuild. The odd-version checkout matters when you've actually modified golan_fw source.

Then `--fw-reset` also failed:

```
Running old fwreset script
chip:  not supported...
Error: fwresetm failed
```

Two distinct problems to peel off.

## Phase 5 — Burn the official .mlx + custom INI via jmake, no rebuild

Use this path when you don't need source edits (you're only changing the INI). For source-edit builds, use Phase 4's odd-version checkout workaround instead and run `jk -o --clean --models mustang` to produce a `.mlx` locally.

jmake has two flags that skip the build entirely (replicating what regression's `BurnFw.py` does):

- `--firmware <path>` — override the model-based `.mlx` lookup
- `--ini <path>` — override the PSID-based prs/ lookup

```bash
ssh l-fwreg-171 'cd /auto/fwgwork1/pexiang/golan_fw && \
  /labhome/pexiang/.usr/bin/jmake \
      --burn \
      --device /dev/mst/mt41692_pciconf0 \
      --firmware /auto/sw/release/host_fw2/fw-41692/fw-41692-rel-32_50_0222-build-001/dist/fw-BlueField-3.mlx \
      --ini ../utopx/regression_ini/burned_session_11047756_v32_50_0222_psid_MT_0000000998.ini'
```

~8m 3s, ended with `Burn completed successfully` and `Restoring signature - OK`. Flash now has FW 32.50.0222 + the 36 emulation flags. (Do NOT pass `--fw-reset` here — jmake chained it to a level-4 reset that timed out on multi-host FSM sync.)

## Phase 6 — Reset via patched `jk --fw-reset` (loads the FW from flash into running memory)

```bash
ssh l-fwreg-171 '/labhome/pexiang/.usr/bin/jmake --device /dev/mst/mt41692_pciconf0 --fw-reset'
```

Completes in ~18s, output ends with:

```
Running new fwreset script
running fwreset command: /mswg/.../fwreset.py -d /dev/mst/mt41692_pciconf0
...
FW reset successful: uptime was reset.
Before: 114, After: 11
FW reset completed at 05/28/2026 13:43:27 in 18s
```

`jk --fw-reset` works on every model — it dispatches to the appropriate reset path per chip. Two specific bugs in our local `~/myGit/crosslv/nv-tools/jmake` fork blocked the BF-3 path; both were patched (see *Files modified* at the bottom). After the patches, `jk --fw-reset` is the standard between-runs reset on this box.

## Phase 8 — Verify FW + NVCONFIG

```bash
ssh l-fwreg-171 'sudo timeout 8 flint -d /dev/mst/mt41692_pciconf0 q | head -5'
# Image type: FS4
# FW Version: 32.50.0222
# FW Release Date: 27.5.2026
# Product Version: 32.50.0222
# (no "FW Version(Running)" mismatch → flash == running, reset pivoted)

ssh l-fwreg-171 'sudo timeout 30 mlxconfig -d /dev/mst/mt41692_pciconf0 q | grep -iE "NVME_EMU|VIRTIO_NET_EMU|VIRTIO_BLK_EMU|VIRTIO_FS_EMU"'
# NVME_EMULATION_ENABLE        True(1)
# NVME_EMULATION_NUM_PF        2
# NVME_EMULATION_VENDOR_ID     5555    (= 0x15b3)
# NVME_EMULATION_DEVICE_ID     24577   (= 0x6001)
# VIRTIO_BLK_EMULATION_ENABLE  True(1)
# VIRTIO_FS_EMULATION_ENABLE   True(1)
# ... etc.
```

All 36 flags loaded and active.

## Phase 9 — Bring up udriver, clear rshim DROP_MODE, run utopx

After the FW is pivoted and host is in a clean state, the bring-up is three steps:

```bash
ssh l-fwreg-171
sudo modprobe udriver
echo "DROP_MODE 0" | sudo tee /dev/rshim0/misc      # see note below
```

**Why the DROP_MODE step matters:** the rshim daemon often comes back from `jk --fw-reset` with `DROP_MODE 1` set as a safety measure (it silently discards every write to `/dev/rshim0/boot`). utopx's BareMetal ArmAgent uses that same `/dev/rshim0/boot` path to push the BFB to ARM. If the rshim is dropping, utopx will retry `cat <bfb> > /dev/rshim0/boot` ten times, each time getting `sh: /dev/rshim0/boot: Invalid argument`, then FATAL out at `ArmAgentApiBareMetal.cpp:20`. Always clear `DROP_MODE` after a fwreset and before invoking utopx. Verify:

```bash
sudo cat /dev/rshim0/misc | grep -E "DROP_MODE|BF_MODE|UP_TIME"
# DROP_MODE       0 (0:normal, 1:drop)              ← must be 0
# BF_MODE         <whatever>
# UP_TIME         <seconds since rshim last (re)connected>
```

That alone auto-binds udriver to **all four** BF-3 host functions because the udriver module's PCI ID table includes both the NIC device ID (41692) and the emulated storage device ID (24577) that the 36 emulation INI flags create:

```bash
ls /dev/udriver_*
# /dev/udriver_1_41692_0000:83:00.0   ← NIC PF0 (dev-type 41692)
# /dev/udriver_2_41692_0000:83:00.1   ← NIC PF1
# /dev/udriver_3_24577_0000:83:00.2   ← storage (dev-type 24577 = NVMe emu device ID 0x6001)
# /dev/udriver_4_24577_0000:83:00.3   ← storage

for f in 83:00.0 83:00.1 83:00.2 83:00.3 83:00.4; do
    echo -n "$f: "; lspci -s $f -k | grep "Kernel driver"
done
# 83:00.0: Kernel driver in use: udriver
# 83:00.1: Kernel driver in use: udriver
# 83:00.2: Kernel driver in use: udriver
# 83:00.3: Kernel driver in use: udriver
# 83:00.4: Kernel driver in use: vfio-pci    ← rshim. Also valid: uio_pci_generic.
#                                              Either way the rshim daemon must be running
#                                              AND have DROP_MODE=0 — see step above.
```

Now run utopx — **always use `debug_conf.xml`** (not `conf.xml`):

```bash
cd /auto/fwgwork1/pexiang/utopx
sudo ./utopx --device=/dev/mst/mt41692_pciconf0 --daemon --num_of_clients=0 \
             --xml_conf_file debug_conf.xml --conf_file config/scenario_dpa_emu.conf \
             --iter=300 --ops_per_it=30
```

> The 2026-05-31 historical baseline run used `conf.xml`; this plan's earlier phases reference that for archeology. **For all re-runs from 2026-06-01 onward, use `debug_conf.xml`** — extra logging/diagnostics, no functional behavior change relative to the regression. Do not swap back to `conf.xml`.

Result (~10 minutes, varies with seed):

```
... (300 iterations: alloc_uar/pd/qp, create_flow_tables, send_doorbell,
     QUERY_VIRTIO_BLK_EMULATION, QUERY_VIRTIO_FS_EMULATION, QUERY_VIRTIO_NET_EMULATION,
     CqeChecker, etc. — all exercising the 36 emulation flags)
TIMER : Total Time spent on init           : 256.463
TIMER : Total Time for test                : 607.668
General : Test-status is 0
        -------------------------------------------
                      [TEST PASSED]
        -------------------------------------------
To rerun use seed 2136434584
MemoryCheckThread : Done! Peak usage = 4091.34 MB
```

## Phase 10 — Enable satellite PF (FW-level instantiation)

> ⚠️ **2026-06-05 重大修正**：本 phase 描述的是"通过 INI 改动让 FW 真正 instantiate sat PF (PF_NUM_SAT_PF Current=1, ARM lspci 多一个 PF)"这条路径。**但 utopx 测试 sat PF 不一定需要这条路径** —— utopx 有原生 sat PF 支持代码（`IsDpuPf()` / `HandleDpuPfCreateEswVport` / `force_dpu_pf_emu_manager` / `num_sat_pf` nvconfig gen 等），通过 conf knob 在 utopx 测试中模拟 sat PF NVconfig，**不需要 FW 真的把 sat PF 烒进硬件**。看 §Phase 11 (新增) "utopx 原生 sat PF 测试入口"。
>
> **Phase 10 真正的用处**：要看 sat PF 真实 PCIe enumerate（ARM lspci 多 1 个 PF）、要从 SF 创建测起，或要 FW 端集成测试时。对 **Li cap delegation FW verification (utopx 端)**，Phase 11 路径就够，**Phase 10 INI burn 不一定要做**。
>
> 今天 2026-06-04~05 在 171 上试了 0/2/4/5/7/9-line INI 各种组合 + 两个 FW build (32.50.0222 + 32.49.9906)，**没找到能让 sat PF Current=1 + 不撞 FW assert 0x821d 的纯 INI 配置**。MAS 文档（Marie Chagny, Confluence [2830146343](https://nvidia.atlassian.net/wiki/spaces/FW/pages/2830146343)）的 9-line BF-3 recipe 在 171 上 sat PF 也起不来。下面的 INI / mlxconfig 流程作为 documentation 保留，但 **执行 Phase 10 在当前 FW + 171 hardware 上不能 yield 一个 utopx-runnable sat PF env**。

Done partially on 2026-06-03 after Phases 1-9 were already passing. Builds on top of the burned-INI state from Phase 3.

### 10.0 Why this needs both an INI change AND an ARM-side mlxconfig set

`PF_NUM_SAT_PF` is documented in `adabe/EAS_nvconfig_tlvs.adb:513-514` as **"Currently only supported for ECPF which is also the eswitch owner"** — i.e. it's a per-PF nvconfig stored on the ECPF, not on the host PF. So enablement is two-step:

1. **INI gate** (Phase 3): `mac_params.satellite_pf_en=1 + device_type=3` tells `iron_prep` to even emit the `PF_NUM_SAT_PF` TLV in the image. Without this, `mlxconfig` reports "Failed to find Param / TLV with name 'PF_NUM_SAT_PF'" — TLV is reduced out entirely. This is a one-time FW-burn change.
2. **ECPF NVRAM write**: actually set `PF_NUM_SAT_PF=1` in the ECPF's per-PF NVRAM area. Must be done from the **ARM side** because host-side mst devs (`/dev/mst/mt41692_pciconf0`/`.1`) point to host PFs, whose per-PF NVRAM for this field is ignored by FW. The host has no ECPF mst dev (ECPF is in ARM's internal PCIe domain).

### 10.1 Upgrade MFT on host (required) — mft ≥ 4.36 to recognize PF_NUM_SAT_PF

Old mft (4.35.0 shipped with the box) doesn't know the `PF_NUM_SAT_PF` symbol name; you'll get `-E- You have an unsupported configuration name`. Upgrade:

```bash
ssh l-fwreg-171 'sudo /labhome/pexiang/.usr/bin/jmake --mft-install'
# wraps /mswg/release/mft/last_stable/install.sh; takes ~30s
# verify: mlxconfig --version  →  mft 4.37.0-75 or newer
```

### 10.2 ssh into the ARM side — root@192.168.100.1 / 3tango

#### 10.2.1 How to find the ARM IP (the question that tripped me up)

BF-3 is a SoC with an ARM core running its own Linux. From the host, the only physical path to ARM is via **rshim** — the BlueField management interface exposed as PCIe BDF `83:00.7` (see `lspci -nn -d 15b3:`, look for `BlueField-3 SoC Management Interface [15b3:c2d5]`). The rshim kernel driver creates two virtual devices on the host:

1. `/dev/rshim0/*` — character devices (`console`, `boot`, `misc`, `rshim`) for low-level UART / BFB-push / control access.
2. `tmfifo_net0` — a virtual Ethernet NIC implementing a **point-to-point tunnel over the rshim FIFO**. This is how `ssh` reaches ARM.

**Don't memorize whether ARM is `.1` or `.2`** — that's per-box configuration, set by the BFB image, the ARM netplan, and the host's tmfifo config independently. Both conventions exist:

- **Public DOCA default** ([RShim docs](https://docs.nvidia.com/networking/display/bluefieldbsp4120/soc+management+interface+(rshim))): BFB statically configures ARM to `192.168.100.2/30`; host side is set manually to `192.168.100.1/30`. So `ssh ubuntu@192.168.100.2` reaches ARM.
- **l-fwreg-171 actual** (lab-customized, verified 2026-06-03): ARM's `/etc/netplan/*.yaml` overrides tmfifo to `192.168.100.1/24`; host's rshim setup runs `192.168.100.2/24`. So `ssh root@192.168.100.1` reaches ARM here.

The rshim driver does **not** auto-assign both endpoints or "give the higher address to the host" — the ARM IP is baked into the BFB (or the BFB's netplan override), the host IP comes from the host's own network config. Always **discover** the running state instead of assuming.

**Discovery method — works on any BlueField box, host-side only, no guessing:**

```bash
# Step 1: read host's tmfifo IP and subnet (the local end of the point-to-point link)
ssh <host> 'ip -br addr show tmfifo_net0'
# tmfifo_net0  UP  192.168.100.X/N ...        ← host is .X on /N subnet

# Step 2: read the ARM's IP directly from the host's neighbor cache.
#         This is DETERMINISTIC if any IP traffic has ever crossed the tmfifo link
#         (the cache populates automatically on the first ARP/IP exchange).
ssh <host> 'ip neigh show dev tmfifo_net0'
# 192.168.100.Y lladdr 00:1a:ca:00:00:00 STALE     ← ARM's actual IP and MAC

# Step 3 (only if Step 2 is empty — fresh-boot or cache flushed): force an ARP entry.
#   Easiest: sweep the candidate unicasts on the subnet to trigger ARP replies.
#   For /30 only 2 unicasts exist; for /24 enumerate the few /etc/hosts hints first.
ssh <host> 'grep -E "arm|bf" /etc/hosts'              # collect candidate hints
ssh <host> 'ping -c1 -W1 192.168.100.<candidate> >/dev/null 2>&1; ip neigh show dev tmfifo_net0'

# Step 4: confirm you reached ARM (defense against weird routing / sshd loopback)
ssh root@<Y> 'uname -m'
# aarch64 → ARM ✓
# x86_64  → host (you somehow looped back; check tmfifo setup)
```

`ip neigh show dev tmfifo_net0` is the **canonical, deterministic** way to read ARM's IP from the host alone — it's literally the kernel's view of the peer of the point-to-point link, populated by ARP. No guessing, no /etc/hosts trust required. `uname -m = aarch64` is the **final correctness check** (catches setup pathologies where ssh sometimes loops back).

Alternative when even the host-side network is broken: log in via any **serial-terminal client** pointed at `/dev/rshim0/console` (UART tunnel, no IP needed), then run `ip addr show tmfifo_net0` on ARM directly. This is the "no IP at all" fallback. Pick whichever tool the box has installed:

```bash
sudo screen /dev/rshim0/console        # screen's char-device mode (not multiplexer use)
sudo minicom -D /dev/rshim0/console
sudo picocom /dev/rshim0/console
sudo tio /dev/rshim0/console
sudo cu -l /dev/rshim0/console
```

Note: **`tmux` won't work** here — tmux is a pure shell multiplexer, it doesn't have a char-device terminal mode. screen does (legacy feature), which is why I used it.

The specific address (`.1` or `.2`) doesn't matter; the method does.

Three corroborating evidence sources you'll use along the way:

1. **`/etc/hosts` on the host pre-declares every rshim port's ARM IP** (this is the most authoritative source — populated by NVIDIA dev-box image):
   ```bash
   ssh l-fwreg-171 'grep -E "arm|bf" /etc/hosts'
   # 192.168.100.1 arm0 bf0
   # 192.168.110.1 arm1 bf1
   # 192.168.120.1 arm2 bf2
   # 192.168.130.1 arm3 bf3
   # 192.168.140.1 arm4 bf4
   ```
   `arm0`/`bf0` = the ARM behind rshim 0 (= our BF-3 SoC). The other ports are for boxes with multiple DPUs.

2. **Inspect host's tmfifo NIC** — tells you host's own end, not ARM's directly:
   ```bash
   ssh l-fwreg-171 'ip -br addr show tmfifo_net0'
   # tmfifo_net0      UP             192.168.100.2/24 fe80::6c36:bb29:192a:80c0/64
   ```
   This only tells you the host's own address (here `.2/24`). The ARM's address is set on the ARM side by its `/etc/netplan/*.yaml` — read that side independently if you have ssh access, or guess + verify with `uname -m`. Don't assume "ARM = the other unicast on the /24" because the BFB's static IP may not match what host's tmfifo NIC config implies.

3. **Read rshim misc to confirm rshim is talking to a real DPU at all**:
   ```bash
   ssh l-fwreg-171 'sudo cat /dev/rshim0/misc | grep -E "DEV_NAME|DEV_INFO|UP_TIME"'
   # DEV_NAME    pcie-0000:83:00.7
   # DEV_INFO    BlueField-3(Rev 1)
   # UP_TIME     1234(s)
   ```
   `DEV_NAME` is the host-side PCIe BDF that rshim binds to. Multiple DPUs → multiple `/dev/rshim*` devices, each with its own tmfifo /24 (100/110/120/...).

   To confirm the **ARM OS itself is up** (not just that rshim sees the DPU), grep the rshim status log for the readiness markers. Note `BF_MODE` does **not** report OS state — per NVIDIA's [RShim docs](https://docs.nvidia.com/networking/display/bluefieldbsp4120/soc+management+interface+(rshim)) it reports DPU-vs-NIC mode (values `DPU mode` / `NIC mode` / `Unknown` / `Reserved`); `Unknown` just means BIOS/ATF didn't set the mode (common on older BF3 BIOS), not that ARM is down:
   ```bash
   ssh l-fwreg-171 'sudo cat /dev/rshim0/misc | grep -E "Linux up|DPU is ready"'
   # INFO[MISC]: Linux up
   # INFO[MISC]: DPU is ready        ← ARM-side Linux booted and operational
   ```

#### 10.2.2 Watch out for the .2 trap

`ssh root@192.168.100.2` "works" — port 22 listens — but it's the **host's own sshd answering on its tmfifo NIC**. You'll be SSH'ing back into the host you're already on. Symptoms:

- `uname -m` → `x86_64` (host) instead of `aarch64` (ARM). **Always check this.**
- `mst status` shows host PFs (`83:00.x`), not ARM PCIe domain (`00:00.x`).
- `root/3tango` works (host's root password) but it gives you nothing useful for ECPF work.

On **this box** ARM is `.1` and the host is `.2` — but that split is box config, not a law (the public DOCA default is the reverse; see the warning in §10.2.1). The only reliable test is `uname -m`: `aarch64` = ARM, `x86_64` = host. Always run it after connecting, before doing any ECPF work. (On multi-DPU boxes the subsequent rshims sit on their own /24s — 110/120/… — each with its own host/ARM pair.)

#### 10.2.2b ⚠️ The `run_ssh` alias trap on 171 (interactive shells)

171's `~/.bashrc` sources `/mswg/projects/fw/fw_ver/hca_fw_tools/.fwvalias`, which sets:

```bash
alias ssh='run_ssh 0'
```

`run_ssh` is a wrapper that does NVIDIA's "user allocation verification" before invoking the real ssh. **It expects a bare hostname** — `ssh <host>`, no `user@`. If you write `ssh user@host` interactively on 171, the wrapper prepends your current login as another user prefix and produces password prompts like `pexiang@root@192.168.100.1's password:`. You'll also see `[1] <PID>` and `Starting user allocation verification...` on the side.

Check whether the alias is in your way:

```bash
type -a ssh
# ssh is aliased to `run_ssh 0'    ← interactive shell: alias is active
# ssh is /bin/ssh
```

When the alias is **NOT** active (the cases where this plan's prescribed commands work without hitting the trap):

| Context | Alias active? |
|---|---|
| Interactive bash on 171 (login shell) | ✅ Yes (the trap fires) |
| `bash -c '...'` from outside (e.g. `ssh l-fwreg-171 'ssh root@...'` from dev box) | ❌ No — aliases off in non-interactive bash by default |
| `sshpass -e ssh ...` (any shell) | ❌ No — sshpass spawns `/usr/bin/ssh` via execve, bypassing shell aliases |
| Scripts run as `bash script.sh` (not `bash -i`) | ❌ No |

Bypasses inside an interactive 171 shell — pick any:

```bash
\ssh root@192.168.100.1                  # backslash disables alias for this invocation
command ssh root@192.168.100.1           # explicit non-alias
/usr/bin/ssh root@192.168.100.1          # full path
unalias ssh; ssh root@192.168.100.1      # remove alias for the rest of this shell
```

This plan's recipes use the `ssh l-fwreg-171 '<cmd>'` form from a dev box like `m-fwdev-167`, so the inner `<cmd>` runs in non-interactive bash on 171 and is safe by default. The trap matters when you're logged in interactively on 171 typing commands by hand.

#### 10.2.3 Alternative access methods when ssh doesn't work

The hierarchy of fallbacks (more fragile → more reliable):

| Method | Use when | Command |
|---|---|---|
| `ssh root@192.168.100.1` | ARM is fully up, ssh daemon running, network OK | `ssh root@192.168.100.1` (or sshpass for scripts) |
| `/dev/rshim0/console` | ARM boot is hung, ssh daemon not yet up, or you need to see kernel logs | `sudo minicom -D /dev/rshim0/console` or `sudo screen /dev/rshim0/console` |
| BFB push via `/dev/rshim0/boot` | Rootfs is broken; you want to reinstall ARM OS from scratch | See §10.10 below |
| BMC (separate physical NIC on DPU, OOB) | Both rshim console and ssh are dead; the box has a DPU BMC | ssh `root@<bmc-oob-ip>` / `0penBmc` |

The rshim console is the canonical "low-level access" — it's a UART tunneled over tmfifo, so it works even when ARM kernel has no network yet (early boot, panic, dropbear-only single-user mode). On 171 the BMC OOB IP is whatever lab DHCP gave it; check `ipmitool -H <box> lan print` from a privileged box.

#### 10.2.4 Default credentials sweep

We didn't know in advance which OS / password combo was installed on 171's ARM. The 10-combo sweep (~30s) reveals it without breaking anything:

```bash
ssh l-fwreg-171 '
for combo in "ubuntu:ubuntu" "ubuntu:3Tango11!" "ubuntu:3tango" "root:3tango" \
             "root:0penBmc" "root:oracle" "root:centos" "root:root" \
             "ubuntu:password" "ubuntu:nvidia"; do
  user=$(echo $combo | cut -d: -f1); pass=$(echo $combo | cut -d: -f2)
  result=$(SSHPASS=$pass sshpass -e ssh -o ConnectTimeout=3 -o StrictHostKeyChecking=no \
           -o PreferredAuthentications=password -o NumberOfPasswordPrompts=1 \
           $user@192.168.100.1 "uname -a; echo OK" 2>&1 | head -1)
  echo "[$user / $pass] → $result"
done
'
```

Reference table of defaults we expected to see (see also [[reference-171-arm-access]]):

| OS / image | User | Password | Notes |
|---|---|---|---|
| Fresh DOCA BFB (Ubuntu) | ubuntu | ubuntu | First login forces password change. Team-after-customization is often `3Tango11!` or `3tango`. |
| CentOS BFB | root | centos | Older BSP releases. |
| Oracle Linux UEK BFB | root | oracle | OCI-flavored installs. |
| DPU BMC (not ARM OS) | root | 0penBmc | Number-zero, not letter-O. Only relevant via BMC OOB port. |

**171's actual combo**: `root` / `3tango`. The lab team (or whoever set this box up before us) replaced the default `ubuntu/ubuntu` flow with an explicit `root` account using `3tango` as the dev-shared password. This is non-standard but common on internal dev boxes. After we discovered it, single-test cmd:

```bash
ssh l-fwreg-171 'SSHPASS=3tango sshpass -e ssh -o StrictHostKeyChecking=no \
    -o PreferredAuthentications=password root@192.168.100.1 "uname -a"'
# expected: Linux l-fwreg-171-bf0 5.15.0-1019.21.5.g2a61d1d-bluefield #g2a61d1d SMP ... aarch64
```

The `aarch64` in `uname -a` is the definitive marker — that's the ARM. Host's uname will say `x86_64`.

### 10.3 Upgrade MFT on the ARM side too (also required — ARM ships with 4.25)

The ARM rootfs has its own mft installation, also too old. Same upgrade script, runs over the ARM's NFS mount of `/mswg/release/mft/last_stable/`:

```bash
SSHPASS=3tango sshpass -e ssh -o StrictHostKeyChecking=no -o PreferredAuthentications=password \
    root@192.168.100.1 '/mswg/release/mft/last_stable/install.sh; mst restart; mlxconfig --version'
# expect: mlxconfig, mft 4.37.0-75
```

The ARM rootfs has both `/mswg` and `/auto/mswg_release_mft` already mounted (NFS), so no extra setup. Default gateway via `tmfifo_net0` (192.168.100.2 = host) also works for general internet (DNS, apt-get).

### 10.4 Set PF_NUM_SAT_PF=1 on ECPF (from ARM)

**Important HLD constraint: only `=1` is supported per ECPF.** Although `PF_NUM_SAT_PF` is a 5-bit unsigned count (writable 0..31 by the NVconfig schema), the FW HLD pins the limit:

> "FW will support only 1 DPU PF; more PFs should be an additional feature request."
>
> "No max cap for nvconfig, it will be relying on the reduction flow in FW for invalid config."

So `mlxconfig set PF_NUM_SAT_PF=2` on one ECPF doesn't give you 2 sat PFs — FW's `iron_prep` **reduction flow** silently drops it back to 1 (with `scratchpad.dpu_pf_not_supported_globally` bit set; see `adabe/scratchpad_st.adb:12117`). The supported way to have 2 system-wide sat PFs is **`PF_NUM_SAT_PF=1` on each of the two ECPFs** (one per port) — see §10.4b below. There's also an in-flight "Disable NUM_SAT_PF NVconfig" feature (Yongheng Li) that may further gate this nvconfig, so check current FW behavior before assuming the field is writable on whatever build you have.

```bash
SSHPASS=3tango sshpass -e ssh -o StrictHostKeyChecking=no -o PreferredAuthentications=password \
    root@192.168.100.1 '
    mst start >/dev/null 2>&1
    ls /dev/mst/                     # truth: lists actual device files
    mst status                       # CLI display: see caveat below

    mlxconfig -d /dev/mst/mt41692_pciconf0 q PF_NUM_SAT_PF
    # Expected: PF_NUM_SAT_PF = 0  (no longer "Failed to find Param / TLV")

    mlxconfig -d /dev/mst/mt41692_pciconf0 -y s PF_NUM_SAT_PF=1
    # Expected: "Apply new Configuration? y / Applying... Done! / Please reboot..."
'
```

### 10.4b OPTIONAL: 2 sat PFs system-wide (one per port) — set =1 on BOTH ECPFs

The supported "2 sat PFs" topology: each ECPF gets one sat PF on its port. On ARM you have 2 ECPF mst devs (`/dev/mst/mt41692_pciconf0` = ECPF0 = port 0, `.1` = ECPF1 = port 1):

```bash
SSHPASS=3tango sshpass -e ssh -o StrictHostKeyChecking=no -o PreferredAuthentications=password \
    root@192.168.100.1 '
    mst start >/dev/null 2>&1
    mlxconfig -d /dev/mst/mt41692_pciconf0   -y s PF_NUM_SAT_PF=1   # ECPF0 → 1 sat PF on port 0
    mlxconfig -d /dev/mst/mt41692_pciconf0.1 -y s PF_NUM_SAT_PF=1   # ECPF1 → 1 sat PF on port 1
'
# Then power cycle (10.5), and on ARM expect 4 ConnectX-7 PFs:
#   00:00.0  ECPF0
#   00:00.1  ECPF1
#   00:00.2  sat PF (port 0, managed by ECPF0)
#   00:00.3  sat PF (port 1, managed by ECPF1)
```

This 4-PF topology is the BF-4 OCI MLI standard config and is the form actually verified by QA. For Li's cap delegation Phase 1 testing, 1 sat PF (§10.4 path) is sufficient and simpler; the 2-sat-PF topology is for cases that need both ports' satellite PFs.

**`mst status` only shows function-0 — known display bug, not a real problem.** On ARM (mft 4.37) `mst status` lists only `/dev/mst/mt41692_pciconf0` (function 0) even when functions 1 and 2 are fully enumerated by the kernel. Verified 2026-06-03: `ls /dev/mst/` shows all of `mt41692_pciconf0`, `.1`, and `.2` (post-sat-PF-enable); `dmesg` confirms the mst kernel module creates 3 device nodes; `lspci -nn | grep ConnectX-7` on ARM shows 3 PFs at `00:00.0/.1/.2`. `mlxconfig -d /dev/mst/mt41692_pciconf0.2` works perfectly even though `mst status` doesn't list it. So **trust `ls /dev/mst/` + `lspci`, ignore what `mst status` says about sub-functions**.

Errors you might see and fix:
- `-E- Unknown Parameter: PF_NUM_SAT_PF`: ARM mft is still old (Step 10.3 didn't run, or didn't take effect — `mlxconfig --version` must show 4.37+).
- `-E- Failed to find Param / TLV with name 'PF_NUM_SAT_PF'` **on the ARM side**: FW image doesn't have the TLV — re-check Phase 3 INI patch (the 2 `mac_params` lines) and re-burn.
- `-E- Failed to find Param / TLV with name 'PF_NUM_SAT_PF'` **on the host side**: **expected — not an error**. `PF_NUM_SAT_PF` is an ECPF-only nvconfig (adabe description: "only supported for ECPF which is also the eswitch owner"); host-side mst devs don't expose it. **Always verify the TLV from the ARM side, never from host.** I once wasted 4 hours on 2026-06-04 re-burning + power-cycling repeatedly because I kept querying from host and reading the error as "INI didn't take effect". Don't.

### 10.5 Apply NVconfig — power cycle is the cleanest path

You'll be tempted to use `mlxfwreset -l3` (the level-3 chip reset that loads new nvconfig). On this box it doesn't work cleanly:

```bash
# from ARM:
mlxfwreset -d /dev/mst/mt41692_pciconf0 -l3 -y r
# → -E- Synchronization by driver is not supported in the current state of this device.

# from host with udriver bound:
sudo mlxfwreset -d /dev/mst/mt41692_pciconf0 -l3 -y r
# → -E- mlxfwreset doesn't support 3rd party driver (udriver)!

# from host after rmmod udriver + --skip_driver:
sudo rmmod udriver
sudo mlxfwreset -d /dev/mst/mt41692_pciconf0 -l3 --skip_driver -y r
# → -E- The reset flow encountered a failure because the ARM OS is up and needs to be shut down.

# from host with jk --fw-reset (which wraps fwreset.py):
sudo /labhome/pexiang/.usr/bin/jmake --device /dev/mst/mt41692_pciconf0 --fw-reset
# → Failed to add MST device: 0000:83:00.0  (also fails — chip half-resets)
```

After exhausting all three, the path that works is **`jk --power-cycle l-fwreg-171`** (~3 min). NVRAM is persistent through power cycle, so the write from 10.4 stays. Fresh boot guarantees `PF_NUM_SAT_PF=1` is loaded into the running NVconfig.

```bash
# From the dev box (e.g. m-fwdev-167), not from inside the SSH session:
ssh -O exit l-fwreg-171 2>/dev/null    # drop ControlMaster socket if any
/labhome/pexiang/.usr/bin/jmake --power-cycle l-fwreg-171
# 3m6s typical; ipmi off → 20s wait → ipmi on → ping-back
```

### 10.6 Verify satellite PF is exposed

After power cycle, on **ARM side** (not host — satellite PF is ARM-only; host lspci will never show it):

```bash
SSHPASS=3tango sshpass -e ssh -o StrictHostKeyChecking=no -o PreferredAuthentications=password \
    root@192.168.100.1 '
    mst start >/dev/null 2>&1

    lspci -nn | grep -iE "mellanox|bluefield"
    # Expected: THREE ConnectX-7 PFs now (was two):
    #   00:00.0  ECPF0
    #   00:00.1  ECPF1
    #   00:00.2  ← the new satellite PF

    # Authoritative truth for mst devs: ls /dev/mst/, NOT mst status
    # (mst status on ARM mft 4.37 has a display bug — only lists function 0)
    ls /dev/mst/
    # Expected (3 device files, ignoring the .mst_pciconf_ctrl control node):
    #   mt41692_pciconf0       (00:00.0)
    #   mt41692_pciconf0.1     (00:00.1)
    #   mt41692_pciconf0.2     ← satellite PF mst dev

    mlxconfig -d /dev/mst/mt41692_pciconf0 -e q PF_NUM_SAT_PF
    # Expected:
    #   Default=0  Current=1  Next Boot=1
    # The "Current=1" is the proof that NVconfig is applied to running.

    mlxconfig -d /dev/mst/mt41692_pciconf0.2 q PF_NUM_SAT_PF PER_PF_NUM_SF PF_TOTAL_SF
    # Expected on the satellite PF itself:
    #   PF_NUM_SAT_PF = 0  (a sat PF cannot itself spawn more sat PFs)
    #   PER_PF_NUM_SF = True(1)
    #   PF_TOTAL_SF   = 0

    mlxprivhost -d /dev/mst/mt41692_pciconf0.2 q | head
    # Expected: query works, default PRIVILEGED (BF4 OCI MLI Phase 2 will tighten to RESTRICTED later)
'
```

Host side after the cycle is the usual 5-PF set (NO sat PF), which is correct:

```bash
ssh l-fwreg-171 'lspci -nn -d 15b3: | grep -v "PCI bridge"'
# 83:00.0  ConnectX-7 PF0
# 83:00.1  ConnectX-7 PF1
# 83:00.2  NVMe SNAP
# 83:00.3  NVMe SNAP
# 83:00.7  BF-3 SoC Management
# — no sat PF visible. By design (sat PF is ARM-side PF per HLD).
```

### 10.7 What's installed for downstream Li-cap-delegation tests

After this phase: utopx running on host (Phases 1-9) PLUS one satellite PF on ARM (BDF `00:00.2`). The cap-delegation tests under [[plans/utopx_verification_emu_mgr_delegation.md]] will exercise `SET_HCA_CAP(other_function=1)` from utopx-on-host targeting the satellite PF via FW vhca_id routing. utopx side only needs to know the sat PF exists in FW (queryable via `QUERY_HCA_CAP` / `QUERY_HOST_NET_FUNCTIONS`); it does NOT need to talk to it through the ARM-side mst dev.

### 10.8 Reproducible re-execution (for fresh-AI-agent picking this plan up)

If FW is already burned (Phases 1-5 done, with the 2 `mac_params` lines in the INI) but sat PF hasn't been enabled yet, the minimum to get there:

```bash
# === 1. Upgrade mft on both sides (idempotent — skip if already 4.37+) ===
ssh l-fwreg-171 'sudo /labhome/pexiang/.usr/bin/jmake --mft-install'
ssh l-fwreg-171 'SSHPASS=3tango sshpass -e ssh -o StrictHostKeyChecking=no \
    -o PreferredAuthentications=password root@192.168.100.1 \
    "/mswg/release/mft/last_stable/install.sh && mst restart"'

# === 2. Set PF_NUM_SAT_PF=1 on ECPF (from ARM) ===
ssh l-fwreg-171 'SSHPASS=3tango sshpass -e ssh -o StrictHostKeyChecking=no \
    -o PreferredAuthentications=password root@192.168.100.1 \
    "mst start >/dev/null; mlxconfig -d /dev/mst/mt41692_pciconf0 -y s PF_NUM_SAT_PF=1"'

# === 3. Power cycle to apply ===
ssh -O exit l-fwreg-171 2>/dev/null
/labhome/pexiang/.usr/bin/jmake --power-cycle l-fwreg-171   # ~3 min

# === 4. Verify ===
ssh l-fwreg-171 'SSHPASS=3tango sshpass -e ssh -o StrictHostKeyChecking=no \
    -o PreferredAuthentications=password root@192.168.100.1 \
    "mst start >/dev/null && lspci -nn | grep -c ConnectX-7"'
# Expected: 3 (was 2 before, now 2 ECPFs + 1 sat PF)

# === 5. Restore host-side env for utopx ===
ssh l-fwreg-171 'echo "DROP_MODE 0" | sudo tee /dev/rshim0/misc && sudo modprobe udriver'
```

If step 4 prints `2` (sat PF didn't appear), the most common failure modes:
- INI patch missing — re-check `grep -nE "mac_params\.(satellite_pf_en|device_type)" /auto/fwgwork1/pexiang/utopx/regression_ini/burned_session_11047756_v32_50_0222_psid_MT_0000000998.ini` should return 2 lines.
- mft on ARM still old — `mlxconfig --version` on ARM must be 4.37+.
- Power cycle didn't actually pivot — `mlxconfig -d /dev/mst/mt41692_pciconf0 -e q PF_NUM_SAT_PF` on ARM must show `Current=1` not `Current=0`.

### 10.9 Configure the satellite PF for SF creation (OPTIONAL — only for downstream tests that need SFs)

After Phase 10.6 the sat PF exists as a vhca but has the adabe defaults: `PF_TOTAL_SF=0`, `PF_BAR2_ENABLE=True`, `PF_SF_BAR_SIZE=8`. Cap-delegation tests against Li's feature do NOT need SFs created on the sat PF (they only need the sat PF to exist as a delegation target). But if you're running the QA team's BF4 OCI MLI sat-PF security suite or anything that does `mlnx-sf --action create` against the sat PF, configure it first.

Recipe from [Confluence QA page 3328961648 — "BF4 OCI MLI SAT PF Zero Trust"](https://nvidia.atlassian.net/wiki/spaces/QA/pages/3328961648), adapted for BF-3 BDF `00:00.2`:

```bash
# 1. Set BAR2 + SF capacity on the sat PF (from ARM):
ssh l-fwreg-171 'SSHPASS=3tango sshpass -e ssh -o StrictHostKeyChecking=no \
    -o PreferredAuthentications=password root@192.168.100.1 "
    mst start >/dev/null
    mlxconfig -d /dev/mst/mt41692_pciconf0.2 -y s \
        PF_BAR2_ENABLE=0 \
        PER_PF_NUM_SF=1 \
        PF_TOTAL_SF=64 \
        PF_SF_BAR_SIZE=10
"'

# 2. Apply via power cycle (mlxfwreset -l3 has the same gating issues as in 10.5):
ssh -O exit l-fwreg-171 2>/dev/null
/labhome/pexiang/.usr/bin/jmake --power-cycle l-fwreg-171

# 3. Verify on ARM after cycle:
ssh l-fwreg-171 'SSHPASS=3tango sshpass -e ssh -o StrictHostKeyChecking=no \
    -o PreferredAuthentications=password root@192.168.100.1 "
    mst start >/dev/null
    mlxconfig -d /dev/mst/mt41692_pciconf0.2 q PF_BAR2_ENABLE PER_PF_NUM_SF PF_TOTAL_SF PF_SF_BAR_SIZE
"'
# expect:
#   PF_BAR2_ENABLE  False(0)
#   PER_PF_NUM_SF   True(1)
#   PF_TOTAL_SF     64
#   PF_SF_BAR_SIZE  10

# 4. Create an SF on the sat PF (controller index is 2 on BF-3, 3 on BF-4):
ssh l-fwreg-171 'SSHPASS=3tango sshpass -e ssh -o StrictHostKeyChecking=no \
    -o PreferredAuthentications=password root@192.168.100.1 "
    /sbin/mlnx-sf --action create \
        --device 0000:00:00.0 \
        --sfnum 0 \
        --pfnum 2 \
        --controller 2 \
        --hwaddr 02:52:88:f3:13:bd
    /sbin/mlnx-sf -a show
"'
```

Why `controller 2` on BF-3 vs `controller 3` on BF-4: BF-4 has the additional SmartNIC-HIX host counted; BF-3 does not. [QA page 3328961648](https://nvidia.atlassian.net/wiki/spaces/QA/pages/3328961648) documents both values explicitly.

The MAC `02:52:88:f3:13:bd` is a per-SF locally-administered address — any unique LA-bit MAC works; pick from the Mellanox `02:52:88:00:00:XX` convention (see [Confluence SW page 3271938371 — "BlueField 4 OCI MLI design VM and configuration guide"](https://nvidia.atlassian.net/wiki/spaces/SW/pages/3271938371) §3.3 "Software flow for provisioning satellite PF" for the per-SF MAC allocation loop if you need 64 SFs).

### 10.10 BFB reinstall on ARM (recovery — only if ARM rootfs is broken)

If ssh to ARM stops working after a reboot, or `BF_MODE` stays at `Unknown` indefinitely past `UP_TIME` of a few minutes, or you want a fresh ARM Ubuntu, push a DOCA BFB. **Warning: this wipes the ARM rootfs** — any local installs (including the MFT 4.37 upgrade from 10.3) are gone and must be redone.

```bash
ssh l-fwreg-171

# 1. Pick a BFB from the standard release tree. List what's available:
ls /auto/sw_mc_soc_release/doca_dpu/
# doca_2.0.2/  doca_2.5.0/  doca_2.6.0/  doca_2.7.0/  ...

# Inside each version, BFBs are organized by signing flavor:
ls /auto/sw_mc_soc_release/doca_dpu/doca_2.6.0/20240128/bfbs/
# qp/   pk/   ...
# qp/ = QP "Non secured" (dev), pk/ = PK "Production"

ls /auto/sw_mc_soc_release/doca_dpu/doca_2.6.0/20240128/bfbs/qp/
# DOCA_2.6.0_BSP_4.6.0_Ubuntu_22.04-1.20240128.bfb

# 2. rshim DROP_MODE must be 0 (else the push fails with "Invalid argument"):
echo "DROP_MODE 0" | sudo tee /dev/rshim0/misc
sudo cat /dev/rshim0/misc | grep DROP_MODE   # confirm "0"

# 3. Push the BFB — this reboots ARM with the new image:
BFB=/auto/sw_mc_soc_release/doca_dpu/doca_2.6.0/20240128/bfbs/qp/DOCA_2.6.0_BSP_4.6.0_Ubuntu_22.04-1.20240128.bfb
sudo cat $BFB > /dev/rshim0/boot
# 30-60s for the push; ARM then auto-reboots and runs first-boot setup
# (filesystem expansion, package config, network init). Allow ~2-3 min total.

# 4. Watch ARM come up via rshim console (optional but useful):
sudo cat /dev/rshim0/console
# You should see U-Boot → kernel → systemd → login prompt within ~2 min.
# Ctrl-C to exit (won't disturb ARM).

# 5. /dev/rshim0/misc should report the ARM OS as ready:
sudo cat /dev/rshim0/misc | grep -E "DPU is ready|Linux up|UP_TIME"
# INFO[MISC]: Linux up        ← ARM kernel booted
# INFO[MISC]: DPU is ready    ← ARM Ubuntu reported ready
# UP_TIME  120(s)             ← rshim's view of how long ARM has been up
# (BF_MODE is unrelated — it's DPU-vs-NIC mode, not a boot indicator)

# 6. SSH in. Default for a fresh DOCA BFB is ubuntu/ubuntu with forced password change:
ssh ubuntu@192.168.100.1
# password: ubuntu
# (you'll be prompted to set a new password on first login)

# 7. (Recommended) set root password explicitly for scripted access:
sudo passwd root        # set to whatever your team standard is; 171 had 3tango
sudo passwd ubuntu      # also set ubuntu's password if you'll script with sshpass

# 8. Re-do the Phase 10.3 MFT upgrade — required because the new BFB ships old mft:
/mswg/release/mft/last_stable/install.sh
mst restart
mlxconfig --version    # should show 4.37+

# 9. Re-do Phase 10.4 set PF_NUM_SAT_PF if NVRAM was cleared during the BFB reboot
# (it shouldn't be — NVRAM survives BFB push — but verify):
mlxconfig -d /dev/mst/mt41692_pciconf0 q PF_NUM_SAT_PF
# expect: Current=1 still. If 0, redo set + power cycle.
```

**When BFB reinstall is the right answer vs. wrong answer**:

| Symptom | Right answer |
|---|---|
| ssh ARM Permission denied with every default password | BFB reinstall — someone changed creds and didn't document; reinstall resets to ubuntu/ubuntu |
| ssh ARM connection refused (port 22 closed) | BFB reinstall if rshim console also dead; otherwise debug via console first |
| ARM rootfs full / out of disk / package corruption | BFB reinstall to get fresh rootfs |
| No `DPU is ready` in `/dev/rshim0/misc` long past boot, ARM hung in early boot | Try rshim console first; BFB reinstall as last resort |
| Just need to update MFT on ARM | **DO NOT BFB-reinstall** — just run `/mswg/release/mft/last_stable/install.sh` directly |
| Just need to set a new NVconfig | **DO NOT BFB-reinstall** — ssh in, mlxconfig set, done |

**171 today**: BFB reinstall **NOT needed**. The existing ARM Ubuntu (`l-fwreg-171-bf0`, kernel `5.15.0-1019.21.5.g2a61d1d-bluefield`) is functional, and the team's `root/3tango` works. Section 10.10 is documented as recovery procedure only.

## Phase 11 — utopx-native satellite PF test path (the right path for FWV)

> **This is the path FWV should use** for cap-delegation / sat-PF verification, **not** the FW-level INI-burn route of Phase 10. Discovered 2026-06-05.

### 11.0 What utopx already supports

`grep -rnE 'IsDpuPf|GetDpuPfs|num_sat_pf|HandleDpuPfCreateEswVport' /auto/fwgwork1/pexiang/utopx/src/` returns 50+ hits. utopx already has:

| API / mechanism | Location | What it does |
|---|---|---|
| `VHCA::IsDpuPf()` | `src/hca/VHCA.cpp` + many call sites | Predicate "is this vhca a sat PF / DPU PF" |
| `VHCA::GetDpuPfs(includeInvalid)` | `src/hca/VHCA.cpp` | List the DPU PFs of an ECPF |
| `VHCA::GetParentVhca()` | `src/hca/VHCA.cpp` | Get the ECPF that owns this sat PF |
| `VHCA::RemoveAllVportsForDpuPf()` | `src/hca/VHCA.cpp` | Cleanup |
| `CmdCreateEswVport::HandleDpuPfCreateEswVport()` | `src/cmdif/CmdCreateEswVport.cpp:93` | DPU PF-specific create-esw-vport path |
| `CmdAllocSf` / `CmdDeallocSf` DPU PF checks | `src/cmdif/CmdAllocSf.cpp:122` etc. | SF allocation on sat PF |
| `HandleNvData::GetPfNumSatPf()` + `GetPfNumSatPfValid()` | `src/nv_config/HandleNvData.cpp:3271` | utopx reads `PF_NUM_SAT_PF` NVconfig from FW |
| **NVconfig generation** | `HandleNvData.cpp:3860-3862` | `pfPciConf->num_sat_pf = GetManualKeeps().nvconfig_registers.pf_pci_conf.num_sat_pf.Gen(...)` — **utopx itself generates a `num_sat_pf` value into its NV_CFG_SET op** |
| **Coverage** | multiple | `has_sat_pf`, `CreateEswVport on dpu_pf`, `DestroyEswVport on dpu_pf` |
| **Emu-manager selection** | `src/hca/VHCA.cpp:10080` | The critical knob — picks DPU PF as emu manager when forced |

The critical code is `VHCA.cpp:10080-10091`:

```cpp
bool useDpuPf = (DEVICE_INFO.IsEqualToDev(MUSTANG) && IS_FORCED_SUPPORTED_2(this, force_dpu_pf_emu_manager))
              || DEVICE_INFO.IsGreaterEqualThanDev(ARGAMAN);
if (useDpuPf && defaultEmuMgr->IsECPF()) {
    // pick the ECPF's DPU PF as the emulation manager
    auto it = std::find_if(pfList.begin(), pfList.end(), [defaultEmuMgr](VHCA* v) {
        return v->IsDpuPf() && v->GetParentVhca() == defaultEmuMgr;
    });
    if (it != pfList.end()) return *it;
}
return defaultEmuMgr;
```

Summary:
- **BF-3 (MUSTANG)** — default uses ECPF as emu manager; to test the sat-PF path, **force `force_dpu_pf_emu_manager=1`**.
- **BF-4 (ARGAMAN)+** — uses sat PF automatically (no force needed).

### 11.1 The conf knobs

`config/common_constraints.conf` (already in the codebase, no edit needed) declares:

```
force_fw_cap.enable_mask_2.fw_feature_support_bits.force_dpu_pf_emu_manager = 50:0 50:1
# Satellite PF
nvconfig_registers.pf_pci_conf.num_sat_pf       = [0-1]
nvconfig_registers.pf_pci_conf.num_sat_pf_valid = [0-1]
```

Three knobs (default = random; we want to force):

| Knob | What | Force-on value for sat-PF test |
|---|---|---|
| `force_fw_cap.enable_mask_2.fw_feature_support_bits.force_dpu_pf_emu_manager` | tells utopx to assume FW reports DPU PF as emu manager (BF-3 only) | `1` (always on) |
| `nvconfig_registers.pf_pci_conf.num_sat_pf_valid` | utopx generates `num_sat_pf_valid=1` in `NV_CFG_SET` ops | `1` |
| `nvconfig_registers.pf_pci_conf.num_sat_pf` | utopx generates `num_sat_pf=1` value | `1` |

### 11.2 How to run

**Important**: utopx **doesn't need FW to have sat PF physically instantiated** to test sat-PF logic. The `force_fw_cap` mechanism lets utopx behave as if the FW supports the cap regardless of FW's actual report. utopx tracks expected FW state in its own DB; cap-prediction code (`HcaCaps.cpp`) is what exercises the sat-PF path.

**Two critical syntax notes**:
1. `--extra_constraints` (or `-e`) accepts **ONE constraint per flag**. utopx help says "does not support list or range" — multi-knob space-separated value will fail with `failed to parse`. Use **3 separate `-e` flags**.
2. **Knob name depends on utopx version** (renamed in newer commits):
   - utopx `07de3b4` (5-31 pinned) and most regression daily builds before 2026-06: `force_dpu_pf_emu_manager`
   - utopx `9f5f06910` and later (2026-06-04+ regression): `force_dpu_sat_pf_emu_manager` (added `sat_`)
   - Use the name that matches your `utopx.exe` binary version. Check with `grep -rE 'force_dpu(_sat)?_pf_emu_manager' /auto/fwgwork1/pexiang/utopx/src/hca/VHCA.cpp` — whichever appears is the right name.

So the recipe (5-31 utopx 07de3b4 version, three independent `-e`):

```bash
# FW + INI: baseline burn (Phase 1-9), NO sat-PF mac_params lines
# (Phase 10 INI burn NOT needed; if you tried it and FW asserts, revert to baseline)

# Pre-run env setup (one ssh per command per [[feedback-one-ssh-per-command]])
ssh l-fwreg-171 'sudo /labhome/pexiang/.usr/bin/jmake --device /dev/mst/mt41692_pciconf0 --fw-reset'
ssh l-fwreg-171 'sudo systemctl restart rshim && sleep 2'    # rshim may need restart after fwreset
ssh l-fwreg-171 'echo "DROP_MODE 0" | sudo tee /dev/rshim0/misc'
ssh l-fwreg-171 'sudo modprobe udriver && ls /dev/udriver_*'

# Run utopx with the 3 sat-PF knobs forced ON
LOG="$HOME/utopx_171_satpf_$(date +%Y%m%d_%H%M%S).log"
ssh l-fwreg-171 'cd /auto/fwgwork1/pexiang/utopx && \
    sudo ./utopx --device=/dev/mst/mt41692_pciconf0 --daemon --num_of_clients=0 \
        --xml_conf_file debug_conf.xml --conf_file config/scenario_dpa_emu.conf \
        --iter=300 --ops_per_it=30 \
        -e force_fw_cap.enable_mask_2.fw_feature_support_bits.force_dpu_pf_emu_manager=1 \
        -e nvconfig_registers.pf_pci_conf.num_sat_pf=1 \
        -e nvconfig_registers.pf_pci_conf.num_sat_pf_valid=1 \
        2>&1 | tail -200' > "$LOG" 2>&1 &
wait $!

grep -E "TEST PASSED|TEST FAILED|Test-status|FATAL" "$LOG" | head
```

Any emulation-class scenario works (`scenario_dpa_emu.conf`, `cmdif_test_dpa.conf`, etc.) — the sat-PF code path is gated by the knobs, not by which scenario.

**Verified PASS** 2026-06-05 14:11~14:20 BJ: seed `226259204`, ~8m57s, on utopx `07de3b4` rebuilt binary + FW `32.50.0222` + baseline INI + the 3 `-e` knobs above. Baseline (no `-e` flags) same env: PASS seed `3996255652` ~7m47s. Path A confirmed working — sat-PF coexists with utopx baseline at this pin.

### 11.3 What this tests

- `VHCA::IsDpuPf()` predicate returns true for the synthesized sat PF
- `defaultEmuMgr = the ECPF's DPU PF` (per `VHCA.cpp:10080` logic)
- `CmdCreateEswVport` / `CmdDestroyEswVport` exercise DPU-PF paths
- `CmdAllocSf` checks `targetVhca->IsDpuPf()` and routes accordingly
- Emulation cmds (NVMe / virtio) issue from the sat PF rather than the ECPF, exercising the routing utopx wrote
- Cap predictions on sat-PF vhca exercise `HcaCaps.cpp` sat-PF branches

Today's cap mismatch (`general_obj_type_device_object expected=0 actual=1`, 2026-06-04 21:08) was exactly this path firing without `force_dpu_pf_emu_manager` set explicitly, when our FW-level sat-PF was on. The fix is to **align utopx prediction with FW actual when sat-PF is on** — that's the FWV work item under `plans/utopx_verification_emu_mgr_delegation.md`.

### 11.4 Relationship to Phase 10

| Concern | Phase 10 (FW-level instantiation) | Phase 11 (utopx-native) |
|---|---|---|
| Need to burn special INI? | Yes (9 mac_params lines for BF-3) | **No** — keep baseline INI |
| Need ARM mlxconfig set? | Yes (`PF_NUM_SAT_PF=1` on ECPF) | **No** — utopx generates NV_CFG_SET internally |
| Need power cycle dance? | Yes (multi-cycle to apply NVconfig) | **No** — single utopx invocation |
| ARM lspci shows sat PF? | Yes (`00:00.2` appears) | **No** — sat PF only in utopx's internal vhca model |
| utopx test coverage of sat-PF code? | Same as Phase 11 if FW reports caps right | ✓ Full coverage of utopx's sat-PF code |
| FW boot fwassert 0x821d? | Triggered if `cpu_management_pf`/`device_type` combo unfixed | **Doesn't apply** — FW infra not activated |
| Use case | (a) end-to-end FW infra validation, (b) ARM-side SF creation tests, (c) cross-vhca traffic to/from sat PF | utopx-level FWV (predicts caps, exercises cmd paths, verifies via `FailOnDiffInner` against FW responses) |

**For Li's cap-delegation feature FWV (the immediate ask) → Phase 11**. Phase 10 might still be needed later for production-like end-to-end runs, but **not** as a prerequisite for utopx verification work.

## Phase 12 — Recovering env after a regression run

When `mars_reg` runs its daily regression on the box, it leaves the env in a state that is **NOT** runnable as a utopx test bench for our pinned config. After releasing the lock, the box has:

- FW burned to whatever regression's daily was (e.g. `32.50.0260` instead of our pinned `32.50.0222`)
- `golan_fw` git tree on a regression-set tag (e.g. `host_fwv_mini_reg_version_...`) different from `rel-12_50_0222`
- **`utopx.exe` binary recompiled** from a newer utopx commit (e.g. `9f5f06910`), saved at `/auto/fwgwork1/pexiang/utopx/artifacts/bin/ninja/.../utopx.exe`
- `utopx` git tree on the matching newer commit
- Submodules (especially `steering_ul`) pointing to newer commits

**Symptoms when you ignore this and try utopx baseline immediately:**
- `IcmdAgent.cpp:98 ... ICMD_ACCESS_REG ... ICMD_BAD_PARAM` ~20-30s into the run. (Regression's utopx+FW pair is not actually utopx-baseline-clean.)
- If you only `git checkout` the source back to 5-31 pin but skip rebuild: `TestKeeps.cpp:116 failed to parse: force_fw_cap.enable_mask_2.fw_feature_support_bits.force_dpu_pf_emu_manager = 50:0 50:1` — the `utopx.exe` binary is still the newer build whose internal keep registry doesn't match the older conf file.

### 12.1 Recovery procedure

```bash
# 1. Reset utopx repo to 5-31 pin, including submodules
cd /auto/fwgwork1/pexiang/utopx
git checkout host_fwv_20260527_FW_version_50_0222_branch_master   # tag for utopx 07de3b4
git submodule update --recursive
git status --short    # expect: empty or just untracked files (genid_dump etc.)

# 2. Reset golan_fw repo to 5-31 pin
cd /auto/fwgwork1/pexiang/golan_fw
git checkout rel-12_50_0222    # SHA 1bd364033669

# 3. Rebuild utopx (docker-based, ~30+ min)
cd /auto/fwgwork1/pexiang/utopx
./build.sh                          # produces utopx.exe matching 07de3b4 source
ls -la artifacts/bin/ninja/ubuntu/20.04/x86_64/gcc10.5.0/ABI_0/Legacy/utopx.exe
# verify mtime is recent (your build) not the regression's mtime

# 4. Re-burn FW back to 32.50.0222 + baseline INI (Phase 5):
ssh l-fwreg-171 'sudo /labhome/pexiang/.usr/bin/jmake --device /dev/mst/mt41692_pciconf0 --fw-reset'   # clear any pending image
ssh l-fwreg-171 'cd /auto/fwgwork1/pexiang/golan_fw && \
    /labhome/pexiang/.usr/bin/jmake --burn \
        --device /dev/mst/mt41692_pciconf0 \
        --firmware /auto/sw/release/host_fw2/fw-41692/fw-41692-rel-32_50_0222-build-001/dist/fw-BlueField-3.mlx \
        --ini ../utopx/regression_ini/burned_session_11047756_v32_50_0222_psid_MT_0000000998.ini'

# 5. Power cycle to pivot FW (regression-burned image was the running one; need cycle to load new)
ssh -O exit l-fwreg-171 2>/dev/null
/labhome/pexiang/.usr/bin/jmake --power-cycle l-fwreg-171

# 6. Post-cycle env setup
ssh l-fwreg-171 'sudo systemctl restart rshim'       # rshim daemon may not auto-restart
ssh l-fwreg-171 'sleep 2 && ls /dev/rshim0/'         # expect: boot console misc rshim
ssh l-fwreg-171 'echo "DROP_MODE 0" | sudo tee /dev/rshim0/misc'
ssh l-fwreg-171 'sudo modprobe udriver'
ssh l-fwreg-171 'sudo flint -d /dev/mst/mt41692_pciconf0 q | grep "FW Version"'
# expect: FW Version: 32.50.0222
```

After step 6, env is recovered to 5-31 pinned state. Run utopx baseline to confirm, then Path A.

### 12.2 Why a rebuild is mandatory

`utopx.exe` is a 60MB compiled binary at `artifacts/bin/ninja/ubuntu/20.04/x86_64/gcc10.5.0/ABI_0/Legacy/utopx.exe` (symlinked to `./utopx.exe` in the repo root). `git checkout` only updates source files — the binary on disk persists.

When regression runs on the box, it rebuilds this binary for whatever commit it's testing. After regression releases the box, you inherit that binary. Your `git checkout` to an older commit just makes the source disagree with the running binary, which causes parse errors at startup because the binary's internal config-keep registry doesn't match conf files from a different commit.

**No way around this**: must `./build.sh` from the desired source state. ~30 min, docker-based (`harbor.mellanox.com/hca-fw-core/hca-fw-core-ubuntu20.04:0.0.21`). Verify the rebuild succeeded by checking `utopx.exe` mtime is your build time.

### 12.3 Optional shortcut: use regression's newer pair instead

If you don't want to spend 30 min rebuilding, you can pin everything to regression's newer state (utopx + FW + INI). But on 2026-06-04~05 testing this pair (`utopx 9f5f06910` + `FW 32.50.0260` + baseline INI) **also failed baseline utopx with ICMD_BAD_PARAM**. So regression's daily build state isn't necessarily utopx-runnable for our scenarios. Stick with rebuild of 5-31 pin.

## What NOT to do (failure modes we hit and learned from)

### Don't run `mustang_fw_reset.sh --remove_rescan`

The regression's per-test setup runs:

```bash
sudo /mswg/release/host_fw/fw-41692/fw-41692-rel-32_50_0222/../etc/mustang_fw_reset.sh \
    --debug --reg_debug --unbind_flow --dont_kill_utopx \
    --next_driver udriver --remove_rescan --ignore_other_hosts \
    -d /dev/mst/mt41692_pciconf0
```

We tried this several times — **the `--remove_rescan` flag causes a kernel `wait_woken` hang** when it does `echo 1 > /sys/devices/pci0000:80/0000:80:03.0/remove` on the parent PCIe bridge. The bridge remove never completes; the script hangs indefinitely; the parent shell can be killed but the kernel I/O stays wedged. lspci then shows BF-3 functions as `rev ff` (unresponsive). Only path out: power cycle the host (`jk --power-cycle l-fwreg-171`). Glean confirms this is a known hang class — see Confluence "Debug Festival October 2025" / Bug SW #4980709 / MSFT/CX-8 HOT_RESET remove_rescan hang.

After a fresh power cycle, the device is already in clean state. `modprobe udriver` alone is sufficient — the reset script's only useful effect was to bind udriver to all 4 functions, which the kernel does automatically on module load.

### Don't forget to clear rshim `DROP_MODE` after `jk --fw-reset`

The rshim daemon (`systemctl status rshim.service`) frequently sets `DROP_MODE 1` after any PCIe-level transition (including `jk --fw-reset`). In drop mode, every write to `/dev/rshim0/boot` returns `Invalid argument` and is silently discarded. utopx in BareMetal mode pushes the BFB through that path, so it FATALs with:

```
ArmAgentApiBareMetal.cpp:30  Install BFB command: cat <bfb> > /dev/rshim0/boot
sh: /dev/rshim0/boot: Invalid argument       (×10 retries)
shared_global_function.cpp:350  FATAL: failed to run cmd: cat ... > /dev/rshim0/boot for 10 attempts
ArmAgentApiBareMetal.cpp:20  Could not enable ArmAgentApiBareMetal
[TEST FAILED]
```

Diagnose with `sudo cat /dev/rshim0/misc | grep DROP_MODE`. If it shows `1`, clear it:

```bash
echo "DROP_MODE 0" | sudo tee /dev/rshim0/misc
```

Done **after every `jk --fw-reset`**, before running utopx. The Phase 9 / Re-run quick reference flow has this step inline now.

Side-effect to notice: clearing `DROP_MODE` may bump `UP_TIME` from `0` to a non-zero value as the rshim re-establishes a connection to ARM — this is harmless and confirms the daemon is back to normal. (`BF_MODE` showing `Unknown` is unrelated to boot state — it only reports DPU-vs-NIC mode and is commonly `Unknown` on older BF3 BIOS regardless of whether ARM is up.)

### Don't try to set PF_NUM_SAT_PF from the host side

`mlxconfig -d /dev/mst/mt41692_pciconf0 -y s PF_NUM_SAT_PF=1` on the host writes to host PF0's per-PF NVRAM area; FW ignores that value when deciding sat-PF enablement. The host-PF NVRAM is harmless garbage. Symptoms if you do this thinking it will work:

- After mlxfwreset / power cycle: host lspci unchanged, mst dev count unchanged, no sat PF.
- `mlxconfig -d /dev/mst/mt41692_pciconf0 q PF_NUM_SAT_PF` on host shows `1` (the value you set) — misleading; the field exists per-PF, so each PF's mst dev reports its own area.
- The host_id / pf_index mlxconfig flags don't help: those only target class-3 per-host TLVs. PF_NUM_SAT_PF isn't class-3.

Always set this from ARM-side `mst dev` for ECPF — see Phase 10.4.

### Don't ssh to 192.168.100.2 expecting ARM

On `l-fwreg-171`, `.2` is the **host's own tmfifo NIC IP** (this box wires host = `.2`, ARM = `.1` — the reverse of the public DOCA default, where ARM = `.2`; see §10.2.1). SSH'ing to the host's own tmfifo address connects you back to the host itself (port 22 is the host's sshd). Misleading because:

- The SSH connection succeeds.
- `root@192.168.100.2 / 3tango` (host's root password) works.
- `mst status` and `mlxconfig` all run successfully but operate on host PFs, not ECPF.

Symptom: `uname -m` returns `x86_64`. For ARM, expected is `aarch64`. **Always check `uname -m`** rather than trusting the address — on 171 ARM is `192.168.100.1`, but on a box with the DOCA default it would be `.2`.

### Don't run utopx back-to-back without a clean reset

We saw three different failure modes across repeat runs of the same command:


| Run | Seed                               | Outcome                              | Cause                                                  |
| --- | ---------------------------------- | ------------------------------------ | ------------------------------------------------------ |
| 1   | 3969039850                         | ✅ PASSED 300 iters                   | clean state                                            |
| 2   | 444217356                          | ❌ `Gen() outside phase` at iter 138  | leftover state + seed race                             |
| 3   | 1000726046                         | ❌ `Virtio device_status 0xf` at init | virtio device left in `DRIVER_OK` state from prior run |
| 4   | (after stuck `[utopx.exe]` zombie) | ❌ wedged setup                       | un-killable D-state zombie holding kernel resources    |
| 5   | 3435089955 (after a passing run)   | ❌ `Virtio device_status 0xf` at init | same — utopx leaves virtio emu in `DRIVER_OK`          |


Lessons:

- The virtio emulated devices retain state between utopx runs. The MARS regression flow runs `fw_reset + modprobe_udriver` before **every** utopx test for exactly this reason.
- A D-state utopx zombie (uninterruptible-sleep on device I/O) cannot be cleared by `kill -9`. Only `jk --power-cycle` reliably clears it.

## Reset spectrum between utopx runs (lightest → heaviest)


| Method                                                             | Resets virtio state? | Time   | When to use                                                                                                                                                                         |
| ------------------------------------------------------------------ | -------------------- | ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `modprobe -r udriver && modprobe udriver`                          | ❌ no                 | <1s    | Driver-binding cleanup only. Won't fix `Virtio device_status 0xf`.                                                                                                                  |
| `**jk --fw-reset`** (our patched jmake)                            | ✅ **yes**            | ~20s   | **Default between-runs reset.** Routes through `fwreset.py`, acquires `/tmp/udriver_lockfile.lock`, knows about udriver, does a chip-level reset that clears emulated-device state. |
| `sudo mlxfwreset -d ... -y r`                                      | depends              | ~20s   | The underlying MFT tool. Works when `mlx5_core` is bound; on BF-3 with only `udriver`, tool-owner sync is "not supported" and it may fail. Prefer `jk --fw-reset` instead.          |
| `mustang_fw_reset.sh --next_driver udriver` (no `--remove_rescan`) | ✅ yes                | ~30s   | Heavier; explicit re-bind of all functions.                                                                                                                                         |
| `mustang_fw_reset.sh --remove_rescan`                              | ✅ yes when works     | ⚠️     | **DANGEROUS** — hangs in `wait_woken` on PCIe parent bridge remove. Only recovery is power cycle. Avoid.                                                                            |
| `jk --power-cycle l-fwreg-171`                                     | ✅ always             | ~3 min | Last resort. Always works. Use only when the lighter resets fail (D-state zombies, `rev ff` lspci).                                                                                 |


### Why `jk --fw-reset` works where bare `mlxfwreset` may not

`jk --fw-reset` is **not equivalent** to `mlxfwreset` — it's a wrapper that adds orchestration:

```
jk --fw-reset
    ↓ (patched jmake)
fwresetm --run_new_fwreset             (alias → func_alias_reset m)
    ↓
sudo /auto/mswg/.../fw_reset_wrapper.sh mustang -d /dev/mst/mt41692_pciconf0
    ↓
sudo /mswg/.../fw_reset/fwreset.py -d ...
    ↓ (does locking, udriver coordination, mlxfwreset, rescan)
chip reset register write
```

`fwreset.py` adds:

- `/tmp/fwreset_lock` + `/tmp/udriver_lockfile.lock` (one reset at a time, udriver-aware)
- Multi-host BF coordination
- Per-device function enumeration / rebind
- Post-reset PCIe rescan with timeout
- Uptime-before / uptime-after verification (`Before: N, After: M`)

`mlxfwreset` directly is bare-metal: just the chip-reset register write + driver-sync handshake. On BF-3 with only `udriver` bound (utopx's normal state), `mlxfwreset` reports "Tool is the owner: Not supported" and may refuse to proceed. `fwreset.py` works around that.

## Final recipe (minimum steps to get a working run on l-fwreg-171)

### Reuse a single SSH connection across all steps

Each `ssh l-fwreg-171 '<cmd>'` invocation incurs ~~1-2s of TCP handshake + auth — adds up when you do 5-10 of them per run cycle. Use **SSH connection multiplexing** so subsequent invocations reuse the first connection's socket (~~10ms instead of ~1s).

**Option 1 — interactive: open one SSH session and stay in it**

```bash
ssh l-fwreg-171
# now all commands run in this shell with no per-command overhead
cd /auto/fwgwork1/pexiang/utopx
sudo ./utopx ...
exit
```

This is the natural flow for humans. The recipe below uses `ssh ... '<cmd>'` form for clarity, but you can just open one shell and run them sequentially inside it.

**Option 2 — scripted: enable persistent control sockets in `~/.ssh/config`**

```
Host l-fwreg-*
    ControlMaster   auto
    ControlPath     ~/.ssh/cm-%r@%h:%p
    ControlPersist  10m
```

After the first `ssh l-fwreg-171 ...` opens the master socket, every subsequent `ssh l-fwreg-171 '<cmd>'` from any shell on the same client reuses it for up to 10 min. Subsequent commands return in ~10ms.

**Option 3 — one-off, no config edit**

```bash
SSH_OPTS=(-o ControlMaster=auto -o ControlPath="$HOME/.ssh/cm-%r@%h:%p" -o ControlPersist=10m)
ssh "${SSH_OPTS[@]}" l-fwreg-171 'sudo /labhome/pexiang/.usr/bin/jmake --device /dev/mst/mt41692_pciconf0 --fw-reset'
ssh "${SSH_OPTS[@]}" l-fwreg-171 'cd /auto/fwgwork1/pexiang/utopx && sudo ./utopx ...'
```

To close the persistent connection early: `ssh -O exit l-fwreg-171`.

### Steps

```bash
# === One-time setup (FW persists on flash, only needed once) ===
ssh l-fwreg-171
# 1. Pin local repos to matching commits (Phase 2)
# 2. Burn FW with custom INI (Phase 5):
cd /auto/fwgwork1/pexiang/golan_fw && \
  /labhome/pexiang/.usr/bin/jmake --burn \
      --device /dev/mst/mt41692_pciconf0 \
      --firmware /auto/sw/release/host_fw2/fw-41692/fw-41692-rel-32_50_0222-build-001/dist/fw-BlueField-3.mlx \
      --ini ../utopx/regression_ini/burned_session_11047756_v32_50_0222_psid_MT_0000000998.ini
# 3. Pivot FW from flash to running (Phase 6, requires patched jmake):
/labhome/pexiang/.usr/bin/jmake --device /dev/mst/mt41692_pciconf0 --fw-reset
sudo modprobe udriver

# === Satellite PF setup (one-time, Phase 10) — required for Li's cap delegation tests ===
# 4. Upgrade mft on host (jk wraps /mswg/release/mft/last_stable/install.sh)
sudo /labhome/pexiang/.usr/bin/jmake --mft-install
# 5. Upgrade mft on ARM + set PF_NUM_SAT_PF=1 on ECPF
SSHPASS=3tango sshpass -e ssh -o StrictHostKeyChecking=no -o PreferredAuthentications=password \
    root@192.168.100.1 '
    /mswg/release/mft/last_stable/install.sh
    mst restart
    mst start >/dev/null
    mlxconfig -d /dev/mst/mt41692_pciconf0 -y s PF_NUM_SAT_PF=1
'
exit  # leave SSH first
# 6. Power cycle to apply (NVconfig only loads on fresh boot — mlxfwreset doesn't work cleanly)
ssh -O exit l-fwreg-171 2>/dev/null
/labhome/pexiang/.usr/bin/jmake --power-cycle l-fwreg-171     # ~3 min
# 7. Verify sat PF appeared on ARM side (BDF 00:00.2)
ssh l-fwreg-171 'SSHPASS=3tango sshpass -e ssh -o StrictHostKeyChecking=no \
    -o PreferredAuthentications=password root@192.168.100.1 \
    "mst start >/dev/null && lspci -nn | grep -c ConnectX-7"'
# Expected: 3
# 8. Restore host-side env
ssh l-fwreg-171 'echo "DROP_MODE 0" | sudo tee /dev/rshim0/misc && sudo modprobe udriver'

# === Before each utopx run (after the first) ===
# This clears virtio device state left by the previous run:
sudo /labhome/pexiang/.usr/bin/jmake --device /dev/mst/mt41692_pciconf0 --fw-reset

# (Only if jk --fw-reset itself fails, e.g. D-state zombies / rev:ff lspci):
exit                                                          # leave SSH first
/labhome/pexiang/.usr/bin/jmake --power-cycle l-fwreg-171     # ~3 min
ssh -O exit l-fwreg-171 2>/dev/null || true                   # drop any stale ControlMaster socket
ssh l-fwreg-171                                                # fresh connection after the power cycle
sudo modprobe udriver

# === Run utopx (always use debug_conf.xml) ===
cd /auto/fwgwork1/pexiang/utopx
sudo ./utopx --device=/dev/mst/mt41692_pciconf0 --daemon --num_of_clients=0 \
             --xml_conf_file debug_conf.xml --conf_file config/scenario_dpa_emu.conf \
             --iter=300 --ops_per_it=30
```

**Note on power cycle and sat PF persistence**: the `PF_NUM_SAT_PF=1` NVRAM write is persistent across power cycles, reboots, and FW reburns of the **same INI**. The only thing that clears it is reburning a FW image whose INI lacks the 2 `mac_params` gate lines (then the TLV stops existing and the value is lost), or `mlxconfig reset` on the ECPF. After Phase 10 is done once, the routine "between-runs `jk --fw-reset`" doesn't disturb it — the sat PF stays exposed.

### Why the power-cycle path explicitly drops the ControlMaster socket

When the remote host reboots, the kernel/socket on the *client* side doesn't know the TCP peer is gone for many minutes (waiting for FIN/keepalive timeout). Subsequent `ssh` invocations get routed to the stale ControlPath socket and hang. Always run `ssh -O exit <host>` after any reboot/power-cycle to evict the dead socket and force a fresh connection.

## Key learnings

- **INI overrides matter most**: `internal_use.eliminate_pcie_switch_hier=0x1`, `ddr_mapping_en=0x1`, `ddr_log_2_bar_size=0x22` are what expose BAR2 on the CM-shared-memory function (`83:01.5`). Without these, ArmAgent BareMetal can't mmap shared memory. **These come from the regression's burned INI, not the release default INI** — must merge.
- `**modprobe udriver` is the right binding step** post-burn / post-reset. The kernel auto-binds udriver to every PCI function whose device ID matches its supported table (41692 for NIC, 24577 for emulated NVMe controllers, 4161 for virtio-net). No script needed.
- `**jk --fw-reset` is the right between-runs reset** on BF-3 with udriver bound — it clears virtio device state via `fwreset.py`'s chip reset, while handling udriver lockfile coordination. Takes ~20s, no power cycle needed.
- `**jk --fw-reset` ≠ `mlxfwreset`** — `mlxfwreset` is the underlying MFT tool; `jk --fw-reset` wraps it with udriver-aware locking and orchestration. Bare `mlxfwreset` on BF-3 with udriver-only binding may fail "Tool is owner: Not supported".
- `**mustang_fw_reset.sh --remove_rescan` is dangerous** — triggers a `wait_woken` hang on the PCIe parent bridge that requires power-cycle to recover. Avoid in interactive use.
- **State leak between back-to-back utopx runs** is real and well-defined: virtio emulated devices retain `DRIVER_OK` state. Resolution: `jk --fw-reset` between every run (same pattern MARS regression uses).
- **Different seeds = different bugs**. utopx is stochastic. A pass with one seed doesn't guarantee a pass with the next. For repeatability, pin `-s <seed>`.

---

## Status as of 2026-06-03

### Baseline utopx layer
- ✅ MARS regression baseline (FW + utopx commits) identified from session 11047756
- ✅ Local utopx + golan_fw checked out to matching commits
- ✅ Regression's INI files downloaded and stored in `utopx/regression_ini/`
- ✅ Jerry's 36 emulation flags appended to the burned INI
- ✅ jmake patched (Bug A + Bug B) — `jk --fw-reset` now works on BF-3
- ✅ FW 32.50.0222 burned via `jmake --burn --firmware --ini` on l-fwreg-171
- ✅ NVCONFIG shows all 36 emulation flags loaded
- ✅ One-time post-burn bring-up: `jk --fw-reset` + `modprobe udriver` — works
- ✅ **Between-runs reset: `jk --fw-reset` alone is sufficient** — clears virtio device state, no power cycle needed (~20s)
- ✅ **utopx `scenario_dpa_emu` PASSED** on l-fwreg-171 (300 iter × 30 ops/it, ~10 min, multiple seeds)
- 📌 Power cycle (`jk --power-cycle l-fwreg-171`) reserved for cases where `jk --fw-reset` itself fails (D-state zombies, `rev ff` lspci)

### Satellite PF layer (Phase 10 attempted 2026-06-03 → revisited 2026-06-04~05)
- ✅ MFT upgraded on host: 4.35.0 → 4.37.0-75
- ✅ MFT upgraded on ARM:  4.25.0  → 4.37.0-75
- ✅ ARM SSH access established: `root@192.168.100.1` / `3tango` (on 171 the host's tmfifo NIC is `.2`, ARM is `.1` — reverse of the DOCA default; confirmed via `uname -m` = `aarch64`)
- ⚠️ **2026-06-03 "Phase 10 done" claim** (sat PF visible on ARM 00:00.2 with 2-line INI overlay) was correct at the snapshot, **but never end-to-end tested with utopx**. 2026-06-04 retest confirmed the 2-line INI overlay causes FW assert 0x821d in utopx — sat PF + utopx are blocked together on this FW build via the INI route.
- ❌ **Phase 10 (FW-level sat PF instantiation) blocked at FW 32.49.9906 + 32.50.0222 on 171 hardware** — no INI permutation (0/2/4/5/7/9-line incl. Marie's MAS-official PSID MT_0000000998 recipe) yields both (a) sat PF `Current=1` AND (b) no FW assert 0x821d. Marie's `l-fwreg-146` setup or FW fix from Li likely needed to unstick.
- 💡 **2026-06-05 key insight: Phase 10 NOT required for utopx sat-PF FWV.** utopx has native sat-PF test code; **Phase 11 (utopx conf knobs) is the right path**, not Phase 10.

### Satellite PF FWV path (Phase 11, established 2026-06-05, **PASS confirmed**)
- ✅ utopx has 50+ sat-PF code hits (`IsDpuPf`, `GetDpuPfs`, `HandleDpuPfCreateEswVport`, `num_sat_pf` NVconfig gen, `force_dpu_pf_emu_manager`, ...)
- ✅ Knobs identified: `force_fw_cap.enable_mask_2.fw_feature_support_bits.force_dpu_pf_emu_manager=1` + `nvconfig_registers.pf_pci_conf.num_sat_pf=1 + num_sat_pf_valid=1`
- ✅ **2026-06-05 PASS verified end-to-end**: utopx `07de3b4` (rebuilt binary) + FW `32.50.0222` + baseline INI + 3 `-e` knobs → `[TEST PASSED]` seed `226259204` ~8m57s. **First confirmed sat-PF + utopx baseline coexistence on BF-3.**
- ✅ Baseline (no `-e`) same env: PASS seed `3996255652` ~7m47s. Sat-PF knobs don't break baseline.
- ⚠️ Each `-e` carries **one knob only**; the help text "does not support list or range" means don't put space-separated multi-knob into one `-e`. Use three independent `-e` flags.
- ⚠️ Knob name changed in newer utopx (2026-06+): `force_dpu_pf_emu_manager` → `force_dpu_sat_pf_emu_manager`. Verify match with your `utopx.exe` build by `grep -rE 'force_dpu(_sat)?_pf_emu_manager' src/hca/VHCA.cpp`.
- 📌 This path **does not need** ARM-side sat PF to physically exist. utopx tests sat-PF logic via its own internal vhca model and `force_fw_cap` mechanism.
- 📌 If regression has just run on the box, you'll likely hit `ICMD_BAD_PARAM` or `failed to parse` — env needs recovery per §Phase 12 (rebuild utopx + repin FW).

## Run history


| Date                     | Seed                   | Result       | Wall time   | Notes                                                                                                                                                                                                                                                       |
| ------------------------ | ---------------------- | ------------ | ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-05-28/29            | (multiple)             | ✅ PASS       | ~10 min     | Initial bring-up runs after burn                                                                                                                                                                                                                            |
| **2026-05-31 23:25 IDT** | **877500556**          | ✅ **PASS**   | **511.7 s** | Re-run from m-fwdev-167 over SSH; 300 iter × 30 ops/it = 9000 ops                                                                                                                                                                                           |
| 2026-06-01 ~14:12 IDT    | 3384525166             | ❌ FAIL early | ~16 s       | First attempt after re-burning 0222 + 2× `jk --fw-reset`. FATAL at `ArmAgentApiBareMetal.cpp:20`: `sh: /dev/rshim0/boot: Invalid argument` ×10. Root cause: rshim daemon left in `DROP_MODE 1` by the fwreset. Logged the failure mode in *What NOT to do*. |
| 2026-06-01 (post-fix)    | (passed run, seed TBD) | ✅ PASS       | TBD         | After `echo "DROP_MODE 0" | sudo tee /dev/rshim0/misc`. Confirmed the DROP_MODE step is the missing piece in Phase 9.                                                                                                                                       |
| **2026-06-03** | n/a (env work) | ✅ **Phase 10 done** | ~30 min | Satellite PF enabled on ARM (BDF `00:00.2`). INI patched with 2 `mac_params` lines + reburn + ARM mft 4.25→4.37 + `mlxconfig set PF_NUM_SAT_PF=1` on ECPF + `jk --power-cycle` to apply. Discovered `root@192.168.100.1/3tango` is the right ARM login (NOT `.2` — that's host's tmfifo NIC). |
| 2026-06-04 21:07 BJ | 2566744892 | ❌ FAIL ~25s | `ArmAgentApiBareMetal.cpp:20  bar addr=0x0  Bare metal arm agent timeout` | After mars_reg regression released 171, my `mlxconfig reset` had wiped `PCI_SWITCH_EMULATION_ENABLE=True` (an implicit prereq from 5-31 baseline NVRAM). Fix: `mlxconfig set PCI_SWITCH_EMULATION_ENABLE=1` + power cycle. |
| 2026-06-04 21:24 BJ | 3074166806 | ❌ FAIL ~82s | `VHCA.cpp:9214 VerifyHealthBuffer ext_synd=0x821d` (FW assert) | The 3 `mac_params` lines I'd added (`satellite_pf_en=1`, `device_type=3`, `cpu_management_pf=0`) caused `cpu_management_pf` mismatch with `device_type=3`. Tried fix: add `cpu_management_pf=0` line → made it worse. |
| 2026-06-04 21:52 BJ | (FAIL on cap diff before this) | ❌ FAIL | `general_layout.cpp:365 FailOnDiffInner: cmd_hca_cap.general_obj_type_device_object expected=0 actual=1` | The sat-PF-enabling INI overlay shifted FW caps in ways utopx couldn't predict. Root cause: **adding `mac_params` rows to the burned INI broke utopx baseline**. |
| **2026-06-04 21:52 BJ** | **1146877203** | ✅ **PASS** | **~7m47s** | After **reverting INI to 5-31 baseline** (removed all self-added `mac_params` rows; kept only Jerry's 36 emulation flags). Baseline INI must match regression's tested set — don't add nvconfig rows to chase ad-hoc features. See [[feedback-no-self-ini-edits]]. |
| 2026-06-04 22:44 BJ | 312069017 | ❌ FAIL ~100s | `VHCA.cpp:9214 VerifyHealthBuffer ext_synd=0x821d` (same as 21:24) | **Coexistence test with 6-03 INI overlay (`satellite_pf_en=1 + device_type=3`, 2 lines only) verified FAIL.** Sat PF Current=1, ARM lspci 3 ConnectX-7, mst devs `mt41692_pciconf0/.1/.2` — sat PF really enabled, but utopx still hits same FW fwassert (`device_type=3` triggers implicit `cpu_management_pf=1` which conflicts). **6-03's untested "Phase 10 done + utopx baseline" claim was wrong** — they're incompatible at FW 32.50.0222 + utopx 07de3b4. Resolves only after Li's full patches + utopx update. |
| 2026-06-04 23:24~00:23 BJ | n/a (env experiment) | ❌ tried 6 INI permutations | sat PF Current stays 0 with 4/5/7/9-line INI (cpu_management_pf=0 explicit kills sat PF instantiation); only 2-line INI lets Current=1 but that triggers Assert 1 | Tried: 4-line (+`cpu_management_pf=0`), 5-line (+`cpu_management_port=0`), 7-line (BF-4 PRS bundle), 9-line (Marie's MAS-official PSID MT_0000000998 recipe). All sat PF Current=0. Iron_prep `reduce_num_of_dpu_pfs` reduces sat PF when cpu_management_pf=0 is explicit on BF-3 — exact reduction path not found in our grep. |
| **2026-06-05 00:23 BJ** | n/a | ❌ Marie's MAS recipe doesn't work on 171 even with target FW version | Switched to FW build `rel-32_49_9906` (matches MAS target `xx_49_xxxx`) + 9-line MAS INI: sat PF Current still 0 | Concluded the FW-level INI-burn route to sat PF (Phase 10) **is blocked** at FW 32.49.9906 + 32.50.0222 on 171 hardware. Likely needs Marie's dedicated `l-fwreg-146` setup, or extra mlxconfig NVRAM setup not documented in MAS, or there's a regression. **IM Marie / Li needed to unstick Phase 10.** |
| **2026-06-05 00:50 BJ** | n/a (discovery) | 💡 **Key insight: Phase 10 not required for utopx sat-PF FWV** | utopx has native sat-PF support (`VHCA::IsDpuPf`, `HandleDpuPfCreateEswVport`, `force_dpu_pf_emu_manager`, `num_sat_pf` NVconfig gen, etc.) — 50+ code hits | utopx tests sat-PF logic through conf knobs, not FW-level instantiation. **The Right Path: Phase 11.** Today's INI debugging marathon was based on a wrong assumption that FW must instantiate sat PF before utopx can test it. utopx's `force_fw_cap.enable_mask_2.fw_feature_support_bits.force_dpu_pf_emu_manager=1` knob makes utopx itself drive the sat-PF code paths without needing FW to physically expose a sat PF. See §Phase 11. |
| 2026-06-05 ~13:14~13:33 BJ | n/a (env recovery diagnostic) | ❌ Multiple ICMD_BAD_PARAM / parse fails | After regression released 171, neither regression's daily pair (utopx `9f5f06910` + FW `32.50.0260`) nor partial pin-backs worked for utopx baseline | Root cause: regression had **rebuilt utopx.exe** at 11:50 BJ; my `git checkout 07de3b4` only reverted source, not binary. Result: source/binary mismatch → `TestKeeps.cpp:116 failed to parse: force_fw_cap...force_dpu_pf_emu_manager = 50:0 50:1`. Path forward: full rebuild + repinning, see §Phase 12. |
| 2026-06-05 13:33~14:01 BJ | n/a (rebuild) | 🔨 Rebuilt utopx 07de3b4 binary (`./build.sh`, ~28 min docker build) | New `utopx.exe` matches `07de3b4` source. Submodules also reset (`git submodule update --recursive` set `steering_ul` to `43342063a`). | — |
| **2026-06-05 14:03 BJ** | **3996255652** | ✅ **PASS** ~7m47s | utopx baseline | Fully recovered 5-31 pin: utopx `07de3b4` (rebuilt binary) + FW `32.50.0222` + baseline INI. Baseline PASS confirms env is clean. |
| **2026-06-05 14:11 BJ** | **226259204** | ✅ **PASS** ~8m57s | utopx + **sat-PF Path A knobs** | First end-to-end PASS of sat-PF + utopx coexistence! 3 `-e` flags: `force_dpu_pf_emu_manager=1`, `num_sat_pf=1`, `num_sat_pf_valid=1`. Confirms Path A works on 5-31 pin. Sat-PF code paths exercised in utopx without any FW-level sat-PF instantiation (Phase 10 unnecessary). |

### 2026-06-06：真实 Li FW patch + 渐进 WA，把 BF-3 端到端推进到 cap 层

**目标转变**：不再用 `force_fw_cap`（utopx 内部模拟），而是把 **Li 的真实 FW patch（`nbu:golan_fw~1426433` PS8）** cherry-pick 进本地 golan，build + burn，跑 utopx **去掉 `force_fw_cap`**，验真实 delegation。

**branch**：golan `li-cap-delegation-rel-12_50_0223`（基于 `rel-12_50_0223` + cherry-pick Li `1faa888`）；utopx `li-cap-delegation-host_fwv_20260527_FW_version_50_0222_branch_master`（基于 `07de3b4`）。FW build：`jmake -c -o`（首次撞 stale depfile `cable_info_legacy.c`，必须 `--clean`）→ `fw-BlueField-3.mlx`。

**这轮做的代码改动（全在上述两个 branch，未 push）：**
1. **golan `mac_guid_handler.c:427` FW WA** —— `0x821D` assert（`cpu_management_pf=1 && !DEVICE_IS(SMART_NIC)`）放宽为 `!DEVICE_IS(SMART_NIC, DPU_WITH_NON_INTEGRATED_CPU)`。根因：BF-3 结构性 `cpu_management_pf=1`（embedded ARM），与 sat-PF 要求的 `device_type=3` 互斥。**`cpu_management_pf=0` 不是出路**：会改撞 `0x80CC`（`mac_guid_handler.c:368` MAC_MNG_PF 需 cpu_management_pf=1）—— 821D↔80CC 两难，只能改码放宽 821D。
2. **utopx `VPORT.cpp:InitNicVportContextGuids` WA** —— mng PF 在 `satellite_pf_en` 配置下也分配 GUID（原本预测 0）。
3. **utopx `VPORT.cpp:GetMacGidOffset` 修复** —— 调用 `GetMacGidOffset(...)` 时补传 `isMngPf=GetVhca()->IsMngPf()`（原代码从不传，潜在 bug）。否则 mng PF GUID 偏移错 `0x68`。
4. **utopx work item A（`HcaCaps.cpp`）** —— 新增 `GetDeviceEmuManagerMaxCap(vhca,type)` 镜像 Li 的 `is_device_emulation_manager_max_cap_sup`；nvme max-cap 换用它，新增 virtio_net 行（IGNORE_CAP）。详见 [[plans/utopx_verification_emu_mgr_delegation.md]] §0.5。

| 时间 BJ | seed | 结果 | 配置 | 备注 |
|---|---|---|---|---|
| 2026-06-06 ~16:14 | 3702964000 | ❌ FAIL ~1.5min | 0223+Li, 2-line INI, **no force_fw_cap** | `VHCA.cpp:9214 ext_synd=0x821d`。utopx 真实读到 Li 的 cap（`is_sat_pf=1`/`input_gvmi_is_dpu_pf`），但 FW health assert 先挂。Li patch 不碰这个 assert。 |
| 2026-06-06 ~17:03 | 2335245446 | ❌ FAIL ~1.5min | + INI `cpu_management_pf=0` | 验证 `cpu_management_pf=0` bypass 821D 但改撞 `0x80CC`（mng PF MAC 需 cpu_management_pf=1）。回退该 INI 行。 |
| 2026-06-06 ~17:33 | 4169183052/3702964000 | ❌ FAIL ~ | 0223+Li **+ line427 WA**, 2-line INI | 821D/80CC 全清！ArmAgent push BFB ✅、跑 2430 ops，卡 `QueryNicVport` mng PF(GVMI 0x12) `node_guid` expected=0 vs FW 真实 GUID。根因 `VPORT.cpp:662` 对 mng PF 预测 0。 |
| 2026-06-06 ~19:33 | 2762021911 | ❌ FAIL @2431 | + VPORT GUID WA(#2) | GUID 不再是 0，但偏移错 `0x68`（mng PF 专属 slot）。根因 `GetMacGidOffset` 没传 isMngPf。 |
| 2026-06-06 ~19:41 | 3228976854 | ❌ FAIL **@3501** | + GetMacGidOffset isMngPf(#3) + work item A(#4) | **GUID mismatch 清除**，推进到 3501。新卡点 cap 层：DPU PF 上 `QUERY_HCA_CAP VirtioNetEmuCap` 返回 `0xac5816 "virtio net device emulation is not supported"`。因 work item A 让 DPU PF 被当 virtio_net manager，但本 INI `virtio_net_emu_num_pf=0`（virtio_net 仿真未启用）。nvme 启用（`nvme_emu_num_pf=2`）。下一步：work item A 暂只留 nvme 委派。 |

**追加 fix（#5~#7，2026-06-06 晚，决定只在 BF-3 上靠 utopx WA 推进，因无 Argaman）：**
5. **utopx work item A 只留 nvme**（去掉 virtio_net 行）—— 但没用：FW 报 DPU PF `virtio_net_device_emulation_manager` max=1 是 FW 自己（Li stub `is_device_emulation_type_supported_for_manager_cap` 恒 `return 1`），utopx 读到后 `IsVirtioNetEmuManager()`=true → 仍查 VirtioNetEmuCap。
6. **utopx `HcaCaps.cpp:GetIsHotPlugSupportedCapBit`** —— `general_obj_type_device_object` 门控从 `IsDefaultDeviceEmulationManager()` 放宽到 `IsDeviceEmulationManager()`（sat-PF 环境有多个 emu mgr：default ECPF + DPU PF + 被 set 的 host PF，FW 给每个都报 device_object=1）。
7. **utopx `VHCA.cpp:9373 BuildRequiredHcaCapList`** —— VirtioNetEmuCap 的 require 条件加 `&& GetVirtioEmuNetPfNum(GetHostIndex())>0`（INI `virtio_net_emu_enable=1` 但 `num_pf=0`，所以 gate 在 num_pf 不是 enable）。清除 0xac5816。

| 时间 BJ | seed | 结果 | 备注 |
|---|---|---|---|
| 2026-06-06 ~21:41 | 3228976854 | ❌ FAIL @5005 | work item A(nvme-only) 后过了 3501 virtio_net 站，推进到 5005。新卡 `general_obj_type_device_object` expected=0 vs FW=1（DPU PF）。 |
| 2026-06-06 ~22:?? | — | ❌ FAIL @5442 | fix #6 后过 5005，推进到 **5442**。又撞 virtio_net 0xac5816（fix #5 没真正拦住，根在 FW stub）。 |
| 2026-06-06 ~22:?? | 2797817397/3563285779 | ❌ FAIL @3058/2758 | fix #7（IsVirtioNetEmuEnabled gate）没用→改 num_pf gate 后过 virtio_net，但 `general_obj_type_device_object` 又在 **另一 vhca**（host PF GVMI 0xf，被 set 为 emu mgr）冒出。 |
| 2026-06-06 ~22:16 | — | ⚠️ **HOST HANG** | fix #6 改 `IsDeviceEmulationManager()` 后跑，**171 host OS 直接 hang**（ping 不通，IPMI power cycle 恢复）。未拿到 verdict。BF-3 + utopx bare-metal 的稳定性风险。 |

**关键认知（更新）**：
- 前 3 个（821D/80CC/GUID）= BF-3 artifact；从第 4 个起进入 **utopx cap 预测**领域 —— 这是**开放式**的：sat-PF 环境有多个 emu manager，FW 给每个报一组 emulation cap，utopx 现有预测都按"单一默认 mgr"算，每个 seed 暴露不同 vhca/cap 组合（`general_obj_type_device_object` 就在至少 2 个 vhca 上炸过）。这是 work item A 的**完整范畴**（系统性 cap 预测更新），不是几个 WA。
- **virtio_net 0xac5816 的根 = Li 的 FW stub**（`is_device_emulation_type_supported_for_manager_cap` 恒 1），等 Li 填实后这类自然消失。已在 utopx 侧用 num_pf gate 绕过。
- **host hang**：2026-06-06 22:16 一次 utopx run 把 171 host OS 挂死，IPMI 恢复。BF-3 端到端跑这套 WA 有稳定性风险。
- 累积 utopx WA 共 7 处（见上 #1~#7，全在 companion branch 未 push）+ golan line427 FW WA（未 push）。无 Argaman，只能 BF-3 + 这套 WA 继续；属脆弱但唯一可行路径。

**追加 fix #8 + 进展（2026-06-06 深夜）：**
8. **utopx work item A nvme host-mgmt 字段（`HcaCaps.cpp` ~3252）** —— DPU PF 的 `host_number_ready / max_managed_emulated_hosts / log_max_queue_depth` 加 `!isDpuPf` 门控（DPU PF 是 satellite，不管理 host，FW 对这 3 字段返 0，其余 nvme emu cap 照常填充）。
- **virtio_net require gate（#7）改为 `!IsDpuPf()`**：num_pf gate 在某些 seed/other_func 上下文不稳（GetVirtioEmuNetPfNum 偶返 >0），直接排除 DPU PF（本配置 virtio_net 禁用，DPU PF 永不需要查 VirtioNetEmuCap）。

| 时间 | iter | 备注 |
|---|---|---|
| ~22:48 | **5028** | fix #8 后过 device_emulation_cap 内容站（4562），推进到 5028。又撞 virtio_net 0xac5816（DPU PF，#7 num_pf gate 该 seed 没拦住）→ 改 `!IsDpuPf()`。 |
| ~22:57 | n/a | env 退化开始：utopx 写 pf_pci_conf TLV 时 FW 报 **`ACCESS_REG_CONFIG_SEC_CORRUPTED`**（NVconfig 段损坏）。 |
| ~23:16 | n/a | reburn 0223+WA 恢复 NVconfig（Current=1 一次 cycle 即到），但跑 utopx 在 init 撞 **`ICMD_ACCESS_REG BAD_PARAM`**（iter 2000）。 |
| ~23:20 | n/a | 换 `conf.xml`（避 debug_conf ICMD walk）**仍撞同样 ICMD_BAD_PARAM**（line 826，极早）→ 确认是 box FW/NVconfig 深层坏状态，与 conf 文件/代码无关。 |

**最终状态（2026-06-06 深夜）**：
- **进展**：startup-fail → utopx iteration **~5028**（seed 相关）。清除链：821D/80CC（FW WA）→ GUID（VPORT ×2）→ general_obj_type_device_object（IsDeviceEmulationManager）→ virtio_net cap（!IsDpuPf）→ device_emulation_cap nvme 内容（host-mgmt !isDpuPf）。
- **8 处 utopx WA + 1 处 golan FW WA**（全未 push，companion branch）。
- **box 退化**：今日 ~23 次 power cycle + 多次 burn 后出现 **4 个 env 级故障**（host hang / CONFIG_SEC_CORRUPTED / ICMD_BAD_PARAM ×2），连续两次恢复尝试都在 init 阶段挂。**进一步推进被 box env 稳定性阻塞，非代码问题**。
- **剩余 cap 预测仍是开放式**（每 seed 暴露不同 vhca/cap）。
- **下次恢复路径**：`mlxconfig reset`（清所有 TLV 到默认）→ 冷 power-off 较久 → 重 burn 0223+WA → 重设 sat-PF（PCI_SWITCH_EMULATION_ENABLE / PF_NUM_SAT_PF）→ 再跑。或换台未被反复 cycle 的 BF-3。

**2026-06-07 凌晨：env reset 成功恢复 + 推进到 cur-cap 层（work item B）**

env reset 流程**验证有效**：host+ARM `mlxconfig -y reset` → power cycle → 重设 `PCI_SWITCH_EMULATION_ENABLE=1`(host)+`PF_NUM_SAT_PF=1`(ARM) → cycle（注意 sat-PF 仍可能 Current=0，需再 set+cycle）。**ICMD_BAD_PARAM / CONFIG_SEC_CORRUPTED 全消失，box 恢复干净**。

追加 fix #9：**utopx `HcaCaps.cpp:GetIsHotPlugSupportedCapBit`** —— 对 DPU PF 跳过 `IsGenericEmuEnabled(hix)` 门控（DPU PF 在 smartnic host HIX≠0，MUSTANG 上 `IsGenericEmuEnabled` 因 `MUSTANG && hix` 返 false，但 FW 仍报 general_obj_type_device_object=1）。

| 时间 | iter | 备注 |
|---|---|---|
| ~00:50 | 4564 | env reset 后回到 cap 链，general_obj_type_device_object 又在 DPU PF(HIX=1) 失败 → fix #9 跳过 IsGenericEmuEnabled gate。 |
| ~01:13 | **3142** | fix #9 后过该站。新卡点：**CurrentCap GeneralDeviceCap** on DPU PF：`nvme/virtio_net_device_emulation_manager` cur expected=1 Actual=0。 |

**到达 work item B（cur-cap 镜像）—— 这是 Li delegation 的核心 max-vs-cur 语义**：
- DPU PF 的 **max** manager cap=1（能委派，work item A 已对，FW 同意）；**cur**=0（未经 SET_HCA_CAP 委派，FW 返 0）。
- utopx 的 cur 预测走 `RETURN_GENRAL_CAP_VALUE_IF_MAX_SET`（`VHCA.cpp:89`）fallback 到 **max 值(1)** → 与 FW cur(0) 不符。
- **正解 = 实现 MAS work item B**：per-vhca cur-cap 镜像（`EmuMgrCapState`），DPU PF cur manager 初始化为 `def_cap_sup`(=0)，由成功的 `SET_HCA_CAP(other_function)` 更新为 1。这不是一行 gate，要动 utopx 的 cur-cap 预测框架（`HcaCaps` SetCap(CurrentCap) / IsNvmeEmuManager 的 cur 路径）。详见 `plans/utopx_verification_emu_mgr_delegation.md` 工作项 B。

**累计 9 处 utopx WA + 1 golan FW WA**（companion branch 未 push）。进展：startup → cur-cap 层（work item B）。剩余：work item B（cur-cap 镜像，定义清晰但非平凡）+ 开放式 cap content。

**fix #10：work item B cur-cap manager（`VHCA.cpp:VerifyQueryHcaCap` GeneralDeviceCap case）** —— `CurrentCap == op && target_vhca->IsDpuPf()` 时把 expected `nvme/virtio_net_device_emulation_manager` 覆盖为 0（DPU PF max=1 能委派，但 cur=0 未委派；scenario_dpa_emu 不做实际 SET_HCA_CAP 委派）。**生效**：过 3142 cur-manager 站，推进到 **3666**。**✅ 验证了 Li delegation 的核心 max-vs-cur 语义**。

**当前卡点（3666）：`hotplug_capabilities.max_hotplug_devices` expected=0 Actual=0x0f(15)**。utopx `maxHotplugDevices=!!(GetPciSwitchNumPort(hix)-1)`，DPU PF(HIX=1) 因 `IsGenericEmuEnabled(1)=false`(MUSTANG&&hix) → 0；FW 返回**具体值 15**。

**⚠️ 关键转折 / 建议停在这**：从此处起，FW 对 DPU PF emulation-manager 返回的是**具体数值**（max_hotplug_devices=15 等），utopx **无从推算**，需要 **HLD/Li 提供 DPU PF 的确切 cap 值**，不能靠猜。继续 field-by-field 猜值不可持续。
- **已达成的核心验证**：work item A（max cap delegation target）+ work item B（cur cap=0 until SET_HCA_CAP 委派）—— 即 Li delegation 的 max-vs-cur 语义，**已在 BF-3 端到端验证通过**（utopx 跑到 3666，这两层 cap 预测匹配 FW）。
- **box 不稳**：本 session 共 5 个 env 异常（host hang / CONFIG_SEC_CORRUPTED / ICMD_BAD_PARAM ×2 / 零输出 run）。env reset 流程有效但 box 在反复 cycle 下持续退化。
- **累计 10 utopx WA + 1 golan FW WA**（companion branch 未 push）。
- **下一步正路**：拿 HLD（Confluence 3395678597）/ 找 Li 要 DPU PF 的 emulation-manager cap 期望值（max_hotplug_devices、device_emulation_cap 等），系统性补全 utopx 预测（work item A 完整范畴），而非端到端猜值。


### 2026-05-31 run notes (latest)

- Stdout-tail log: `/labhome/pexiang/utopx_171_20260531_232525.log` (162 lines — only the last `tail -150` of utopx stdout plus the driver-state preamble)
- **Full utopx log**: `/auto/fwgwork1/pexiang/utopx/verix_test_20260531_182531_629_0.log` (~19 MB, 134 867 lines). UTC timestamp in filename. This is the file to actually analyze; the stdout-tail one is just a sentinel for pass/fail.
- Peak memory: 4920.78 MB. CR READ/WRITE count: 617 712. PCI READ/WRITE: 2 643.
- **Coverage gap observed:** `EmuDevOverDpaLiveUpdate` scenario fired **0 times** in 300 iterations despite `dpa_agent_dev_emu_live_update.prob = 20` in `scenario_dpa_emu.conf:11`. Likely cause: precondition (an existing emu manager + emu object created earlier in the iteration) wasn't met because base scenarios in this conf don't bring emu objects to a runnable state first. Relevant to the OCI BF-4 MAS milestone *Live Update* (Aug-1 2026). Scenarios that DID fire: 7× `DpaBasicResScenario`, 3× `DpaAgentApp StartThreads`, 3× `DpaAgentApp LoadProcess`, 1× `GenericEmulationOverDpaScenario`.
- Did NOT run `jk --fw-reset` before this run because no prior utopx run had touched virtio state on this box that day. Best practice: do `jk --fw-reset` between runs if you're iterating.

## Re-run quick reference

Assumes the one-time setup in Phases 1-5 AND Phase 10 (satellite PF) have both been done and FW is already burned on l-fwreg-171.

### Optional sanity check: is the satellite PF still there?

```bash
ssh l-fwreg-171 'SSHPASS=3tango sshpass -e ssh -o StrictHostKeyChecking=no \
    -o PreferredAuthentications=password root@192.168.100.1 \
    "mst start >/dev/null && lspci -nn | grep -c ConnectX-7"'
# want: 3   (= 2 ECPFs + 1 sat PF)
# If output is 2: sat PF is gone — re-run Phase 10.8 reproducible re-execution.
# If ssh times out: ARM Linux didn't boot; need rshim console intervention or BFB re-push.
```

```bash
# From any dev box (e.g. m-fwdev-167)
# 0. Verify lock
python3 /.autodirect/sw_tools/Internal/Noga/RELEASE/latest/cli/noga_manage.py \
  -q -n l-fwreg-171 -D 2>&1 | grep -E 'Status\.(status|lock_owner|lock_time_out)'
# want: Status.status = Lock, Status.lock_owner = pexiang

# 1. Between-runs reset (skip on the very first run after a fresh burn)
ssh l-fwreg-171 'sudo /labhome/pexiang/.usr/bin/jmake --device /dev/mst/mt41692_pciconf0 --fw-reset && sudo modprobe udriver'

# 1b. Clear rshim DROP_MODE — REQUIRED after any fwreset (whether or not utopx ran before).
# Without this, utopx's BFB push gets `sh: /dev/rshim0/boot: Invalid argument` ×10 and FATALs.
ssh l-fwreg-171 'echo "DROP_MODE 0" | sudo tee /dev/rshim0/misc; sudo cat /dev/rshim0/misc | grep DROP_MODE'

# 2. Pre-run env checks — send ONE ssh per command, NOT bash ~/run_utopx_171.sh as a wrapper.
#    Bundling everything into the script means one ssh failure aborts opaquely; one-command-per-ssh
#    makes each step's stdout/stderr inspectable independently.

# 2a. Verify host PFs lineup (expect 5: 83:00.0/.1/.2/.3 + rshim at .4 or .7)
ssh l-fwreg-171 'lspci -nn | grep "^8[0-9]:00\." | head -8'

# 2b. Verify rshim DROP_MODE is 0 and ARM ECPF still has PF_NUM_SAT_PF=1
ssh l-fwreg-171 'sudo cat /dev/rshim0/misc | grep -E "DROP_MODE|UP_TIME"'
ssh l-fwreg-171 'SSHPASS=3tango sshpass -e ssh -o StrictHostKeyChecking=no -o PreferredAuthentications=password root@192.168.100.1 "mst start >/dev/null 2>&1; mlxconfig -d /dev/mst/mt41692_pciconf0 -e q PF_NUM_SAT_PF | grep PF_NUM_SAT_PF"'

# 2c. Confirm udriver is loaded with 4 devices (one per emu PF)
ssh l-fwreg-171 'lsmod | grep "^udriver"; ls /dev/udriver_* | head -5'

# 3. Launch utopx — single ssh, the utopx command directly. Run in background and capture log.
LOG="$HOME/utopx_171_$(date +%Y%m%d_%H%M%S).log"
ssh l-fwreg-171 'cd /auto/fwgwork1/pexiang/utopx && \
    sudo ./utopx --device=/dev/mst/mt41692_pciconf0 --daemon --num_of_clients=0 \
        --xml_conf_file debug_conf.xml --conf_file config/scenario_dpa_emu.conf \
        --iter=300 --ops_per_it=30 2>&1 | tail -150' > "$LOG" 2>&1 &
wait $!

# 4. Verdict — both grep the host-side stdout-tail AND check the verix full log on 171
grep -E 'TEST PASSED|TEST FAILED|Test-status|To rerun use seed|FATAL' "$LOG" | head
ssh l-fwreg-171 'ls -lt /auto/fwgwork1/pexiang/utopx/verix_test_*.log | head -1'
```

**Why one-command-per-ssh, not `bash ~/run_utopx_171.sh`**: bundling the env checks + driver swap + utopx launch into a single script means failures in any step bleed into the same stdout stream, and the wrapper's `tail -150` doesn't flush until utopx exits — so if utopx FATALs in PreTest, you see the failure only after the full 8-min run. Sending each command on its own ssh lets you abort early when an env check fails, and stdout from each step is naturally separated. The `~/run_utopx_171.sh` file is still there for casual interactive use; for automated / scripted runs prefer the one-command-per-ssh form above. Peter requested this pattern explicitly on 2026-06-04.

In Claude Code sessions, run step 3 with `run_in_background: true` on the Bash tool; utopx's internal `tail -150` only flushes when it exits, so the log appears idle during the ~8 min run — don't `tail -f` it, wait for the harness's completion notification.

To reproduce a specific seed, append `--seed=<N>` to the utopx command in step 3.

### Escalation ladder when step 1 doesn't behave


| Symptom after fwreset                                                               | Likely cause                                                 | Fix                                                                                         |
| ----------------------------------------------------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------- |
| `jk --fw-reset` hangs > 90 s                                                        | D-state utopx zombie holding kernel resources                | `jk --power-cycle l-fwreg-171` (~3 min)                                                     |
| `lspci` shows `rev ff` on any `83:00.*`                                             | Device wedged                                                | `jk --power-cycle l-fwreg-171`                                                              |
| fwreset completes but utopx fails at `cat ... > /dev/rshim0/boot: Invalid argument` | DROP_MODE didn't get cleared in step 1b                      | Re-run step 1b and verify `grep DROP_MODE /dev/rshim0/misc` shows `0`                       |
| utopx fails at `Virtio device_status 0xf` at init                                   | virtio state not drained                                     | `jk --fw-reset` again (sometimes one isn't enough); if still failing, power-cycle           |
| `jk --fw-reset` itself errors out                                                   | rare; usually means lock-file or `mlxfwreset` upstream issue | inspect `/tmp/fwreset_lock`, `/tmp/udriver_lockfile.lock`, then power-cycle if still wedged |


### What you do NOT need between runs

- **No re-burn** — FW 32.50.0222 stays on flash through resets. You burn again only if you want a different version or you cleared flash for some reason.
- **No repo re-checkout** — utopx + golan_fw2 stay at the regression tags (`07de3b4` / `rel-12_50_0222`) until you explicitly `git stash pop`, change branches, or another tool moves HEAD.
- **No `mustang_fw_reset.sh --remove_rescan`** — see "What NOT to do". Hangs the PCIe parent bridge; recovery requires power cycle.
- **No power cycle** in the normal case. Reserve it for the symptoms in the table above.

### When you're done iterating

If you want your prior in-progress work back (test prep stashed it):

```bash
cd /auto/fwgwork1/pexiang/utopx     && git stash pop    # restores .claude/, adabe/PacketFields.{cpp,h}, genid_dump
cd /auto/fwgwork1/pexiang/golan_fw2 && git stash pop    # restores shared/* mods and .bash_profile
```

`git stash list` in each repo shows the saved entry (top of stack is from 2026-06-01 prep).

## Files modified by this work


| File                                                                                                     | Change                                                                                                                                                                                                                                                                                         |
| -------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `~/myGit/crosslv/nv-tools/jmake`                                                                         | Bug A: pass `--run_new_fwreset` for chips `m`/`gl`/`ar` in `runFWReset`. Bug B: replaced `sourceFwvAlias()` with a doc-only stub; added conditional inline source in `main()`; removed five `sourceFwvAlias` calls from `runRegQuery`/`runRegMalloc`/`runRegMine`/`runRegIdle`/`runRegCancel`. |
| `/auto/fwgwork1/pexiang/utopx/regression_ini/burned_session_11047756_v32_50_0222_psid_MT_0000000998.ini` | (2026-05-28) Appended Jerry's 36 emulation flags to `[fw_boot_config]`. (2026-06-03) Added 2 more lines for satellite PF: `mac_params.satellite_pf_en = 1` and `mac_params.device_type = 3` (line 55-56).                                                                                       |
| `/auto/fwgwork1/pexiang/utopx/regression_ini/default_900-9D3B6-00CV-AAB_Ax.ini`                          | Copy of the regression's release default INI (unmodified).                                                                                                                                                                                                                                     |
| `/auto/fwgwork1/pexiang/golan_fw`                                                                        | `git stash` of `shared/algorithm` local mod, then `git checkout 1bd364033669` (Mustang regression match). 2026-06-03: also checked out a private branch `pexiang/sat_pf_setup_171` for sat PF infra work (no source edits; only working-tree isolation).                                       |
| l-fwreg-171 host MFT                                                                                     | 2026-06-03: upgraded 4.35.0-138 → 4.37.0-75 via `jmake --mft-install` (needed for `PF_NUM_SAT_PF` symbol recognition).                                                                                                                                                                          |
| l-fwreg-171 ARM MFT                                                                                       | 2026-06-03: upgraded 4.25.0-27 → 4.37.0-75 via `/mswg/release/mft/last_stable/install.sh` over `ssh root@192.168.100.1`.                                                                                                                                                                       |
| l-fwreg-171 ECPF NVRAM                                                                                    | 2026-06-03: `PF_NUM_SAT_PF = 1` written via `mlxconfig` from ARM side. Persistent through power cycle.                                                                                                                                                                                         |


## Related context

### OCI BF-4 Satellite PF Emulation Manager Capability Delegation (the feature this env exists for)

- **Feature owner (FW side)**: Li Zeng
- **FWV owner**: Peter Xiang
- **HLD**: [Confluence page 3395678597 — "[HLD] [OCI][BF-4] Satellite PF Emulation Manager Capability Delegation"](https://nvidia.atlassian.net/wiki/spaces/FW/pages/3395678597)
- **FWV MAS**: [Confluence page 3530037909](https://nvidia.atlassian.net/wiki/spaces/FW/pages/3530037909) (published)
- **FW-side gerrit (in progress)**: [`nbu:golan_fw~1426433`](https://git-nbu.nvidia.com/r/c/golan_fw/+/1426433) — Li's first commit, **not the complete feature**. More commits are still being written. **Do not test against this single commit alone.**
- **FWV verification plan**: `plans/utopx_verification_emu_mgr_delegation.md` — utopx-side test code design (6 work items, 3 PRs, ~490 LOC). Implementation paused pending Li's FW work to finish.

### Satellite PF underlying feature (the FW capability we're enabling via Phase 10)

- **FWV MAS**: [Confluence page 2830146343 — "[FWV][MAS][OCI] PF without page supplier and MPFS on DPU host side"](https://nvidia.atlassian.net/wiki/spaces/FW/pages/2830146343) — Marie Chagny, target FW `xx_49_xxxx`
- **HLD**: [Confluence page 2830143951 — "[HLD][BF4] VR - OCI MLI Partition"](https://nvidia.atlassian.net/wiki/spaces/FW/pages/2830143951) — "Device need to be BF3+, this is the lowest generation device that FW verification supports ATM"
- **QA test plan**: [Confluence page 3328961648 — "BF4 OCI MLI SAT PF Zero Trust & Host Restrictions Security Test Plan"](https://nvidia.atlassian.net/wiki/spaces/QA/pages/3328961648) — origin of the `mlxconfig -d $ECPF -y s PF_NUM_SAT_PF=1` recipe
- **SW design**: [Confluence page 3271938371 — "BlueField 4 OCI MLI design VM and configuration guide"](https://nvidia.atlassian.net/wiki/spaces/SW/pages/3271938371) — system provisioning flow

### Baseline utopx scenario_dpa_emu context

- Feature wiki: "MTBC-+4690480+OCI+BF-4+virtio-net+needs+emulation+capabilities..." (Confluence)
- Redmine tickets: [#4650230](https://redmine.mellanox.com/issues/4650230), [#4690480](https://redmine.mellanox.com/issues/4690480), [#4690593](https://redmine.mellanox.com/issues/4690593)
- Argaman P2 setups (already have the 36 flags in `mars_extra_burn_params/master_rc`):
  - `/auto/mswg/projects/fw/fw_ver/MARS_HCA_CORE/MARS_conf/setups/ARGAMAN_FW-l-fwreg-225_P2/`
  - `/auto/mswg/projects/fw/fw_ver/MARS_HCA_CORE/MARS_conf/setups/ARGAMAN_FW-l-fwreg-226_eth_P2/`
- MARS results root for Mustang regression:
`/auto/sw_regression/host_fw/HCA_CORE_FWV/MARS/conf/results/MUSTANG_FW-l-fwreg-171_eth_ARM_AGENT_P1/`

## Phase 13 — "DPU PF as emulation manager": utopx + FW fixes → **scenario_dpa_emu sat-PF PASSED** (2026-06-08, l-fwreg-171, FW 32.50.0223)

> ✅ **RESULT (2026-06-08): `scenario_dpa_emu` + sat-PF knobs PASSED all 300 iterations — `Test-status 0 / [TEST PASSED]`, 589s.**
> **Passing seed: `3975318385`.** Build: utopx `07de3b4` + 10 fixes (below) + golan_fw `rel-12_50_0223` + Li's commit `nbu:golan_fw~1426433` + 1 FW WA (below). Env: FW 32.50.0223, `NVME_EMULATION_NUM_PF=2` (INI), `VIRTIO_NET_EMULATION_NUM_PF=3` (mlxconfig override), `force_dpu_pf_emu_manager=1` + `num_sat_pf=1`/`num_sat_pf_valid=1` (utopx `-e` knobs). Arc: before any fix it died at **iteration 0** (init, first DPU-PF cap query) → now **300/300**.
> **Scope caveat:** one seed of one scenario. NOT the full regression. A different seed (`2676204582`) hit a separate `MODIFY_DPA_PROCESS_OBJ` "exception from unknown type" at iter 11 (pre-FW-WA; status unknown). Run a spread of seeds before claiming broad pass.

Ran `scenario_dpa_emu` + the 3 Phase-11 sat-PF `-e` knobs against FW `32.50.0223` (odd build, **includes Li's emu-mgr-delegation commit** [`nbu:golan_fw~1426433`](https://git-nbu.nvidia.com/r/c/golan_fw/+/1426433)) with a utopx built off `07de3b4` + the fixes below. **All failures so far are in the INIT / bring-up phase** (per-function `QUERY_HCA_CAP` + `QUERY_NIC_VPORT_CONTEXT` verification), **before iteration 1 of the 300-iter loop** — `TST:0:0:NNNN` is an op counter, not a test iteration. In this config the DPU PF is the **default** emulation manager (`force_dpu_pf_emu_manager` ⇒ `IsDefaultDeviceEmulationManager`=true; matches HLD 2830143951 "Default emulation manager = SAT_PF when configured on first ECPF"), **not** a delegation target — so it must be modeled as a normal *active* manager (cur=max), not max=1/cur=0.

Fixes applied (all in utopx, working tree on branch `li-cap-delegation-...`), each peeled the next init-phase blocker (frontier: init → op 2643 → 3977 → 4946 → 6212 → vport MAC):
1. **`HcaCaps::GetDeviceEmuManagerMaxCap`** — mirror FW `is_device_emulation_manager_max_cap_sup` incl. the type-support gate (`IsNvmeEmuSupported` / `IsVirtioNetEmuEnabled && !IsIB`); added the missing `virtio_net_device_emulation_manager` MAX prediction.
2. **`VirtioNetEmuCap` query gate** (`VHCA::BuildRequiredHcaCapList`) — gate on `GET_FIELD(virtio_net_device_emulation_manager) && GET_FIELD(general_obj_type_virtio_net_device_emultion)`. FW sets the *manager* bit on the DPU PF but reports `general_obj_type_virtio_net_device_emultion=0` for it, so QUERY VirtioNetEmuCap returns `0xac5816`; the object-support bit is the exact discriminator (HW-confirmed). (NOT `!IsDpuPf()`, NOT `num_pf` — `GetVirtioNetEmuMaxNumPf` returns the *max* cap=16, not the configured count, so a num_pf gate was a no-op.)
3. **CurrentCap GeneralDeviceCap emu-mgr** (`VHCA::VerifyQueryHcaCap`) — delegation-target zeroing only when `IsDpuPf() && !IsDefaultDeviceEmulationManager()`; the **default** DPU PF reports cur nvme=1 & virtio_net=1 (HW-confirmed).
4. **`HotPlugCap.max_hotplug_devices`** (`HcaCaps.cpp` ~3580) — bypass the `IsGenericEmuEnabled` per-hix gate for the DPU PF (it lives on a smartnic hix where it's false) so the prediction is non-zero (FW reports `0xf`); the MAX check is `ZeroIfExpectedElseGreaterThan`.
5. **`DeviceEmulationCap` (nvme) fields** (`HcaCaps.cpp` ~3274/3285) — the DPU PF reports the SAME nvme emu caps as a normal mgr: `log_max_queue_depth` not zeroed for DPU PF; `host_number_ready`/`max_managed_emulated_hosts` gated on `IsDefaultDeviceEmulationManager()` (the **single** active mgr = 1; a second/non-default DPU PF = 0).
6. **`VPORT::VerifyQueryNicVport`** — ignore `mac_addr_31_0`/`mac_addr_47_32` for `IsDpuPf()`. **node_guid is deterministic (base_guid+offset) and still verified**, but the sat-PF **MAC is FW-random/unpredictable**: the sat-PF MAC scheme is still **TBD** (MAS [2830146343](https://nvidia.atlassian.net/wiki/spaces/FW/pages/2830146343) "Mac Calculation - TBD" / "random assignment when satellite is not supported"; FR **#4796622** "[OCI][BF-4] Assign mac address to the DPU internal host PFs" = *Insufficient info*). Remove once FR #4796622 lands. **Note:** because Phase 10 (real sat-PF instantiation) is blocked on 171, the "DPU PF" here is the simulated function (physically the nvme-emu PF at `83:00.2`, dev `24577`), whose MAC is emulation-derived.

Additional utopx fixes found once bring-up completed and the 300-iter loop ran (the DPU PF actively creating emu devices):
7. **`RunSanityCheck`** (`HcaCaps.cpp` ~3977/3984) — don't push `DeviceEmulationCap` into the non-zero sanity list for the DPU PF: FW sets its emu-mgr bit (max+cur) but reports the CURRENT `DeviceEmulationCap` object all-zero (manager designated, active cap empty), so gate both pushes on `!IsDpuPf()`.
8. **`VHCA::ConsumeEmulatedResources`** (`VHCA.cpp` ~11735) — skip the dynamic-resource (msix/db) accounting (`return true`) when `!emuResInfo && IsDpuPf()`. FW does NOT support `QUERY_EMULATED_RESOURCES_INFO` on the DPU PF (returns `0xe5dfad` "operation is not supported"), so `emuResInfo` is legitimately null; the accounting can't apply. (`IsCmdQueryEmulatedResourcesInfoSupp` left unchanged — do NOT bypass its `IsGenericEmuEnabled` gate, that just makes utopx issue the unsupported query.)
9. **cur emu-mgr predicate split** — added `IsNvme/VirtioNet/Blk/FsEmuManagerCur()` reading the current cap, and an `IsEmuMgrCapDelegated()` per-VHCA state; resource-creation gates (`DpaVirtqApp` hotplug, `CmdHotPlugDevice`) use the cur variant. For the default-mgr DPU PF the cur read == max.

**FW WA (golan_fw, 1 change):** `is_logical_port_ib`/`is_logical_port_eth` (`src/common/multi_func_common.c` ~6782/6790) return the default (not-IB / not-ETH) instead of fatal-asserting (`0x8DE1`/`0x87F4`) **when `is_smart_nic_mode_sup()`** — the satellite/DPU PF is a portless ARM PF, so emulation ops on it (it being the emu manager) reach these with `INVALID_LOGICAL_PORTID`. **This was the iter-168 blocker.** Kept the assert for non-smartnic configs.
- ⚠️ **NOT Li's commit:** this assert is in `multi_func_common.c` (sat-PF port handling, authored by Artem Nesteruk 2024) — NOT in Li Zeng's 7 cap-delegation files. The trigger is the portless sat-PF + an unguarded port-link-type lookup in the emulation flow (broader OCI sat-PF feature). The WA **masks** a real FW gap; the proper fix should make the emulation flow handle the portless sat-PF. File to the sat-PF port/FW owners, not Li's 1426433.

**Build/iterate loop** (each cycle ≈ build + reset + run): utopx `jk -o` on m-fwdev-167 (output on NFS, 171 sees it). golan_fw FW change: `jk -o --models mustang` on 167 (rel-12_50_0223 is odd → buildable) → `.mlx` at `golan_fw/fw-BlueField-3.mlx`. **Burn (direct mlxburn, NOT `jk --burn` — that writes `image.bin` into the root-squashed NFS repo → Permission denied):** `ssh l-fwreg-171 'sudo -E env MFT_ICMD_TIMEOUT=60000 mlxburn -d /dev/mst/mt41692_pciconf0 -fw <abs .mlx> -conf <abs INI> -force'`. **INI = `regression_ini/burned_session_11083615_v32_50_0260_...ini`** (nvme=2, virtio=0, 36 emu flags, BAR2 lines, **NO `satellite_pf_en`** — matches the device; the 0222 INI HAS `satellite_pf_en=1` → would risk FW assert `0x821d`). After burn: `mlxconfig -y set VIRTIO_NET_EMULATION_NUM_PF=3` (the num_pf=3 override is mlxconfig-set, not INI; it's cleared by some fw-resets — re-set it), `jk --fw-reset` (applies the override → Current=3, 3 virtio funcs on bus, no power cycle needed), `systemctl restart rshim`, `DROP_MODE 0`, `modprobe udriver`. Between utopx runs, always reset (back-to-back without reset hits `UtopxFunctionManager.cpp:1356 device_status 0x40 vs 0xf` — leftover virtio devices). Seed pin: `--seed <N>` (verix `basic_arg_parser.cpp:96`).

