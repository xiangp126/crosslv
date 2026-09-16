---
name: utopx-traffic-forensics
description: Analyse a utopx run whose traffic failed - reconstruct the offending WQE and packet from the log and utopx_dump, read the CQE checker's verdict, and dump the steering entry the packet actually hit, or walk the whole HW steering chain a packet traverses. Use when a utopx/nicx run reports "Missing responder CQE", "Missing requestor CQE", a CQE field mismatch, a packet that never arrived, when asked what packet/WQE/QP/GVMI caused a fatal, or when tracing which STEs a packet goes through (hwtrace / steering chain / ste_dump). Works on someone else's log too - no build or burn needed.
---

# Reading a utopx traffic failure

Scope: the run **started fine** and traffic then failed. If it never got past bring-up
(`NicPfs list is empty`, `Udriver init failed`, `Found 0 Functions`, ArmAgent, ICMD_BAD_PARAM),
that is a setup problem — see skill `fw-build-burn-utopx`.

Everything below works offline from a log plus `/tmp/utopx_dump_<pid>/`, so it applies to runs on
machines you never touched. Getting hold of that log from a CI/MARS failure is skill
`ci-forensics`.

## 1. Which side is missing a completion, and why that is not arbitrary

Two different checks, both in `src/checkers/CqeChecker.cpp`:

| Signature | Emitted at | Fires when |
|---|---|---|
| `Missing requestor CQE for …` | `:2684` `CheckMissingReqCqe`, called from `:1999` | the sender's own completion never appeared |
| `Missing responder CQE …` | `:2762` `CheckMissingGoodResCqe`, via `GenAndCheckResponderCqe` at `:2030` → `:2479` | the destination never produced a receive completion |

**Which one you get is decided by the opcode, not by the direction of the fault.**
`SndWqe::ConsumesResponderWqeOpcode()` (`src/transport/SndWqe.cpp:2474`) whitelists exactly:

```
SEND, SEND_LSO, SEND_WITH_IMM, SND_INV,
RDMA_WRITE_WITH_IMM, LOAD_REMOTE_MICRO_APP, STORE_REMOTE_MICRO_APP
```

Only these consume a responder WQE. `ATOMIC_*`, `RDMA_READ` and plain `RDMA_WRITE` are completed
by the remote HCA without touching remote software, so **there is no responder CQE to be missing**
— such a failure can only ever be reported on the requestor side.

Practical consequence: the same defect reports differently depending on what the random mix hits
first. Measured on one planted RX-drop defect: default `traffic_test.conf` died on
`ATOMIC_CMP_SWP` / `RDMA_WRITE` with `responderCQE=0`; forcing UD (SEND-only) flipped it to
`responderCQE=3, requestorCQE=0`.

**To force one side**, override the QP service-type mix. The default is
`config/traffic_test_legacy.conf:403`:

```
create_qp_in.qpc.st = 40:SW_QP_TS_RC 10:SW_QP_TS_UC 20:SW_QP_TS_UD 40:SW_QP_TS_XRC …
```

RC/XRC/DCI dominate and carry RDMA/ATOMIC. `create_qp_in.qpc.st = 100:SW_QP_TS_UD` gives
SEND-only traffic (UD supports nothing else) and exercises the responder-side check.

> `config/scenario_*.conf` files are **overlays** — they layer a scenario and do not pull in the
> base constraint chain. Running one directly via `--conf_file` dies at iteration 0 with
> `UtopxRandomTest.cpp:2221 IcmdForceFwCap "…pci_atomic_mode … invalid Gen range"`.
> Always `INCLUDE traffic_test_legacy.conf` first, then the scenario, then your overrides
> (last line wins on key conflicts).

Read the `DETAILS:` field — `[NO RCV CQES]`, `RX: []`, `SX: [LOCAL_LB, ROCE]` tell you whether the
packet left, and whether the receive side saw anything at all. `LOCAL_LB` means loopback on the
same card, so the inbound path is on that same device.

## 2. Reconstructing the WQE — the bytes are already on disk

utopx writes `/tmp/utopx_dump_<pid>/` on a traffic failure (log line
`Dumping all CQ and QPs to …`). On a segfault it is not written automatically — rerun with
`--wait_cycle <cycle>` and press `d`.

Files are `<gvmi>._<TYPE>.<resnum>.<internal id>`, e.g. `0._QP.0x201.0x633`. The `<gvmi>.` prefix
is authoritative for which GVMI a resource lives on. The number after the type is the resource
number (the real QP number); the trailing one is a per-database internal id, so the *same* QP has
different trailing ids in GenDB vs CheckerDB — never treat it as the QP number.

The dump holds contexts, MTTs, the DMA allocation map **and the queue buffers**, so the requestor
QP's file contains the SQ ring with the raw WQEs as `0xNNNN: ` hex lines.

```bash
# 1. the failing wqe id, then its metadata
grep -a 'UFATAL : CqeChecker' <log>          # -> wqe_id: 0x9b (0:2:84)
grep -a 'POST_SEND_WQE.*0x9b' <log>          # -> msg_size, service type, src/dst QP, VHCA/GVMI/BDF
grep -a 'Dumping all CQ and QPs to' <log>    # -> /tmp/utopx_dump_<pid>/
# 2. fingerprint: take ANY data dword the log already printed for that WQE
grep -rl '723bc8da' /tmp/utopx_dump_<pid>    # -> 0._QP.0x201.0x633
# 3. cut on stride boundaries
grep -n '^0x00' 0._QP.0x201.0x633 | head
```

**Cut on stride boundaries, never on eyeballed line numbers.** `ds` in the control segment is the
WQE length in 16-byte descriptor segments (`ds=0x0e` → 14 → four 0x40-byte strides, e.g.
`0x0005`–`0x0008`). A guessed slice silently drops the control/address segments at the front and
picks up idle ring entries at the back.

**Then reconcile against `msg_size`.** Sum every SGE and inline length; it must equal `msg_size`
*exactly*. In one investigation a 2-byte shortfall was the only symptom of a bad slice that had
hidden a fifth SGE — and it was initially waved away as "≈". Do not wave it away.

The dump reconstruction is **more complete than the log's own WQE print**, which truncates
trailing inline segments and later SGEs.

## 3. What you can and cannot recover of the packet

| Part | Source | Recoverable |
|---|---|---|
| All header fields | WQE control + address-vector segments, plus QP context | **yes** |
| Inline payload segments | embedded in the WQE | **yes**, actual bytes |
| SGE-pointed payload | registered user buffers | **no** (see below) |

Header fields worth pulling from the address vector: `destination_qp_dct`, `dc_key/q_key`
(cross-check against both QP contexts), `rmac_47_16`/`rmac_15_0`, `rgid_rip`, `tclass`,
`hop_limit`, `flow_label`, `rlid_udp_sport`, `sl_eth_prio`, `static_rate`, `grh`. BTH PSN comes
from the QP context's `next_send_psn`.

**The SGE payload is not in the dump.** utopx dumps *queue* buffers (SQ/RQ/CQ rings) only, not
user-registered data buffers: the MKEY files carry context plus MTT and nothing else (e.g. 1582 B
of dump for a 443 KB region). Across a whole dump directory only the QP files contain
`0xNNNN: ` buffer lines.

**Do not try to read it from host memory.** SGE addresses are IOVAs whenever `intel_iommu=on`
(check `/proc/cmdline`, `/sys/class/iommu`). On one box the address landed in a `PCI Bus …` range
in `/proc/iomem` rather than System RAM and `dd if=/dev/mem` returned all `0xff`; translating
would mean walking DMAR page tables, and the buffers are freed when the test exits anyway.

If you genuinely need those bytes, add a print inside
`DataValidationDB::BuildExpectedDataFromWqe()` (`src/utopx_infra/DataValidation.cpp:100`) — it
already reads the SGE contents to build the expected-data DB. Ask first whether the payload
matters: for a packet dropped in steering, it never got as far as payload processing.

**There may be no software packet object at all.** For plain traffic utopx fills random buffers,
builds a WQE and rings the doorbell — the *hardware* assembles the wire packet. The `Packet` /
`PacketBuilder` classes only run when steering has to be predicted. Symptom: with file logging at
debug, `LOG_KEY_BLD_PKT` / `LOG_KEY_PKT_BUILDER` / `PACKET_2_PACKETINFO` produce **zero** lines
while `STEERING_RESOLVER` / `PACKET_INFO_GEN` produce hundreds. Before hunting for a switch that
prints X, check whether X exists on this path — one `grep -c` per key over a debug log answers it.

> `steering.states.unified_packet_testing = 1` gates `SteeringResolver.cpp`'s
> `PrintSteeringPacket()`, but switching it on moves the generator to the `NewPacketCtrl` path
> whose `layers_types` keeps are unconfigured in the `traffic_test_legacy` chain: the run then
> dies at iteration 1 with `MatchSpec.cpp:325 "Generated concrete l2_tag_type is not supported"`
> and an identical poison value every time. Leave it alone outside the
> `steering_only_test.sconf` config set.

## 4. Where the packet actually went — dump the STE

```bash
sudo bash /mswg/projects/fw/fw_ver/hca_fw_tools/stedmp.sh -d $D -g <gvmi> --full -i <ste_ix>
```

Gives `hit_ix` / `miss_ix` with symbolic names, `entry_type` and `my_lu_type`, so you can walk the
chain and see which entry sent the packet to a drop.

**Dump it while the test is still running.** STE tables live inside utopx's VHCA/steering
resources; once the test exits you get zeros or nonsense (`gvmi=0x545f`, `my_lu_type=0x57 N_A`).
The documented way is `--wait_cycle` plus a second shell, which needs an attended terminal;
without one, start the run in the background and dump ~45 s in while it is alive.
(`hca_fw_tools/steering/ste_dump.py` is a different tool and reported `STE is empty or not exist`
in this situation.)

## 4b. Walking the whole steering chain, not just one entry

`stedmp.sh` gives you one entry at a time, and it does print `bit_mask`/`tag_data` — but like
every text dump it prints **only non-zero fields**, so a `tag=0, mask!=0` constraint is invisible.
Scripts must use the importable `SteInfoFetcher` API (what `ste_dump.py` wraps), which returns the
full attribute dict including zeros. To get the **whole chain a packet traverses**, use
the HW trace — it is ground truth, and it prints a reproduce-command for every hop.

```bash
# 1) freeze utopx at the failure. The flag is --wait_on_err (NOT --wait_on_error):
#    UtopxFatalHandler::exit_utopx does getchar() when TestConfigs->wait_on_err, and it
#    does that BEFORE LimitedHostCleanUp / CloseUdriver -- so every VHCA and STE is still
#    alive while it blocks. Headless: hold stdin open or getchar() gets EOF and sails past.
tail -f /dev/null | sudo ./utopx.exe --device=$D ... --wait_on_err &
until grep -qa 'press any key to continue' utopx.log; do sleep 1; done

# 2) capture, from a root shell, while it is frozen
sudo /mswg/projects/fw/fw_ver/hca_fw_tools/steering_basic_debug.sh -d $D -o /tmp/ --hwtrace
sudo /tmp/phwtrace.runme --experimental        # writes /tmp/phwtrace.log
```

**Do not add `--fsdump` on ConnectX-8.** It shells out to `mlxdump ... fsdump`, which answers
`-E- Device not supported by this command`, and the failure makes the whole invocation look
broken. `--hwtrace` alone works and is what produced the captures used below.

**`--wait_cycle` is not a substitute here.** Format is `iter.cycle[.precondOp]`, and
`CheckWaitCycle` stops the VHCA threads and then blocks on a menu keypress — it needs an
attended terminal. Two attempts in a headless run (`0.90`, `0.10`) never reached the pause
point; utopx hit its FATAL first. Use `--wait_on_err`.

Each hop in that output carries `hit_ix`/`miss_ix`, `entry_type`, `my_lu_type`, the non-zero
tag/mask fields, **and 16 raw dwords** — so the whole trace can be re-parsed offline later with
`SteInfoFetcher.parseRawSte(adb, dwords)`, no device needed.

`ste_chain.py` (`/auto/fwgwork1/pexiang/bugZilla/Hackathon/`) automates the analysis:

```bash
python3 ste_chain.py --trace phwtrace.log                      # fold into the unique chain
python3 ste_chain.py --trace phwtrace.log --self-test          # derive a packet, verify the matcher
python3 ste_chain.py --trace base.log --vs-device -d $D \
        --device-gvmi -g 0x0                                   # which STE changed on this card
```

**Capture once, then work offline forever.** A trace carries 16 raw dwords per hop, so it can be
turned into a local STE database; after that a walk needs no device, no utopx and no sudo:

```bash
python3 ste_chain.py --trace phwtrace.log --build-ste-db ste_db.json
python3 ste_chain.py --walk --ste-db ste_db.json --packet pkt.json -g 0x0 -i 0x12001 -v
# on a live card you can record what the walk reads instead:
sudo python3 ste_chain.py --walk -d $D ... --capture-ste-db ste_db.json
```

The db stores STE *bytes* only — hit/miss and the next hop are still recomputed from the packet,
so the chain is derived, not replayed.

**Pulling one packet's path out of a multi-packet capture.** A capture interleaves packets
(`phwtrace_bad.log` holds a unicast one that is dropped and a multicast one that is not), and
`--derive-packet` will happily solve a self-contradictory packet from the mixture. Three rules
separate them, none of which peeks at the answer: keep the **first occurrence** of each
`(gvmi, ix)`; per direction keep only the **first root-table hop** (a second root lookup is the
next packet entering); **stop after a DROP**.

**MPFS root tables live at `GLOBAL_GVMI` (0x8111), not the per-function gvmi.**
`steering_shared.c` does `initialize_steering_table(GLOBAL_GVMI, DEFAULT_PORTID,
STEERING_TABLE_ETH_IB_MPFS_REGULAR_RX_ROOTS)`, and the trace logs that hop as `gvmi=0x8111`
while the next one is back on the function's own gvmi. Reading it at the wrong gvmi returns
zeros and the chain looks like it ends at the SX terminator.

**The RX port is not always the SX port.** On a loopback the packet can come back on the other
port -- `phwtrace_bad.log` is SX port 1 -> RX port 0 while `phwtrace_good.log` stays on port 1 --
so the RX root index cannot be derived from the SX one. `ste_chain.py` takes `--rx-port` for this.

`--vs-device` is the way to locate a firmware steering change **without** re-capturing a trace:
it walks the baseline trace's hop list against the live card and diffs each entry. Only a
**base-entry → base-entry** pointer change is conclusive — table indices (`>= 0x11000`) are
allocated per run and legitimately differ between captures.

### Five traps when reading a steering chain

1. **`hit_ix` into a table is only the table base** — the real next hop is one of
   `2^next_log_size` entries — **but it is resolvable in software.** `next.hash_type`
   tells you how: LINEAR is no hash at all, just selected bits assembled LSB-first
   (bit tables in `hal_static_configuration.c` `CONFIG_LINEAR_HASH`); REGULAR is a real
   hash, but insert and lookup share it, so the slot whose stored tag *non-vacuously*
   matches the packet is where it lands (scan the table; empty-mask slots match
   vacuously and mean nothing). The MISS target (`miss.miss_address`) is a direct
   pointer — always exact, never scaled by `next_log_size`.
2. **The 128-bit tag/mask is a union over every field group.** `tag_data.ethl2_des.*`,
   `tag_data.ibl2.*`, `tag_data.source_gvmi_qp.*` are all present at once — different readings
   of the same bits. Only the group selected by `my_lu_type` applies (`getNextMatchDefiner()`
   instead when `byte_mask_mode` is set). Copy the mapping from `SteInfoFetcher.tagFields()`.
3. **`miss.match_polarity=1` inverts the verdict**: `hit = match XOR polarity`. It is not
   "always miss" — a polarity entry whose fields matched goes to *miss*, and one whose fields
   did not goes to *hit*.
4. **"Printing only non-zero fields" hides real constraints.** A field with `bit_mask != 0` and
   no printed `tag_data` line means **"must equal 0"**, not "unconstrained". Read
   `ste.attributes`, never the pretty-printed text.
5. **STE tables only exist while the test runs.** After it exits you get zeros or nonsense.

### Index spaces (from `query_steering_dictionary.py`)

```
< 0x11000      GVMI base entry   (resolvable in steering_dictionary.txt)
>= 0x11000     steering table
>= 0x10000000  dynamic resource
>= 0xe0000000  SW steering
```

Base entries and table entries are **not the same index space** — classify before resolving a name.

## 5. Useful context to pull alongside

```bash
D=/tmp/utopx_dump_<pid>
grep -aE '^ (st|state|pd|q_key|cqn_snd|cqn_rcv|next_send_psn|log_sq_size)' $D/0._QP.<src>.*
grep -aE '^ (st|state|pd|q_key|cqn_rcv|rq_type|log_rq_size)'               $D/0._QP.<dst>.*
grep -aE '^ (status|log_cq_size|consumer_counter|producer_counter)'        $D/0._CQ.<cqn>.*
grep -a -A4 'qp_doorbell_record' $D/0._QP.<src>.*        # posted vs read index
head -1 $D/0._MKEY.<idx>.*                               # lkey high bits = mkey index: 0x4651 -> 0x46
```

Both QPs in `RTS`, matching `q_key`, a CQ with `status OK` and no overrun, and a doorbell record
whose `posted_index` advanced — that combination rules out the endpoints and points at the path.

## 6. Log mechanics that bite

- utopx writes a **second, far more detailed log** next to stdout: `verix_test_<ts>_0.log` in the
  **current directory** (`conf.xml`'s `<log_name>` is only a default). `gg` opens the newest one —
  it is an alias (`less -R $(lastlogname)`) from
  `/mswg/projects/fw/fw_ver/hca_fw_tools/.fwvalias`, so it only works from the utopx repo and is
  not available in non-interactive shells.
- Screen and file have **separate verbosity** (`log_screen_verbosity` / `log_file_verbosity`).
  `KDEBUG` output goes to the **file** only — it will not be in stdout.
- Per-key levels live in the `<keys>` block of the xml conf; `conf_keys.xml` lists all 69 keys.
  **List them before guessing** which one prints what you want.

## Related

- Team wiki, worth reading before reverse-engineering source — search Glean for
  "Debugging missing responder Cqe in UtopX" and "Debugging traffic failures in Utopx"
  (Confluence, space FW). They document `steering_basic_debug.sh --fsdump --hwtrace`,
  `/tmp/hwtrace.runme` → `/tmp/phwtrace.runme`, reading SX/RX steering stages, spotting a packet
  sent to `DROP_QP`, `first_related_error` via `fwtrace`, and the rxt drop counters in devmon.
- Setting the run up in the first place, and bring-up failures: skill `fw-build-burn-utopx`.
- Getting the log out of a CI/MARS failure: skill `ci-forensics`.
- Filing what you find: skill `utopx-regression-ticket`.
