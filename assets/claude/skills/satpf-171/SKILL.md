---
name: satpf-171
description: Rebuild and verify the satellite-PF (sat-PF) test environment on the BlueField-3 box l-fwreg-171 (PSID MT_0000000998) after mars_reg hands it back re-burned, and pick an alternative box from the 998 pool. Also carries BlueField firmware-config read-back traps. Use when working on sat-PF / OCI_EMU, running tests on l-fwreg-171, checking VIRTIO_NET_EMULATION or PF_NUM_SAT_PF, or looking for a machine with PSID MT_0000000998.
---

# Rebuilding the sat-PF test env on l-fwreg-171

`l-fwreg-171` (BF-3, PSID `MT_0000000998`) is currently the only turnkey box for this feature.

`mars_reg` always hands the box back **re-burned** (typically FW `32.50.xxxx`, `LINK_TYPE=IB`,
an odd `bus81` count), so rebuild **unconditionally** after taking the lock:

```bash
bash /auto/fwgwork1/pexiang/bugZilla/OCI_EMU/tools/env_rebuild_171.sh
# parameterised for other 998 boxes:
# HOST=<box> ARM_IP=<arm ip> EMU_BUS=<bus> bash env_rebuild_171.sh
```

It burns the FUR `.mlx` + the 998 gate INI, writes the x86 NV set, sets `PF_NUM_SAT_PF=1` on both
ARM ECPFs, and power-cycles (~10–15 min).

## Then verify independently — do not trust the script's summary

| Check | Expected |
|---|---|
| `flint -d /dev/mst/mt41692_pciconf0 q` | FW `32.48.6007` |
| `mlxconfig -e q LINK_TYPE_P1 LINK_TYPE_P2` | `current=ETH(2) next=ETH(2)` on both |
| `mlxconfig -e q VIRTIO_NET_EMULATION_NUM_PF` | `current=3 next=3` |
| `lspci \| grep -c '^81:'` | **8** = 2 CX7 + 2 NVMe SNAP + 3 virtio-net + 1 SoC-mgmt |

ARM `PF_NUM_SAT_PF` normally reads back as unreadable — the DOCA sshd does not come up once
sat-PF materializes. Known and non-blocking; `bus81=8` together with ETH links is the proof.

## Running a test

```bash
ssh root@l-fwreg-171 'bash /auto/fwgwork1/pexiang/bugZilla/OCI_EMU/tools/per_run_reset.sh \
    -U <utopx repo> --seed 3975318385 --iter 300'
```

It gates on FW `32.48.6007` (`--fw` / `--any-fw` to override) and on `bus81=8`, refusing to
launch off-baseline rather than producing junk results.

## Firmware-config traps worth carrying to any BlueField box

- **`mlxconfig "Applying... Done!"` does not mean the write landed.** Right after a burn the NV
  set can report Done while next-boot stays unchanged. **Always read next-boot back.**
- **In `mlxconfig -e q` output the columns are Default / Current / Next Boot, and a leading `*`
  on modified rows shifts them.** Index with `$NF`, never a fixed column number.
- **One symptom is rarely a sufficient verdict.** A `bus81=8` count can be reached on the
  previous holder's leftover NV while the ports are still IB, silently breaking the sat-PF gate.
  Check every necessary condition, not the most convenient one.
- **Do not use ping to decide whether a BlueField ARM is alive.** The host's own `tmfifo_net0` is
  `192.168.100.2`, so pinging `.2` always succeeds — you are pinging yourself. The only valid
  test is `ssh root@<ip> 'uname -m'` returning `aarch64` (171's ARM is `.1`).
- **Do not read the emulation bus number before the burn.** The 998 INI re-lays the BDF map: one
  box had its BF-3 on bus 83 beforehand and on bus 81 afterwards.

## Machine pool for this PSID

```bash
/mswg/projects/fw/fw_ver/hca_fw_tools/noga_allocation/get_setups_info.py \
    --team_name hca_fw --where "psid MT_0000000998"
```

26 boxes, but effectively only 171 is usable:

- **171** — Ubuntu 20.04, ARM eMMC carries DOCA. The only turnkey box, hence the daily
  contention.
- **183** — the only box where satellite PFs actually materialize (ARM `00:00.2/.3`), but it runs
  RHEL 7.4 (glibc 2.17) and **cannot execute utopx** (the binary needs glibc ≥2.29 /
  GLIBCXX_3.4.26 and only a `ubuntu/20.04` build exists). **Reference box only.** Its tmfifo is
  mirrored (ARM=`.2`), PCI lands on bus 83, and its ARM `/dev/mst` nodes are stale — address its
  ECPFs as `mlxconfig -d pciconf-00:00.0`.
- **147 / 149 / 178 / 179 / 180** — Ubuntu, so utopx would run, but their ARM eMMC has no OS
  (`UP_TIME` climbs with no `DPU is ready` / `Linux up`, console silent). That is why they sit
  idle. Enabling one costs a BFB push (~30 min; `tools/bf_171.cfg` is a working config).
- The `VirtIO` partition is tagged `INCOMPATIBLE_UTOPX` — skip it.

## Related

- Taking the lock / waiting for `mars_reg` to release: skill `noga-lock`.
- If the card stops enumerating after a config write: skill `nic-livefish-recovery`.
