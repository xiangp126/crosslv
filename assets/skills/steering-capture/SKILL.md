---
name: steering-capture
description: >-
  Capture STE and steering-chain state from a LIVE utopx run: freeze the test at its failure with
  --wait_on_err, dump one steering entry with stedmp.sh, or capture the whole chain a packet
  traverses with steering_basic_debug.sh --hwtrace. Use when asked to dump an STE, capture or walk
  a steering chain, get an hwtrace, find which entry dropped a packet, pause or resume a utopx run
  for inspection, or when a steering dump comes back as zeros/garbage because the test had already
  exited, or when you have a dump/trace in hand and need to read it correctly (tag/mask
  unions, match polarity, hash-resolved next hops, index spaces).
---

# Capturing steering state from a live utopx run

**Everything here needs the test still running.** STE tables live inside utopx's VHCA/steering
resources — once the process exits you get zeros or nonsense (observed: `gvmi=0x545f`,
`my_lu_type=0x57 N_A`), which reads like a broken tool rather than an empty table.

So the order is always: **freeze first (§1), then capture (§2 or §3)**.

## 1. Freeze the run

Two mechanisms, different purposes.

### 1a. `--wait_on_err` — freeze at the failure. Use this for forensics.

```bash
tail -f /dev/null | sudo ./utopx.exe --device=$D ... --wait_on_err &
until grep -qa 'press any key to continue' utopx.log; do sleep 1; done
```

- The flag is **`--wait_on_err`**, not `--wait_on_error`.
- Why it leaves the resources alive: `UtopxFatalHandler::exit_utopx` calls `getchar()` when
  `TestConfigs->wait_on_err` is set, and it does that **before** `LimitedHostCleanUp` /
  `CloseUdriver`. Every VHCA and every STE is still intact while it blocks — that is exactly what
  makes the dump possible.
- **Headless runs must hold stdin open** (the `tail -f /dev/null |` above). Otherwise `getchar()`
  gets EOF, sails straight past the pause, and the process tears itself down before you can
  attach.
- Resume: send it a character on stdin.

### 1b. `--wait_cycle <iter.cycle[.precondOp]>` — freeze at a chosen point. Needs a terminal.

- `CheckWaitCycle` stops the VHCA threads and then blocks on a **menu keypress**, so it needs an
  attended terminal.
- It does not substitute for §1a in an unattended run: two headless attempts (`0.90`, `0.10`)
  never reached the pause point — utopx hit its own FATAL first.
- Its other use: **on a segfault the dump is not written automatically.** Rerun with
  `--wait_cycle <cycle>` and press `d` at the pause to write `/tmp/utopx_dump_<pid>/` by hand.

**Rule of thumb:** forensics → always §1a. Use §1b only to stop at a specific iteration with
someone at the keyboard, or to force a dump after a segfault.

## 2. Dump one steering entry

Two tools, same target, different strengths. Both live under
`/mswg/projects/fw/fw_ver/hca_fw_tools/`.

### `stedmp.sh` — quick look at one entry

```bash
sudo bash /mswg/projects/fw/fw_ver/hca_fw_tools/stedmp.sh -d $D -g <gvmi> --full -i <ste_ix>
```

Gives `hit_ix` / `miss_ix` with symbolic names, plus `entry_type` and `my_lu_type`, so you can
step to the next entry by hand.

🔴 **It prints only non-zero fields.** A field with `bit_mask != 0` and no printed `tag_data` line
means **"must equal 0"**, not "unconstrained" — and the text dump shows you nothing at all. When
that distinction matters, use `ste_dump.py` below, and never parse this pretty-printed output in a
script.

### `ste_dump.py` — the `SteInfoFetcher` CLI: full attributes, offline, remote

```bash
python /mswg/projects/fw/fw_ver/hca_fw_tools/steering/ste_dump.py \
       -d /dev/mst/mt4131_pciconf0 -g 0x0 -i 0xf
```

It has **no execute bit** (`-rw-r--r--`) — call it through `python`, not as a command. It wraps
the importable `SteInfoFetcher` and prints `ste.dumpToString()`, i.e. the full attribute set
including zero-valued fields, which is exactly what `stedmp.sh` hides.

Three modes beyond the plain query:

| Flag | What it buys |
|---|---|
| `--raw "0x… 0x…"` / `--raw -` / `--raw-file F` | **Parse dwords with no device at all** (`SteInfoFetcher.parseRawSte`). Requires `-a <adb>`. Accepts 16-dword payload, 20-dword with segment header, or raw `resourcedump` text — the Segment Type/Size/Data lines are ignored. **This is the offline entry point for hwtrace dwords (§3).** |
| `--host H --user U --password P` | Runs only the `resourcedump` CLI on a remote box; parsing stays local. Useful when the card is on another machine. |
| `-a <adb>` · `-dict <file>` | ADB defaults to the FW dir; the symbol dictionary defaults to `./steering_dictionary.txt` — pass it explicitly when running outside the tools dir. |

If it answers `STE not found or dump failed for the given index/gvmi`, the index/gvmi is wrong
**or the test already exited** (§1) — the entry is not "empty", it is gone.

## 3. Capture the whole chain — hwtrace

```bash
sudo /mswg/projects/fw/fw_ver/hca_fw_tools/steering_basic_debug.sh -d $D -o /tmp/ --hwtrace
sudo /tmp/phwtrace.runme --experimental        # writes /tmp/phwtrace.log
```

**Do not add `--fsdump` on ConnectX-8.** It shells out to `mlxdump ... fsdump`, which answers
`-E- Device not supported by this command`, and that failure makes the whole invocation look
broken. `--hwtrace` on its own works.

Why this beats `stedmp.sh` when you can afford it:

| | `stedmp.sh` | hwtrace |
|---|---|---|
| Scope | one entry per invocation | **the whole chain a packet traversed** |
| Authority | what the table says now | **ground truth — the path actually taken** |
| Reproducibility | — | prints a reproduce-command for every hop |
| Offline reuse | — | carries **16 raw dwords per hop** — feed them straight to `ste_dump.py --raw` (§2), no device needed |

That last row is the important one: **capture once, then work offline indefinitely.** A trace plus
a packet is enough to re-derive hit/miss and the next hop without the card, utopx, or sudo:

```bash
python .../steering/ste_dump.py -a <adb> --raw "<the 16 dwords of one hop>"
```

## 4. Reading what you captured — five traps

Capturing is the easy half. These five are what make a correct dump read wrong.

1. **`hit_ix` into a table is only the table base** — the real next hop is one of
   `2^next_log_size` entries — **but it is resolvable in software.** `next.hash_type` tells you
   how: LINEAR is no hash at all, just selected bits assembled LSB-first (bit tables in
   `hal_static_configuration.c` `CONFIG_LINEAR_HASH`); REGULAR is a real hash, but insert and
   lookup share it, so the slot whose stored tag *non-vacuously* matches the packet is where it
   lands (scan the table; empty-mask slots match vacuously and mean nothing). The MISS target
   (`miss.miss_address`) is a direct pointer — always exact, never scaled by `next_log_size`.
2. **The 128-bit tag/mask is a union over every field group.** `tag_data.ethl2_des.*`,
   `tag_data.ibl2.*`, `tag_data.source_gvmi_qp.*` are all present at once — different readings of
   the same bits. Only the group selected by `my_lu_type` applies (`getNextMatchDefiner()` instead
   when `byte_mask_mode` is set). Copy the mapping from `SteInfoFetcher.tagFields()`.
3. **`miss.match_polarity=1` inverts the verdict**: `hit = match XOR polarity`. It is not "always
   miss" — a polarity entry whose fields matched goes to *miss*, and one whose fields did not goes
   to *hit*.
4. **"Printing only non-zero fields" hides real constraints.** A field with `bit_mask != 0` and no
   printed `tag_data` line means **"must equal 0"**, not "unconstrained". Read `ste.attributes`
   (i.e. `ste_dump.py`, §2), never the pretty-printed text.
5. **STE tables only exist while the test runs.** After it exits you get zeros or nonsense — this
   is why §1 comes first.

### Index spaces

An index alone does not tell you what it names. Classify it before resolving
(from `query_steering_dictionary.py`):

```
< 0x11000      GVMI base entry   (resolvable in steering_dictionary.txt)
>= 0x11000     steering table
>= 0x10000000  dynamic resource
>= 0xe0000000  SW steering
```

Base entries and table entries are **not the same index space** — a name looked up in the wrong
one is wrong, not missing.

## 5. Which capture to take

| Situation | Take |
|---|---|
| You already know the entry index and want its fields | `stedmp.sh` (§2) |
| You do not know where the packet went, or it was dropped | hwtrace (§3) |
| You need to compare against a later run / another card | hwtrace — it is the only one you can re-read offline |
| You need the zero-valued constraints, not just what is printed | `ste_dump.py` (§2) — `stedmp.sh` hides them |
| You have dwords from an old capture and no card | `ste_dump.py --raw` (§2) |
| The card is on another machine | `ste_dump.py --host/--user/--password` (§2) |
| The test already exited | neither — re-run under `--wait_on_err` first (§1a) |

## Related

- Getting a run to start at all → skill `fw-build-burn-utopx`
- Driving a feature that needs these captures → skill `feature-delivery`
- Reproducing a specific regression bit-for-bit → skill `regression-repro`
