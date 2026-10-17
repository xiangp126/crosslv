# Regression repro — procedure (Phases 1–11)

## The three artifacts a repro needs

A MARS session pins three artifacts; reproduce with **all three** matching — one or two matching
yields look-alike failures that are not the bug.

| Artifact | Recorded in (MARS step) | Also visible in ticket as |
|---|---|---|
| **FW build** (`.mlx` + version + PSID) | `new_burn_fw` | `flint_nv_dump_<dev>_<VER>_*` attachment filename |
| **Burned INI** (release default + regression overrides) | `new_burn_fw` (`new_ini_file`) | `dump_nv_data_*` attachment (the resulting NVconfig) |
| **Test-tool commit** + the exact **command & seed** | `get_last_commit` / `run_case` | `run_case_<key_id>.log` attachment |

**The box drifts daily** (fresh FW burn and test-tool re-pin every day): never assume a version —
read it from the ticket's session and verify the running FW with `flint q`.

---

## Phase 1 — Decode the Redmine ticket into reproduction coordinates

Input: the ticket URL only.

```
yai__get_tickets(ticket_ids=[<NNNNN>], include="full")   # real-time, with attachments + history
yai__resolve_redmine_url("<URL>")                         # also expands a project-filter/saved-query URL
```

Extract, in order:

1. **Signature, test tool, regression stream** — from `subject` and the `Fatal message:` line in
   `description`, shaped `[UTOPX] <signature> ; <cmd_struct> ; <REGRESSION_STREAM> DEVICE_NAME_LIKE[<DEV>]`
   (test tool = utopx; `<signature>` = what to reproduce; `<REGRESSION_STREAM>` = the verification
   branch/carveout; `<DEV>` = the device family).
2. **The MARS `view_log.php` URL in `description`** — the bridge to the reproducible env:

   | Param | Use |
   |---|---|
   | `results_dir` | NFS results root, mounted on every dev box — read it directly, skip the auth'd web UI |
   | `setup_id` | encodes **machine** + **device** + **mode** + suite, e.g. `<DEV>_FW-<machine>_<MODE>_P1` |
   | `session_id` | the session → tarball `<results_dir>/<setup_id>/<session_id>/<session_id>.tgz` |
   | `key_id` | the **failing step path** inside the tarball; also the suffix on every attachment |
   | `status` | `Failed` confirms it is a failure to reproduce |

3. **Device / MST / FW** — `custom_fields` "Chips" = device family. From attachment filenames:
   `flint_nv_dump_<mstdev>_<FWVER>_*` → **MST device** (e.g. `mt41695_pciconf0`) and **running FW**
   (e.g. `82.48.1632`); `mst_dump_file_for_step_..._<mstdev>_...` / `print_mst_devs_*.log` confirm the
   MST node; `fixed_version` = the release the fix lands in.
4. **Exact command + env from the attachments** (faster than the tarball) — download via each
   `content_url` (Redmine attachment-download tool, `curl -H "X-Redmine-API-Key: $KEY"`, or a browser),
   or read the same file from the tarball (Phase 2):

   | Attachment | What it gives you |
   |---|---|
   | `run_case_<key_id>.log` | **the exact test command**: scenario `.conf`, `--iter`/`--ops_per_it`, any `-e` knobs, and the **seed** to pin |
   | `oplist_<key_id>.log` | the op sequence (for narrowing the failing op) |
   | `dump_nv_data_<key_id>.log` | the NVconfig that was active (cross-check your INI burn) |
   | `flint_nv_dump_<dev>_<ver>_*` | FW version + NV dump |
   | `fw_reset_*.log`, `modprobe_udriver_*.log`, `print_mst_devs_*.log` | the regression's per-test reset/bring-up sequence to mirror |
   | `basic_debug_*.log`, `remote_file_analysis_*.log`, `Verify_utopx_executable_existence_*.log` | utopx binary path/version sanity, extra context |

5. **History** (`journals`) — who reassigned/triaged it and any analysis link (e.g. an Orion
   AI-overview URL); reassignment from the auto-filer to a dev usually marks the start of real triage.

Done when the **Environment** table of `REPRO_<ticket#>.md` (from `templates/repro.md`) is
fully filled from the ticket alone.

## Phase 2 — Extract the exact versions from the MARS session tarball

The **INI path/PSID** (`new_burn_fw`) and the **test-tool git commit** (`get_last_commit`) usually
live only in the tarball.

```bash
RESULTS=<results_dir>; SETUP=<setup_id>; SID=<session_id>; KEY=<key_id>
mkdir -p /tmp/mars_$SID

# Find the version steps + the failing run_case (step numbering varies per session):
tar -tzf $RESULTS/$SETUP/$SID/$SID.tgz | grep -E "new_burn_fw|get_last_commit|$KEY/run_case"

# Extract just those logs (not the whole multi-hundred-MB tarball):
tar -xzf $RESULTS/$SETUP/$SID/$SID.tgz -C /tmp/mars_$SID/ \
    <a.b.c>/log.txt <d.e.f>/log.txt $KEY/run_case.cap
```

- `new_burn_fw` `log.txt` → `grep -E "fw_file:|default_ini:|FW Version:|psid:|new_ini_file:"`:
  `fw_file` = the official `.mlx` to burn; **`new_ini_file`** = the regression-generated INI to copy
  (it carries the injected overrides; the release default does NOT).
- `get_last_commit` `log.txt` → `grep -E "git_describe|commit_id"`: the `git_describe` tag is the most
  self-documenting test-tool reference; the SHA always resolves.
- `run_case.cap` → `grep -oE '<tsr_args>[^<]+'` = the exact args (cross-check `run_case_<key_id>.log`).

### Translate the FW *product* version → FW *source-tree* commit/tag

No MARS step records FW source (FW is a pre-built `.mlx`). In the FW repo:
- `git log --all --oneline --grep="Updated version <src-family>.<MM>.<bld>"` — tools report a
  *product* number (e.g. `82.48.1632`), the source tree a different family digit with the same build
  number, so grep the trailing `.<MM>.<bld>`.
- Release tag = `rel-<src-family>_<MM>_<bld>` (drop the family prefix, dots → underscores).

### Read the release tag's tree, not your clone's checkout

A repro clone usually sits on a feature/triage branch lacking the release line under test; grepping
it gives confidently wrong conclusions (#5138907: a syndrome literal absent from the checkout → a
fabricated "this validation is missing" root cause). Until Phase 4 pins the repo, read the tag in
place, without checking it out:

```bash
git grep -n '<pattern>' <rel-tag> -- 'src/*.c'      # search the release tree in place
git show <rel-tag>:<path> | sed -n '<a>,<b>p'       # read a file at that tag
```

A build date *earlier* than your clone's HEAD does not mean the code is in your clone.

## Phase 3 — Allocate & preflight the SAME server that reported the issue

**MANDATORY: reproduce on the exact box from `setup_id`, with the exact command, env and steps the
regression ran.** No other host, command, scenario/iter/ops or "cleaner" bring-up: only a bit-for-bit
match is a valid repro; anything else can hide or fake the failure. Box held by someone else → monitor
it and grab it the instant it frees (§3b); never swap boxes except per the same-PSID exception in §3b.

The test machine is the `<machine>` parsed from `setup_id` (e.g. `BRONCO_FW-`**`m-fwreg-029`**`_DPU_MODE_P1`).

**Unsure of a reg-server / reservation / lab-tooling command or flag** (malloc options, querying a
queue, what a Noga field means)? Ask the **nvidia-glean** MCP (`glean_search` or `glean_chat`, e.g.
"how to malloc a regression server fwreg / extend allocation / noga lock") before inventing one;
confirm with `--help` where one exists.

### 3a. Reserve the box

Lock mechanics — taking, extending, releasing and verifying the lock, the `not in allocation pool`
fallback, the interactive `--reg-extend` trap, reading `TIME LEFT` — are in **skill `noga-lock`**.
Reserve **the box named in `setup_id`**, never a substitute (exception: same-PSID substitution, §3b).

### 3b. If the box is busy: monitor and grab it the instant it frees

When `jmake --reg-malloc <machine>` reports `Resource locked by <holder> until <ts>`, do not switch
hosts or re-type malloc by hand — first malloc wins, so use the unattended loop. It already handles
what a hand-written `until` loop gets wrong: heartbeat with owner + seconds-to-expiry, chaining the
provisioning step with `--then`, and the two failure modes that silently kill a monitor.

```bash
~/myGit/crosslv/assets/skills/noga-lock/scripts/noga_wait.sh -n <machine> -L 8 --hours 8 \
    --then '<provisioning command>'
```

Start it with the long-running-job method in `references/hosts/<runtime>.md`; keep one watcher and
observe that same job — never start duplicates. Details and traps: **skill `noga-lock`**.

**A released lease does not mean an idle box** — confirm the regression really ended before the
first burn/reset, however you got the lock (skill `noga-lock` → "Before touching any box you
locked"); at minimum this must print 0 (run it as its own `ssh` command):

```bash
ssh <box> 'ps -eo cmd | grep -cE "[u]topx\.exe|[R]egTools|[m]ars_tests|[F]wreset|[m]lxburn"'
```

#### Exception — same-PSID substitution (only with explicit user approval)

Only when the exact box is locked long-term **and the user explicitly approves a substitution**
("find an idle server with same PSID"). Match the **board, not just the family**: the same **PSID**
is what makes the FW expose the same caps.

1. **List every box with the PSID via Noga** (authoritative; MARS INI names only cover boxes that ran
   this suite). The PSID is the **NIC** resource's `Setup Automation.psid` attribute (each server
   links its card as `Relation.has a = NIC:<box>-bf2-<mac>` / `Specific.MELLANOX_CARD_1`):

   ```bash
   NOGA=/.autodirect/sw_tools/Internal/Noga/RELEASE/latest/cli/noga_manage.py
   python3 $NOGA -q -t nic -e "psid:<PSID>"          # e.g. psid:MT_0000000704
   #   -> table of ID/Name/Group/Status/lock_owner for every board with that PSID.
   #   'Release' / empty owner = free;  'Lock' by mars_reg = a regression holds it (or a stale
   #   reservation if the box is actually down -- verify reachability, don't trust the lock alone).
   ```

   Different schema → locate the PSID attribute by dumping the card:
   `python3 $NOGA -q -n <box> -t server -D | grep -iE 'MELLANOX_CARD|has a'`, then
   `python3 $NOGA -q -n <nic-name> -t nic -D | grep -iE 'psid|device_id|NIC_Type'`. Coarser fallback:
   `ls <results_dir> | grep -iE '<DEV>.*<MODE>'` (MARS *sibling setups* only — misses same-PSID boxes
   that never ran this suite).

2. **Pick idle candidates**: `jmake --reg-idle` and/or
   `noga_manage.py -q -n <cand> -D | grep -E 'Status\.(status|lock_owner)'`. `Release`/empty owner =
   free; `Lock` by `mars_reg` = a regression is running it — **unless the box is unreachable/down,
   where it is a stale reservation**. Confirm with `ssh <cand> hostname` (using the runtime adapter)
   and the newest real session mtime.
   - **Only `*-fwreg-*` boxes are candidates.** The PSID listing and `jmake --reg-idle` also return
     `l-fwdev-*` developer boxes; drop them even when they show `Release` (skill `noga-lock`).
   - **MANDATORY platform check — utopx setups are Supermicro-only.** The allocation-pool health scan
     (`update_noga_resource.py` → `RegTools/is_setup_compatible_with_utopx.py`) flags a box
     `INCOMPATIBLE_UTOPX` purely on `dmidecode -s system-manufacturer` ∉ {supermicro}.
     `noga_manage.py -q -n <cand> -D | grep -iE 'Server_Model|Free_text'` must show BOTH
     `Server_Model = Supermicro` and no `noga_alloc_note:[INCOMPATIBLE_UTOPX]` in Free_text (also red
     in the Allocated-setups dashboard). A conveniently idle box may be idle *because* of this flag.
     Ignoring it is dangerous, not just unsupported: an HP (iLO4) box, l-fwreg-068, took the
     virtio-full-emu PCI-switch nvconfig and hard-hung in BIOS POST, unrecoverable remotely.
   - **It may lack this suite's box-specific `topology_<mode>.xml`** (the RegTools clear_nv_data /
     Fwreset / check_arm_agent need per-box entry_points). Author one from the original box's: copy
     `topo/<orig>/topology_<mode>.xml` + `<orig>_<mode>.xml` and swap BASE_IP / CONNECTION IP, the
     `rocep*` SUB_DEVICE names, PCI_BUS and the per-port data-plane IPs (20.x/21.x) for the
     substitute's, discovered with
     `ssh <cand> "ip -br addr; sudo mst status; rdma link; lspci | grep -i mellanox"` (runtime adapter).

3. **Confirm same PSID + healthy** from the candidate's latest session tarball
   (`<results_dir>/<sibling_setup>/<latest_sid>/<sid>.tgz`), `new_burn_fw` log: `psid:` == the
   ticket's PSID, `FW Version:` == target, `Burn FW RC = 0`/`Final RC = 0`.
   - **Status-only archives** (log.txt purged by retention): `tar -tzf <sid>.tgz | grep new_burn_fw.cap`
     gives the burn step ids (e.g. `1.25.1.1`/`1.28.1.1`, one per port/segment);
     `tar -xzOf <sid>.tgz --wildcards "<step>/status.txt"` → `result: 0` = burn OK. Health at a glance:
     `summary_results.json` → `Total_summary` (a healthy board on an active branch shows tens of
     PASSED). **0 PASSED + burn RC=1 across several consecutive sessions = sick box — disqualify it
     even if PSID/mode match** (Phase 6 must burn FW on it).
   - **No tarball at all:** the burn-INI filename embeds PSID and FW version —
     `ls /auto/sw/work/hca_fw/data/burn_fw/ini_files | grep session_<sid>_` →
     `..._session_<sid>_version_<ver>_psid_<PSID>.ini`. A session with NO ini_files entry often means
     its burn failed.
   - **Health-rank ALL candidates before picking**: mode fidelity (non-SD vs SD) decides which
     *failure face* you will likely see, burn health whether the box is usable at all. Prefer
     healthy + mode-faithful > healthy + SD > mode-faithful but sick.

4. **Bonus signal**: `tar -xzOf <sid>.tgz | grep -m1 "<signature>"` — if the sibling's own latest
   regression hit the SAME fatal, the bug is systemic to that board/FW and the substitute is
   high-confidence.

5. Lock the substitute (direct Noga lock if it lacks the malloc-pool label — §3a / skill `noga-lock`),
   record the substitution + approval in the run log, and leave the original box untouched.

### 3c. Preflight (once you hold the lock)

```bash
# Capture current FW state as a restore point before touching anything.
ssh <machine> 'sudo flint -d <MST device> q full'

# STALE-PROCESS CHECK (esp. boxes that fell out of rotation) - a leftover test daemon from a
# prior session can still hold the device. Find & kill it:
ssh <machine> 'sudo fuser -v /dev/udriver_* 2>&1; ps -eo pid,etime,cmd | grep -E "[u]topx.exe.*--daemon"'
ssh <machine> 'sudo kill -9 <pid> <ppid>'   # the leftover utopx + its sudo parent; then re-check fuser
```

- A leftover daemon makes fw_reset fail later with `udriver cannot be unloaded, file /dev/udriver_* is opened, possibly by utopx` / `Device is busy`.
- A regression ran on the box since the failure (FW != target, test binary mtime fresh) → do the
  Phase 9 env-drift recovery before trusting any result.

## Phase 4 — Pin local repos to the regression's commits

### 4a. Fastest path: reuse the regression's deployed test-tool binary

The regression deploys the prebuilt `utopx.exe` + its configs to `/tmp/mars_tests/<test-DB>/tests/`
on the test box (the `<test-DB>` from `get_last_commit`). If that tree still exists, its binary **is**
the regression's exact binary — no clone/build, the cleanest pin (perfect three-way match). Verify:

```bash
ssh <machine> 'ls -lL /tmp/mars_tests/<test-DB>/tests/utopx.exe;
  ls /tmp/mars_tests/<test-DB>/tests/{conf.xml,config/<scenario>.conf}'
# cross-check commit vs Phase-2 get_last_commit (and the run prints "tarball git tag is: <describe>")
```

Build locally only if the deployed tree was cleaned — in a per-ticket worktree off the repro clone
(§4b/§4c): FW off `/auto/fwgwork1/$USER/golan_fw2`, utopx off `/auto/fwgwork1/$USER/utopx2` (per
user). Never pin or check out inside a clone's own checkout — it may be another ticket's, or an
active `[USE_THIS_WORKSPACE]` clone. Worktree traps (background checkout, `git submodule status`
lying in a fresh worktree, renaming): skill `fw-build-burn-utopx` §1.

### 4b. NEVER edit source inside `/tmp/mars_tests/<test-DB>/tests/`

mars_reg runs the nightly regression straight out of that tree: use it read-only (run its
`utopx.exe`, read its configs, check its commit). No patch, probe or in-place rebuild — not even
temporarily with a backup: if the lease expires or the box is grabbed before you restore, the next
regression silently runs your binary and nothing in the archive points back at you.

Every source edit — a candidate fix *or* a read-only debug probe — goes on a **named private branch
in a per-ticket worktree off the repro clone**, never in the clone's own checkout. The fix branch is
`fix_<ticket#>_<topic>_<line>`, off `origin/<full-branch-name>`:

```bash
C=/auto/fwgwork1/$USER/utopx2              # FW: golan_fw2, worktree golan_fw_<ticket#>
W=/auto/fwgwork1/$USER/utopx_<ticket#>     # jmake needs a path segment starting utopx/golan/nicx
git -C $C fetch origin <full-branch-name>
git -C $C worktree add -b fix_<ticket#>_<topic>_<line> $W origin/<full-branch-name>
cd $W
git submodule update --init --recursive    # MANDATORY - see below
# edit, then build in place (a copied tree will not build - cmake caches absolute paths)
jmake -c -o                                # clean build; then read the log, not the exit code
```

The ticket already has a worktree in that repo (the §4c pin)? Switch inside it instead of adding a
second one — `git -C $W checkout -b fix_<ticket#>_<topic>_<line> origin/<full-branch-name>` — then
run the same submodule update and wipe every autogen tree before the clean build: a checkout leaves
the previous branch's generated files behind (SKILL.md, "A branch checkout does not give you a clean
tree"). Worktree traps: skill `fw-build-burn-utopx` §1.

**Never skip `git submodule update` after `worktree add` or a checkout**: a fresh worktree starts
with empty submodule directories, and `git checkout -b` does not move submodule working trees, so a
reused tree still holds the previous branch's pointers. Symptom: the build
fails inside `hca_fwv_shared/autogen/*`, e.g. `'hca_fwv_ib_pkt_hdr_boeth' was not declared in this scope`
— it looks like a broken baseline but is a submodule at the wrong commit. In `git status --porcelain`,
a bare `M <submodule>` = pointer moved; an `M <submodule>` that persists *after* the update with only
an untracked `compile_commands.json` inside = harmless build residue (diff shows `<sha>` vs
`<sha>-dirty`).

Run that binary on the test box over NFS (`/auto/fwgwork1/...` is mounted there, no copying):

```bash
ssh <box> 'cd /auto/fwgwork1/$USER/utopx_<ticket#>/<artifacts path> && sudo ./utopx.exe --device=... '
```

### 4c. Pin each repo to the failing version

**Never work from a stale detached HEAD left by a previous ticket**: it carries no label, and
`git branch` shows only `* (HEAD detached from rel-12_48_1633)` — possibly another line than the
ticket's (#5184928: clone detached on the **48** family, ticket on **51**; the same function was a
`static inline` in `include/hca_cap.h` there but a real function in `src/main/hca_cap.c` at the
correct tag). A clone's own checkout is where such a HEAD sits, so pin in a new per-ticket worktree
off the repro clone, on the **investigation/pin branch `<ticket#>_<topic>`** at the failing version —
never a detached HEAD, never the clone itself. Name it after the ticket and the topic, no personal
names; append the version only when it carries information (e.g. an official+1 build tag):
`5285522_virtio_net`, `5285522_virtio_net_0291`. Edit only the repo the fix needs (often just
`golan_fw2`; the test tool frequently needs no change).

Once pinned, the working tree is authoritative — grep/read/edit normally, no `git show <tag>:<file>`.

For **each** repo (FW source + test tool):

```bash
C=/auto/fwgwork1/$USER/golan_fw2              # test tool: C=/auto/fwgwork1/$USER/utopx2
W=/auto/fwgwork1/$USER/golan_fw_<ticket#>     # test tool: W=/auto/fwgwork1/$USER/utopx_<ticket#>
git -C $C fetch --all --tags   # ALWAYS first — release tags are often remote-only; a
                               # "rel-X-NNN-g<sha>" describe = stale tag list, not a missing tag
git -C $C worktree add -b <ticket#>_<topic> $W <tag-or-sha-from-Phase-2>
cd $W
git submodule update --init --recursive    # submodules' recorded commits may need a fetch
git describe --tags                        # confirm WHICH tree you are on (see below)
git log -1 --format='%H %ci %s'            # verify it matches the regression
```

Worktree traps (background checkout, `git submodule status` lying in a fresh worktree, renaming):
skill `fw-build-burn-utopx` §1.

**Moving tags lie — branch from the SHA and confirm with `git describe --tags`.**
`regression_stable_tag` moves: the run log's `regression_stable_tag-0-g3207d90` records where it
pointed on the day of the regression, while your local copy may be months stale (#5184928: local tag
at a 2026-05-31 commit vs the regression's `3207d90` from 2026-08-01). `git describe --tags` on the
SHA (e.g. `host_fwv_20260801_FW_version_51_0098_branch_master`) independently confirms date and FW
line — a much stronger check than the moving tag name.

Keep a table — branch / tag / SHA are interchangeable references; the two repos often use different
branch-naming conventions, so never assume a shared branch name:

| Repo | Branch | Tag | SHA |
|---|---|---|---|
| <FW source> | <branch> | <rel-tag> | <sha> |
| <test tool> | <branch> | <describe-tag> | <sha> |

## Phase 5 — Reproduce the regression's INI

```bash
mkdir -p <repo>/regression_ini
cp <default_ini path>  <repo>/regression_ini/default_<name>.ini      # reference
cp <new_ini_file path> <repo>/regression_ini/burned_<session>.ini    # the one you burn
diff <repo>/regression_ini/default_*.ini <repo>/regression_ini/burned_*.ini
```

Understand the diff: `BurnFw.py` appends device-specific overrides (BAR/PCIe/DDR-mapping, emulation
flags, etc.) that the release default lacks — often what makes the device behave like the regression. Cross-check against
the ticket's `dump_nv_data_*` attachment (the NVconfig the failing run actually had). **Never add your
own nvconfig/INI rows** (e.g. to chase a side feature): they shift FW caps the test tool cannot
predict and produce look-alike failures. Burned INI == the regression's, exactly.

## Phase 6 — Burn FW + INI to the device

**Path A — no source edits (INI only):** burn the official `.mlx` + your INI, no build (same as
`BurnFw.py`):

```bash
ssh <test machine> 'cd <FW source repo> && \
  $HOME/.usr/bin/jmake --burn --device <MST device> \
      --firmware <official .mlx> --ini <repo>/regression_ini/burned_<session>.ini'
# Do NOT chain --fw-reset here. If jmake hits a root-squashed-NFS "Permission denied"
# writing image.bin into the repo, burn with direct mlxburn instead:
ssh <test machine> 'sudo -E env MFT_ICMD_TIMEOUT=60000 \
    mlxburn -d <MST device> -fw <abs .mlx> -conf <abs INI> -force'
```

**Path B — FW must be built from source edits:** local builds reject **even** subminor versions. Check
out the **next odd** release tag (same code, only the version tag differs), build with
`jmake -o --clean --models <model>` → `<repo>/fw-<device>.mlx`, then burn as in Path A. Which image to
use when, and proving the odd tag equivalent: Phase 9.5 step 2.

## Phase 7 — Pivot FW + bring up drivers (mirror the regression's per-test setup)

The ticket's `fw_reset_*.log` / `modprobe_udriver_*.log` / `print_mst_devs_*.log` attachments are the
authoritative bring-up sequence. Generic shape:

```bash
ssh <test machine> 'sudo $HOME/.usr/bin/jmake --device <MST device> --fw-reset'   # pivot flash→running
ssh <test machine> 'sudo flint -d <MST device> q | head -5'                       # verify flash==running
ssh <test machine> 'sudo modprobe <driver>'                                       # e.g. udriver
# Device-specific gotchas to mirror from the logs, e.g.:
#   - clear any management-channel "drop"/safety mode before the test uses it
#   - restart the management daemon if --fw-reset left it down
#   - for SoC/DPU devices, wait for the ARM/OS to finish booting (until-loops, not bare sleep)
```

Prefer the wrapped `jmake --fw-reset`: on boxes where only a 3rd-party driver is bound, bare
`mlxfwreset` may refuse (`Tool is owner: Not supported`). What the wrapper adds: jmake reference at
the end.

**To match the regression bit-for-bit, run its OWN per-test reset script** — the exact cmd is in the
`fw_reset_<key>` step's `log.txt` (`Executing cmd: …`). For HCA-core:

```bash
ssh <machine> 'sudo /auto/mswg/projects/fw/fw_ver/hca_fw_tools/fw_reset/fwreset.py \
    --debug --next_driver <driver> -d 0000:<pci>'   # e.g. --next_driver udriver -d 0000:ca:00.0
ssh <machine> 'sudo modprobe <driver>'              # the separate modprobe_udriver step
```

- Success prints `FW reset successful: uptime was reset. Before: N, After: ~15` and rebinds the driver.
- Loops `Unbind attempt … is opened by process: <pid>`, then errors `Device is busy` → a stale daemon
  holds the device: kill it (§3c) and retry.
- **DPU/BlueField: never power-cycle to recover a wedged run or to pivot between runs** — use
  `jmake --fw-reset --device <MST device>`, or, to match the regression bit-for-bit, its own
  per-test reset script above. On BlueField `*_ARM_AGENT_*` setups during a repro, use the
  regression's own reset, not `jmake --fw-reset`: run the logged `fw_reset` command (for BF3,
  `.../etc/mustang_fw_reset.sh --debug --reg_debug --unbind_flow --dont_kill_utopx --next_driver
  udriver --remove_rescan --ignore_other_hosts -d <pciconf0>,<pciconf1>`) from a clean sudo
  environment (no `PYTHONPATH`), then `echo "DROP_MODE 0" > /dev/rshim0/misc`, then utopx — that
  keeps the ARM in the bare-metal-agent state. A power-cycle boots the ARM from eMMC into DOCA, and on ARM-agent
  setups utopx's BareMetal ArmAgent then dies before the first op
  (`ArmAgentApiBareMetal.cpp:20 Bare metal arm agent timeout`). Power-cycle a DPU only when a
  pending NV change needs a cold boot (`mlxfwreset -d <MST device> q` answers
  `There is no supported reset-level`), then confirm the ARM is alive before running (skill
  `bluefield-fwconfig`). Non-DPU NIC boxes: Phase 10.

## Phase 8 — Run the EXACT command + seed and watch for the signature

Take the command **verbatim** from `run_case_<key_id>.log` / `run_case.cap` — same scenario `.conf`,
`--iter`, `--ops_per_it`, `-e`/`--extra_constraints` knobs, `--timeout`/`--case_name`. **Never drop,
add, simplify or reorder an argument** (e.g. lowering `--iter` to go faster can hide a failure that
only surfaces at the original count). Run from the regression's working dir. **Pin the seed** from
`run_case` (`To rerun use seed <N>`):

```bash
LOG="$HOME/repro_<NNNNN>_$(date +%Y%m%d_%H%M%S).log"
ssh <test machine> 'cd <test tool repo> && \
    sudo ./<test binary> <exact args from run_case> --seed=<N> 2>&1 | tail -300' \
    > "$LOG" 2>&1 &
wait $!
# Look for the SAME signature (success = it reproduces):
grep -E '<failure signature>|TEST FAILED|FATAL|Test-status' "$LOG" | head
ssh <test machine> 'ls -lt <test tool repo>/verix_test_*.log | head -1'   # full log for analysis
```

- **One command per ssh, one reused connection per box, closed before any reboot** — the ssh rules:
  skill `lab-box-login` §1.
- In an agent session, launch with the long-running-job method in `references/hosts/<runtime>.md` and
  observe that same job to completion; never start a duplicate because output is quiet.

**Debug logging: re-run with `--xml_conf_file debug_conf.xml`** (change it in the `tsr_args`/run
command). The regression's `--xml_conf_file conf.xml` is INFO level and omits the keyed `KDEBUG(...)`
internals. `debug_conf.xml` ships in the utopx repo (same dir, includes `conf_keys.xml`) and sets
`log_file_verbosity=debug` + screen=debug and the key default to `debug`, so a key not listed in
`conf_keys.xml` (e.g. `PACKET_HANDLER`) is captured. It shows *which* internal path failed — e.g. the
steering resolver's `KDEBUG("PACKET_HANDLER", …)` lines (`No steering dest capsules found` /
`ERROR: …` / `Failed to translate steering dest…` / the full `steering_path:` dump). Do NOT hand-edit
`conf_keys.xml`; `debug_conf.xml` is the supported switch. Output: `/tmp/verix_test*.log` (and stdout).

## Phase 9 — Confirm / handle divergence; env drift recovery

**Reproduced** = the local log shows the **same** failure signature (same struct/field, same fatal);
record the seed and the verix log path.

**Not reproduced** (passes, or fails differently):
- Re-verify the three artifacts: Phase-2 versions, INI diff vs `dump_nv_data`, test-tool *binary*
  (env drift below). With the seed pinned, a *different* failure usually means an artifact mismatch
  (a stochastic tool exposes different bugs per seed).
- Try the failing op directly from `oplist`; widen seeds only once the pinned seed is confirmed to
  match the regression's.
- **A "different fatal" can be the SAME bug at another device state** — common for *bring-up* bugs.
  E.g. ticket signature `cmd_hca_cap actual cap < expected` (caps read `0x0`), while a dirtier device
  hits an earlier `VerifyHealthBuffer` FW assert (`ext_synd 0x817e severity 0x5`) in
  `PreTest/QuickInit` — both mean "device didn't bring up". The fatal's **VHCA topology dump**
  confirms it: stages stuck at `HCA_STAGE_QUERY_HCA_CAP_MAX_BY_TRUSTED_HCA`/`HCA_STAGE_DISABLED_HCA`
  with `phy port up: 0` / `vport_state=PORT_DOWN`. Decode the health-buffer `fw_version` field to
  confirm FW (e.g. `0x52300660` = `82.48.1632`). To steer toward the *exact* signature, recreate the
  regression's clean state: **fresh re-burn FW+INI → regression fw_reset → re-run** (never
  power-cycle a DPU/BlueField box — Phase 7). Bring-up bugs are often non-deterministic across
  device state even with a pinned seed — record the divergence honestly rather than forcing a match.

**Env drift (a regression ran on the box since):** FW re-burned, repos on regression tags, and the
test-tool **binary recompiled** — `git checkout` reverts *source* only, so the on-disk binary
disagrees and produces parse errors / cap mismatches / ICMD BAD_PARAM that masquerade as the bug.
Recover in order: repin both repos (Phase 4) → **rebuild the test-tool binary clean**
(`jmake -c -o`, autogen trees wiped first — skill `fw-build-burn-utopx` §6; verify its mtime is
fresh) → reburn FW+INI (Phase 6) → pivot (DPU/BlueField box:
`jmake --fw-reset --device <MST device>`, never a power-cycle — Phase 7; non-DPU NIC box:
power-cycle) → re-do bring-up → run a **baseline** to confirm a clean env → then the repro.

## Phase 9.5 — Verify a candidate fix ON THE BOX (before any Gerrit commit)

A fix that has not run on hardware is a **proposal**, not a fix — sound-looking reasoning has
repeatedly been wrong on this codebase (see `key-learnings.md`). Phase 11 is reached only from a
verified run. The fix may live in `golan_fw2`, in `utopx2`, or in **both** — never assume FW-only; a
test-tool defect (a stale expectation, a check that no longer matches intended HW behaviour) is an
equally valid outcome. Check which repo(s) your change touches before building.

1. **Before building, write the hypothesis and the diff into the Investigation log** — root-cause
   statement, code evidence (`file:line`), attribution (`git blame` / `git log --author`), and the
   exact diff under test. Written afterwards, "it passed" is unauditable.

2. **Build the candidate** on the ticket's named private branch (Phase 4 pin), clean: `jmake -c -o`.
   **Read the build log — not the exit code**: jmake prints `BUILD SUCCESS` and exits 0 even when a
   stage died. utopx: confirm the binary's mtime is fresh.
   - **Even-subminor gate (FW only; CLAUDE.md hard rule 4):** a local build of an even `SUBMINOR` is
     refused outright (`Even-numbered FW Subminor Version can only be compiled by official build`), so
     building the released version yourself always means **official + 1**. Against an even release
     tag, build the **next odd** tag (same code, only the version stamp differs) — and build the
     **control from that same odd tag**, so patched vs control differ by exactly one variable.
   - **Which image when:** *reproducing* (Phases 6–8) → the **official released `.mlx`**, never a
     local build (only the bit-exact image the regression ran can prove the ticket's failure);
     *verifying a fix* (this phase) → the local next-odd build, control included.
   - **Prove the odd tag equivalent; do not just assert it.** Code-level:
     `git diff rel-X_YY_<even> rel-X_YY_<odd>` should touch only `Version` and the auto-generated
     version vector in `adabe/upgrade_ini_defaults.adb`. Behavioural (one extra run — what you show a
     reviewer): on a **clean NV**, the **unpatched odd build** vs the **official even image** on the
     same seed must give the same signature, count and `LOG_OP` depth (#5285522: official `0290` →
     `0xac5816` x4, GoldenTlv 0, `LOG_OP` 252; local unpatched `0291` → `0xac5816` x4, GoldenTlv 0,
     `LOG_OP` 253 — equivalent).
   - Record the version correspondence in `FINDINGS_<ticket#>.md` section 2: which artifacts are
     byte-identical to the ticket's, which single one deviates and why ("did you actually run what
     the ticket ran" is a reviewer's first question — answer it in the document, not in chat).
   - **A locally built image is not the official release image**: even at an identical source tag it
     may expose a different NV/TLV inventory and die in init before reaching the bug (#5285522:
     `GoldenTlv: data length exceeds maximum supported size`, 516 > 255, zero `LOG_OP` lines). That
     control is VOID, not a pass — re-burn the **official** `.mlx` and confirm the original signature
     still reproduces before blaming anything. (Phase 10 attributes the same GoldenTlv signature to NV
     state accumulated over repeated runs.)

3. **Deploy it.** FW fix → **reburn** (Phase 6) + pivot (`jmake --fw-reset`); never pivot alone and
   assume the new image is live — a stale flash silently masks the fix and you "verify" the old
   binary. utopx fix → rebuild and run *that* binary over NFS (never patch the deployed
   `/tmp/mars_tests/...` tree — §4b; also a hard rule in SKILL.md). Both → do both before the rerun.
   Then redo the regression's own bring-up (Phase 7: its `fw_reset` / `Fwreset.py --next_udriver` /
   `modprobe`), not a cleaner equivalent.

4. **Rerun the EXACT pinned command + seed** from `run_case` (Phase 8) — same scenario, `--iter`,
   `--ops_per_it`, same everything; not a shortened or widened run.

5. **Judge the run by how it ENDED, not by the signature counters:** `TEST PASSED|FAILED` /
   `To rerun use seed` / `terminate called` / `SEGMENTATION FAULT` / whether the tool even initialised
   (zero `LOG_OP` lines = it never ran an operation). Zero target signature followed by a crash, or
   death before init, is **VOID — not a pass**.

   **The signature disappearing does NOT mean the bug is fixed — read the NEW fatal.** #5285522: the
   patch removed `0xac5816` completely (`LOG_OP` 252, the test ran properly), yet the run ended
   `TEST FAILED` on `FailOnDiffInner: actual cap fields can't be less than expected` (three cap fields
   `0x0` against an expected `0x1`). The defect had **two halves**; the first patch fixed one:

   | Half | What it does | Where |
   |---|---|---|
   | admission check | may this query proceed at all | `cmdif_checks.c` opmod switch |
   | **data fill** | what gets written into the returned struct | `cmdif_commands.c` → `fill_*_caps()` → the `get_*_cur_cap()` getters |

   Both consulted the same tightened `*_cur_cap_sup()` helper, so patching only the gate turned
   "request refused" into "request answered with zeros". **Rule:** a cap/feature query has separate
   check and fill paths, and a semantic change underneath a shared helper hits both — grep every
   caller of the helper you change (`grep -rn '<helper>' src/ include/`) before declaring the fix
   complete; the compiler will not find them, and the test shows only the first one that trips.

6. **Run the control: same tree, same tag, same configs, same command, same seed, patch removed.** It
   must still show the signature; if it does not, something besides your patch changed the outcome
   and the verification proves nothing — stop and find out what. Without it, a pre-existing failure
   and one you introduced look identical. (The most-skipped step.)

7. **Acceptance bar — a full green run is NOT required** (long randomised runs, 200 iter x 50 ops;
   unrelated failures are common and not yours to fix): **getting past the original failure point
   with no similar fatal remaining counts as a fix.** Classify what is left instead of counting
   `TEST FAILED`:
   - **target signature gone** — necessary, not sufficient;
   - **no *akin* fatal** — nothing failing for the *same root cause* down another path (#5285522:
     `virtio_emulation_cap: <field> ... expected 0x1 Actual 0x0` — same cur/max semantics, different
     code path ⇒ that run was PARTIAL, not fixed);
   - **it got further** — `LOG_OP` count vs the unpatched control; the same depth means you probably
     did not clear the original blocker;
   - **anything else** (traffic, steering, an unrelated checker) = unrelated failure ⇒ still a fix.

   Encode this in the run script's verdict rather than eyeballing it, and state in
   `FINDINGS_<ticket#>.md` §6 which remaining failures you judged unrelated and why.

   Signs you loosened a check **too far**:
   - **`LOG_OP` *below* the unpatched control** — the test now fails *earlier*; a real fix moves the
     count up, never down (zero target signature + a shorter run = a regression wearing a success
     mask, which is why the verdict must compare against the control's depth, not just "signature
     gone").
   - **A field mismatch that flips direction** — the bug was FW under-reporting
     (`expected=0x1 Actual 0x0`); over-loosened, the checker complains the other way
     (`expected=0x0 Actual 0x1`): FW now advertises a capability the test knows that function must
     *not* have. Read the direction of a mismatch, not just its presence.

   **A gate added by a named bug fix is a strong prior that its strictness is deliberate**: check
   `git log -S` on the line before relaxing it, settle it with one build rather than an argument, and
   accept the answer when the run says the gate was right. Record the failed experiment in §5 as a
   rejected attempt with the evidence, so nobody re-runs it.

8. **Adjacent-case sanity pass** — a handful of neighbouring cases/ops, to catch a regression the fix
   itself introduces; a fix that kills the target signature while breaking its neighbours is not done.

9. **Record every run** in BOTH the Run log table (one row per run, note which build) and the
   Investigation log (before/after signature, control result, explicit verdict). Verdicts:
   `VERIFIED` / `VOID - <reason>` / `NOT REPRODUCED` / `PARTIAL` — never a bare pass/fail.

10. **Only a VERIFIED fix proceeds to Phase 11.** If verification fails, go back to root-cause work and
    **keep the failed attempt in the log** — the record stops the next attempt repeating it.
    - **Do not "improve" a verified patch on the way to gerrit.** Push exactly the expression you
      verified; a cleaner or more general form is a **new, unverified change** that needs its own run
      ("strictly better" reasoning is not evidence). #5273244: the verified host-count bound
      `DEVICE_INFO.GetNumOfNonSnHosts()` (mismatch 6 → 0, no crash) was swapped, unrun, for
      `vhca->GetDevice()->GetMaxNumNonSmartNicHosts()` (also covers non-ECPF mode) — mismatch still 0,
      but it **segfaulted**; only the control (unmodified deployed binary, same seed: 6 mismatches, no
      segfault) showed the crash was self-inflicted.
    - **Name patches by verdict the moment it is in:** `FIX_<topic>.patch` for the one that passed
      (exactly one file), `REJECTED_<vN>_<why>.patch` for each disproved candidate — a superseded
      attempt still called `fix_*` is indistinguishable from the deliverable. Built images likewise:
      one named copy per candidate with its md5, since `jmake` overwrites the same output file every
      build.

11. **Write / finish `FINDINGS_<ticket#>.md`** (from `templates/findings.md`), starting as soon as a
    root-cause hypothesis exists — not deferred to "the write-up later". It is the deliverable handed
    to Peter and the code owner, produced whether or not the Gerrit commit happens in the same session.

## Phase 9b — Codify the repro: env_rebuild + per_run from the lab-box template (as soon as Phases 1–2 are decoded)

**Write both scripts as soon as Phases 1–2 are decoded — do NOT wait for the box or for a confirmed
repro.** Everything they need comes from the session tarball, not the hardware. Reserving a contended
box can take hours: write them in that window, so you run instead of type when the lock lands and the
first (most error-prone) attempt is already scripted.

**Start from `templates/lab-box/`, never from a blank file.** Copy its four files into
`<task dir>/tools/`:

| File | What it is | Edit it? |
|---|---|---|
| `lab.conf` | everything task-specific: box, card, image, NV recipe, tool, verdict `MODE`, `count_signal`, and the hooks that replace a default step | **fill it in** |
| `env_rebuild.sh` | from the dev box, once per lock: guards, box setup, `--cycle` / `--burn`, gates | no |
| `per_run.sh` | on the reg box, once per attempt: guards, gates, reset, run, verdict as the exit code | no |
| `selftest.sh` | runs both scripts against stubs, no box needed; checks every exit path | run it after any script change |

- Change a script only when no hook can express what the task needs, and record why in the ledger.
  The scripts implement every rule of this phase; a hook you write must keep them too.
- A second box or a control group is a second conf that sources `lab.conf` and overrides a few
  values; both scripts take it with `--lab <file>` (the end of `lab.conf` shows the shape).
- `MODE` says what exit 0 means: `repro` — the signature appeared; `fixverify` — the defect's trigger
  was present and its signature was not; `feature` — the new path ran and the run passed (skill
  `feature-delivery`, Phase 4). `count_signal` decides it: the defect's signature verbatim, or for
  a feature the lines only the new code emits.

Counter false confidence with honest labelling and opt-in danger, not delay:

1. **`VERIFIED=` in `lab.conf` stays empty until a run reproduces the exact signature** (feature:
   produces the intended outcome); while it is empty both scripts print `!!! UNVERIFIED !!!`.
   Correct structure is not verification: a pair with a multi-factor verdict, before/after PCI
   snapshot + diff, pre-fix-binary guard and a hard baseline gate still produced the false
   `REPRO SUCCESS` dissected under Verdict discipline. **Bypassing a step is not running it**:
   burning by hand because the script's burn path is broken leaves that path unverified — keep
   `VERIFIED=` empty and record the bypass in the ledger.
2. **Every destructive path is opt-in** — `env_rebuild.sh` only verifies unless given `--burn`, and
   then asks for a typed confirmation (`--yes` skips it).
3. **Ownership guard first** — both scripts refuse to touch the box unless Noga's
   `Status.lock_owner` is you. A `hostname` check is not enough: the nightly regression runs on that
   same box, and an `mst start` / `Fwreset` inside someone else's live session corrupts it.
4. **A gate that cannot be grounded yet may start as a warning, and becomes a hard gate the day the
   first known-good environment exists** — copy that environment's values (`EXPECT_FW`,
   `WANT_CLASSES`, `NV_RECIPE`) into `lab.conf` then. A warning nobody promotes lets a drifted box
   through: a PF that came back as InfiniBand still passes a function-count check.

### `env_rebuild.sh` — from the dev box, once per lock

In order: Noga owner → nothing running on the box (a bounded `ps`: `/proc` blocks behind a D-state
process, so a timeout is a diagnosis) → every check that may refuse (`--burn`: input files, the
typed confirmation, the offline image gate) → `setup_box` → with `--burn`: `nv_restore`, detached
`mlxburn` with its log polled, `make_live`; with `--cycle`: `make_live` only → verify gates →
`ENV_REBUILD_RC=<rc>` as the last line, the same value as the exit code. A run that refuses must
refuse before it changes anything: a `setup_box` install followed by a refused burn leaves the box
half-changed. Run it again after anything that resets or re-provisions the box, your own
power-cycles and every MARS session that took the box back included; redoing the equivalent by hand
is how a step silently stops being part of the procedure.

**Use the smallest mode that covers what changed**, and ask before the heavy ones on a box whose
environment is already set up:

| What changed | Mode |
|---|---|
| nothing, or not sure (start of a session, after a run that went wrong) | default: verify only |
| something that only a cold boot loads — a kernel module `setup_box` installed, a pending NV value | `--cycle` |
| the image, or the NV must be redone (after MARS had the box, a different build) | `--burn` |

- **Offline image gate** — `mlxburn -wrimage` + `flint -i` on the dev box: the image's PSID must be
  the card's and its version `EXPECT_FW`. Nothing touches the card before it passes.
- **NV is part of the environment.** Burning and power-cycling leave NV as the last user left it,
  so `nv_restore` puts it back: `mlxconfig reset`, then `NV_RECIPE` with at most 4 parameters per
  `mlxconfig set` and Next Boot read back after each (global hard rule 2). The known-good NV is not
  the factory default — after `reset` the card carries no TLVs at all. On a box in a MARS rotation
  it is that setup's own recipe: `tar -xzOf <sid>.tgz | grep -a 'running cmd: sudo mlxconfig'`.
- **Making it live** — NIC box: `jmake --power-cycle`. DPU/BlueField box: never a power-cycle to
  pivot (Phase 7) — `jmake --fw-reset --device <dev>`; power-cycle only when `mlxfwreset -d <dev> q`
  answers `There is no supported reset-level` (a pending NV change needs a cold boot), and have
  `setup_box` confirm the ARM is alive (skill `bluefield-fwconfig`; `tmfifo_net0` being up or
  pingable proves nothing).
- **Verify gates** — FW version (flash, and running where `flint` reports it), the PCI class codes
  of the 15b3 functions in BDF order (`0200` Ethernet, `0207` InfiniBand, `0801` DMA controller), and
  every `NV_RECIPE` parameter's **Current** value. The raw NV TLVs are printed for the record and never
  gated, and neither is "no Current ≠ Next": a TLV's writer ID depends on who wrote it, TLVs carry
  fields outside the recipe, and a known-good state can carry a pending value that never takes
  effect.
- **Assert the property, not the presence** — anything you were tempted to write as a `note` for the
  human is a check you have not written yet. `lsmod | grep -c udriver` answers "is a module loaded",
  never "is it the right build", and prints a reassuring `1` for a driver that cannot run your test
  (udriver `3.07` predates the `udriver_dma_map_v2` API the PSF feature calls; every run then hangs
  inside an ioctl). Check the symbol you call in the header, a recorded commit hash
  (`/bin/udriver_commit_hash`), or `flint q` for a version.
- **The udriver on the box must be the one utopx is built against** — `UDRIVER_VERSION` in the
  tree's `build.sh`, an artifact under `/.autodirect/mswg/projects/fw/fw_ver/artifacts/udriver/`.
  The official way to install it is `install_udriver` (`.fwvalias` function `install_udriver_func`):
  it clones `hca_fw/udriver` master on **the host it runs on** — run it on the box through `SSH`
  with `.fwvalias` sourced, not on the dev box — and runs `install.sh`, which installs the library,
  the headers and the `.ko` and loads nothing. The new library is in use at once and the new module
  only after `make_live`, so install, then `--cycle`, then run; a box in between runs a new library
  on an old module. Compare `/bin/udriver_commit_hash` with the pin, and once loaded,
  `/sys/module/udriver/srcversion` with `modinfo -F srcversion udriver`.

#### ssh from a script, or from an agent's shell

The scripts follow the ssh rules of skill `lab-box-login` §1: BatchMode on every ssh and
`unset DISPLAY`, one ControlMaster per box with ServerAlive, the master closed before a power
cycle, and a new boot id read over a fresh connection before anything checks the rebooted box.

### `per_run.sh` — on the reg box, once per attempt

In order: guards (this host, not root, Noga owner, no tool running, the tool exists; `FIX_COMMIT`
absent for `repro`, present for `fixverify`) → identity (tree HEAD, md5 of the executable and its
libraries) → FW gate → **baseline gate**: PCI classes and `NV_RECIPE` Current, before every run and
not only after the rebuild — the lock is advisory, and MARS or another user can rewrite NV in between
→ pre-run `reset_device`, a hard gate → PCI snapshot and a `/dev/kmsg` marker → EXIT trap →
`run_tool` → PCI diff and the kernel log since the marker → verdict. Everything a run produces lands
in `<log dir>/<RUN_NAME>_seed<seed>_<stamp>.*`.

- **`reset_device`** — default `jmake --fw-reset` plus binding every 15b3 function to udriver. A
  repro mirrors the regression's own per-case reset (`Fwreset.py --next_udriver`, i.e.
  StartDriverAndBind); a CX8 that exposes a PSF needs the PSF-aware reset (skill
  `fw-build-burn-utopx` section 5). `lab.conf` spells out both replacements.
- **ARM agent** — a DPU / ARM-agent suite runs the regression's `check_arm_agent.py` before every
  attempt and stops when it fails; `lab.conf` shows it as a `before_run` hook.
- **Kernel evidence** — a DMAR fault, `Call Trace` or soft lockup between the marker and the end of
  the run makes the run not clean even when the tool printed `TEST PASSED`.
- Running the case more than once also requires clearing NV between runs (Phase 10).

### Verdict discipline — the single most important part

Build the verdict from **independent** factors; the *direct evidence of the defect* decides, and a
downstream symptom (a later script failing) only corroborates:

| Factor | Role |
|---|---|
| baseline PASS | **precondition** — the pre-run reset is a hard gate |
| tool actually initialised | **validity** — if it died at startup the run is VOID, not "reproduced" |
| expected syndrome/signature present | **trigger** — proves the defect path was entered |
| **before/after state diff non-empty** | **CORE** — proves the defect's actual effect |
| downstream script failure | **corroborating only — NEVER decisive** |

Report each factor separately — never collapse to pass/fail. `per_run.sh` prints the factors and
maps the outcome to an exit code (`RUN VOID` / `NOT REPRODUCED` / `FAILED DIFFERENTLY` /
`REPRO SUCCESS`; the table is in its header). When the signature can appear without the defect's
trigger or its core effect, make `count_signal` require them too (the PCI snapshots sit next to the
log as `<stamp>.pci_before.txt` / `.pci_after.txt`): a signature without them is `PARTIAL`, not a
repro.

What a single-signal verdict hides (#5138907): a harness declared `✅ REPRO SUCCESS` on
`post_run_fwreset_rc != 0` alone, while every independent factor said the run proved nothing:
- **precondition** — the baseline Fwreset was already failing on an unrelated
  `PermissionError: /dev/rshim0/misc` (Phase 9c);
- **validity** — the tool never initialised (`ARM agent replied with error`,
  `Udriver init failed: no devices found`, exit 255);
- **trigger** — the syndrome appeared **0** times (the script itself printed "syndrome NOT seen");
- **core** — the PCI address it cited had shifted for an unrelated reason (topology trap below).

### Harness traps

- **Never `N=$(grep -c PATTERN "$LOG" || echo 0)`.** `grep -c` already prints `0` **and** exits 1 on
  no match, so `N` becomes `"0\n0"`, not `"0"`, and every `[ "$N" = 0 ]` downstream takes the **else**
  branch — the verdict fails towards good news (genuinely zero feature fingerprints printed
  `NEW PATH EXERCISED`), which reading the output never catches. Use `|| true`, and sanity-check a
  counter by feeding it a pattern you know is absent.
- **Pair every error counter with a progress counter** (operations logged, iterations reached, log
  bytes growing) and conclude nothing from the absence of errors: `FATAL == 0` also fits a tool that
  stopped producing output long ago, so an error-only verdict scores a deadlock as your best run. Hang
  tells (e.g. the tool blocked inside an uninterruptible driver ioctl): `LOG_OP` count 0, a log far
  below normal size (44 KB vs ~500 KB), and **`pgrep` itself timing out** — walking `/proc` blocks on
  a `D`-state process; only a power-cycle cleared it. A hanging process listing is evidence, not a
  flaky box.
- **"That failure is just the environment" is a hypothesis and needs a control like any other.**
  Untested, it poisons later experiments — you credit its appearances and disappearances to whatever
  you changed. Before spending a second run on "is it flaky", spend it on **a build where the feature
  cannot be involved** (same `.mlx`, same tool, same seed, INI with the feature gate **off**), and give
  the env script a `--no-<feature>` switch so that control is one flag away.
- **A recovery script must assume the box is wedged**: an `env_rebuild` idle guard running `pgrep`
  hangs on the same D-state process (`/proc` stalls). `timeout` every probe and treat a timeout as a
  *diagnosis* ("something is blocking /proc — power-cycle"; on a DPU/BlueField box
  `jmake --fw-reset --device <dev>` instead, Phase 7), not something to wait out.
- **Check a new measurement script against one hand-run case** before believing any rate it reports:
  its first numbers may describe the script, not the system (a too-short post-power-cycle wait reports
  "box did not come back" for a box that is up and reachable).
- **The exit code must carry the verdict.** A script that prints "did not pass cleanly" and then
  exits 0 turns every failed run green for whatever wraps it (a batch loop, CI, a summary grep on
  `$?`). Give each verdict class its own non-zero code — e.g. 3 RUN VOID, 4 invalid control group,
  5 new path never entered, 6 ran but failed (tool rc != 0, no PASS marker, or FATAL > 0) — list
  the table in the script header, and end with an explicit `exit "$VERDICT_RC"`. Check that the
  tool's own rc is 0 on a passing run before folding it into the verdict.
- **Reset after the run from an EXIT trap, not only before the next one.** Install
  `trap on_exit EXIT` and `trap 'exit 130' INT TERM` just before the tool starts. `on_exit` saves
  `$?`, waits a bounded time (e.g. 60 s) for the tool process to exit, then resets; if the reset
  fails or cannot run (tool still alive), it reports that and turns an otherwise-0 exit into its own
  non-zero code while keeping any earlier non-zero code. Never mark the reset done before trying it.
  A trap does not cover SIGKILL or a wedged box, and bash runs it only after the foreground pipeline
  ends, so keep the pre-run reset and its success gate. A local Ctrl-C reaches a remote script only
  through `ssh -t`.
- **Derive the log directory from the binary under test** (`LOGDIR=$(dirname "$TOOL")/logs`) and
  print the binary identity every run — the worktree's HEAD, the md5 of the executable and of its
  libraries — so each log says which build produced it. Build a control in the ticket's own
  worktree (switch to the control commit, build, run, switch back) rather than in a second
  worktree; the identity line keeps its evidence apart from the stack under test.
- **Test the exit paths with stubs before trusting them.** `selftest.sh` runs both scripts against
  stubbed `sudo`, `ssh`, `flint`, `mlxconfig`, `lspci`, Noga and the reset, and checks every outcome
  (pass, fail, void, control leak, reset failure, SIGTERM, drifted baseline, busy box); extend it
  whenever you change a script.
- **Topology trap — an env-setup side effect can perfectly mimic the bug's signature.** On #5138907
  the signature was "PCI address changed"; it did change (81→83) — because `mlxconfig` had enabled the
  emulated PCIe switch, which inserts bridges at 81/82 and moves the endpoints to 83: expected, and
  unrelated to the bug. The baseline is the topology captured **immediately after `env_rebuild` and
  before the tool runs** — never an earlier snapshot, never a bus number reasoned out rather than
  observed.


### The box is re-provisioned daily: script the rebuild

The nightly regression locks and re-provisions the box, scrambling whatever you set up — the
installed tools and the NV alike (the session runs its own `mlxconfig set`, and other users' utopx
runs randomise NV): rebuild the repro environment at the start of every session, as **one command**
(`env_rebuild.sh --burn`). A ticket's own repro steps can be followed exactly and still fail because
**they assume an already-provisioned box** (the reporter ran them right after a regression,
toolchain already in place).

**Find what the regression installs** — the `log.txt` of its provisioning step (`install_Tools.cap`,
`install_Lock_Tools.cap`) prints the exact command and the pinned versions:

```bash
S=$(tar -tzf <sid>.tgz | grep install_Tools.cap | head -1 | sed 's|/install_Tools.cap||')
tar -xzOf <sid>.tgz "$S/log.txt" | grep -iE "install|version"
```

That yields the umbrella invocation (e.g.
`install_tools_per_branch.py --install_ofed true --install_mft true --install_udriver true …`) plus the
exact OFED / MFT / driver versions. **The umbrella may not run on your box's OS**: it shells out to
sub-wrappers via their shebang (system python), and the older-python lab RegTools die in dependency
imports on a newer distro — call each sub-wrapper explicitly with the lab's own python
(`MARS_PYVERSION`, e.g. `/auto/sw_tools/OpenSource/python/INSTALLS/python_3.7.5/.../python3`).

**Provision from `setup_box`** — directly, or through a `tools/provision_<box>.sh` it calls:
idempotent (skip what is present, `--force` to redo); long steps launched detached, so an SSH drop
cannot kill a 20-minute install; a verify block at the end. Order matters — a driver-stack install
with `--force --all` typically **removes** other tool packages, so reinstall them after it, not
before.

**A missing component masquerades as "the documented steps don't work".** Before debugging the
procedure, check the box has what it assumes: MFT present, driver stack installed, the tool's Python
deps, NFS mounted, the device visible in `lspci`.

## Phase 9c — Reg-box realities that silently invalidate a run

Check these BEFORE blaming FW, the tool, or your own harness.

### The ticket's own repro steps outrank your script

If the reporter wrote out their steps in the ticket comments, **run them verbatim first.** Each of
these divergences costs a full cycle: **dropping a setup step** (`clear_nv_data` + power-cycle) leaves
the device in a *different starting topology* than the regression's, so the bug cannot present the
same way; **adding arguments** (`--timeout`, `--case_name`) to the recorded tool command. Diff
anything you think differs before assuming it matters — two candidate INI files with different
filenames were **byte-identical**.

### Privileged helpers: RegTools need `sudo`

`check_arm_agent.py` / `Fwreset.py` read `/dev/rshim0/misc` (`crw------- root root`); unprivileged they
die with `PermissionError: [Errno 13] ... '/dev/rshim0/misc'`, so **every** Fwreset fails, forever. Use
`sudo -E python ...`. A gate that fails identically before *and* after your trigger is environment,
not the bug (with Fwreset permanently broken, a verdict keyed on "post-run Fwreset failed" was true
before the tool ever ran — the #5138907 false positive, Phase 9b).

### Reg boxes may NET-BOOT a fresh image on every reboot

There a power-cycle wipes installed packages and `/tmp`, and boot takes **10-19 min** (not ~30s):
- **MFT (`flint`/`mst`/`mlxburn`) disappears after every power-cycle.** Reinstall with
  `sudo apt-get install -y dkms` (prerequisite) then `sudo /mswg/release/mft/last_stable/install.sh`;
  wrap both in an idempotent `ensure_mft()` and call it after every power-cycle, before the next device
  op — not once at start.
- **Write logs to NFS (`/auto/...`), never `/tmp`**, if they must survive a reboot.
- Size the `wait_host` timeout for the *slow* case; a 3-min bound reports a false "box did not return"
  on a box that needs 19.
- MARS reinstalls MFT during session setup, which is why this is invisible in regression logs.

### `clear_nv_data` opens a window where the card cannot boot

It erases every `NV_DATA` section (`flint v showitoc`), and the card needs an **immediate** FW re-burn.
On a net-booting box: clear NV → power-cycle → MFT gone → the burn cannot run → the card strands in
**Flash Recovery (Livefish)** (`lspci`: `[BlueField-2 SoC Flash Recovery]`). Ensure MFT *before* the
burn, and offer a `--skip-nv-clear` switch for when a recovery run already cleared NV. Safe-use rules
for the script: Phase 10.

### Livefish recovery is a lab tool, not manual flashing

The fully remote recovery procedure (`relay_controller.py` + IPMI) is skill `nic-livefish-recovery`.
The alternative is the **HCA System Service** web tool (Recovery History → run). Its pipeline:
Pre-flight → **Enable Livefish** → Cold Boot → Health Check → Device Check → FW Burn → **Disable
Livefish** → Final Cold Boot (~19 min). The explicit enable/disable-Livefish steps are what manual
flashing lacks; these **all fail** to bring the card out: `mlxburn -d <BDF>` (even when it reports
"Image burn completed successfully"), a full `flint -no_fw_ctrl -i <img> b`, a plain IPMI
power-cycle, a 90s power-off.
- **Do NOT blind-flash a generic `.mlx` to "fix" Livefish**: it lacks device-specific sections
  (`DEV_INFO` carries that board's GUID/MAC), a full-flash write can clobber board identity, and it
  does not help.
- `mlxconfig` refuses in Livefish outright, and `/dev/rshim0` is absent, so the rshim/BFB route is
  unavailable too.
- Read-only diagnostics that DO work: `flint -d <BDF> q` and `flint -d <BDF> -no_fw_ctrl v showitoc`.

### Emulation nvconfig + power-cycle can hang the host at PCI enumeration

A virtio-full-emu / multi-port emulated-PCI-switch config plus power-cycle was fine layered onto
existing NV, but wedged the host for >1h when NV had just been rebuilt from scratch (chassis power ON,
no ping/SSH; a 90s power-off did not help) — the failure class that permanently wedged l-fwreg-068.
**Prefer letting the regression bring the environment up** (run its own session) and take over from
the post-mlxconfig state, rather than reconstructing emulation NV by hand.

### Keep the lock on a wedged box

So the nightly regression does not schedule onto a broken card:

```bash
noga_manage.py -l -t server -n <box> -L <hours> -N "<why> - under recovery by <user>"
```

## Phase 10 — Between-runs reset discipline

Device/emulation state leaks between back-to-back runs; reset between every run:

| Method | Resets device state? | Time | When |
|---|---|---|---|
| `modprobe -r <drv> && modprobe <drv>` | no | <1s | driver re-bind only |
| **`jmake --fw-reset`** | yes | ~20s | **default between-runs reset** (chip reset, lockfile-aware) |
| bare `mlxfwreset -y r` | depends | ~20s | underlying tool; may refuse with a 3rd-party driver |
| **`jmake --power-cycle <box>`** | yes, always | ~3 min | non-DPU NIC box, last resort: `--fw-reset` itself hangs, D-state zombie, `rev ff` lspci, wedged device. DPU/BlueField box: only for a pending NV change that needs a cold boot (Phase 7) |
| **`clear_nv_data.sh` + immediate re-burn** | yes — **the only thing that clears NV** | ~12 min | NV state accumulated across runs (below) |

Escalation on a non-DPU NIC box when the light reset misbehaves: reset hangs >90s or `lspci` shows
`rev ff` → power-cycle; failure on stale device-status/leftover-object → `--fw-reset` again, then
power-cycle. A DPU/BlueField box is never power-cycled to recover a wedged run —
`jmake --fw-reset --device <MST device>` (Phase 7). Avoid PCIe `remove`+`rescan` on parent bridges
(can hang in `wait_woken`, recoverable only by power cycle).

### `--fw-reset` does NOT clear NV. Repeated local runs poison the device.

The nightly regression runs `clear_nv_data` once per session and always starts from clean NV; a local
repro loop does not, and the tool itself writes NV state — two or three runs of the same case drift
the device into a state the regression never sees. Signature (#5285522: run 1 reproduced; runs 2 and 3,
same official FW, INI and pinned seed, died in init):

```text
UFATAL GoldenTlvNvgn.cpp:375 WriteGoldenTlv
"GoldenTlv: Golden TLV data length exceeds maximum supported size — length: 516, max length: 255"
```

with **zero `LOG_OP` lines** and the target signature **0** times. Cause:
`GoldenTlvNvgn::PrepareGoldenTlv()` calls `ReadAllTlvsFromNvgn(dev)`, which reads **every NV TLV
currently on the device** and accumulates them; each run leaves TLVs behind, so by run 2 the total
exceeds `NV_MAX_SIZE` (255). The same file has `VerifyNoGoldenTlvInFlash()` — the test expects no
leftover golden TLV.

- **Reproduced, then stopped reproducing after a run or two → suspect accumulated NV state before
  your build, your patch, or the box.** The *official* image failing identically settles that it is
  not your build.
- The tell is *how it dies*: died in init / no `LOG_OP` lines / target signature count 0 ⇒ the test
  never reached the bug. That is `VOID` — not "the fix worked", not "cannot reproduce".
- **Any verification loop that runs the case more than once must clear NV between runs**:
  `clear_nv_data.sh <mst>` → **immediately** re-burn FW+INI → `--fw-reset` → bring-up → run. Build it
  into `per_run.sh`'s `reset_device` (Phase 9b), not into your memory.

**`clear_nv_data` is safe only if you can re-burn right after.** It erases every `NV_DATA` section
(`flint -no_fw_ctrl e <addr>` per section found via `v showitoc`), and the card cannot boot until FW
is re-burned. Verify MFT is present **before** erasing, do **not** power-cycle inside that window, and
keep the Noga lock (on a net-booting box a power-cycle there strands the card in Livefish — Phase 9c).
Script: `/auto/mswg/projects/fw/fw_ver/regression/clear_nv_data.sh` (takes the mst device).

## Phase 11 — Commit the fix

Precondition: the fix (in `golan_fw2` / `utopx2`) is **verified on the test server (Phase 9.5)** —
signature gone, control still failing, run ended cleanly. **Commit/push only when the user asks.**
Commit on the fix branch `fix_<ticket#>_<topic>_<line>` in the ticket's worktree (§4b), and **write
the commit message per skill `gerrit-change`** — it owns the format, the message checks and pushing
a dependent stack.

```bash
cd <worktree>        # /auto/fwgwork1/$USER/golan_fw_<ticket#> or utopx_<ticket#>, on the fix branch
git add -p           # stage only the fix hunks

# /tmp/repro_<ticket#>_commit.txt is written per skill gerrit-change, without a Change-Id line —
# the commit-msg hook adds it
git -c user.name="Peter Xiang" -c user.email="pexiang@nvidia.com" \
    commit --author="Peter Xiang <pexiang@nvidia.com>" -F /tmp/repro_<ticket#>_commit.txt
git log -1 --format='%an <%ae>%n%n%B'    # verify author + message + auto Change-Id
```

- **Author** = Peter Xiang `<pexiang@nvidia.com>`.
- **`Change-Id:`** is appended by the Gerrit `commit-msg` hook — never write it by hand; on amend, keep
  the existing one.

## jmake / build-&-burn command reference (generic)

`jk` is an alias for `jmake` (`$HOME/.usr/bin/jmake`); use `jmake` directly in scripts. All entries are
device/feature-agnostic — substitute `<MST device>`, `<.mlx>`, `<INI>`, `<host>`, `<model>`.

| Action | Command | Notes |
|---|---|---|
| **Build FW locally** | `cd <fw repo> && jmake -o --models <model>` | docker build (~8 min). Add `--clean` (`jmake -c -o`) after a big branch switch / stale-depfile error. Even subminor versions are official-build-only ("can only be compiled by official build") → build the next odd tag (Phase 6 Path B). |
| **Build test tool** | `cd <tool repo> && jmake -o` (or `./build.sh`) | docker build (~8–30 min); product is `<tool>.exe`, output on NFS so the test box sees it. |
| **Burn FW + INI (no rebuild)** | `cd <fw repo> && jmake --burn --device <MST device> --firmware <.mlx> --ini <INI>` | replicates regression `BurnFw.py`. ~8 min. **Do NOT chain `--fw-reset`** (triggers a heavier reset that times out). |
| **Burn — NFS-permission fallback** | `sudo -E env MFT_ICMD_TIMEOUT=60000 mlxburn -d <MST device> -fw <abs .mlx> -conf <abs INI> -force` | when `jmake --burn` hits `Permission denied` writing `image.bin` into a root-squashed NFS repo. |
| **Pivot flash → running** | `jmake --device <MST device> --fw-reset` | ~20s. The default between-runs reset; clears emulated-device state; lockfile + udriver-aware. |
| **Power cycle the box** | `jmake --power-cycle <host>` | ~3 min. Non-DPU NIC box: last resort — `--fw-reset` itself hangs, D-state zombie, `rev ff` lspci. DPU/BlueField box: only for a pending NV change that needs a cold boot (Phase 7). Run `ssh -O exit <host>` first to drop the stale ControlMaster socket. |
| **Upgrade MFT** | `sudo jmake --mft-install` | wraps `/mswg/release/mft/last_stable/install.sh`; needed when a tool/symbol isn't recognized by the box's old MFT. |

- **`jmake --fw-reset` ≠ bare `mlxfwreset`.** It wraps `fwreset.py`, adding `/tmp/fwreset_lock` +
  `/tmp/udriver_lockfile.lock`, multi-host coordination, function rebind, post-reset PCIe rescan, and an
  uptime before/after check. Bare `mlxfwreset` on a box with only a 3rd-party driver bound may refuse
  (`Tool is owner: Not supported`).
- **`jmake --burn` only sets the image default**; a prior `mlxconfig set` on the box shadows it. Clear
  persistent overrides explicitly (`mlxconfig ... s <KNOB>=<default>`) if a reburn does not take effect.
