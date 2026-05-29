# Today's flow — reproducing the Mustang DPA + ARM-agent regression on l-fwreg-171

Chronological record of what was done across 2026-05-28 and 2026-05-29 to take a failing `utopx scenario_dpa_emu` run from "fails on dev box at `resource2_wc` open" all the way to a clean **PASS** on l-fwreg-171. Includes the recipe for repeat runs, the failure modes we hit along the way, and how to recover from each.

This is not a how-to guide — it's the log of what happened, with the diagnostic dead-ends included.

---

## Phase 0 — Starting point

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

The web view needs auth, but the **`results_dir` path is an NFS share** mounted on every dev box. So instead of fetching via the web, just read the same files directly:

```bash
ls /auto/sw_regression/host_fw/HCA_CORE_FWV/MARS/conf/results/MUSTANG_FW-l-fwreg-171_eth_ARM_AGENT_P1/11047756/
# 11047756.tgz
```

Every MARS session's full logs are packed in one `<sid>.tgz` under that path. The directory layout inside the tarball follows MARS's step-numbering scheme (e.g. `1.26.1.1`, `0.22.1.1.1.8.1.7.1.8.1` — each level is a sub-step). Inside each step dir there's a `log.txt` (human output) and a `<step_name>.cap` (the XML that defines the step).

### Step 1A: find the two steps that hold the version info

Two MARS steps capture the exact versions used in a session:

1. **`new_burn_fw`** — the FW burn step. The log shows what `.mlx`, `.ini`, FW version, and PSID were burned.
2. **`get_last_commit`** — runs before the build/install of utopx in regression. It calls a helper that does `git describe` inside the utopx checkout in the MARS workspace and prints the commit hash.

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

The **`new_ini_file`** path is the *actual* file BurnFw.py generated and passed to `mlxburn`. That's the one you want to copy locally — it has all the regression-injected overrides baked in.

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
- **utopx git short SHA**: `07de3b4`
- **branch**: `master_rc` (from the tag stem `..._branch_master`)
- **utopx DB name**: `HCA_CORE_FW-utopx_carveout_master_rc.db` — also useful if you want to find the same regression suite for a different setup later

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

Checked current state of both repos under `/auto/fwgwork1/pexiang/`:

```bash
cd /auto/fwgwork1/pexiang/utopx
git log -1 --format='%H %h %ci %s'
# 07de3b4319491c961586206c1a6ece0967c37e7f 07de3b431 2026-05-27 ... — already at target ✓
```

```bash
cd /auto/fwgwork1/pexiang/golan_fw
git status
# HEAD detached at rel-12_25_0222    ← wrong (12.25.0222 from 2019)
# Changes not staged: shared/algorithm modified
git rev-parse 1bd3640336   # confirmed the target commit exists in this repo
# 1bd364033669a37a34acefc32b559a6e9b60d935
```

To fix golan_fw — stash local change to `shared/algorithm`, checkout target commit:

```bash
cd /auto/fwgwork1/pexiang/golan_fw
git stash push -u -m "auto-stash before checkout to 1bd3640336 (Mustang regression match)"
git checkout 1bd3640336
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

These are what make BAR2 visible on the rshim function — exactly what the dev-box run was missing. The rest of the diff is whitespace normalization (the default INI has comments and `=`-without-spaces; the burned one has comments stripped and `= ` formatting).

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

Notes on the value choices (all match Jerry's email exactly):

| Section | Key values |
|---|---|
| NVMe | vendor=`0x15b3` (NVIDIA), device=`0x6001`, 2 PFs enabled |
| virtio-net | vendor=`0x1af4` (Red Hat / virtio), device=`0x1041` (virtio-net PCI), class=`0x028000` (Ethernet), 0 PFs at boot (added dynamically), max 16 PFs / 255 VFs |
| virtio-blk | vendor=`0x1af4`, device=`0x1042` (virtio-blk PCI), class=`0x010800` (NVMe / Mass Storage), 0 PFs at boot, max 16 PFs / 255 VFs |
| virtio-fs | vendor=`0x1af4`, device=`0x105a` (virtio-fs PCI), class=`0x010800`, 0 PFs at boot, max 16 PFs / 255 VFs |

### 3d — Final state of the burned INI

```
File:    /auto/fwgwork1/pexiang/utopx/regression_ini/burned_session_11047756_v32_50_0222_psid_MT_0000000998.ini
Before:  670 lines, sections [image_info], [mfg_info], [device_info], [boot_record],
                    [fw_boot_config] (lines 34-64), [fw_main_config] (lines 66+),
                    [hw_boot_config], [hw_main_config]
After:   714 lines (added 44 in [fw_boot_config] tail)

Verify:
  grep -cE "emulation_nvme|emulation_virtio_(net|blk|fs)" <file>       → 36
  grep -n "^\[" <file>                                                  → sections unchanged, indices shifted:
    [image_info]      line 1   (unchanged)
    [mfg_info]        line 7
    [device_info]     line 11
    [boot_record]     line 15
    [fw_boot_config]  line 34
    [fw_main_config]  line 110  (was line 66 — 44 lines moved by insertion)
    [hw_boot_config]  line 146
    [hw_main_config]  line 610
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

Then `--fw-reset` also failed:

```
Running old fwreset script
chip:  not supported...
Error: fwresetm failed
```

Two distinct problems to peel off.

## Phase 5 — Burn the official .mlx + custom INI via jmake, no rebuild

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

Out of the box `jk --fw-reset` does **not** work on BF-3/CX-8/CX-9 — required two patches to `~/myGit/crosslv/nv-tools/jmake` (see *Files modified* at the bottom).

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

## Phase 9 — Bring up udriver and run utopx

After the FW is pivoted and host is in a clean state, the bring-up is just two steps:

```bash
ssh l-fwreg-171
sudo modprobe udriver
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
# 83:00.4: Kernel driver in use: vfio-pci    ← rshim, intentionally not udriver
```

Now run utopx:

```bash
cd /auto/fwgwork1/pexiang/utopx
sudo ./utopx --device=/dev/mst/mt41692_pciconf0 --daemon --num_of_clients=0 \
             --xml_conf_file conf.xml --conf_file config/scenario_dpa_emu.conf \
             --iter=300 --ops_per_it=30
```

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

### Don't run utopx back-to-back without a clean reset

We saw three different failure modes across repeat runs of the same command:

| Run | Seed | Outcome | Cause |
|---|---|---|---|
| 1 | 3969039850 | ✅ PASSED 300 iters | clean state |
| 2 | 444217356 | ❌ `Gen() outside phase` at iter 138 | leftover state + seed race |
| 3 | 1000726046 | ❌ `Virtio device_status 0xf` at init | virtio device left in `DRIVER_OK` state from prior run |
| 4 | (after stuck `[utopx.exe]` zombie) | ❌ wedged setup | un-killable D-state zombie holding kernel resources |
| 5 | 3435089955 (after a passing run) | ❌ `Virtio device_status 0xf` at init | same — utopx leaves virtio emu in `DRIVER_OK` |

Lessons:
- The virtio emulated devices retain state between utopx runs. The MARS regression flow runs `fw_reset + modprobe_udriver` before **every** utopx test for exactly this reason.
- A D-state utopx zombie (uninterruptible-sleep on device I/O) cannot be cleared by `kill -9`. Only `jk --power-cycle` reliably clears it.

## Reset spectrum between utopx runs (lightest → heaviest)

| Method | Resets virtio state? | Time | When to use |
|---|---|---|---|
| `modprobe -r udriver && modprobe udriver` | ❌ no | <1s | Driver-binding cleanup only. Won't fix `Virtio device_status 0xf`. |
| **`jk --fw-reset`** (our patched jmake) | ✅ **yes** | ~20s | **Default between-runs reset.** Routes through `fwreset.py`, acquires `/tmp/udriver_lockfile.lock`, knows about udriver, does a chip-level reset that clears emulated-device state. |
| `sudo mlxfwreset -d ... -y r` | depends | ~20s | The underlying MFT tool. Works when `mlx5_core` is bound; on BF-3 with only `udriver`, tool-owner sync is "not supported" and it may fail. Prefer `jk --fw-reset` instead. |
| `mustang_fw_reset.sh --next_driver udriver` (no `--remove_rescan`) | ✅ yes | ~30s | Heavier; explicit re-bind of all functions. |
| `mustang_fw_reset.sh --remove_rescan` | ✅ yes when works | ⚠️ | **DANGEROUS** — hangs in `wait_woken` on PCIe parent bridge remove. Only recovery is power cycle. Avoid. |
| `jk --power-cycle l-fwreg-171` | ✅ always | ~3 min | Last resort. Always works. Use only when the lighter resets fail (D-state zombies, `rev ff` lspci). |

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

# === Before each utopx run (after the first) ===
# This clears virtio device state left by the previous run:
sudo /labhome/pexiang/.usr/bin/jmake --device /dev/mst/mt41692_pciconf0 --fw-reset

# (Only if jk --fw-reset itself fails, e.g. D-state zombies / rev:ff lspci):
exit
/labhome/pexiang/.usr/bin/jmake --power-cycle l-fwreg-171   # ~3 min
ssh l-fwreg-171
sudo modprobe udriver

# === Run utopx ===
cd /auto/fwgwork1/pexiang/utopx
sudo ./utopx --device=/dev/mst/mt41692_pciconf0 --daemon --num_of_clients=0 \
             --xml_conf_file conf.xml --conf_file config/scenario_dpa_emu.conf \
             --iter=300 --ops_per_it=30
```

## Key learnings

- **INI overrides matter most**: `internal_use.eliminate_pcie_switch_hier=0x1`, `ddr_mapping_en=0x1`, `ddr_log_2_bar_size=0x22` are what expose BAR2 on the CM-shared-memory function (`83:01.5`). Without these, ArmAgent BareMetal can't mmap shared memory. **These come from the regression's burned INI, not the release default INI** — must merge.
- **`modprobe udriver` is the right binding step** post-burn / post-reset. The kernel auto-binds udriver to every PCI function whose device ID matches its supported table (41692 for NIC, 24577 for emulated NVMe controllers, 4161 for virtio-net). No script needed.
- **`jk --fw-reset` is the right between-runs reset** on BF-3 with udriver bound — it clears virtio device state via `fwreset.py`'s chip reset, while handling udriver lockfile coordination. Takes ~20s, no power cycle needed.
- **`jk --fw-reset` ≠ `mlxfwreset`** — `mlxfwreset` is the underlying MFT tool; `jk --fw-reset` wraps it with udriver-aware locking and orchestration. Bare `mlxfwreset` on BF-3 with udriver-only binding may fail "Tool is owner: Not supported".
- **`mustang_fw_reset.sh --remove_rescan` is dangerous** — triggers a `wait_woken` hang on the PCIe parent bridge that requires power-cycle to recover. Avoid in interactive use.
- **State leak between back-to-back utopx runs** is real and well-defined: virtio emulated devices retain `DRIVER_OK` state. Resolution: `jk --fw-reset` between every run (same pattern MARS regression uses).
- **Different seeds = different bugs**. utopx is stochastic. A pass with one seed doesn't guarantee a pass with the next. For repeatability, pin `-s <seed>`.

---

## Status as of 2026-05-29

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

## Files modified by this work

| File | Change |
|---|---|
| `~/myGit/crosslv/nv-tools/jmake` | Bug A: pass `--run_new_fwreset` for chips `m`/`gl`/`ar` in `runFWReset`. Bug B: replaced `sourceFwvAlias()` with a doc-only stub; added conditional inline source in `main()`; removed five `sourceFwvAlias` calls from `runRegQuery`/`runRegMalloc`/`runRegMine`/`runRegIdle`/`runRegCancel`. |
| `/auto/fwgwork1/pexiang/utopx/regression_ini/burned_session_11047756_v32_50_0222_psid_MT_0000000998.ini` | Appended Jerry's 36 emulation flags to `[fw_boot_config]`. |
| `/auto/fwgwork1/pexiang/utopx/regression_ini/default_900-9D3B6-00CV-AAB_Ax.ini` | Copy of the regression's release default INI (unmodified). |
| `/auto/fwgwork1/pexiang/golan_fw` | `git stash` of `shared/algorithm` local mod, then `git checkout 1bd364033669` (Mustang regression match). |

## Related context

- Feature wiki: "MTBC-+4690480+OCI+BF-4+virtio-net+needs+emulation+capabilities..." (Confluence)
- Redmine tickets: [#4650230](https://redmine.mellanox.com/issues/4650230), [#4690480](https://redmine.mellanox.com/issues/4690480), [#4690593](https://redmine.mellanox.com/issues/4690593)
- Argaman P2 setups (already have the 36 flags in `mars_extra_burn_params/master_rc`):
  - `/auto/mswg/projects/fw/fw_ver/MARS_HCA_CORE/MARS_conf/setups/ARGAMAN_FW-l-fwreg-225_P2/`
  - `/auto/mswg/projects/fw/fw_ver/MARS_HCA_CORE/MARS_conf/setups/ARGAMAN_FW-l-fwreg-226_eth_P2/`
- MARS results root for Mustang regression:
  `/auto/sw_regression/host_fw/HCA_CORE_FWV/MARS/conf/results/MUSTANG_FW-l-fwreg-171_eth_ARM_AGENT_P1/`
