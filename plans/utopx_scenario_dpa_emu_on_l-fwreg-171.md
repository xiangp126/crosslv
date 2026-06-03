# FWV test env on l-fwreg-171 — for OCI BF-4 Satellite PF Emulation Manager Capability Delegation

**Feature:** `OCI BF-4 Satellite PF Emulation Manager Capability Delegation`. [HLD (Confluence page 3395678597)](https://nvidia.atlassian.net/wiki/spaces/FW/pages/3395678597). [FWV MAS (Confluence page 3530037909)](https://nvidia.atlassian.net/wiki/spaces/FW/pages/3530037909). Peter is the FWV owner.

**Aim:** stand up the BlueField-3 test environment on `l-fwreg-171` that this feature's FW verification will eventually run against. Two layers:

1. **Baseline utopx layer** — `utopx scenario_dpa_emu` running successfully on 171 with the right FW + INI (Jerry's 36 NVMe/virtio emulation flags). This is the existing test that exercises emulation paths and gives us a regression-known-good state to build on.
2. **Satellite PF layer** — `PF_NUM_SAT_PF=1` enabled on the ECPF so a satellite PF (ARM-side PF, BDF `00:00.2`) is exposed. This is the **prerequisite infrastructure**: cap delegation lets the ECPF delegate emulation-manager capability to a satellite PF via `SET_HCA_CAP(other_function=1)`, so without a satellite PF present there's nothing to delegate to. See [[feedback-satellite-pf-vs-cap-delegation]] — satellite PF enablement is independent of the FW cap-delegation patches; the satellite-PF infrastructure is BF3+-supported FW feature that pre-exists this feature work.

**Status of the FW feature on the implementation side (as of 2026-06-03):** **in progress, not yet ready for verification runs**. Li Zeng's gerrit [`nbu:golan_fw~1426433`](https://git-nbu.nvidia.com/r/c/golan_fw/+/1426433) is only *part* of the FW-side implementation — additional commits are still being written. Do **not** treat the current code on master_rc as a testable build. This plan focuses on **env preparation** so that when Li's feature work is complete, the test bench is already standing. Until then, only the baseline utopx scenario_dpa_emu layer is exercised; the satellite-PF layer just sits ready.

**For a fresh AI agent** picking this up: follow Phase 0 → 9 (utopx scenario_dpa_emu baseline) then Phase 10 (satellite PF). The "Final recipe" and "Re-run quick reference" sections at the bottom collapse it to a runnable script once the one-time setup is done. The phases below are the diagnostic log with every dead-end we hit so future debug is faster; phases marked "OPTIONAL" can be skipped if you just want to re-execute.

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
sudo cat /dev/rshim0/misc | grep -E "BF_MODE|UP_TIME"
# BF_MODE Unknown, UP_TIME 0(s)  — ARM not booted
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

## Phase 10 — Enable satellite PF (prereq for Li's cap delegation)

Done on 2026-06-03 after Phases 1-9 were already passing. Builds on top of the burned-INI state from Phase 3 (which now includes the 2 `mac_params` lines — make sure they're there before doing this phase, otherwise PF_NUM_SAT_PF won't exist as a TLV).

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

The tmfifo link is a /24 with two endpoints; by NVIDIA convention:
- **Host gets `192.168.100.2`**
- **ARM gets `192.168.100.1`**

Three independent ways to figure this out:

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

2. **Inspect host's tmfifo NIC** and infer the peer from /24 + the convention:
   ```bash
   ssh l-fwreg-171 'ip -br addr show tmfifo_net0'
   # tmfifo_net0      UP             192.168.100.2/24 fe80::6c36:bb29:192a:80c0/64
   ```
   Host is `.2/24` → ARM (the only other endpoint on the /24) is `.1`. The `.2 vs .1` allocation is fixed by the rshim driver: it always assigns the higher of the two to the host side.

3. **Read rshim misc to confirm rshim is talking to a real DPU at all**:
   ```bash
   ssh l-fwreg-171 'sudo cat /dev/rshim0/misc | grep -E "DEV_NAME|DEV_INFO|UP_TIME|BF_MODE"'
   # DEV_NAME    pcie-0000:83:00.7
   # DEV_INFO    BlueField-3(Rev 1)
   # UP_TIME     1234(s)
   # BF_MODE     Unknown        (or "Live" if ARM OS has reported ready)
   ```
   `DEV_NAME` is the host-side PCIe BDF that rshim binds to. Multiple DPUs → multiple `/dev/rshim*` devices, each with its own tmfifo /24 (100/110/120/...).

#### 10.2.2 Watch out for the .2 trap

`ssh root@192.168.100.2` "works" — port 22 listens — but it's the **host's own sshd answering on its tmfifo NIC**. You'll be SSH'ing back into the host you're already on. Symptoms:

- `uname -m` → `x86_64` (host) instead of `aarch64` (ARM). **Always check this.**
- `mst status` shows host PFs (`83:00.x`), not ARM PCIe domain (`00:00.x`).
- `root/3tango` works (host's root password) but it gives you nothing useful for ECPF work.

The point-to-point convention is unambiguous: ARM is **never** `.2`; it's always `.1` (or `.3`, `.5`, ... for multi-DPU boxes' subsequent rshims).

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

```bash
SSHPASS=3tango sshpass -e ssh -o StrictHostKeyChecking=no -o PreferredAuthentications=password \
    root@192.168.100.1 '
    mst start >/dev/null 2>&1
    mst status
    # Expected: 2 BlueField3 devices, /dev/mst/mt41692_pciconf0 (00:00.0, ECPF0)
    #                                  /dev/mst/mt41692_pciconf0.1 (00:00.1, ECPF1)

    mlxconfig -d /dev/mst/mt41692_pciconf0 q PF_NUM_SAT_PF
    # Expected: PF_NUM_SAT_PF = 0  (no longer "Failed to find Param / TLV")

    mlxconfig -d /dev/mst/mt41692_pciconf0 -y s PF_NUM_SAT_PF=1
    # Expected: "Apply new Configuration? y / Applying... Done! / Please reboot..."
'
```

If you see `-E- Unknown Parameter: PF_NUM_SAT_PF`, ARM mft is still old (step 10.3 didn't run).

If you see `-E- Failed to find Param / TLV with name 'PF_NUM_SAT_PF'`, the FW image doesn't have the TLV — re-check Phase 3 INI patch (the 2 mac_params lines) and re-burn.

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

    mst status
    # Expected: THREE mst devs:
    #   /dev/mst/mt41692_pciconf0       (00:00.0)
    #   /dev/mst/mt41692_pciconf0.1     (00:00.1)
    #   /dev/mst/mt41692_pciconf0.2     ← satellite PF mst dev

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

# 5. /dev/rshim0/misc should show BF_MODE becoming non-Unknown:
sudo cat /dev/rshim0/misc | grep -E "BF_MODE|UP_TIME"
# BF_MODE  Live              ← ARM Ubuntu reported ready
# UP_TIME  120(s)            ← rshim's view of how long ARM has been up

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
| `BF_MODE Unknown` forever, ARM hung in early boot | Try rshim console first; BFB reinstall as last resort |
| Just need to update MFT on ARM | **DO NOT BFB-reinstall** — just run `/mswg/release/mft/last_stable/install.sh` directly |
| Just need to set a new NVconfig | **DO NOT BFB-reinstall** — ssh in, mlxconfig set, done |

**171 today**: BFB reinstall **NOT needed**. The existing ARM Ubuntu (`l-fwreg-171-bf0`, kernel `5.15.0-1019.21.5.g2a61d1d-bluefield`) is functional, and the team's `root/3tango` works. Section 10.10 is documented as recovery procedure only.

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

Side-effect to notice: clearing `DROP_MODE` may bump `UP_TIME` from `0` to a non-zero value as the rshim re-establishes a connection to ARM — this is harmless and confirms the daemon is back to normal. `BF_MODE Unknown` is also normal pre-BFB-push.

### Don't try to set PF_NUM_SAT_PF from the host side

`mlxconfig -d /dev/mst/mt41692_pciconf0 -y s PF_NUM_SAT_PF=1` on the host writes to host PF0's per-PF NVRAM area; FW ignores that value when deciding sat-PF enablement. The host-PF NVRAM is harmless garbage. Symptoms if you do this thinking it will work:

- After mlxfwreset / power cycle: host lspci unchanged, mst dev count unchanged, no sat PF.
- `mlxconfig -d /dev/mst/mt41692_pciconf0 q PF_NUM_SAT_PF` on host shows `1` (the value you set) — misleading; the field exists per-PF, so each PF's mst dev reports its own area.
- The host_id / pf_index mlxconfig flags don't help: those only target class-3 per-host TLVs. PF_NUM_SAT_PF isn't class-3.

Always set this from ARM-side `mst dev` for ECPF — see Phase 10.4.

### Don't ssh to 192.168.100.2 expecting ARM

That's the **host's own tmfifo NIC IP** (point-to-point tmfifo link: host = .2, ARM = .1). SSH'ing to .2 connects you to the host itself (port 22 is the host's sshd). Misleading because:

- The SSH connection succeeds.
- `root@192.168.100.2 / 3tango` (host's root password) works.
- `mst status` and `mlxconfig` all run successfully but operate on host PFs, not ECPF.

Symptom: `uname -m` returns `x86_64`. For ARM, expected is `aarch64`. Always check. Use `192.168.100.1` for ARM.

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

### Satellite PF layer (Phase 10, added 2026-06-03)
- ✅ INI patched with `mac_params.satellite_pf_en = 1` + `mac_params.device_type = 3` (gates `PF_NUM_SAT_PF` TLV emission in `iron_prep`)
- ✅ MFT upgraded on host: 4.35.0 → 4.37.0-75
- ✅ MFT upgraded on ARM:  4.25.0  → 4.37.0-75
- ✅ ARM SSH access established: `root@192.168.100.1` / `3tango` (the host's tmfifo NIC is `.2`, ARM is `.1`)
- ✅ `PF_NUM_SAT_PF = 1` set on ECPF NVRAM from ARM side
- ✅ `jk --power-cycle l-fwreg-171` applied the NVconfig
- ✅ **Satellite PF appears** at ARM BDF `00:00.2` with mst dev `/dev/mst/mt41692_pciconf0.2`; mlxconfig + mlxprivhost both queryable on it
- ✅ Host-side state unchanged after sat PF setup — `scenario_dpa_emu` baseline still runnable
- 📌 Ready for downstream Li-cap-delegation tests (see [[plans/utopx_verification_emu_mgr_delegation.md]])

## Run history


| Date                     | Seed                   | Result       | Wall time   | Notes                                                                                                                                                                                                                                                       |
| ------------------------ | ---------------------- | ------------ | ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-05-28/29            | (multiple)             | ✅ PASS       | ~10 min     | Initial bring-up runs after burn                                                                                                                                                                                                                            |
| **2026-05-31 23:25 IDT** | **877500556**          | ✅ **PASS**   | **511.7 s** | Re-run from m-fwdev-167 over SSH; 300 iter × 30 ops/it = 9000 ops                                                                                                                                                                                           |
| 2026-06-01 ~14:12 IDT    | 3384525166             | ❌ FAIL early | ~16 s       | First attempt after re-burning 0222 + 2× `jk --fw-reset`. FATAL at `ArmAgentApiBareMetal.cpp:20`: `sh: /dev/rshim0/boot: Invalid argument` ×10. Root cause: rshim daemon left in `DROP_MODE 1` by the fwreset. Logged the failure mode in *What NOT to do*. |
| 2026-06-01 (post-fix)    | (passed run, seed TBD) | ✅ PASS       | TBD         | After `echo "DROP_MODE 0" | sudo tee /dev/rshim0/misc`. Confirmed the DROP_MODE step is the missing piece in Phase 9.                                                                                                                                       |
| **2026-06-03** | n/a (env work) | ✅ **Phase 10 done** | ~30 min | Satellite PF enabled on ARM (BDF `00:00.2`). INI patched with 2 `mac_params` lines + reburn + ARM mft 4.25→4.37 + `mlxconfig set PF_NUM_SAT_PF=1` on ECPF + `jk --power-cycle` to apply. Discovered `root@192.168.100.1/3tango` is the right ARM login (NOT `.2` — that's host's tmfifo NIC). |


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

# 2. Kick off the test in the background
LOG="$HOME/utopx_171_$(date +%Y%m%d_%H%M%S).log"
ssh l-fwreg-171 "bash ~/run_utopx_171.sh > '$LOG' 2>&1" &
wait $!

# 3. Verdict (short)
tail -50 "$LOG" ; grep -E 'TEST PASSED|TEST FAILED|Test-status' "$LOG"

# 4. Find the FULL run log (the one to actually analyze)
ls -lt /auto/fwgwork1/pexiang/utopx/verix_test_*.log | head -1
```

In Claude Code sessions, run step 2 with `run_in_background: true` on the Bash tool; the script's internal `tail -150` only flushes when utopx exits, so the log appears idle during the ~8 min run — don't `tail -f` it, wait for the harness's completion notification.

To reproduce a specific seed, modify `~/run_utopx_171.sh:23-26` to append `--seed=<N>` (or invoke utopx directly with the seed flag — see Phase 9 above).

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

