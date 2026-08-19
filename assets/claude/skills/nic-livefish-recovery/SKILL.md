---
name: nic-livefish-recovery
description: Recover a ConnectX/BlueField NIC that vanished from PCI (Livefish flash recovery) fully remotely using relay_controller.py plus IPMI, and restore GUID/MAC, firmware and NV config afterwards. Also carries the hard rule against bulk-applying a whole mlxconfig dump. Use when lspci shows no Mellanox device, /dev/mst is empty, a card is bricked after an mlxconfig write, or when planning any large mlxconfig set.
---

# Un-bricking a NIC that vanished from PCI (Livefish, fully remote)

**Symptom**: `lspci -d 15b3:` returns 0, `/dev/mst` empty, and the PCIe **root port itself** is
gone from `lspci` (BIOS hides a port whose link never trained). Typical cause: an mlxconfig write
the board cannot enumerate under. Neither `mlxfwreset` nor any power cycle recovers this — the
card never gets far enough to answer.

## Use `relay_controller.py`, not `fishme.py`

The Confluence pages (FW/2830883398, SW/2937307643) document `fishme.py`, which needs a
USB-serial controller at `/dev/ttyUSB*` on a separate "livefish host". Most reg boxes have no
such thing and Noga carries no livefish fields for them — **that path dead-ends.** The relay
board is reachable over the network instead.

```bash
# Tool (clone once): ssh://<user>@git-nbu.nvidia.com:12023/hca_fw/hca_system_service
R=hca_system_service/BackEnd/relay_controller.py
LF=<host>-lf                 # plain DNS entry, e.g. l-fwreg-055-lf -> 10.141.203.103
BMC=<host>-ilo               # plain DNS entry too; creds ADMIN/ADMIN
IPMI="ipmitool -I lanplus -H $BMC -U ADMIN -P ADMIN"
```

## STEP 0 — DO NOT SKIP: record GUID and MAC

The recovery burn needs `-ignore_dev_data`, which does **not** write the device-data section:
Base GUID and Base MAC come back as `N/A` and the card is unusable (utopx dies at
`DeviceInfo.cpp:37 "Unknown device"`). Record them for **every** card that will enter recovery —
`-m enable` defaults to `-p all`, so that is all of them.

```bash
for D in /dev/mst/mt*_pciconf[0-9]; do
  echo "== $D"; flint -d $D q full | grep -E '^(Base GUID|Base MAC|PSID)'
done
```

If the card is already dead and you never recorded this: **do NOT invent a GUID** — a made-up
value can collide with another card in the lab. Get the original from lab inventory / VPD.

## The recovery sequence

```bash
python3 $R -s $LF -m status         # 2-port board; both OFF in normal operation
python3 $R -s $LF -m enable         # short the flash-presence pins

# A DC cycle is REQUIRED. A warm `reboot` does not put the card into recovery mode.
$IPMI chassis power off; sleep 60; $IPMI chassis power on
# Back up: lspci shows "ConnectX-9 Flash Recovery"; mst nodes become mt548_pciconf{0,1}

# Pick the image by PSID from the mapping file — never guess from the filename.
B=/mswg/release/BUILDS/fw-<devid>/fw-<devid>-rel-<ver>-build-001/etc/bin
grep <PSID> $B/bin_files_list.csv          # -> PSID,part-number,filename,md5,path

for A in 0x0 0x40000 0x80000; do flint -d /dev/mst/mt548_pciconf0 -ocr e $A; done
flint -d /dev/mst/mt548_pciconf0 -i <bin> -nofs -ignore_dev_data -ocr -y b
# repeat for mt548_pciconf1 — `-m enable` defaults to `-p all`, so BOTH cards enter recovery

python3 $R -s $LF -m disable
$IPMI chassis power off; sleep 60; $IPMI chassis power on
```

## STEP N — the other half of STEP 0

The card enumerates again but GUID/MAC are `N/A`. Write back the recorded values, per card:

```bash
flint -d /dev/mst/mt4133_pciconf0 -y --guid <GUID> --mac <MAC> sg
reboot                                    # or mlxfwreset, to load it
flint -d /dev/mst/mt4133_pciconf0 q full | grep -E '^(Base GUID|Base MAC)'   # verify
```

`Orig Base GUID: N/A` afterwards is expected — the original device data is gone; what matters is
that Base GUID / Base MAC now read the recorded values.

## A recovered card is not yet a usable test environment

Livefish only gets it enumerating. Three things still have to be restored, **in this order**:

1. **GUID/MAC** — step N above.
2. **The FW build the environment actually expects.** Livefish forces a raw `.bin`, so you burn
   whatever official release image matches the PSID. A verification environment usually wants the
   internal build instead (`/mswg/projects/fw/fw_ver/mfa_dir/<ver>/*.mfa2`). The release image
   lacks verification-only commands such as `GET_GVMI`, and utopx then dies at
   `DeviceInfo.cpp:37 "Unknown device"` — `GetDevType()` returns `cmd_get_gvmi.device_id`, which
   is 0 on a release image, so the switch falls through to `default`. **Same version string and
   same PSID on both, so `flint q` cannot tell them apart.** Re-burn with the `.mfa2` once the
   card enumerates normally (that path writes device data properly, unlike `-ignore_dev_data`).
3. **NV config** — erasing the flash returns the board to its factory personality (an `IB_2P`
   board comes back as IB), so re-apply `LINK_TYPE` and friends.

**Burn FW first, set NV config second.** In the other order the new firmware's defaults overwrite
what you just configured.

## Mechanical notes

- Bind one PF back to `mlx5_core` before a normal burn. From a udriver-only state flint warns
  `BME is not set, DMA access is not supported` and the burn takes minutes instead of seconds.
- After recovery the mst nodes go back to `mt4133_pciconf*`, and **the pciconf↔BDF mapping may
  differ from before**. Always re-check with `mst status -v` before configuring or burning.
- The burn rewrites the whole flash, **wiping the NV config with it** — exactly what you want
  when a bad mlxconfig is what broke the card.
- In livefish the device cannot report its PSID, so flint cannot pick an image out of an `.mfa2`
  archive. **A raw `.bin` is mandatory.**
- Run `flint ... -ocr hw query` first: it prints flash type/size and `Flash0.WriteProtected`.
  Only issue `hw set Flash0.WriteProtected=Disabled` if it actually reads enabled.

## The mlxconfig rule this exists to prevent

**Never bulk-transplant a whole mlxconfig dump onto another box.** Diff the two and set only the
handful of parameters that bear on what you are chasing. Replaying a 457-parameter dump from a
reference box in one `mlxconfig set`, followed by a cold boot, took out **three cards in one
day**. (A PreToolUse hook now blocks oversized `mlxconfig set` calls; see
`~/myGit/crosslv/assets/claude/hooks/guard.py`.)

Be honest about what is and is not known here:

- The two boards were **identical** (`900-9X91E-00EB-ST0_IB_2P_CORE_INT_DK_Ax`, same PSID), so
  this was *not* an SKU mismatch — an earlier write-up of this incident claimed it was, wrongly.
- The dump contained only 2 read-only parameters and neither was written, so that is not it.
- **The actual mechanism was never established.** One untested theory is that a single `set`
  transaction that large leaves the NV section inconsistent. Nobody should brick a fourth card
  to find out.

The empirical rule: apply a few parameters at a time, read back Next Boot after each, and verify
Current after the cold boot. Treat anything that re-lays the PCI/BAR map with extra care —
`PF_LOG_BAR_SIZE`, `NUM_PF_MSIX` / `NUM_VF_MSIX`, `MEMIC_BAR_SIZE`, `PF_BAR2_*`,
`PCI_SWITCH_EMULATION_*`, `*_EMULATION_ENABLE`.

**Stop at the first anomaly.** After one cold boot the card was still present but its FW had
reverted and `LINK_TYPE` had moved **in the Default column** — a Default can only change if the
running FW changed, i.e. the device was already unwell. Reading that as "the config didn't take"
and pushing another burn + cold boot is what finished it off.

## Related

- More mlxconfig read-back traps: skill `satpf-171`.
- Taking / releasing the box: skill `noga-lock`.
