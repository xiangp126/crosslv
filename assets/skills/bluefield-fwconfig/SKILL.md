---
name: bluefield-fwconfig
description: Read and write firmware configuration on any BlueField DPU safely — the mlxconfig traps that make a write look applied when it is not, how to parse `mlxconfig -e q` output correctly, and how to tell whether the ARM side is actually alive. Use for ROUTINE mlxconfig work on a healthy BlueField box - reading or writing NV settings a few at a time, verifying one took effect, checking whether a DPU's ARM has booted, or when a setting reads back wrong after a burn. If the card is already unreachable, or you are planning a bulk write, use skill nic-livefish-recovery instead.
---

# Firmware config on a BlueField DPU

Applies to **any** BlueField box — nothing here is specific to a feature, a PSID or a machine.

## `"Applying... Done!"` does not mean the write landed

Right after a burn, `mlxconfig set` can print `Applying... Done!` while Next Boot stays
unchanged. The read-back is the only evidence — always read Next Boot back before believing a
write:

```bash
mlxconfig -d <dev> -e q <PARAM>        # check the Next Boot column, not the command's exit
```

Write a few parameters at a time — **at most 8 `PARAM=value` pairs in one `mlxconfig set`** — and
never from a file or dump (no `-f`/`--file`, no `$(cat …)` or `` `cat …` `` building the list).
Claude Code's guard hook denies a command that breaks either limit; Codex has no such hook, so check
both yourself. Full rule against bulk-applying a dump: skill `nic-livefish-recovery`.

## Parse `mlxconfig -e q` by field position from the END

Columns are **Default / Current / Next Boot**, but a modified row carries a leading `*` that
shifts every column one to the right — a fixed column index silently reads the wrong value on
exactly the rows you just changed.

```bash
mlxconfig -d <dev> -e q LINK_TYPE_P1 | awk '/LINK_TYPE_P1/ {print $NF}'   # Next Boot
```

Use `$NF` (Next Boot) and `$(NF-1)` (Current). Never `$3`/`$4`.

## Do not use ping to decide whether the ARM is alive

The host's own `tmfifo_net0` is `192.168.100.2`, so pinging `.2` **always succeeds — you are
pinging yourself.** The only valid liveness test is a shell on the ARM:

```bash
ssh root@<arm-ip> 'uname -m'           # must print aarch64
```

`UP_TIME` climbing with a silent console and no `DPU is ready` / `Linux up` means the ARM eMMC has
no OS — it needs a BFB push (~30 min); more waiting will not help.

## One symptom is never a sufficient verdict

A PCI device count can be reached on the **previous holder's leftover NV** while the ports are
still the wrong link type — the feature gate is silently broken although that one check passed.
Enumerate every necessary condition and check them all, not the most convenient one.

## Do not read a bus number before the burn

A gate INI can re-lay the BDF map (one BF-3 moved from bus 83 before the burn to bus 81 after).
Any bus/BDF value collected pre-burn is void — re-read it after the burn.

## Related

- Bulk mlxconfig writes; un-bricking a card that stopped enumerating: skill
  `nic-livefish-recovery`.
- Taking a lab box before any of this: skill `noga-lock`.
