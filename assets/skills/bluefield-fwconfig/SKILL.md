---
name: bluefield-fwconfig
description: Read and write firmware configuration on any BlueField DPU safely — the mlxconfig traps that make a write look applied when it is not, how to parse `mlxconfig -e q` output correctly, and how to tell whether the ARM side is actually alive. Use for ROUTINE mlxconfig work on a healthy BlueField box - reading or writing NV settings a few at a time, verifying one took effect, checking whether a DPU's ARM has booted, or when a setting reads back wrong after a burn. If the card is already unreachable, or you are planning a bulk write, use skill nic-livefish-recovery instead.
---

# Firmware config on a BlueField DPU

These apply to **any** BlueField box. None of them is specific to a feature, a PSID or a machine.

## `"Applying... Done!"` does not mean the write landed

Right after a burn, an `mlxconfig set` can print `Applying... Done!` while next-boot stays
unchanged. **Always read next-boot back** before believing a write:

```bash
mlxconfig -d <dev> -e q <PARAM>        # check the Next Boot column, not the command's exit
```

Treat the read-back as the only evidence. This is the same discipline as the hard rule against
bulk-applying an mlxconfig dump — see skill `nic-livefish-recovery`.

## Parse `mlxconfig -e q` by field position from the END

The columns are **Default / Current / Next Boot**, but a modified row carries a leading `*`,
which shifts every column one to the right. Indexing by a fixed column number silently reads the
wrong value on exactly the rows you care about — the ones you just changed.

```bash
mlxconfig -d <dev> -e q LINK_TYPE_P1 | awk '/LINK_TYPE_P1/ {print $NF}'   # Next Boot
```

Use `$NF` (and `$(NF-1)` for Current). Never `$3`/`$4`.

## Do not use ping to decide whether the ARM is alive

The host's own `tmfifo_net0` is `192.168.100.2`, so pinging `.2` **always succeeds — you are
pinging yourself.** The only valid liveness test is a shell on the ARM:

```bash
ssh root@<arm-ip> 'uname -m'           # must print aarch64
```

`UP_TIME` climbing with a silent console and no `DPU is ready` / `Linux up` means the ARM eMMC
has no OS — a BFB push is needed (~30 min), not more waiting.

## One symptom is never a sufficient verdict

A PCI device count can be reached on the **previous holder's leftover NV** while the ports are
still the wrong link type, so the feature gate is silently broken even though your one check
passed. Enumerate every necessary condition and check them all, not the most convenient one.

## Do not read a bus number before the burn

A gate INI can re-lay the BDF map: the same box had its BF-3 on bus 83 before the burn and bus 81
after. Any bus/BDF value collected pre-burn is void — re-read it afterwards.

## Related

- Bulk mlxconfig writes and un-bricking a card that stopped enumerating: skill
  `nic-livefish-recovery`.
- Taking a lab box before any of this: skill `noga-lock`.
