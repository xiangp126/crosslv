---
name: nic-livefish-recovery
description: Recover a ConnectX/BlueField NIC that vanished from PCI (Livefish flash recovery) fully remotely using relay_controller.py plus IPMI, and restore GUID/MAC, firmware and NV config afterwards. Also carries the hard rule against bulk-applying a whole mlxconfig dump. Use when the card is already LOST or at risk - lspci shows no Mellanox device, /dev/mst is empty, a card is bricked after an mlxconfig write, or you are about to apply a bulk mlxconfig set. For ordinary per-parameter mlxconfig on a healthy BlueField, use skill bluefield-fwconfig.
---

# Un-bricking a NIC that vanished from PCI (Livefish, fully remote)

**Symptom**: `lspci -d 15b3:` returns 0, `/dev/mst` is empty, and the PCIe **root port itself** is
gone from `lspci` (BIOS hides a port whose link never trained). Typical cause: an mlxconfig write
the board cannot enumerate under. Neither `mlxfwreset` nor any power cycle recovers this — the
card never gets far enough to answer.

## Use `relay_controller.py`, not `fishme.py`

The Confluence pages (FW/2830883398, SW/2937307643) document `fishme.py`, which needs a USB-serial
controller at `/dev/ttyUSB*` on a separate "livefish host". Most reg boxes have no such thing and
Noga carries no livefish fields for them — **that path dead-ends.** The relay board is reachable
over the network instead:

```bash
# Tool (clone once): ssh://<user>@git-nbu.nvidia.com:12023/hca_fw/hca_system_service
R=hca_system_service/BackEnd/relay_controller.py
LF=<host>-lf                 # plain DNS entry, e.g. l-fwreg-055-lf -> 10.141.203.103
BMC=<host>-ilo               # plain DNS entry too; creds ADMIN/ADMIN
IPMI="ipmitool -I lanplus -H $BMC -U ADMIN -P ADMIN"
```

## STEP 0 — DO NOT SKIP: record GUID and MAC

The recovery burn needs `-ignore_dev_data`, which does **not** write the device-data section: Base
GUID and Base MAC come back as `N/A` and the card is unusable (utopx dies at
`DeviceInfo.cpp:37 "Unknown device"`). Record them for **every** card that will enter recovery —
`-m enable` defaults to `-p all`, so that is all of them:

```bash
for D in /dev/mst/mt*_pciconf[0-9]; do
  echo "== $D"; flint -d $D q full | grep -E '^(Base GUID|Base MAC|PSID)'
done
```

Card already dead and nothing recorded: **do NOT invent a GUID** — a made-up value can collide
with another card in the lab. Get the original from lab inventory / VPD.

## The recovery sequence

Image: in livefish the device cannot report its PSID, so flint cannot pick an image out of an
`.mfa2` archive — **a raw `.bin` is mandatory**. Pick it by PSID from the mapping file, never by
guessing from the filename. Before erasing, run `flint ... -ocr hw query`: it prints flash
type/size and `Flash0.WriteProtected`; issue `hw set Flash0.WriteProtected=Disabled` only if it
actually reads enabled.

```bash
python3 $R -s $LF -m status         # 2-port board; both OFF in normal operation
python3 $R -s $LF -m enable         # short the flash-presence pins

# A DC cycle is REQUIRED. A warm `reboot` does not put the card into recovery mode.
$IPMI chassis power off; sleep 60; $IPMI chassis power on
# Back up: lspci shows "ConnectX-9 Flash Recovery"; mst nodes become mt548_pciconf{0,1}

B=/mswg/release/BUILDS/fw-<devid>/fw-<devid>-rel-<ver>-build-001/etc/bin
grep <PSID> $B/bin_files_list.csv          # -> PSID,part-number,filename,md5,path

for A in 0x0 0x40000 0x80000; do flint -d /dev/mst/mt548_pciconf0 -ocr e $A; done
flint -d /dev/mst/mt548_pciconf0 -i <bin> -nofs -ignore_dev_data -ocr -y b
# repeat for mt548_pciconf1 — `-m enable` defaults to `-p all`, so BOTH cards enter recovery

python3 $R -s $LF -m disable
$IPMI chassis power off; sleep 60; $IPMI chassis power on
```

The burn rewrites the whole flash, **wiping the NV config with it** — exactly what you want when a
bad mlxconfig is what broke the card.

## STEP N — the other half of STEP 0

The card enumerates again but GUID/MAC are `N/A`. The mst nodes go back to `mt4133_pciconf*`, and
**the pciconf↔BDF mapping may differ from before** — re-check with `mst status -v` before
configuring or burning anything. Write back the recorded values, per card:

```bash
flint -d /dev/mst/mt4133_pciconf0 -y --guid <GUID> --mac <MAC> sg
reboot                                    # or mlxfwreset, to load it
flint -d /dev/mst/mt4133_pciconf0 q full | grep -E '^(Base GUID|Base MAC)'   # verify
```

`Orig Base GUID: N/A` afterwards is expected — the original device data is gone; what matters is
that Base GUID / Base MAC now read the recorded values.

## A recovered card is not yet a usable test environment

Livefish only gets it enumerating. Restore three things, **in this order**:

1. **GUID/MAC** — STEP N.
2. **The FW build the environment actually expects.** Livefish forces a raw `.bin`, i.e. the
   official release image matching the PSID; a verification environment usually wants the internal
   build (`/mswg/projects/fw/fw_ver/mfa_dir/<ver>/*.mfa2`). The release image lacks
   verification-only commands such as `GET_GVMI`, so utopx dies at
   `DeviceInfo.cpp:37 "Unknown device"` (same signature as missing GUID/MAC): `GetDevType()`
   returns `cmd_get_gvmi.device_id`, which is 0 on a release image, so the switch falls through to
   `default`. **Same version string and same PSID on both — `flint q` cannot tell them apart.**
   Re-burn with the `.mfa2` once the card enumerates normally (that path writes device data
   properly, unlike `-ignore_dev_data`).
3. **NV config** — erasing the flash returns the board to its factory personality (an `IB_2P`
   board comes back as IB): re-apply `LINK_TYPE` and friends, under the rule below.

**Burn FW first, set NV config second** — in the other order the new firmware's defaults overwrite
what you just configured.

Before a normal burn, bind one PF back to `mlx5_core`: from a udriver-only state flint warns
`BME is not set, DMA access is not supported` and the burn takes minutes instead of seconds.

## The mlxconfig rule: never bulk-apply a dump

**Never bulk-transplant a whole mlxconfig dump onto another box.** Diff the two and set only the
handful of parameters that bear on what you are chasing.

- **At most 8 `PARAM=value` pairs in one `mlxconfig set`** — fewer is better. Apply a few
  parameters at a time, read back Next Boot after each, and verify Current after the cold boot.
- **Never feed `set` or `apply` from a file or dump**: no `-f`/`--file`, and no `$(cat …)` or
  `` `cat …` `` building the parameter list.
- Treat anything that re-lays the PCI/BAR map with extra care — `PF_LOG_BAR_SIZE`,
  `NUM_PF_MSIX` / `NUM_VF_MSIX`, `MEMIC_BAR_SIZE`, `PF_BAR2_*`, `PCI_SWITCH_EMULATION_*`,
  `*_EMULATION_ENABLE`.
- **Stop at the first anomaly.** If after a cold boot the card is present but its FW has reverted,
  or a value (e.g. `LINK_TYPE`) moved **in the Default column**, the device is already unwell — a
  Default can only change if the running FW changed. Do not read it as "the config didn't take"
  and push another burn + cold boot; that is what finishes a card off.
- Enforcement: in Claude Code the PreToolUse hook `~/myGit/crosslv/assets/claude/hooks/guard.py`
  denies any `mlxconfig ... set`/`apply` command carrying more than 8 `PARAM=value` pairs,
  `-f`/`--file`, or a `$(cat …)`/`` `cat …` `` substitution. Codex has no such hook: check both
  limits yourself before constructing any `mlxconfig set` command.

An identical board and PSID on both sides does not make a bulk transplant safe, and skipping the
read-only parameters does not either. The failure mechanism is unknown; do not experiment with it.

## Related

- More mlxconfig read-back traps: skill `bluefield-fwconfig`.
- Taking / releasing the box: skill `noga-lock`.
