## The three artifacts a repro needs

A MARS session pins three things; reproducing the failure requires **all three** to match
(matching one or two yields look-alike failures that aren't the bug):

| Artifact | Recorded in (MARS step) | Also visible in ticket as |
|---|---|---|
| **FW build** (`.mlx` + version + PSID) | `new_burn_fw` | `flint_nv_dump_<dev>_<VER>_*` attachment filename |
| **Burned INI** (release default + regression overrides) | `new_burn_fw` (`new_ini_file`) | `dump_nv_data_*` attachment (the resulting NVconfig) |
| **Test-tool commit** + the exact **command & seed** | `get_last_commit` / `run_case` | `run_case_<key_id>.log` attachment |

> **The box drifts daily.** The setup re-burns fresh FW and re-pins the test tool every
> day. Never assume a version — read the ticket's session and verify the running FW with
> `flint q` before trusting anything.

---

## Phase 1 — Decode the Redmine ticket into reproduction coordinates

This is the entry point. Input = the URL only.

```
# Pull the ticket (real-time, with attachments + history):
yai__get_tickets(ticket_ids=[<NNNNN>], include="full")
# or, to also expand a project-filter/saved-query URL:
yai__resolve_redmine_url("<URL>")
```

Extract these, in order:

1. **Failure signature + test tool + regression stream** — from `subject` and the
   "Fatal message:" line in `description`. Example shape:
   `[UTOPX] <signature> ; <cmd_struct> ; <REGRESSION_STREAM> DEVICE_NAME_LIKE[<DEV>]`.
   → test tool = utopx; signature = the `<...>` you must reproduce; `<REGRESSION_STREAM>`
   is the verification branch/carveout; `<DEV>` is the device family.

2. **The MARS `view_log.php` URL in `description`** — parse its query params (this is the
   bridge from Redmine to the reproducible env):
   | Param | Use |
   |---|---|
   | `results_dir` | NFS results root (mounted on every dev box — read it directly, skip the auth'd web UI) |
   | `setup_id` | encodes **machine** + **device** + **mode** + suite, e.g. `<DEV>_FW-<machine>_<MODE>_P1` |
   | `session_id` | the session → tarball `<results_dir>/<setup_id>/<session_id>/<session_id>.tgz` |
   | `key_id` | the **failing step path** inside the tarball; also the suffix on every attachment |
   | `status` | `Failed` confirms it's a failure to reproduce |

3. **Device / MST / FW** — from `custom_fields` "Chips" (device family) and from the
   attachment filenames:
   - `flint_nv_dump_<mstdev>_<FWVER>_*` → **MST device** (`<mstdev>`, e.g. `mt41695_pciconf0`)
     and **running FW version** (`<FWVER>`, e.g. `82.48.1632`).
   - `mst_dump_file_for_step_..._<mstdev>_...` / `print_mst_devs_*.log` → confirm MST node.
   - `fixed_version` → the target release the fix lands in.

4. **The exact command + env, straight from the attachments** (faster than the tarball;
   download each via its `content_url` — use the Redmine attachment-download tool, or
   `curl -H "X-Redmine-API-Key: $KEY"` / your browser, or read the same file from the
   tarball in Phase 2):
   | Attachment | What it gives you |
   |---|---|
   | `run_case_<key_id>.log` | **the exact test command**: scenario `.conf`, `--iter`/`--ops_per_it`, any `-e` knobs, and the **seed** to pin |
   | `oplist_<key_id>.log` | the op sequence (for narrowing the failing op) |
   | `dump_nv_data_<key_id>.log` | the NVconfig that was active (cross-check your INI burn) |
   | `flint_nv_dump_<dev>_<ver>_*` | FW version + NV dump |
   | `fw_reset_*.log`, `modprobe_udriver_*.log`, `print_mst_devs_*.log` | the regression's per-test reset/bring-up sequence to mirror |
   | `basic_debug_*.log`, `remote_file_analysis_*.log`, `Verify_utopx_executable_existence_*.log` | utopx binary path/version sanity, extra context |

5. **History** (`journals`) — note who reassigned/triaged it and any analysis link
   (e.g. an Orion AI-overview URL). Reassignment from the auto-filer to a dev usually
   marks when real triage started.

At the end of Phase 1 you should have filled the **Environment** block above completely
from the ticket alone.

## Phase 2 — Extract the exact versions from the MARS session tarball

The attachments give command + FW version, but the **INI path/PSID** (`new_burn_fw`) and
the **test-tool git commit** (`get_last_commit`) usually live only in the tarball.

```bash
RESULTS=<results_dir>; SETUP=<setup_id>; SID=<session_id>; KEY=<key_id>
mkdir -p /tmp/mars_$SID

# Find the version steps + the failing run_case (step numbering varies per session):
tar -tzf $RESULTS/$SETUP/$SID/$SID.tgz | grep -E "new_burn_fw|get_last_commit|$KEY/run_case"

# Extract just those logs (not the whole multi-hundred-MB tarball):
tar -xzf $RESULTS/$SETUP/$SID/$SID.tgz -C /tmp/mars_$SID/ \
    <a.b.c>/log.txt <d.e.f>/log.txt $KEY/run_case.cap
```

- `new_burn_fw` `log.txt` → `grep -E "fw_file:|default_ini:|FW Version:|psid:|new_ini_file:"`.
  - `fw_file` = official `.mlx` to burn; **`new_ini_file`** = the regression-generated INI
    to copy (has the injected overrides; the release default does NOT).
- `get_last_commit` `log.txt` → `grep -E "git_describe|commit_id"`. The `git_describe` tag
  is the most self-documenting test-tool reference; the SHA always resolves.
- `run_case.cap` → `grep -oE '<tsr_args>[^<]+'` for the exact args (cross-check the
  `run_case_<key_id>.log` attachment).

> **Read the RELEASE TAG's tree, not whatever your clone is checked out at.** A repro clone sits
> on some feature/triage branch that usually does **not** contain the release line under test, so
> grepping it yields confidently wrong conclusions — on #5138907 the syndrome literal was absent
> from the checkout, which led to a fabricated "this validation is missing" root cause. Resolve
> the tag first (below), then read that tree **without checking it out**:
> ```bash
> git grep -n '<pattern>' <rel-tag> -- 'src/*.c'      # search the release tree in place
> git show <rel-tag>:<path> | sed -n '<a>,<b>p'       # read a file at that tag
> ```
> Sanity check: a build date *earlier* than your clone's HEAD does not mean the code is in it.

### Translate the FW *product* version → FW *source-tree* commit/tag
There is usually no MARS step for FW source (FW is a pre-built `.mlx`). Recover it:
- **By version string**: `git log --all --oneline --grep="Updated version <src-family>.<MM>.<bld>"`
  in the FW repo. Mind the family-prefix convention — tools report a *product* number
  (e.g. `82.48.1632`) while the source tree uses a different family digit; the build
  number matches, the family digit doesn't. Grep the trailing `.<MM>.<bld>` to be safe.
- Release tag = `rel-<src-family>_<MM>_<bld>` (drop family prefix, dots→underscores).

## Phase 3 — Allocate & preflight the SAME server that reported the issue

> **MANDATORY — reproduce on the exact box from `setup_id`, with the exact command, env,
> and steps the regression ran.** Do NOT substitute a different host, a different command,
> a different scenario/iter/ops, or a "cleaner" bring-up. A repro is only valid if it
> matches the regression bit-for-bit; a different box/command can hide or fake the failure.
> If the box is locked by someone else, **monitor it and grab it the instant it frees**
> (§3b) — do not swap boxes.

> **Unknown command? Ask Glean first, don't guess.** If you're unsure of a reg-server /
> reservation / lab-tooling command or flag (malloc options, how to query a queue, what a
> Noga field means, etc.), query the **nvidia-glean** MCP (`glean_search` or `glean_chat`,
> e.g. "how to malloc a regression server fwreg / extend allocation / noga lock") before
> inventing a command. Confirm with `--help` where one exists.

The test machine is the `<machine>` parsed from `setup_id` (e.g. `BRONCO_FW-`**`m-fwreg-029`**`_DPU_MODE_P1`).

### 3a. Reserve the box

Taking, extending, releasing and verifying the lock — including the `not in allocation pool`
fallback, the interactive `--reg-extend` trap and how to read `TIME LEFT` — is lock machinery:
**skill `noga-lock`**.

The only repro-specific rule here: reserve **the box named in `setup_id`**, never a substitute
(exception: §3b-bis).

### 3b. If the box is busy: monitor and grab it the instant it frees

When `jmake --reg-malloc <machine>` reports `Resource locked by <holder> until <ts>`, do **not**
switch hosts and do **not** re-type malloc by hand. Whoever malloc's first wins, so an unattended
monitor is the only reliable way to get a contended box.

Use the ready-made loop — it already carries the traps that a hand-written `until` loop gets
wrong (heartbeat with owner + seconds-to-expiry, chaining the provisioning step with `--then`,
and the two failure modes that silently kill a monitor):

```bash
~/myGit/crosslv/assets/skills/noga-lock/scripts/noga_wait.sh -n <machine> -L 8 --hours 8 \
    --then '<provisioning command>'
```

Start it with the long-running-job method in `references/hosts/<runtime>.md`, retain one watcher,
and observe that same job rather than starting duplicates. Details and traps: **skill `noga-lock`**.

⚠ **A released lease does not mean the box is idle.** Before trusting it, confirm no run is still
alive: `ssh <box> 'ps -eo cmd | grep -c "[u]topx.exe"'` must be 0. Grabbing a box while a
regression session was still running has happened.

### 3b-bis. EXCEPTION — same-PSID substitution (only with explicit user approval)

Default is still "never substitute the host." But if the exact box is locked long-term and the
**user explicitly approves a substitution** ("find an idle server with same PSID"), pick a box
that matches the **board, not just the family** — same **PSID** is what makes the FW expose the
same caps. Procedure:
1. **Find every box with the exact PSID via Noga (authoritative — do NOT rely on MARS INI names,
   which only cover boxes that box has actually run).** The PSID lives on the **NIC** resource's
   `Setup Automation.psid` attribute (each server links its card as
   `Relation.has a = NIC:<box>-bf2-<mac>` / `Specific.MELLANOX_CARD_1`). Query all NICs with the
   ticket's PSID in one shot:
   ```bash
   NOGA=/.autodirect/sw_tools/Internal/Noga/RELEASE/latest/cli/noga_manage.py
   python3 $NOGA -q -t nic -e "psid:<PSID>"          # e.g. psid:MT_0000000704
   #   -> table of ID/Name/Group/Status/lock_owner for every board with that PSID.
   #   'Release' / empty owner = free;  'Lock' by mars_reg = a regression holds it (or a stale
   #   reservation if the box is actually down -- verify reachability, don't trust the lock alone).
   ```
   To discover which attribute holds the PSID on any box (if the schema differs), dump the card:
   `python3 $NOGA -q -n <box> -t server -D | grep -iE 'MELLANOX_CARD|has a'` → then
   `python3 $NOGA -q -n <nic-name> -t nic -D | grep -iE 'psid|device_id|NIC_Type'`.
   (Fallback, coarser: `ls <results_dir> | grep -iE '<DEV>.*<MODE>'` lists MARS *sibling setups*,
   but misses same-PSID boxes that never ran this suite — the Noga query is the real inventory.)
2. Find which candidates are **idle**: `jmake --reg-idle`, and/or
   `noga_manage.py -q -n <cand> -D | grep -E 'Status\.(status|lock_owner)'`
   (`Release`/empty owner = free; `Lock` by `mars_reg` = a regression is running it — **but a
   `mars_reg` lock on an unreachable/down box is just a stale reservation, not an active run**;
   confirm with `ssh <cand> hostname` (using the runtime adapter) and the newest real session
   mtime before believing it).
   - **MANDATORY platform check — utopx setups are Supermicro-only.** The allocation-pool health
     scan (`update_noga_resource.py` → `RegTools/is_setup_compatible_with_utopx.py`) flags a box
     `INCOMPATIBLE_UTOPX` purely on `dmidecode -s system-manufacturer` ∉ {supermicro}. Before
     substituting, check BOTH: `noga_manage.py -q -n <cand> -D | grep -iE 'Server_Model|Free_text'`
     — require `Server_Model = Supermicro` and no `noga_alloc_note:[INCOMPATIBLE_UTOPX]` in
     Free_text (also shown red in the Allocated-setups dashboard). **A box being conveniently
     idle can be BECAUSE it carries this flag.** Ignoring it is dangerous, not just unsupported:
     an HP(iLO4) box took the virtio-full-emu PCI-switch nvconfig and hard-hung in BIOS POST,
     unrecoverable remotely (l-fwreg-068, 2026-07-23).
   - **A same-PSID box may still lack this suite's box-specific `topology_<mode>.xml`** (the
     RegTools clear_nv_data / Fwreset / check_arm_agent need per-box entry_points). If so, author
     one from the original box's template — copy `topo/<orig>/topology_<mode>.xml` +
     `<orig>_<mode>.xml`, and swap BASE_IP / CONNECTION IP, the `rocep*` SUB_DEVICE names, PCI_BUS,
     and the per-port data-plane IPs (20.x/21.x) to the substitute's (discover via
     `ssh <cand> "ip -br addr; sudo mst status; rdma link; lspci | grep -i mellanox"`, using the
     runtime adapter).
3. **Confirm same PSID + healthy** from the candidate's most recent session tarball
   (`<results_dir>/<sibling_setup>/<latest_sid>/<sid>.tgz`): extract its `new_burn_fw` log and
   check `psid:` == the ticket's PSID, `FW Version:` == target, and `Burn FW RC = 0`/`Final RC =
   0` (proves the box burns FW and is healthy).
   - **Archives are often status-only** (log.txt purged by retention). If `new_burn_fw`'s
     log.txt is gone, read the burn steps' `status.txt` instead: find the step ids via
     `tar -tzf <sid>.tgz | grep new_burn_fw.cap` (e.g. `1.25.1.1`/`1.28.1.1`, one per
     port/segment), then `tar -xzOf <sid>.tgz --wildcards "<step>/status.txt"` —
     `result: 0` = burn OK. Box health at a glance: extract `summary_results.json` →
     `Total_summary` (a healthy board on an active branch shows tens of PASSED; **0 PASSED +
     burn RC=1 across several consecutive sessions = sick box — disqualify it even if
     PSID/mode match**, because Phase 6 must burn FW on it).
   - **PSID/FW version without any tarball:** the burn-INI filename embeds both —
     `ls /auto/sw/work/hca_fw/data/burn_fw/ini_files | grep session_<sid>_` →
     `..._session_<sid>_version_<ver>_psid_<PSID>.ini`. (A session with NO ini_files entry
     often means its burn failed.)
   - **Health-rank ALL candidates this way before picking** — mode fidelity (non-SD vs SD)
     decides which *failure face* you'll likely see, but burn health decides whether the box
     is usable at all. Prefer: healthy+mode-faithful > healthy+SD > mode-faithful-but-sick.
4. **Bonus signal:** stream-grep that tarball for the ticket's signature
   (`tar -xzOf <sid>.tgz | grep -m1 "<signature>"`) — if the sibling's own latest regression hit
   the SAME fatal, the bug is systemic to that board/FW and the substitute is high-confidence.
5. Lock the substitute (direct Noga lock if it lacks the malloc-pool label — see 3a), then
   proceed. Record the substitution + approval in the run log; leave the original box untouched.

### 3c. Preflight (once you hold the lock)

```bash
# Capture current FW state as a restore point before touching anything.
ssh <machine> 'sudo flint -d <MST device> q full'

# If a regression has run on the box since the failure (FW != target, test binary mtime
# fresh), do Phase 9 (env recovery) before trusting any result.

# STALE-PROCESS CHECK (esp. boxes that fell out of rotation): a leftover test daemon from a
# prior session can still hold the device, which makes fw_reset fail later ("udriver cannot be
# unloaded, file /dev/udriver_* is opened, possibly by utopx" / "Device is busy"). Find & kill it:
ssh <machine> 'sudo fuser -v /dev/udriver_* 2>&1; ps -eo pid,etime,cmd | grep -E "[u]topx.exe.*--daemon"'
ssh <machine> 'sudo kill -9 <pid> <ppid>'   # the leftover utopx + its sudo parent; then re-check fuser
```

## Phase 4 — Pin local repos to the regression's commits

> **FASTEST PATH — reuse the regression's already-deployed test-tool binary.** Before building
> anything, check the test box: the regression deploys the prebuilt `utopx.exe` + its configs to
> `/tmp/mars_tests/<test-DB>/tests/` (the same `<test-DB>` from `get_last_commit`). If that tree
> still exists, that binary **IS** the regression's exact binary — no local clone/build needed,
> and it's the cleanest test-tool pin (perfect three-way match). Verify the commit matches:
> ```bash
> ssh <machine> 'ls -lL /tmp/mars_tests/<test-DB>/tests/utopx.exe;
>   ls /tmp/mars_tests/<test-DB>/tests/{conf.xml,config/<scenario>.conf}'
> # cross-check commit vs Phase-2 get_last_commit (and the run prints "tarball git tag is: <describe>")
> ```
> Only fall back to a local build if the deployed tree was cleaned. **Local build repos (per
> user): FW = `/auto/fwgwork1/$USER/golan_fw2`, utopx = `/auto/fwgwork1/$USER/utopx2`** — do NOT
> pin/checkout inside an active `[USE_THIS_WORKSPACE]` clone; use a dedicated per-ticket workspace.
>
> ### ⛔ NEVER edit source inside `/tmp/mars_tests/<test-DB>/tests/`
>
> That tree is **MARS's own deployment and mars_reg runs the nightly regression straight out of
> it.** Reuse it read-only — run its `utopx.exe`, read its configs, check its commit. **Never
> patch a source file, add a probe, or rebuild in place there**, not even "temporarily with a
> backup".
>
> The lease is not a safety net: if it expires, or the box is grabbed, before you restore, **the
> next regression runs on your modified binary** — silently wrong results for someone else, with
> nothing in the archive pointing back at you.
>
> Any source edit — a candidate fix *or* a read-only debug probe — goes on a **named private
> branch in the repro clone**:
>
> ```bash
> cd /auto/fwgwork1/$USER/utopx2
> git status --porcelain                     # tracked mods are someone's work - stash, don't clobber
> git checkout -b fix_<ticket#>_<topic>_<line> origin/<full-branch-name>
> git submodule update --init --recursive    # MANDATORY - see below
> # edit, then build in place (a copied tree will not build - cmake caches absolute paths)
> jmake -o
> ```
>
> **Do not skip `git submodule update` after the checkout.** A repro clone usually has submodule
> pointers left over from the previous ticket, and `git checkout -b` does **not** move submodule
> working trees. The build then fails inside `hca_fwv_shared/autogen/*` with things like
> `'hca_fwv_ib_pkt_hdr_boeth' was not declared in this scope` — which reads as "the baseline is
> broken" and sends you debugging the wrong thing. It is just the submodule sitting at the wrong
> commit. Check with `git status --porcelain`: a bare `M <submodule>` line means the pointer moved;
> `M <submodule>` that persists *after* the update with only an untracked `compile_commands.json`
> inside is harmless build residue (the diff shows `<sha>` vs `<sha>-dirty`).
>
> Then run **that** binary on the test box over NFS — `/auto/fwgwork1/...` is mounted there, so no
> copying is needed:
>
> ```bash
> ssh <box> 'cd /auto/fwgwork1/$USER/utopx2/<artifacts path> && sudo ./utopx.exe --device=... '
> ```
>
> Violated repeatedly on 2026-09-15/16 while chasing #5273244 / #5273909 — four rounds of patching
> and rebuilding inside the deployed tree. Each round was restored afterwards, but the window was
> real and the practice is banned.
>
> ### Do not "improve" a verified patch on the way to gerrit
>
> Whatever expression you verified on the box is the one you push. If a cleaner or more general
> form occurs to you afterwards, it is a **new, unverified change** and needs its own run — the
> reasoning that it is "strictly better" is not evidence.
>
> #5273244, 2026-09-16: the host-count bound `DEVICE_INFO.GetNumOfNonSnHosts()` had been verified
> clean (mismatch 6 -> 0, no crash). Before pushing it was swapped for
> `vhca->GetDevice()->GetMaxNumNonSmartNicHosts()` because that also covers non-ECPF mode — sound
> reasoning, never run. The result still showed mismatch 0 on every signature counter, and
> **segfaulted**. Only the control run (the unmodified deployed binary, same seed: 6 mismatches,
> no segfault) established that the crash was self-inflicted.
>
> Two habits follow:
> - **Judge a verification run by how it ENDED, not only by the signature counters.** Check
>   `To rerun use seed` / `TEST PASSED|FAILED` / `terminate called` / `SEGMENTATION FAULT`. A run
>   that scores 0 on every target signature and then crashes is not a pass. This exact mistake was
>   made twice in two days (#5273909 arm v2: 3/3 terminated while all counters read 0).
> - **Always run the unmodified control on the same seed.** Without it you cannot tell a
>   pre-existing failure from one you introduced, and the temptation is to assume the former.

```bash
git fetch --all --tags    # ALWAYS first — release tags are often remote-only; a
                          # "rel-X-NNN-g<sha>" describe = stale tag list, not a missing tag
```
> **Create a NAMED PRIVATE BRANCH from the failing version in each repo — never work on a
> detached HEAD.** `git checkout <tag-or-sha>` leaves you detached, and a detached HEAD is the
> single easiest way to end up analysing the wrong source line: it carries no label, it survives
> from the *previous* ticket, and `git branch` shows only `* (HEAD detached from rel-12_48_1633)`
> — a line that may have nothing to do with the release under test. Observed on #5184928: the
> repro clone sat detached from `rel-12_48_1633` (the **48** family) while the ticket was **51**
> family, so the first discovery greps read the wrong tree; the same function was a `static inline`
> in `include/hca_cap.h` there but a real function in `src/main/hca_cap.c` at the correct tag.
>
> Once you are ON a branch created from the right base, **the working tree is authoritative** and
> you can grep/read/edit normally — no more `git show <tag>:<file>` gymnastics, and the fix has
> somewhere to live.

> ### A branch is for CHANGES. Read-only analysis just checks out the tag.
>
> Do not create a branch in a repo you are only reading. Root-causing at the ticket's version means
> `git checkout <tag>` and nothing more — an empty branch adds no information and leaves litter to
> clean up later. Create a branch **at the moment you are about to edit code**, and only in the repo
> you are about to edit (often that is `golan_fw2` only; the test tool frequently needs no change
> at all).
>
> Checking out a **named tag** also satisfies the "don't get lost" requirement below: `git describe`
> prints the tag, so you always know which tree you are reading. The #5184928 trap was a *stale
> detached HEAD carried over from a previous ticket*, not a deliberate checkout of a named tag.

For **each** repo (FW source + test tool) — pin it, then branch only if you will edit it:
```bash
cd <repo>
git status --porcelain          # LOOK FIRST. Untracked build artifacts are fine to carry over;
                                # tracked modifications are someone's work — stash, don't clobber.
git stash push -u -m "auto-stash before <ticket#>"    # only if tracked files are modified

# Read-only (root-cause analysis) — the normal case for the test tool:
git checkout <tag-from-Phase-2>

# ONLY when you are about to change code, branch from the failing version.
# Name it after the ticket and the topic. No personal names — "<ticket#>_<topic>" is the style;
# append the version only when it carries information (e.g. an official+1 build tag):
#   5285522_virtio_net          5285522_virtio_net_0291
git checkout -b <ticket#>_<topic> <tag-or-sha-from-Phase-2>

git submodule update --init --recursive    # submodules' recorded commits may need a fetch
git describe --tags                        # confirm WHICH tree you are on, branch or tag
git log -1 --format='%H %ci %s'            # verify it matches the regression
git describe --tags                        # the self-documenting confirmation — see below
```

> **Resolve the SHA, and confirm with `git describe` — moving tags lie.** `regression_stable_tag`
> is a *moving* tag: the run log's `regression_stable_tag-0-g3207d90` records where it pointed
> **on the day of the regression**, but your local copy of that tag may be months stale (on
> #5184928 the local `regression_stable_tag` pointed at a commit from **2026-05-31**, while the
> regression's `3207d90` was from **2026-08-01**). Always branch from the **SHA**, then run
> `git describe --tags` on it: it printed `host_fwv_20260801_FW_version_51_0098_branch_master`,
> which independently confirms both the date and the FW line — a much stronger check than the
> moving tag name.
Keep a table — branch / tag / SHA are interchangeable references (the two repos often use
different branch-naming conventions; don't assume they share a branch name):

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
Understand the diff — `BurnFw.py` appends device-specific overrides (BAR/PCIe/DDR-mapping,
emulation flags, etc.) the release default lacks; those are often what make the device
behave like the regression. Cross-check the result against the ticket's `dump_nv_data_*`
attachment (that's the NVconfig the failing run actually had).

> **Do NOT add your own nvconfig/INI rows** to chase a side feature — it shifts FW caps
> the test tool can't predict and produces look-alike failures. Keep the burned INI ==
> the regression's exactly.

## Phase 6 — Burn FW + INI to the device

**Path A — no source edits (INI only):** burn the official `.mlx` + your INI, no build
(same as `BurnFw.py`):
```bash
ssh <test machine> 'cd <FW source repo> && \
  $HOME/.usr/bin/jmake --burn --device <MST device> \
      --firmware <official .mlx> --ini <repo>/regression_ini/burned_<session>.ini'
# Do NOT chain --fw-reset here. If jmake hits a root-squashed-NFS "Permission denied"
# writing image.bin into the repo, burn with direct mlxburn instead:
ssh <test machine> 'sudo -E env MFT_ICMD_TIMEOUT=60000 \
    mlxburn -d <MST device> -fw <abs .mlx> -conf <abs INI> -force'
```
**Path B — you must build FW from source edits:** local builds reject **even** subminor
versions. Checkout the **next odd** release tag (same code, only the version tag differs)
and `jmake -o --clean --models <model>` → `<repo>/fw-<device>.mlx`, then burn as Path A.

## Phase 7 — Pivot FW + bring up drivers (mirror the regression's per-test setup)

Use the ticket's `fw_reset_*.log` / `modprobe_udriver_*.log` / `print_mst_devs_*.log`
attachments as the authoritative bring-up sequence. Generic shape:
```bash
ssh <test machine> 'sudo $HOME/.usr/bin/jmake --device <MST device> --fw-reset'   # pivot flash→running
ssh <test machine> 'sudo flint -d <MST device> q | head -5'                       # verify flash==running
ssh <test machine> 'sudo modprobe <driver>'                                       # e.g. udriver
# Device-specific gotchas to mirror from the logs, e.g.:
#   - clear any management-channel "drop"/safety mode before the test uses it
#   - restart the management daemon if --fw-reset left it down
#   - for SoC/DPU devices, wait for the ARM/OS to finish booting (until-loops, not bare sleep)
```
> `jmake --fw-reset` wraps `mlxfwreset` with lockfile + driver-aware orchestration; on
> boxes where only a 3rd-party driver is bound, bare `mlxfwreset` may refuse ("Tool is
> owner: Not supported") — prefer the wrapped reset.
>
> **To match the regression bit-for-bit, run its OWN per-test reset script** (read the exact cmd
> from the `fw_reset_<key>` step's `log.txt` — "Executing cmd: …"). For HCA-core it is:
> ```bash
> ssh <machine> 'sudo /auto/mswg/projects/fw/fw_ver/hca_fw_tools/fw_reset/fwreset.py \
>     --debug --next_driver <driver> -d 0000:<pci>'   # e.g. --next_driver udriver -d 0000:ca:00.0
> ssh <machine> 'sudo modprobe <driver>'              # the separate modprobe_udriver step
> ```
> Success prints `FW reset successful: uptime was reset. Before: N, After: ~15` and rebinds the
> driver. If it loops "Unbind attempt … is opened by process: <pid>" then errors "Device is busy",
> a stale daemon holds the device — kill it (Phase 3c) and retry.
> **DPU/BlueField: do NOT `--power-cycle`** to recover — it breaks the BareMetal ArmAgent (memory
> utopx-bf3-repro-use-regression-fwreset). Use the regression fw_reset / a clean re-burn instead.

## Phase 8 — Run the EXACT command + seed and watch for the signature

Take the command **verbatim** from `run_case_<key_id>.log` / `run_case.cap` — same scenario
`.conf`, same `--iter`, same `--ops_per_it`, same `-e`/`--extra_constraints` knobs, same
`--timeout`/`--case_name`. **Do not drop, add, simplify, or reorder any argument** (e.g.
don't lower `--iter` to "go faster" — the failure may only surface at the original count),
and run it from the same working dir as the regression. **Pin the seed** from `run_case`
("To rerun use seed <N>") for determinism:
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
> **Debug logging — swap `conf.xml` → `debug_conf.xml` for verbose KDEBUG output.** The
> regression runs utopx with `--xml_conf_file conf.xml` (INFO level), which does NOT print the
> keyed `KDEBUG(...)` internals. The utopx repo ships a ready **`debug_conf.xml`** (same dir,
> includes `conf_keys.xml`) that sets `log_file_verbosity=debug` + screen=debug and the key
> default to `debug`. To see *which* internal path failed — e.g. the steering resolver's
> `KDEBUG("PACKET_HANDLER", …)` lines ("No steering dest capsules found" / "ERROR: …" /
> "Failed to translate steering dest…" / the full `steering_path:` dump) — just re-run with
> **`--xml_conf_file debug_conf.xml`** (change it in the `tsr_args`/run command). Do NOT
> hand-edit `conf_keys.xml`; `debug_conf.xml` is the supported switch. Debug output then lands in
> `/tmp/verix_test*.log` (and stdout). Per-KEY targeting: a key not listed in `conf_keys.xml`
> uses the file default (`debug` under `debug_conf.xml`), so `PACKET_HANDLER` is captured.
>
> **One command per ssh** (don't bundle into a remote script — buffered `tail` hides an
> early FATAL until the run ends, and a bundled failure aborts opaquely). **Reuse one SSH
> connection** (`ControlMaster auto`/`ControlPath`/`ControlPersist`); after any
> reboot/power-cycle run `ssh -O exit <box>` first to drop the stale socket. In an agent
> session, launch with the long-running-job method in `references/hosts/<runtime>.md` and observe
> the same job through completion; never start a duplicate because output is temporarily quiet.

## Phase 9 — Confirm / handle divergence; env drift recovery

**Confirm:** the local log shows the **same** failure signature (same struct/field, same
fatal). If so, the bug is reproduced — record the seed and the verix log path.

**If it does NOT reproduce** (run passes, or fails differently):
- Re-verify all three artifacts match (Phase-2 versions, INI diff vs `dump_nv_data`,
  test-tool *binary* — see drift note below). A stochastic tool exposes different bugs per
  seed; you pinned the seed, so a *different* failure usually means an artifact mismatch.
- Try the failing op directly from `oplist`, or widen seeds only after the pinned seed is
  confirmed to match the regression's.
- **A "different fatal" can be the SAME underlying bug at a different device state** — common
  for *bring-up* bugs. E.g. ticket signature = `cmd_hca_cap actual cap < expected` (caps read
  `0x0`), but a dirtier device gives an earlier `VerifyHealthBuffer` FW assert
  (`ext_synd 0x817e severity 0x5`) in `PreTest/QuickInit` before the cap check is even reached.
  Both = "device didn't bring up." Read the **VHCA topology dump** in the fatal: stages stuck at
  `HCA_STAGE_QUERY_HCA_CAP_MAX_BY_TRUSTED_HCA`/`HCA_STAGE_DISABLED_HCA` with `phy port up: 0` /
  `vport_state=PORT_DOWN` confirm bring-up never completed. Decode the health-buffer `fw_version`
  field to confirm FW (e.g. `0x52300660` = `82.48.1632`). To steer toward the *exact* signature,
  give the device the cleanest state the regression had: **fresh re-burn FW+INI → regression
  fw_reset → re-run** (do NOT power-cycle a DPU). A bring-up bug is often non-deterministic across
  device state even with a pinned seed — note the divergence honestly rather than forcing a match.

**Env drift (a regression ran on the box since):** FW re-burned, repos on regression tags,
and crucially the test-tool **binary recompiled** — `git checkout` reverts *source* only,
so the on-disk binary disagrees and you get parse errors / cap mismatches / ICMD BAD_PARAM
that masquerade as the bug. Recovery: repin both repos (Phase 4) → **rebuild the test-tool
binary** (`./build.sh` / `jk -o`; verify its mtime is fresh) → reburn FW+INI (Phase 6) →
power-cycle to pivot → re-do bring-up → run a **baseline** first to confirm a clean env,
then the repro.

## Phase 9.5 - Verify a candidate fix ON THE BOX (before any Gerrit commit)

Reading code until you have a root-cause hypothesis is not the end of the job. A fix that has not
run on hardware is a **proposal**, not a fix - and "the reasoning is sound" has repeatedly turned
out to be wrong on this codebase (see key-learnings.md). Phase 11 must never be reached from a
hypothesis; it is reached from a verified run.

> **The fix may live in `golan_fw2`, in `utopx2`, or in BOTH. Do not assume FW-only.** A test-tool
> defect (a stale expectation, a check that no longer matches intended HW behaviour) is an equally
> valid outcome of root-cause work. Check which repo(s) your change actually touches before building.

1. **Write the hypothesis and the diff into the Investigation log BEFORE building.** Root-cause
   statement, code evidence (`file:line`), attribution (`git blame` / `git log --author`), and the
   exact diff you are about to test. Written afterwards, "it passed" is unauditable - nobody can
   tell a fix that worked from a run that happened not to crash.

2. **Build the candidate** on the ticket's named private branch (Phase 4 pin), clean:
   `jmake -c -o`. **Read the build log - do not trust the exit code**; jmake prints `BUILD SUCCESS`
   and exits 0 even when a stage died. utopx: confirm the binary's mtime is actually fresh.

   > **Even-subminor gate (FW only)** — the standing rule, see CLAUDE.md hard rule 4. A local build
   > of an even `SUBMINOR` is refused outright ("Even-numbered FW Subminor Version can only be
   > compiled by official build"). Building the released version yourself always means
   > **official + 1**: to verify a fix against an even release tag, build the **next odd** tag (same
   > code, only the version stamp differs) and build the **control from that same odd tag** too, so
   > patched vs control still differ by exactly one variable.
   >
   > **Which image to use when — do not blur these:**
   > - **Reproducing** (Phases 6-8): burn the **official released `.mlx`**, never a local build. You
   >   want the bit-exact image the regression ran; a local build is by definition a different
   >   artifact and cannot prove the ticket's failure.
   > - **Verifying a fix** (this phase): local build is unavoidable (the patch has to be compiled),
   >   so use the next odd tag — and build the control there too.
   >
   > **Prove the odd tag is behaviourally identical - do not just assert it.** `git diff
   > rel-X_YY_<even> rel-X_YY_<odd>` should touch only `Version` and the auto-generated version
   > vector in `adabe/upgrade_ini_defaults.adb`; that is the code-level check. The stronger,
   > behavioural check costs one extra run and is what you show a reviewer: on a **clean NV**, run
   > the **unpatched odd build** and compare it against the **official even image** on the same
   > seed. Same signature, same count, same `LOG_OP` depth = the odd tag introduces no behavioural
   > difference, and the odd-tag control is trustworthy.
   >
   > #5285522 measured: official `0290` -> `0xac5816` x4, GoldenTlv 0, `LOG_OP` 252; local
   > unpatched `0291` -> `0xac5816` x4, GoldenTlv 0, `LOG_OP` 253. Equivalent, so the only variable
   > left between control and patched was the patch itself.
   >
   > Record the version correspondence explicitly in `FINDINGS_<ticket#>.md` section 2 - which
   > artifacts are byte-identical to the ticket's, and which single one deviates and why. A
   > reviewer's first question about any on-box verification is "did you actually run what the
   > ticket ran"; answer it in the document, not in chat.
   >
   > **A locally built image is not the official release image.** Even at an identical source tag it
   > may expose a different NV/TLV inventory, which can make the test die in init before it reaches
   > the bug (observed on #5285522: `GoldenTlv: data length exceeds maximum supported size`, 516 >
   > 255, zero `LOG_OP` lines). If that happens the control is VOID, not a pass - re-burn the
   > **official** `.mlx` and confirm the original signature still reproduces before blaming anything.

3. **Deploy it.**
   - FW fix -> **reburn** (Phase 6) + pivot (`jmake --fw-reset`). Never pivot alone and assume the
     new image is live; a stale flash silently masks the fix and you "verify" the old binary.
   - utopx fix -> rebuild and run *that* binary over NFS (never patch the deployed
     `/tmp/mars_tests/...` tree - see the hard rule in SKILL.md).
   - Both -> do both before the rerun.
   - Then redo the regression's own bring-up (Phase 7): its `fw_reset` / `Fwreset.py --next_udriver`
     / `modprobe`, not a cleaner equivalent.

4. **Rerun the EXACT pinned command + seed** from `run_case` - same scenario, `--iter`,
   `--ops_per_it`, same everything (Phase 8). Not a shortened or widened run.

5. **Judge the run by how it ENDED, not by the signature counter.** Check
   `TEST PASSED|FAILED` / `To rerun use seed` / `terminate called` / `SEGMENTATION FAULT` /
   whether the tool even initialised (zero `LOG_OP` lines = it never ran an operation). A run that
   scores 0 on the target signature and then crashes, or that died before init, is **VOID - not a
   pass**. This mistake has been made twice in two days.

   > **The signature disappearing does NOT mean the bug is fixed.** A `TEST FAILED` with the target
   > signature at 0 is the single most misleading result you will get, because it looks like
   > success in every counter you were watching. Read the NEW fatal before concluding anything.
   >
   > #5285522: the patch removed `0xac5816` completely (0 occurrences, `LOG_OP` 252 — the test ran
   > properly), and the run still ended `TEST FAILED`, now on
   > `FailOnDiffInner: actual cap fields can't be less than expected` with three cap fields reading
   > `0x0` against an expected `0x1`. The defect had **two halves** and the first patch fixed one:
   >
   > | half | what it does | where |
   > |---|---|---|
   > | admission check | may this query proceed at all | `cmdif_checks.c` opmod switch |
   > | **data fill** | what gets written into the returned struct | `cmdif_commands.c` -> `fill_*_caps()` -> the `get_*_cur_cap()` getters |
   >
   > Both consulted the same tightened `*_cur_cap_sup()` helper, so patching only the gate turned
   > "request refused" into "request answered with zeros".
   >
   > **Generalise this:** when a cap/feature query misbehaves, the check path and the fill path are
   > two separate places and a semantic change underneath a shared helper hits both. Grep for every
   > caller of the helper you are changing (`grep -rn '<helper>' src/ include/`) before declaring a
   > fix complete — the compiler will not find these for you, and the test only shows you the first
   > one that trips.

6. **Run the control: same tree, same tag, same configs, same command, same seed, patch removed.**
   The control must still show the signature. If it does not, something other than your patch
   changed the outcome and the verification proves nothing - stop and find out what. This is the
   single most skipped step and the one that most often turns a "confirmed fix" into a retraction.

7. **Acceptance bar: a full green run is NOT required.** These are long randomised runs (200 iter x
   50 ops); unrelated failures are common and are not yours to fix. Peter's standing bar
   (2026-09-17):

   > **Getting past the original failure point with no similar fatal remaining counts as a fix.**

   So classify what is left, don't just count `TEST FAILED`:
   - **target signature gone** — necessary, not sufficient;
   - **no *akin* fatal** — nothing failing for the *same root cause* down another path. On
     #5285522 the akin fatal was `virtio_emulation_cap: <field> ... expected 0x1 Actual 0x0` — same
     cur/max semantics, different code path ⇒ that run was PARTIAL, not fixed;
   - **it got further** — compare `LOG_OP` count against the unpatched control. Same depth means
     you probably did not clear the original blocker at all;
   - **anything else** (traffic, steering, an unrelated checker) = unrelated failure ⇒ still a fix.

   Encode this in the run script's verdict rather than eyeballing it, and state in
   `FINDINGS_<ticket#>.md` §6 which remaining failures you judged unrelated and why.

   > **Two signals that you loosened a check TOO FAR** — both seen on #5285522's rejected v3:
   > - **`LOG_OP` *below* the unpatched control.** Fewer ops than baseline means the patch made the
   >   test fail *earlier*. A real fix moves that count up, never down. Zero target signature plus a
   >   shorter run is a regression wearing a success mask — which is why the verdict logic must
   >   compare against the control's depth instead of just checking "signature gone".
   > - **A field mismatch that flips direction.** The bug had FW under-reporting
   >   (`expected=0x1 Actual 0x0`). After over-loosening, the checker complained the other way
   >   (`expected=0x0 Actual 0x1`) — FW now advertising a capability the test knows that function
   >   must *not* have. Read the direction of a mismatch, not just its presence.
   >
   > **When the gate you want to relax was added by a named bug fix, that is a strong prior that
   > the strictness is deliberate.** Check `git log -S` on the line before touching it. Then settle
   > it with one build rather than an argument — and accept the answer when the run says the gate
   > was right. A failed experiment like this is not wasted: it converts "maybe we should relax this
   > one too" from an open question into a closed one. Record it in §5 as a rejected attempt with
   > the evidence, so the next person does not re-run it.

8. **Adjacent-case sanity pass** - a handful of neighbouring cases/ops, to catch a regression the
   fix itself introduces. A fix that kills the target signature while breaking its neighbours is
   not done.

9. **Record every run** in BOTH the Run log table (one row per run, note which build) and the
   Investigation log (before/after signature, control result, explicit verdict). Verdicts are
   `VERIFIED` / `VOID - <reason>` / `NOT REPRODUCED` / `PARTIAL` - never a bare pass/fail.

10. **Only a VERIFIED fix proceeds to Phase 11.** If verification fails, go back to root-cause work
   and **keep the failed attempt in the log** - the rule against "improving" a verified patch
   applies just as hard to a rejected one: the record is what stops the next attempt repeating it.

   > **Name patches by verdict, the moment the verdict is in.** Iterating leaves several candidates
   > in the ticket dir: use `FIX_<topic>.patch` for the one that passed (exactly one file) and
   > `REJECTED_<vN>_<why>.patch` for each disproved candidate. A superseded attempt still called
   > `fix_*` is indistinguishable from the deliverable - on #5285522 two `fix_*.patch` files sat
   > side by side and the reviewer had to ask which was real. Same for built images: keep one named
   > copy per candidate with its md5, since `jmake` overwrites the same output file every build.

11. **Write / finish `FINDINGS_<ticket#>.md`** (from `templates/findings.md`). Start it as soon as a
    root-cause hypothesis exists - do not defer it to "the write-up later". This is the deliverable
    handed to Peter and the code owner, and it is produced whether or not the Gerrit commit happens
    in the same session.

## Phase 9b — Codify the repro: write env_rebuild + per_run_reset (after first confirmed repro)

> **Write these scripts as soon as Phase 1–2 are decoded — do NOT wait for the box or for a
> confirmed repro.** Reserving a contended reg box can take hours; that waiting time is exactly
> when the scripts should be built, so the moment the lock lands you run instead of type.
> Everything they need comes from the session tarball, not the hardware.
>
> The old rule here was "only write them after the first confirmed repro." That was the wrong
> trade: it serialised writing behind waiting and left the first (most error-prone) attempt
> unscripted. What that rule was really protecting against is **false confidence**, and the fix
> for that is not delay — it is honest labelling plus opt-in danger:
> 1. **`!!! UNVERIFIED !!!` banner** at the top of each script until a run reproduces the exact
>    signature. Remove the banner in the same commit that records the first confirmed repro.
> 2. **Every destructive path is opt-in** — default mode is verify/read-mostly; burning, NV
>    clearing, and power operations need an explicit flag plus a typed confirmation.
> 3. **Ownership guard first.** Both scripts must refuse to touch the box unless
>    `noga_manage.py -q -n <box> -D` shows `Status.lock_owner == $USER`. A `hostname` check is not
>    enough — the nightly regression runs on that same box, and an `mst start` / `Fwreset` inside
>    someone else's live session corrupts it. Query Noga, compare the owner, exit non-zero.
> 4. **Gates that cannot yet be grounded start as warnings**, not hard aborts (e.g. a PCI-topology
>    gate before any real baseline has been captured — see the #5138907 trap below).

Once the repro is confirmed, write two scripts in `tools/` under the ticket's working dir and
`chmod +x` both. The split keeps env setup (slow, once per lock) separate from the per-run loop
(fast, runs many times).

### `tools/env_rebuild_<box>.sh` — run **from the dev box**, once per lock

Rebuilds the box environment from scratch. Canonical shape:

```bash
HOST=<reg box>
MUX=/tmp/ssh-cm-pexiang@${HOST}
SSH() {
    ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 \
          -o ControlMaster=auto -o ControlPath=$MUX -o ControlPersist=28800 \
          pexiang@$HOST "$@"
}
```

Steps (in order):
1. **Guard** — abort if utopx is already running (`SSH 'pgrep -o utopx.exe'`); `FORCE=1` to override.
2. **ControlMaster warm-up** — one `SSH 'echo connected'` to establish the master socket before
   any long-running command. This avoids NFS-home auth failures in the first ~30 s after boot:
   the socket stays alive for 28800 s (`ControlPersist`), so every subsequent SSH/sudo/flint
   reuses it without re-authenticating.
3. **Burn FW + INI** — launch `mlxburn` in background on the box via
   `SSH "sudo setsid bash -c 'mlxburn ... > /tmp/burn_<box>.log 2>&1' </dev/null &"`;
   poll `cat /tmp/burn_<box>.log` until "Image burn completed successfully" (or a `-E-` error).
4. **mlxconfig** — set all required NV params with `sudo mlxconfig -d <dev> -y s ...`.
5. **Power-cycle** — `$JMAKE --power-cycle $HOST`; then wait for SSH (poll `SSH 'echo UP'`).
6. **Verify** — `flint q` for FW version + PSID; `lspci` to assert baseline bus (≥2 functions);
   `ip link show tmfifo_net0` for ARM UP (BF/DPU only).
7. **Print the next step** — output the `per_run_reset.sh` command so the user can paste it.

One script per box (topology file, entry_points, expected PCI bus differ per machine).

### `tools/per_run_reset.sh` — run **on the reg box**, once per repro attempt

Runs the full repro sequence without re-burning. Default arguments hard-code the known-good
values (seed, iter count, utopx path, expected FW); callers override with `--seed N` `--iter N`
`-U PATH` `--any-fw`. Always verify hostname at entry (abort if called from the dev box).

Steps (in order):
1. **Guards** — `hostname -s` check (refuse if called from dev box); tool not already running;
   **assert the tool binary is the PRE-fix commit** (`git merge-base --is-ancestor <fix> HEAD`
   → abort if the fix is present, since a fixed tool can never trigger the defect).
2. `sudo mst start` + kill stale tool processes.
3. **FW gate** — `flint q` → assert expected FW version; abort with instructions to run
   `env_rebuild_<box>.sh` if wrong.
4. **PCI gate** — `lspci -D` → assert the *post-env_rebuild* topology. Derive this from a real
   captured baseline, never from intuition: enabling emulation/PCI-switch nvconfig inserts
   bridges and **shifts endpoints to a higher bus**, so the "obvious" pre-mlxconfig bus is wrong
   and the gate will abort every run (see the trap below).
5. `check_arm_agent.py` (BF/DPU suites only).
6. `Fwreset.py --next_udriver` (StartDriverAndBind).
7. **Baseline reset/health check — MUST PASS, hard abort.** Not a warning. Without it a
   post-run failure is indistinguishable from a pre-existing one.
8. **Snapshot the observable state** (`lspci -D | sort > before.txt`) — *before* running the tool.
9. **Run pre-fix tool at pinned seed** — `sudo ./<tool> ... --seed=$SEED ... 2>&1 | tee $LOG`.
10. **Snapshot again + diff** (`after.txt`, `diff -u before after`) — this diff is the evidence.
11. **Verdict — multi-factor, never single-signal** (see below).

Log to `<workdir>/per_run_seed${SEED}_$(date +%m%d_%H%M%S).log`; keep the before/after/diff
snapshots alongside it.

### Verdict discipline — the single most important part

Build the verdict from **independent** factors, and make the *direct evidence of the defect* the
deciding one. A downstream symptom (a later script failing) is corroborating at best:

| Factor | Role |
|---|---|
| baseline PASS | **precondition** — hard-gated at step 7 |
| tool actually initialised | **validity** — if it died at startup the run is VOID, not "reproduced" |
| expected syndrome/signature present | **trigger** — proves the defect path was entered |
| **before/after state diff non-empty** | **CORE** — proves the defect's actual effect |
| downstream script failure | **corroborating only — NEVER decisive** |

Report each factor separately in the output, and distinguish `RUN VOID` / `NOT REPRODUCED` /
`PARTIAL` / `REPRO SUCCESS` rather than collapsing everything into pass-fail.

> **Real false positive this rule comes from (#5138907, 2026-07-24).** The harness declared
> `✅ REPRO SUCCESS` on `post_run_fwreset_rc != 0` alone. In fact: the baseline Fwreset was
> *already* failing on an unrelated `PermissionError: /dev/rshim0/misc`; the tool never
> initialised (`ARM agent replied with error`, `Udriver init failed: no devices found`, exit
> 255); the syndrome appeared **0** times — the script itself printed "syndrome NOT seen" and
> declared success anyway; and the PCI address it cited as proof had shifted for an unrelated
> reason (see below). Four independent reasons the run proved nothing, and a single-signal
> verdict masked all four.

> **Trap — an env-setup side effect can perfectly mimic the bug's signature.** In #5138907 the
> signature was "PCI address changed". The address *did* change (81→83) — but because
> `mlxconfig` had enabled the emulated PCIe switch, which inserts bridges at 81/82 and moves the
> endpoints to 83. Normal, expected, and nothing to do with the bug. Always capture the topology
> **immediately after `env_rebuild` and before the tool runs**, and treat *that* as baseline —
> never an earlier snapshot, and never a bus number you reasoned out rather than observed.

### Conventions and checklist
- `chmod +x tools/env_rebuild_<box>.sh tools/per_run_reset.sh` immediately after writing.
- Both scripts: color-coded output (`hdr`/`step`/`ok`/`warn`/`err`/`note` helpers), `set -u`, and
  early-exit on every failure.
- **Writing them is not verifying them.** The first pair written to this spec had correct
  structure — multi-factor verdict, before/after PCI snapshot + diff, pre-fix-binary guard, hard
  baseline gate — and still carried a `REPRO SUCCESS` that was the false positive dissected
  above. Keep the `!!! UNVERIFIED !!!` banner until a run reproduces the exact signature.

## Phase 9b-bis — The box is re-provisioned DAILY: script the rebuild

**The nightly regression locks the box and re-provisions it, scrambling whatever you set up.**
So a repro environment is not something you build once — you rebuild it at the start of every
session. Budget for that, and make it **one command**.

This is why a ticket's own repro steps can be followed exactly and still fail: **they assume an
already-provisioned box.** The reporter ran them right after a regression, so the toolchain was
already in place and they never mention it.

**Find what the regression installs, from its own session tarball.** Look for a provisioning
step (`install_Tools.cap`, `install_Lock_Tools.cap`) and read its `log.txt` — it prints the
exact command and the pinned versions:
```bash
S=$(tar -tzf <sid>.tgz | grep install_Tools.cap | head -1 | sed 's|/install_Tools.cap||')
tar -xzOf <sid>.tgz "$S/log.txt" | grep -iE "install|version"
```
That yields the umbrella invocation (e.g. `install_tools_per_branch.py --install_ofed true
--install_mft true --install_udriver true …`) plus the exact OFED / MFT / driver versions.

> **The umbrella script may not run on your box's OS.** It shells out to sub-wrappers via their
> shebang (system python), and lab RegTools are older-python code — on a newer distro they die
> in dependency imports. Call each sub-wrapper explicitly with the lab's own python
> (`MARS_PYVERSION`, e.g. `/auto/sw_tools/OpenSource/python/INSTALLS/python_3.7.5/.../python3`).

**Write `tools/provision_<box>.sh`** — idempotent (skip what's present, `--force` to redo),
long steps launched detached so an SSH drop can't kill a 20-minute install, and a verify block
at the end. Order matters: a driver-stack install with `--force --all` typically **removes**
other tool packages, so reinstall them after it, not before.

**Then daily is:** `provision_<box>.sh` → `env_rebuild_<box>.sh` → `per_run_reset.sh`.

> **A missing component does not announce itself — it masquerades as "the documented steps
> don't work".** Before debugging the procedure, check the box actually has what the procedure
> assumes: MFT present, driver stack installed, the tool's Python deps, NFS mounted, the device
> visible in `lspci`. Each absence produces a failure that looks like a different bug entirely.

## Phase 9c — Reg-box realities that silently invalidate a run

Learned the expensive way on l-fwreg-102 (2026-07-27): ~4h lost and the card wedged twice.
Check these BEFORE blaming FW, the tool, or your own harness.

### The ticket's own repro steps outrank your script

If the reporter wrote out their steps in the ticket comments, **run them verbatim first.**
Two divergences, both of which cost a full cycle:
- **Dropping a setup step** (`clear_nv_data` + power-cycle) left the device in a *different
  starting topology* than the regression's — the bug then cannot present the same way.
- **Adding arguments** (`--timeout`, `--case_name`) to the recorded tool command.
Diff anything you think differs before assuming it matters: the two candidate INI files here
looked different by filename but were **byte-identical**.

### Privileged helpers: RegTools need `sudo`

`check_arm_agent.py` / `Fwreset.py` read `/dev/rshim0/misc`, which is `crw------- root root`.
Unprivileged they die with `PermissionError: [Errno 13] ... '/dev/rshim0/misc'` — so **every**
Fwreset fails, forever. Use `sudo -E python ...`.

> This single omission produced the #5138907 false positive: with Fwreset permanently broken,
> a verdict keyed on "post-run Fwreset failed" was true before the tool ever ran. If a gate
> fails identically both before *and* after your trigger, it is environment, not the bug.

### Reg boxes may NET-BOOT a fresh image on every reboot

On such boxes a power-cycle wipes installed packages and `/tmp`, and boot takes **10-19 min**
(not ~30s). Practical consequences:
- **MFT (`flint`/`mst`/`mlxburn`) disappears after every power-cycle.** Reinstall with
  `sudo apt-get install -y dkms` (prerequisite) then `sudo /mswg/release/mft/last_stable/install.sh`.
  Any script that power-cycles must re-ensure MFT before the next device op — wrap those two
  commands in an idempotent `ensure_mft()` and call it after every power-cycle, not once at start.
- **Write logs to NFS (`/auto/...`), never `/tmp`**, if they must survive a reboot.
- Size your `wait_host` timeout for the *slow* case; a 3-min bound will report a false "box did
  not return" on a box that needs 19.
- MARS reinstalls MFT during session setup, which is why this is invisible in regression logs.

### `clear_nv_data` opens a window where the card cannot boot

It erases every `NV_DATA` section (`flint v showitoc`), and the card needs an **immediate** FW
re-burn. On a net-booting box that is a trap: clear NV → power-cycle → MFT gone → the burn can't
run → the card strands in **Flash Recovery (Livefish)**
(`lspci`: `[BlueField-2 SoC Flash Recovery]`). Ensure MFT *before* the burn, and offer a
`--skip-nv-clear` switch for when NV was already cleared by a recovery run.

### Livefish recovery is a lab tool, not manual flashing

Use the **HCA System Service** web tool (Recovery History → run). Its pipeline is Pre-flight →
**Enable Livefish** → Cold Boot → Health Check → Device Check → FW Burn → **Disable Livefish** →
Final Cold Boot (~19 min). The explicit enable/disable-Livefish steps are what manual flashing
lacks. Verified: `mlxburn -d <BDF>` reporting "Image burn completed successfully", a full
`flint -no_fw_ctrl -i <img> b`, an IPMI power-cycle, and a 90s power-off **all failed** to bring
the card out.

> **Do NOT blind-flash a generic `.mlx` to "fix" Livefish.** It lacks device-specific sections
> (`DEV_INFO` carries that board's GUID/MAC); a full-flash write can clobber board identity. It
> did not help and only added risk. `mlxconfig` refuses in Livefish outright, and `/dev/rshim0`
> is absent, so the rshim/BFB route is unavailable too. Read-only diagnostics that DO work:
> `flint -d <BDF> q` and `flint -d <BDF> -no_fw_ctrl v showitoc`.

### Emulation nvconfig + power-cycle can hang the host at PCI enumeration

Applying a virtio-full-emu / multi-port emulated-PCI-switch config and power-cycling was fine
when layered onto existing NV, but wedged the host for >1h when the NV had just been rebuilt
from scratch (chassis power ON, no ping/SSH; a 90s power-off did not help). Same class of
failure that permanently wedged l-fwreg-068. **Prefer letting the regression bring the
environment up** (run its own session) and taking over from the post-mlxconfig state, rather
than reconstructing emulation NV by hand.

### Keep the lock on a wedged box

`noga_manage.py -l -t server -n <box> -L <hours> -N "<why> - under recovery by <user>"` so the
nightly regression does not schedule onto a broken card.

## Phase 10 — Between-runs reset discipline

Device/emulation state leaks between back-to-back runs; reset between every run:

| Method | Resets device state? | Time | When |
|---|---|---|---|
| `modprobe -r <drv> && modprobe <drv>` | ❌ | <1s | driver re-bind only |
| **`jmake --fw-reset`** | ✅ | ~20s | **default between-runs reset** (chip reset, lockfile-aware) |
| bare `mlxfwreset -y r` | depends | ~20s | underlying tool; may refuse with 3rd-party driver |
| **`jmake --power-cycle <box>`** | ✅ always | ~3 min | last resort: D-state zombie, `rev ff` lspci, wedged device |
| **`clear_nv_data.sh` + immediate re-burn** | ✅ **the only thing that clears NV** | ~12 min | NV state accumulated across runs — see below |

### `--fw-reset` does NOT clear NV. Repeated local runs poison the device.

**The nightly regression runs `clear_nv_data` once per session, so it always starts from clean NV.
A local repro loop does not — and the tool itself writes NV state.** Run the same case two or three
times in a row and the device drifts into a state the regression never sees.

Real case, #5285522 (2026-09-17): the bug reproduced perfectly on run 1. Runs 2 and 3 — same
official FW, same INI, same pinned seed — died in init instead:

```text
UFATAL GoldenTlvNvgn.cpp:375 WriteGoldenTlv
"GoldenTlv: Golden TLV data length exceeds maximum supported size — length: 516, max length: 255"
```

with **zero `LOG_OP` lines** and the target signature appearing **0 times**. Cause:
`GoldenTlvNvgn::PrepareGoldenTlv()` calls `ReadAllTlvsFromNvgn(dev)` — it reads **every NV TLV
currently on the device** and accumulates them; each run leaves TLVs behind, so by run 2 the total
blows past `NV_MAX_SIZE` (255). The same file even has `VerifyNoGoldenTlvInFlash()`, i.e. the test
expects no leftover golden TLV.

Two hours went into blaming the local build before the *official* image failed identically and
settled it. So:

- **If a setup that was reproducing stops reproducing after a run or two, suspect accumulated NV
  state before you suspect your build, your patch, or the box.**
- The tell is *how it dies*: died in init / no `LOG_OP` lines / target signature count 0 ⇒ the test
  never reached the bug. That is `VOID`, not "the fix worked" and not "cannot reproduce".
- **Any verification loop that runs the case more than once must clear NV between runs**:
  `clear_nv_data.sh <mst>` → **immediately** re-burn FW+INI → `--fw-reset` → bring-up → run.
  Build that into `per_run_reset.sh` (Phase 9b), not into your memory.

> **`clear_nv_data` is safe only if you can re-burn right after.** It erases every `NV_DATA`
> section (`flint -no_fw_ctrl e <addr>` per section found via `v showitoc`), and the card cannot
> boot until FW is re-burned. Verify MFT is present **before** erasing, do **not** power-cycle
> inside that window, and keep the Noga lock. On a net-booting box a power-cycle there removes MFT,
> the burn cannot run, and the card strands in Livefish. Script:
> `/auto/mswg/projects/fw/fw_ver/regression/clear_nv_data.sh` (takes the mst device).

Escalation when the light reset misbehaves: reset hangs >90s or `lspci` shows `rev ff`
→ power-cycle; failure on stale device-status/leftover-object → `--fw-reset` again, then
power-cycle. Avoid PCIe `remove`+`rescan` on parent bridges (can hang in `wait_woken`,
recoverable only by power cycle).

## Phase 11 — Commit the fix

Once a fix (in `golan_fw2` / `utopx2`) has been **verified on the test server (Phase 9.5)** -
signature gone, control still failing, run ended cleanly - commit it in the project's Gerrit format:

```
[<Type>][<Subsystem>] <concise summary>

1. <change one>          (for a pure refactor, item 1 is "No logic change.")
2. <change two>
3. <change three>

Issue: <ticket#>
Reviewed By: AI, Yanku
Change-Id: I<auto-generated by the gerrit commit-msg hook — do NOT hand-write>
```

Rules:
1. **Title = `[<Type>][<Subsystem>] <summary>`** — bracket tags then a concise summary, e.g.
   `[Bug][CORE] ...`, `[Feature][CORE] ...`. Keep it short.
2. **Body = numbered list** (`1.` `2.` `3.` …), one item per change, no prose paragraphs.
3. **`Issue: <ticket#>`** — the Redmine bug number from Phase 1 (this is how golan_fw links
   the commit to the tracker; do not put `#<ticket>` in the title).
4. **`Reviewed By: AI, Yanku`**.
5. **Author = Peter Xiang `<pexiang@nvidia.com>`**.
6. **`Change-Id:`** is appended automatically by the Gerrit `commit-msg` hook — never write
   it by hand; on amend, keep the existing one.

```bash
cd <repo>            # /auto/fwgwork1/$USER/golan_fw2 or utopx2
git add -p           # stage only the fix hunks

# Write the message to a file (keeps the numbered list + trailers intact; omit Change-Id —
# the commit-msg hook adds it):
cat > /tmp/repro_<ticket#>_commit.txt <<'EOF'
[<Type>][<Subsystem>] <concise summary>

1. <change one>
2. <change two>
3. <change three>

Issue: <ticket#>
Reviewed By: AI, Yanku
EOF

git -c user.name="Peter Xiang" -c user.email="pexiang@nvidia.com" \
    commit --author="Peter Xiang <pexiang@nvidia.com>" -F /tmp/repro_<ticket#>_commit.txt
git log -1 --format='%an <%ae>%n%n%B'    # verify author + message + auto Change-Id
```
> Commit/push only when the user asks.

Reference example of the exact format:
```
[Feature][CORE] Remove CR-space access from hal_icmc.h

1. No logic change.
2. In cmdif_checks_dmfs.c and cmdif_cmds_advanced.c, move all CR-space accesses into a dedicated HAL file.
3. For ICMC HAL, create hal_icmc_w_crspace.h and move all CR-space access macros and functions from hal_icmc.h into this new file.

Issue: 4635735
Reviewed By: YuvalA, Yanku
Change-Id: Ic8acf872ed8db2ea7aaf551024ff5ede8e5252a2
```
(Our repro commits use `Reviewed By: AI, Yanku`; the names above are just the sample's.)

## jmake / build-&-burn command reference (generic, distilled from the l-fwreg-171 playbook)

`jk` is an alias for `jmake` (`$HOME/.usr/bin/jmake`); use `jmake` directly in scripts.
All of these are device/feature-agnostic — substitute `<MST device>`, `<.mlx>`, `<INI>`,
`<host>`, `<model>`.

| Action | Command | Notes |
|---|---|---|
| **Build FW locally** | `cd <fw repo> && jmake -o --models <model>` | docker build (~8 min). Add `--clean` (`jk -c -o`) after a big branch switch / stale-depfile error. |
| **Build test tool** | `cd <tool repo> && jmake -o` (or `./build.sh`) | docker build (~8–30 min); product is `<tool>.exe`, output on NFS so the test box sees it. |
| **Burn FW + INI (no rebuild)** | `cd <fw repo> && jmake --burn --device <MST device> --firmware <.mlx> --ini <INI>` | replicates regression `BurnFw.py`. ~8 min. **Do NOT chain `--fw-reset`** (triggers a heavier reset that times out). |
| **Burn — NFS-permission fallback** | `sudo -E env MFT_ICMD_TIMEOUT=60000 mlxburn -d <MST device> -fw <abs .mlx> -conf <abs INI> -force` | use when `jmake --burn` hits `Permission denied` writing `image.bin` into a root-squashed NFS repo. |
| **Pivot flash → running** | `jmake --device <MST device> --fw-reset` | ~20s. The default between-runs reset; clears emulated-device state; lockfile + udriver-aware. |
| **Power cycle the box** | `jmake --power-cycle <host>` | ~3 min. Last resort (D-state zombie, `rev ff` lspci). Run `ssh -O exit <host>` first to drop the stale ControlMaster socket. |
| **Upgrade MFT** | `sudo jmake --mft-install` | wraps `/mswg/release/mft/last_stable/install.sh`; needed when a tool/symbol isn't recognized by the box's old MFT. |

Generic gotchas (all from the 171 playbook, not device-specific):
- **Even subminor versions are official-build-only** ("can only be compiled by official
  build"). For a local FW build, checkout the **next odd** release tag — same code, only
  the version tag differs — then `jmake -o --clean --models <model>`.
- **`jmake --fw-reset` ≠ bare `mlxfwreset`.** It wraps `fwreset.py`, adding
  `/tmp/fwreset_lock` + `/tmp/udriver_lockfile.lock`, multi-host coordination, function
  rebind, post-reset PCIe rescan, and an uptime before/after check. Bare `mlxfwreset` on a
  box with only a 3rd-party driver bound may refuse ("Tool is owner: Not supported").
- **`--fw-reset` is the right between-runs reset**; reserve `--power-cycle` for when
  `--fw-reset` itself hangs or the device shows `rev ff`.
- **`jmake --burn` only sets the image default**; a prior `mlxconfig set` on the box
  shadows it. Clear persistent overrides explicitly (`mlxconfig ... s <KNOB>=<default>`)
  if a reburn doesn't take effect.
