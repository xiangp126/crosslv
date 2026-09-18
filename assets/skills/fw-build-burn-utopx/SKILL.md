---
name: fw-build-burn-utopx
description: >-
  Build golan_fw firmware, verify and burn it to a local NIC or DPU, then run utopx end to end.
  Use for self-built FW, local traffic_test runs, local-card reproduction, GA even/odd version
  selection, OFED-to-udriver handoff, or setup failures such as "NicPfs list is empty",
  "Udriver init failed: no devices found", "Found 0 Functions", and ArmAgent UFATALs.
---

# Build → burn → run utopx, on a local card

Verified end-to-end on `m-fwdev-167` on 2026-09-08 (ConnectX-8, GA 2026-July baseline,
`traffic_test.conf`, `TEST PASSED` 150/150, zero UFATAL).

## 0. Pick the baseline

GA branches carry the same name in **both** repos, e.g. `GA_2026_July_from_50_0408`
(`golan_fw` and `fw_ver/utopx`). Newest GA wins; find it with

```bash
git for-each-ref --sort=-committerdate --format='%(committerdate:short) %(refname:short)' \
    refs/remotes/origin | grep -i '/GA_' | head
```

**You cannot build the released version.** The release bot tags an **even** `SUBMINOR` and then
bumps the branch to the next **odd** one; a local build of an even version is refused
(`Even-numbered FW Subminor Version can only be compiled by official build` →
`make[1]: *** [Makefile:226: pre_comp] Error 1`). So build **official + 1** — the GA branch HEAD.
The delta is only `Version` plus the auto-generated version vector in
`adabe/upgrade_ini_defaults.adb`; never functional code. This is global hard rule 4.

Released artifacts (for the INI, and for a bit-exact image if you ever need one):
`/mswg/release/BUILDS/fw-<devid>/fw-<devid>-rel-<ver>-build-001/dist/`
— `devid` is `41692` for BF3, `4131` for CX8. `dist/BUILD_ID` names the exact tag and commit.

## 1. Worktrees

### 1.0 Which clone to branch from

Feature work → `golan_fw` / `utopx`. Repro → `golan_fw2` / `utopx2`. Never cross them; the full
rule and its rationale live in `CLAUDE.md` → **Repos**. Then give each task its **own worktree**
off that clone — never work in the clone's own checkout, which usually sits on someone else's
branch.

**The path must make `jmake` happy.** It detects the repo type with
`case "${fWorkingDir,,}" in */golan*|*/nicx*|*/utopx*)`, so a **path segment must start with**
`golan` / `nicx` / `utopx`. `wt_fw_x` and even `wt_golan_fw_x` are both rejected — use
`golan_fw_<tag>` / `utopx_<tag>` (a `-` separator works too: `golan_fw-<tag>`, `utopx-<tag>`).

```bash
SRC=/auto/fwgwork1/$USER/golan_fw          # feature work; use golan_fw2 for a repro (§1.0)
git -C "$SRC" fetch origin <BRANCH>
git -C "$SRC" worktree add -b <topic> /auto/fwgwork1/$USER/golan_fw_<tag> origin/<BRANCH>
git -C /auto/fwgwork1/$USER/golan_fw_<tag> submodule update --init --recursive   # 23 submodules, ~2min
```

Two traps here:

- **Run the checkout in the background.** A full golan_fw checkout on NFS takes ~8 minutes and
  will blow any 2-minute foreground timeout, leaving a half-populated directory with no `.git`.
  Recover with `git worktree prune` + `rm -rf <dir>`, then re-add (reuse the branch, drop `-b`).
- **`git submodule status` lies in a fresh worktree.** It prints no `-` prefix (so
  `grep -c '^-'` is 0) because the worktree shares the main repo's `.git/modules`, yet the
  submodule directories are **empty**. Check with `ls shared/glib`, not with `submodule status`.

Renaming a worktree later: `git worktree move` refuses when submodules are present, and
git < 2.30 has no `worktree repair`. Do it by hand — only two pointers need editing:

```bash
mv "$OLD" "$NEW"
printf '%s\n' "$NEW/.git" > "$COMMON/.git/worktrees/<name>/gitdir"          # absolute
grep -rl '<oldbasename>' "$COMMON/.git/worktrees/<name>" \
  | xargs sed -i 's|\.\./<oldbasename>/|../<newbasename>/|g'                # core.worktree back-refs
```

The worktree's own `.git` file and the submodules' `.git` files need no change (the metadata
directory name does not move, and the submodule paths are relative).

## 2. Build the firmware

`jmake` model → chip: `arava`=CX6DX · `tamar`=CX6LX · `viper`=BF2 · `mustang`=BF3 · `carmel`=CX7 ·
**`gilboa`=CX8** · `argaman`=CX9 · `alpine`=CX10. Artifacts: `fw-BlueField-3.mlx`,
`fw-ConnectX8.mlx`, …

```bash
LOG=$PWD/fw_build.log
setsid bash -c "jmake -w /auto/fwgwork1/$USER/golan_fw_<tag> -m <model> -o >> $LOG 2>&1; \
                echo \"EXIT=\$?\" >> $LOG" < /dev/null > /dev/null 2>&1 &
```

~6–7 minutes with a warm adabe cache. Always detach — it outruns the foreground timeout.

## 3. Verify the image OFFLINE before burning

`.mlx` is not a burnable binary (`flint -i` says `Invalid Image signature`). Compile it with the
board INI and query the result. This step never touches the device and is the gate that stops a
wrong image from reaching the card.

```bash
D=/dev/mst/<node>
PN=$(sudo mlxfwmanager -d $D --query | awk '/Part Number:/{print $3}')
DIST=/mswg/release/BUILDS/fw-<devid>/fw-<devid>-rel-<gaver>-build-001/dist
mlxburn -fw <built>.mlx -conf $DIST/${PN}.ini -wrimage /tmp/fw.bin
flint -i /tmp/fw.bin q | grep -E 'FW Version|PSID|Security'
```

The INI must match the board **part number exactly** — the release dist ships near-identical
variants (`..._4_PORTS_MH_INT_Ax.ini`, `..._HM_INT_Ax.ini`, `..._2PCORES_Ax.ini`); picking the
wrong one is how a card gets a wrong board config. Check `psid`/`name` at the top of the file.

Expect the built `FW Version` to be the odd version from §0 and the `PSID` to match the card.
**Version or PSID mismatch → stop, do not burn.** A self-built `.mlx` is typically the exact same
byte size as the GA release `.mlx` and differs only in md5 — that is the version stamp, not a bug.
On secure-boot cards, `Security Attributes: secure-fw, dev` on both image and card means a
dev-signed self-build is accepted.

## 4. Burn

```bash
sudo mst start
sudo flint -d $D q                      # record the pre-burn state
pgrep -a utopx.exe                      # must be empty
# on a DPU: a still-booting ARM holds ICMD and the burn dies at the very end
sudo mlxburn -dev $D -fw <built>.mlx -conf $DIST/${PN}.ini -y
```

Wait for `Image burn completed successfully`; abort on `^-E-` / `Burn failed`. ~2.5 minutes.
Do not touch the device while it burns. If any driver holds the PFs, unbind first (`unbind`, not
`rmmod`).

## 5. Make it live — and let a driver initialise it

```bash
jmake --fw-reset --device $D             # ALWAYS use jmake, not bare mlxfwreset (Peter's rule)
sudo /etc/init.d/openibd start           # <<< mandatory, see below
ethtool -i <netdev> | grep firmware      # the authoritative "running" version
```

**Every test run gets its own fw-reset, and it goes through `jmake`.** `jmake --fw-reset` wraps
`fwresetfunc`: it stops/starts the driver and re-scans PCI around the reset, which bare
`mlxfwreset -d $D -l 3 -y reset` does not. On a DPU it also tries the ARM side and will log
`openibd force-restart failed` if the ARM's sshd is down — that part is non-fatal for host-side
work. Neither form reboots the host.

- `flint -d $D q` reads the **flash image**, so it shows the new version even without a reset.
  The running version is what `ethtool -i` / `mlxfwmanager --query` / a fresh `dmesg` probe says.
- **`mlxfwreset` alone is not enough.** It reloads the firmware but nobody runs `INIT_HCA`, so
  utopx's `QueryPfTopology()` ICMD calls fail instantly and every PF is discarded →
  `NicPfs list is empty`. Letting `openibd start` bring the card up once fixes it. Tell-tale in
  the log: on a healthy run there are **~20 seconds** between `Found N Functions` and
  `Searching for Physical functions`; on the broken one both land in the same millisecond.
- If `mlxfwreset -d $D q` answers `There is no supported reset-level`, a pending NV parameter
  needs a **cold boot** — see hard rule 5 before rebooting anything.

## 6. Build utopx

**Build with `jmake`, and clean before you build.** Not `./build.sh` directly.

```bash
git -C /path/to/utopx2 worktree add -b <topic> /auto/fwgwork1/$USER/utopx_<tag> origin/<GA_BRANCH>
cd /auto/fwgwork1/$USER/utopx_<tag> && git submodule update --init --recursive
jmake -c -o                              # clean + build; dockerised; ~8 min
cat container_build_result.txt           # must be 0
```

Submodules: `steering_ul`, `hca_fwv_shared`, `hca_fw_core_platform`. Output is `utopx.exe`
(~59 MB) under `artifacts/bin/ninja/ubuntu/20.04/x86_64/gcc10.5.0/ABI_0/Legacy/`.

### The three clean levels, and which one you actually need

| flag | runs | clears |
|---|---|---|
| `-c`, `--clean` | `./build.sh -C` | build artifacts |
| `--git-clean` | `git clean -fdx` | ignored files in the **main** repo — **submodules preserved** |
| `--clean-submodule` | `git submodule deinit --all -f` | the **submodule working trees** |

`-c -o` is the default habit. Reach for the other two when a build misbehaves in a tree that has
been reused across tickets.

### ⚠ Stale generated files inside a submodule survive everything you would expect to clear them

`hca_fwv_shared/autogen/*.cpp|*.h` are **gitignored generated files**, and
`autogen/CMakeLists.txt` merely does `file(GLOB_RECURSE autogen_sources "*.cpp")` — it globs
whatever is on disk and does **not** regenerate. So they are refreshed by neither
`git checkout`, nor `git submodule update`, nor `--git-clean` (which preserves submodules).

Symptoms of a stale set, all of which read like "the baseline is broken":

```
hca_fwv_shared/autogen/PacketFields.cpp: error: 'hca_fwv_ib_pkt_hdr_boeth' was not declared
    in this scope; did you mean 'hca_fwv_ib_pkt_hdr_eoeth'?
```

and — worse, because it is silent — the binary links an **old** `hca_fwv_shared` and then
behaves differently from the regression's own build: on 2026-09-16 a reproduction that fired
reliably in the deployed tree would not reproduce at all from the private clone, and every run
segfaulted. Both went away once the stale files were removed.

Check by timestamp against the deployed tree, then let the build regenerate:

```bash
ls -la --time-style=+%m-%d hca_fwv_shared/autogen/*.cpp | head -3
ssh <box> 'ls -la --time-style=+%m-%d /tmp/mars_tests/<test-DB>/tests/hca_fwv_shared/autogen/*.cpp | head -3'
```

#### Wipe by `git clean`, never by a glob — and wipe **all four** trees

A glob misses whatever the *other* branch's generator emitted. The layout is not stable across
submodule revisions: one revision writes `hca_fwv_shared/autogen/*.cpp` flat, another writes
`autogen/enum2str/`, `autogen/packet_fields/`, `autogen/*_parts/`. `rm -f autogen/*.cpp` then
leaves the subdirectories of the previous branch behind, the CMake `GLOB_RECURSE` picks them up,
and you get `error: '_TlpEmuChannelObject' was not declared in this scope`. Same in the main repo:
`autogen/parts_root/` exists only on branches whose `adabe/Makefile` has a `parts_root` target.

Let git decide what is generated — it never deletes a tracked file:

```bash
git clean -fdx autogen src/cmdif/include/autogen
rm -f adabe/PacketFields.cpp adabe/PacketFields.h
git submodule foreach --recursive 'if [ -d autogen ]; then git clean -fdx autogen; fi'
jmake -c -o
```

Survivors must be tracked files only — `autogen/{.gitignore,CMakeLists.txt}` and
`*/autogen/{CMakeLists.txt,build_standalone.sh}`. Verify that before starting the build.

`jmake --clean-submodule` achieves the same by deiniting the submodules outright.

### ⚠ `BUILD SUCCESS` and `jmake` exit 0 do not mean the build succeeded

jmake runs the stages (`shared`, `adb_gen`, `sul`, `arm_agent`, `dpa_apps`, `utopx`) and prints
the banner from the **last** one. A `shared` stage that dies with `ninja: build stopped:
subcommand failed` still ends in `BUILD SUCCESS` / exit `0`, and the `utopx` stage then links the
**previous** `hca_fwv_shared` — measured on 2026-09-16, where a stale-autogen failure produced a
56 MB binary and a green banner.

Judge the log, not the exit code:

```bash
grep -nE 'FAILED: |ninja: build stopped|make: \*\*\*|Traceback' build.log
grep -n 'build time (min:sec)' build.log     # a stage that "finished" in 00:05 failed fast
```

A stage time far below its usual (`shared` ~00:28, `adb_gen` ~00:22) is the other tell.

**This is the strongest argument for the worktree in the recipe above rather than reusing a
branch in a long-lived clone**: a fresh worktree has no residue to go stale. The price on
git 2.25.1 is that each worktree re-clones all three submodules and costs a full build tree
(`cmakeBuild` alone is ~8 GB), so reuse a clone only when you are willing to run these checks.

## 7. Hand the card over to udriver, then run

Order matters. **Stop OFED first, then load/bind udriver.**

```bash
sudo /etc/init.d/openibd force-stop      # check `ip route show default` first: if the box routes
                                         # over an mlx5 netdev this cuts your session
sudo modprobe udriver                    # never `modprobe -r udriver` (global hard rule)
ls /sys/bus/pci/drivers/udriver/ | grep 0000:
# empty? bind by hand — an already-loaded PCI driver does not re-probe devices that mlx5 freed:
echo 0000:<bdf> | sudo tee /sys/bus/pci/drivers/udriver/bind      # once per PF
# dmesg should show: UDRIVER ... probe ... DEVICE: <devid>, PCI_ADDR: 0000:<bdf>
```

Run it with the CI parameters (`utopx_fixed.cases:27`):

```bash
cd /auto/fwgwork1/$USER/utopx_<tag>
sudo ./utopx.exe --device=$D --daemon --num_of_clients=0 \
  --xml_conf_file conf.xml --conf_file config/traffic_test.conf \
  --iter=150 --ops_per_it=100 --seed 7 --timeout 900 \
  2>&1 | tee logs/run_$(date +%m%d_%H%M%S).log
```

Pass = `[TEST PASSED]` **and** zero `UFATAL` / `MAIN_FATAL` / `Field mismatch`, with the max
`(GEN:0:N` reaching `--iter`. ~3.5 minutes for 150/100 on CX8.

Put the box back afterwards: `sudo /etc/init.d/openibd start`.

## 7b. When a run that used to pass suddenly fails

Do these **in this order**. Skipping to step 3 is how a whole afternoon gets burned.

1. **Run the known-good control first.** Re-burn the last image that passed and run the same
   seed. Until you have that data point you cannot tell "my change broke it" from "the box
   drifted". One control run costs ~10 minutes and settles it.
2. **Diff the NV between the two runs — from the logs, not the device.** utopx dumps the whole
   NV as raw TLVs at the top of every run (`UtopxRandomTest.cpp:487`, `Configuration of
   Device ...`), followed by `mlxconfigchecksum:<sum> <lines>`. So **every past run's log holds
   a snapshot of the NV at that moment**:

   ```bash
   extract() { sed 's/\x1b\[[0-9;]*m//g' "$1" \
               | sed -n '/MLNX_RAW_TLV_FILE/,/Collecting\.\.\./p' | grep -aE '^0x' | sort; }
   diff <(extract good.log) <(extract bad.log)
   ```

   Build a table of *every* run (NV snapshot × pass/fail) before theorising. If the same NV
   appears on both a pass and a fail, NV is not your variable — stop touching it.
3. **Only then** start changing things. And change **one** thing at a time.

**Do not "fix" NV by guessing.** Setting parameters one by one to what you *think* the baseline
was can move the config further from the passing state, not closer — watch the checksum line
drift. If you are sure NV is the variable, restore it wholesale (`mlxconfig -d $D -y reset` for
factory defaults, or `set_raw` with the TLVs captured from the passing log) rather than
parameter-by-parameter. Note a factory reset is **not** necessarily the passing state: a card
that has run utopx carries TLVs written by the test itself.

**Get the real error before theorising about it.** utopx's `debug_conf.xml` raises logging to
debug and prints every ICMD with its status:

```bash
sudo ./utopx.exe --device=$D --daemon --num_of_clients=0 \
  --xml_conf_file debug_conf.xml --conf_file config/traffic_test.conf \
  --iter=1 --ops_per_it=1 --seed 7 --timeout 300 --no_arm_agent
grep -aE 'Executing ICMD|Status: ICMD_' <log>
```

That is how `NicPfs list is empty` was finally traced to
`ICMD_OPCODE_VER_QUERY_PF_TOPOLOGY → Status: ICMD_INVALID_OPCODE` — a fact no amount of
black-box reasoning had produced.

## 7c. The run started but traffic failed

Out of scope here — that is a different job with a different toolkit: WQE reconstruction from
`/tmp/utopx_dump_<pid>/`, the CQE checker's requestor-vs-responder semantics, and steering dumps
via `/mswg/projects/fw/fw_ver/hca_fw_tools/stedmp.sh`. None of it needs a build or a burn, and it
works on a log from a machine you never touched.

Rough boundary: **this** skill is "the test will not run"; that one is "the test ran and the
traffic failed".

## 7d. Log mechanics that bite

- utopx writes a **second, far more detailed log** next to stdout: `verix_test_<ts>_0.log` in the
  **current directory** (`conf.xml`'s `<log_name>` is only a default). `gg` opens the newest one —
  it is an alias (`less -R $(lastlogname)`) from
  `/mswg/projects/fw/fw_ver/hca_fw_tools/.fwvalias`, so it only works from the utopx repo and is
  not available in non-interactive shells.
- Screen and file have **separate verbosity** (`log_screen_verbosity` / `log_file_verbosity`).
  `KDEBUG` output goes to the **file** only — it will not be in stdout.
- Per-key levels live in the `<keys>` block of the xml conf; `conf_keys.xml` lists all 69 keys.
  **List them before guessing** which one prints what you want.

## 8. Failure signatures → cause

| Signature | Cause / fix |
|---|---|
| `Even-numbered FW Subminor Version can only be compiled by official build` | §0 — build the odd version (GA branch HEAD) |
| `jmake: Error: Unknown repo type` | §1 — path segment must start with `golan`/`nicx`/`utopx` |
| `fatal: cannot chdir to '../../../../../../<old>/…'` | §1 — worktree renamed without fixing `core.worktree` back-refs |
| `Udriver init failed: no devices found` | §7 — OFED still up, or utopx not run under `sudo` |
| `Found 0 Functions` | §7 — udriver loaded but not bound to the PFs; bind by hand |
| `NicPfs list is empty` (`UtopxFunctionManager.cpp:241`) | `OpenPfs()` keeps only PFs with `IsPfTopologyValid() && is_resource_manager`. Three distinct causes seen: (a) no `INIT_HCA` since the reset — run `openibd start` once (§5); (b) the card is a DPU in `INTERNAL_CPU_MODEL=EMBEDDED_CPU`, where the resource manager is the ARM ECPF, so host-side utopx needs the ARM agent; (c) `QueryPfTopology()`'s ICMD itself fails — **get the status with `debug_conf.xml`** before guessing (§7b) |
| `Status: ICMD_INVALID_OPCODE` on `ICMD_OPCODE_VER_*` | the FW is not answering the verification ICMDs utopx needs. Check what is actually running (`ethtool -i`), and reset through `jmake --fw-reset` rather than bare `mlxfwreset` |
| `Missing requestor CQE` / `Missing responder CQE` | traffic reached the checker — this is not a setup fault, and a different investigation. Which side is reported depends on the **opcode**, not on the direction of the fault: only `SEND*`, `RDMA_WRITE_WITH_IMM` and `SND_INV` consume a responder WQE, so `ATOMIC_*` / `RDMA_READ` / plain `RDMA_WRITE` can only ever be reported on the requestor side |
| `cmd_hca_cap: <field> not greater than … expected=0x1 Actual 0x0` | tree × FW mismatch — the utopx tree expects a capability the burned FW predates. Burn the matching FW |
| `Could not enable ArmAgentApiBareMetal … resource2_wc` | ARM-agent prerequisite missing: `PCI_SWITCH_EMULATION_ENABLE=1` applied **by a cold boot** (`mcra $D 0x311e20` must be non-zero). Without it utopx writes CR space at the wrong decoder base and can wedge the card into `wait_fw_init`. Use `--no_arm_agent` when the ARM is not the point of the test |
| `wait_fw_init: Waiting for FW pre-initializing (0x87010000)` in dmesg, netdevs gone | card wedged. It is **not** livefish if `flint`/`mlxfwreset` still answer: `openibd force-stop` (drops the stuck probe loops) → `mlxfwreset -l 3` → `FW was loaded successfully` |

## Related

- Global hard rules 2 (no bulk mlxconfig), 4 (even/odd versions), 5 (reboot approval).
- Card gone from PCI / `/dev/mst` empty → skill `nic-livefish-recovery`.
- Matching a failure against CI history → skill `ci-forensics`.
- Dumping an STE or capturing the steering chain a packet took → skill `steering-capture`
  (it must be captured while the run is still alive — freeze it with `--wait_on_err`).
- Reproducing a specific regression bit-for-bit → skill `regression-repro`.
- **Driving a feature to merged, not just building it once** → skill `feature-delivery`.
  Everything above is a one-shot sequence; a feature means two repos, two review threads, gates
  that may still be closed, and a reg box that `mars_reg` re-provisions **daily** — so the
  sequence gets scripted (`env_rebuild_<box>.sh` + `per_run_<task>.sh`) and the verdict becomes
  "did the new code path execute", not `TEST PASSED`.
