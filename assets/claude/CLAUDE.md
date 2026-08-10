# Project Notes

- `jk` is an alias for `jmake` (located at `$HOME/.usr/bin/jmake`). Use `jmake` directly in Bash since shell aliases aren't available.
- When running builds in other directories, prefix with `cd /path/to/dir &&`.
- `code` is a bash function defined in `$HOME/Templates/code-function.sh`. It's a VS Code / Cursor remote CLI wrapper. Before using `code`, source the function first: `source $HOME/Templates/code-function.sh && code <args>`.
- If an `ssh` command is denied by the session permission system, use `myssh` instead with the same arguments (`$HOME/.usr/bin/myssh`, a symlink to /bin/ssh).

## Host: m-fwdev-167 (Ubuntu 20.04, glibc 2.31)

- ai-pim-utils CLIs (`confluence-cli`, `jira-cli`, `glean-cli`, `nvbugs-cli`, `redmine-cli`, `outlook-cli`, `calendar-cli`, `slack-cli`, `helios-cli`, `transcript-cli`, `pplx-cli`, `sharepoint-cli`, ...) run via the Docker container `pim` (image `ai-pim:latest`). Native binaries don't run on this host — glibc too old (need ≥2.34).
- Bashrc wraps all 28 CLIs as shell functions; just call them by name (`confluence-cli foo`). The wrapper lives in `~/myGit/crosslv/track-files/bashrc` guarded by `hostname -s == m-fwdev-167`.
- First call auto-starts the persistent `pim` container; subsequent calls `docker exec` into it (~10 ms overhead).
- Build the image: `docker build -t ai-pim:latest ~/myGit/crosslv/assets/aipim`. Dockerfile lives there too.
- Image lives on root fs at `/var/lib/docker/` (957 GB volume), not on the 5 GB NFS home.
- Helpers in bashrc: `aipim-shell` (interactive bash inside the container) — though the simple wrappers are usually enough.
- On any other NVIDIA host: native `~/.local/bin/*-cli` binaries work directly; the bashrc guard skips the docker wrap.

### After reboot (on m-fwdev-167)

- **No manual step needed.** The `pim` container persists in Docker's storage but transitions to `Exited` on shutdown. The bashrc wrapper `pim_ensure` does `docker start pim` on the next CLI call, which boots the existing container in ~1 s. Subsequent calls are `docker exec`.
- If you ever want to start it eagerly without invoking a CLI: `docker start pim`.
- All state in `~/.ai-pim-utils/` (tokens, config) and `~/.confluence_env` is on NFS home and survives the reboot.

### After reimaging m-fwdev-167 (or moving to a fresh box that still needs the wrap)

The image and container live on local disk under `/var/lib/docker/` and are **lost** on reimage. NFS-home state (`~/.confluence_env`, `~/.ai-pim-utils/`, `~/myGit/crosslv/`) survives. Recovery:

1. **Install Docker** — run `~/myGit/crosslv/jc --docker` (Peter's bootstrap script installs from the official Docker PPA).
2. **Add yourself to the docker group:** `sudo usermod -aG docker $USER`, then log out / back in so the new group is active. Verify: `id | grep docker`.
3. **Build the image:** `docker build -t ai-pim:latest ~/myGit/crosslv/assets/aipim` (~25 s — the Dockerfile fetches `install.sh` from a GitLab Pages URL and runs it inside ubuntu:24.04).
4. **First CLI call** auto-creates the `pim` container via the bashrc wrapper. No manual `docker run` needed.
5. **Token/credentials** are already in place under NFS home; no re-auth needed unless tokens have been rotated.

## Confluence writes (AI-only path)

- **For AI agents publishing/updating Confluence pages, use `~/myGit/crosslv/assets/aipim/confluence-update`** (raw curl). The user does NOT run this helper themselves — it is solely for AI use.
- **Do NOT use `confluence-cli page create/update`** for writes — those require an interactive TTY for typed confirmation, which AI sessions cannot provide. Reads (`page get`, etc.) are fine.
- Credentials in `~/.confluence_env` (mode 600), exporting `ATLASSIAN_EMAIL`, `ATLASSIAN_API_TOKEN`, `CONFLUENCE_BASE` (= `https://nvidia.atlassian.net/wiki`). User: `pexiang@nvidia.com`.
- Same Atlassian token works for `jira-cli` (Cloud Jira shares Atlassian auth).
- `confluence-update <page-id> <md-file>` updates an existing page. `confluence-update <md-file>` extracts the page id from a `<!-- confluence-page-id: N -->` HTML comment embedded in the markdown's front matter — convention: write that comment to a markdown file immediately after creating a Confluence page so future updates are idempotent.
- For **creating a new** page (the helper only updates), pattern after the curl POST used on 2026-05-28:
  1. `sed '1{/^# /d;}' <md> | pandoc -f gfm -t html5 > body.html` — strip the leading H1 (Confluence shows title separately) and convert to storage XHTML.
  2. Build JSON via `python3 json.dumps` (NEVER hand-quote — HTML breaks shell escaping). Payload: `{type:"page", title, space:{key:"FW"}, ancestors:[{id:"<parent>"}], body:{storage:{value:<html>, representation:"storage"}}}`.
  3. `POST $CONFLUENCE_BASE/rest/api/content` with `Content-Type: application/json`.
  4. Capture returned page id; add `<!-- confluence-page-id: <id> -->` to the markdown source.
- Confluence-specific macros (Page Properties, Info panels, Status badges) won't appear from plain markdown push — those need UI edits or pre-converted XHTML using `<ac:structured-macro>` tags.

## gitlab-master.nvidia.com

- SSH on **port 12051**, not the default 22. Clone with `git clone ssh://git@gitlab-master.nvidia.com:12051/<group>/<repo>.git`. The server prints this on banner if you connect on port 22.
- HTTPS clones need a PAT (`https://oauth2:<token>@gitlab-master.nvidia.com/<group>/<repo>.git`).

## Gerrit commit message format (nbu / fw_ver)

Follow this shape exactly. Getting it wrong wastes a review round every time.

```
Title: [<Tag>]<Area> short summary

Description: first line of prose starts right after the label
continuation lines start at column 0 — NOT indented to align under
"Description:"

Issue: 5149895

Reviewed By: AI, yanku

(cherry picked from commit <full 40-char sha>)

Change-Id: I<40 hex>
```

Rules that actually matter:
- **Continuation-line style is per-project.** For `fw_ver/utopx`, Peter's
  standard (2026-08-05) is **hanging indent**: continuation lines aligned
  under the text after `Description: ` (13 spaces), `Issue:` lines tight
  below with no blank line, blank line only before `Change-Id:`. The old
  column-0 rule below came from a golan re-wrap incident — apply it only
  where hanging indent is actually seen to collapse, don't carry it across
  projects.
- For golan (`fw_ver/golan_fw`): continuation lines at **column 0** (gerrit
  re-wrapped hand-aligned text there; the first line wraps, padded ones
  don't).
- **Keep every line ≤ 72 chars** (the `Title:` line may exceed it; gerrit only
  warns `subject >50 characters`, which is harmless). Wrap prose yourself —
  do not rely on the renderer.
- **Blank line between every block**: Title / Description / Issue / Reviewed By /
  cherry-pick note / Change-Id.
- `Change-Id` must be the **last** block. If adding `(cherry picked from …)`,
  put it in its own block **before** Change-Id, or gerrit stops parsing the footer.
- Take the cherry-pick sha from `git rev-parse <short>` — never hand-type it.
- Verify before pushing: `git log -1 --format=%B <sha> | awk '{print length($0), $0}'`

Sanity checks before any push:
- exactly one `Change-Id:` per commit — the commit-msg hook appends a **second**
  one when the message contains a non-standard trailer like `Reviewed By:`
  (note the space). Bypass it: `git commit --no-verify` / `commit-tree`.
- reusing a Change-Id that belongs to an **abandoned** change on the same branch
  gets the push rejected (`change ... closed`); generate a fresh one with
  `NEWCID="I$(git rev-parse HEAD)"`.

## Getting the raw failure log behind a test result

Applies to any MARS session (minireg / DoA / regressions) — all you need is the session_id.
Symptom: the upper layer reports only a verdict (Jenkins `Completed golan_fw_minireg #N : FAILURE`,
or an email report saying `Failed: 2`) with no hint of which case failed or why.

Three hops to the original log, **no authentication needed at any step**:
1. `curl https://mars.nvidia.com/api/session/<session_id>` — returns XML (the `/ui/...` web page
   requires interactive login and 302s; the API does not). Take `<RESULT_DIR>` from it. It also
   reports `PASSED`/`FAILED`/`IGNORED`/`NATIVE_STATUS` — check these first to tell
   "ran and then failed" from "never got started".
2. `<RESULT_DIR>/<setup name>/<session_id>/<session_id>.tgz` — the full archive, readable
   directly over NFS.
3. Unpack it, then filter on `result:` in each `status.txt`: `0`=pass, `1`=fail, `2`=not executed.
   **Only the deepest leaves carrying `result: 1` are the real failing cases** — parent nodes
   merely propagate it upward. The sibling `log.txt` holds the raw
   `UFATAL` / `Field mismatch: expected=X Actual=Y` / `To rerun use seed N`.

Where to get the session_id: `--session_id N` in the upstream log, `Amonitor.php?session_id=N`,
or the table in the email report.

**Attribution discipline**: before calling a failure "environment" or "our code", find a control
sample matching on **branch + mode + setup** — did someone else's change pass under identical
conditions? Drop any one of those dimensions and the conclusion can flip. Log size and whether
the node was taken offline are **not** valid evidence; node offlining is the system's generic
response to any failure.

`fsearch` only records case-level failures — anything dying in setup/init never reaches it.
It also **returns 0 rows silently when a parameter value is invalid**, so judge by elapsed time:
a real query takes 70–90 s; an instant return is a false negative.

## Re-running utopx CI on a gerrit change

Credentials live in `~/.jenkins_env` (mode 600, NFS home, survives reboots).
`source` it to get `JENKINS_URL` (internal, l-jenkins-005) /
`JENKINS_BLOSSOM_URL` (blossom, where utopx_ci itself runs) / `JENKINS_USER` /
`JENKINS_API_TOKEN`. **Keep the token in that file only** — never in docs, memory
or commit messages. Regenerate at `$JENKINS_URL/user/<user>/configure`.

Re-runs go through the dedicated **`utopx_ci_rerun`** job — do not re-trigger
`utopx_ci` directly.

```bash
source ~/.jenkins_env

# 1. ALWAYS read the current REASON choices first. The list is edited over time
#    (dated entries get added and removed) and the value must match verbatim.
curl -s -u "$JENKINS_USER:$JENKINS_API_TOKEN" "$JENKINS_URL/job/utopx_ci_rerun/api/json" \
| python3 -c "import sys,json;d=json.load(sys.stdin);[print(c) for a in d['actions'] for p in a.get('parameterDefinitions',[]) for c in p.get('choices',[])]"

# 2. ALWAYS check concurrency before triggering. utopx_ci caps at 15 and the
#    scheduler HARD-ABORTS the excess ~1 min in (CI Execution Checkpoint stage) —
#    it does not queue. Wasted runs also spawn a new patchset each time.
curl -s "$JENKINS_BLOSSOM_URL/job/utopx_ci/api/json?tree=builds%5Bnumber,building%5D" \
| python3 -c "import sys,json;print(sum(1 for b in json.load(sys.stdin)['builds'] if b.get('building')))"
#    Do NOT add a range like {0,40}: long builds and quickly-aborted ones interleave,
#    so a windowed query under-counts badly (measured 8 when the real figure was 26).
#    Trigger only at <= 11, and re-measure 20 s later to avoid a transient dip.

# 3. Trigger (expect HTTP 201)
CRUMB=$(curl -s -u "$JENKINS_USER:$JENKINS_API_TOKEN" "$JENKINS_URL/crumbIssuer/api/json" \
        | python3 -c "import sys,json;print(json.load(sys.stdin)['crumb'])")
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  -u "$JENKINS_USER:$JENKINS_API_TOKEN" -H "Jenkins-Crumb: $CRUMB" \
  --data-urlencode "CHANGE_URL=https://git-nbu.nvidia.com/r/c/fw_ver/utopx/+/<change>" \
  --data-urlencode "REASON=<one choice, verbatim>" \
  "$JENKINS_URL/job/utopx_ci_rerun/buildWithParameters"

# 4. Confirm it actually started, and that it survived the checkpoint ~90 s later
#    (that gate is where over-concurrency kills it).
```

Notes:
- `$JENKINS_BLOSSOM_URL` serves `consoleText` and `api/json` **anonymously** —
  reading logs needs no auth. The `nvidia-jenkins` MCP fails against it
  (`not a member of SSA-allowed DLs: blossom-sre`), so use curl.
- Anonymous has read-only rights on `utopx_ci_rerun`; the token is what allows triggering.
- `/auto/mswg/projects/fw/fw_ver/jenkins/svc-sw-hca-bot.auth` is readable but belongs
  to the CI service account — do not use it for manual re-runs, the audit trail
  would name the bot instead of you.
- **Get Code-Review+2 in place BEFORE re-running.** The `utopx_ci_rerun` job will
  happily start, but the pipeline's own `Pre Gerrit Validation` stage hard-checks
  the vote and aborts with
  `Code-Review vote is insufficient` / `Strongest Vote: 0` — it never reaches
  Compile or DoA. Pushing a new patchset outdates existing votes, so after any
  re-push you must re-collect CR+2 first. Do not plan on "run it green, then get
  the vote"; that order does not work.
- **A re-run cannot fix a deterministic failure.** DoA uses fixed seeds, so a real
  code defect reproduces identically every time. Confirm the failure is
  environmental first (see the attribution discipline above); otherwise each
  re-run only burns a queue slot and copies stale `Verified-1` votes onto a new
  patchset.

## Monitoring and locking a lab server (NOGA)

Generic recipe for "watch server X until it frees up, take it, then set it up". Works for any
host in the NOGA pool; substitute `$HOST`. The concrete sat-PF example is in the next section.

### Query, take, release

```bash
CLI=/.autodirect/sw_tools/Internal/Noga/RELEASE/latest/cli/noga_manage.py
HOST=l-fwreg-171                              # any pool host

python3 $CLI -ql -t host -n $HOST             # query -> Status.lock_owner / Status.lock_time_out
python3 $CLI -l  -t host -n $HOST -L 8        # take for 8 h; also renews when already ours
python3 $CLI -u  -t host -n $HOST             # release
```

`-l` on a host you already hold just extends the lease, so a monitor can call it blindly.
A refused grab is harmless — keep polling.

### Reading `lock_time_out`

It is **UTC**, formatted `DD-MON-YY HH.MM.SS.ffffff AM/PM` (local CST = UTC+8). Always convert
before reasoning about it; doing it in your head has caused a 23-minute error before.

```python
from datetime import datetime, timezone
dt = datetime.strptime(s, "%d-%b-%y %I.%M.%S.%f %p").replace(tzinfo=timezone.utc)
seconds_past_expiry = int((datetime.now(timezone.utc) - dt).total_seconds())   # >0 == expired
```

### When you may take a lock

1. `lock_owner` is empty — free, take it.
2. `lock_owner` is set **but** `lock_time_out` is more than a grace period (15 min works well)
   in the past. **NOGA does not clear `lock_owner` when a lease expires**, so a monitor that
   only waits for an empty owner can idle for hours beside a lock that already lapsed. This
   cost ~7 h of waiting once before the rule was understood.
3. Otherwise wait. Do not fight a live holder; in this pool `mars_reg` is the regression
   service and always wins by convention. Note its habit: it releases around **13:05–13:15 CST**,
   typically well before its nominal timeout.

### The monitor loop

Run it as a `run_in_background` Bash task and **chain the setup work into the same task**, so
the whole grab-and-provision sequence is unattended and reports once at the end.

```bash
for i in $(seq 1 480); do                      # 480 * 60 s = 8 h ceiling
  Q=$(python3 $CLI -ql -t host -n $HOST 2>/dev/null)
  owner=$(echo "$Q" | grep -i lock_owner    | awk -F'= ' '{print $2}' | tr -d ' ')
  tout=$( echo "$Q" | grep -i lock_time_out | awk -F'= ' '{print $2}')
  [ "$owner" = "$USER" ] && { echo "ALREADY_OURS"; break; }
  exp=$(python3 expiry.py "$tout")             # helper from the snippet above
  if [ -z "$owner" ] || [ "$exp" -gt 900 ]; then
    python3 $CLI -l -t host -n $HOST -L 8
    owner=$(python3 $CLI -ql -t host -n $HOST | grep -i lock_owner | awk -F'= ' '{print $2}' | tr -d ' ')
    [ "$owner" = "$USER" ] && { echo "LOCK_ACQUIRED $(date '+%F %T')"; break; }
  fi
  [ $((i % 20)) -eq 0 ] && echo "heartbeat t=+${i}min owner=$owner expired=${exp}s $(date '+%H:%M')"
  sleep 60
done
# ... then: inventory the box, rebuild it, verify ...
```

Emit a heartbeat every ~20 iterations carrying **both** the owner and seconds-to-expiry — that
one line answers "is the task alive" and "how much longer" at a glance.

### Practical notes

- **Session commands such as `/model` can kill background tasks.** If the user switches models
  mid-wait, re-check liveness (output-file mtime, plus `ps`) and restart the monitor. A silent
  dead monitor looks exactly like a busy one.
- Poll at 60 s. Anything faster only adds load; the interesting transition happens once a day.
- Reaching the box: `sshpass -p <pw> ssh -o StrictHostKeyChecking=no -o ControlMaster=auto \
  -o ControlPath=/tmp/ssh_mux_<box> -o ControlPersist=28800 root@$HOST`. Give each box its own
  mux socket, otherwise concurrent work on two machines crosses wires.
- After any power cycle the mux socket is stale — close it (`ssh -O exit`) before reconnecting.
- **Verify the final state yourself instead of trusting the setup script's own summary.** Scripts
  have reported READY off a stale or partially-applied config more than once.
- Release locks you are no longer using — holding several boxes "just in case" blocks other teams.

## Un-bricking a NIC that vanished from PCI (Livefish, fully remote)

Symptom: `lspci -d 15b3:` returns 0, `/dev/mst` empty, and the PCIe **root port itself** is gone
from `lspci` (BIOS hides a port whose link never trained). Typical cause: an mlxconfig write the
board cannot enumerate under. Neither `mlxfwreset` nor any power cycle recovers this — the card
never gets far enough to answer.

**Use `relay_controller.py`, not `fishme.py`.** The Confluence pages (FW/2830883398,
SW/2937307643) document `fishme.py`, which needs a USB-serial controller at `/dev/ttyUSB*` on a
separate "livefish host". Most reg boxes have no such thing and Noga carries no livefish fields
for them — that path dead-ends. The relay board is reachable over the network instead.

```bash
# Tool (clone once): ssh://<user>@git-nbu.nvidia.com:12023/hca_fw/hca_system_service
R=hca_system_service/BackEnd/relay_controller.py
LF=<host>-lf                 # plain DNS entry, e.g. l-fwreg-055-lf -> 10.141.203.103
BMC=<host>-ilo               # plain DNS entry too; creds ADMIN/ADMIN
IPMI="ipmitool -I lanplus -H $BMC -U ADMIN -P ADMIN"

# ==== STEP 0, DO NOT SKIP ====
# The recovery burn needs -ignore_dev_data, which does NOT write the device-data
# section: Base GUID and Base MAC come back as N/A and the card is unusable
# (utopx dies at DeviceInfo.cpp:37 "Unknown device"). Record them for EVERY card
# that will enter recovery — `-m enable` defaults to `-p all`, so that is all of them.
for D in /dev/mst/mt*_pciconf[0-9]; do
  echo "== $D"; flint -d $D q full | grep -E '^(Base GUID|Base MAC|PSID)'
done
# If the card is already dead and you never recorded this: do NOT invent a GUID —
# a made-up value can collide with another card in the lab. Get the original from
# lab inventory / VPD instead.

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

# ==== STEP N, the other half of step 0 ====
# Card enumerates again but GUID/MAC are N/A. Write back the recorded values, per card:
flint -d /dev/mst/mt4133_pciconf0 -y --guid <GUID> --mac <MAC> sg
reboot                                    # or mlxfwreset, to load it
flint -d /dev/mst/mt4133_pciconf0 q full | grep -E '^(Base GUID|Base MAC)'   # verify
# `Orig Base GUID: N/A` afterwards is expected — the original device data is gone;
# what matters is that Base GUID / Base MAC now read the recorded values.
```

- **A recovered card is not yet a usable test environment.** Livefish only gets it enumerating.
  Three separate things still have to be restored, in this order:
  1. **GUID/MAC** — see step N above.
  2. **The FW build the environment actually expects.** Livefish forces a raw `.bin`, so you burn
     whatever official release image matches the PSID. A verification environment usually wants
     the internal build instead (`/mswg/projects/fw/fw_ver/mfa_dir/<ver>/*.mfa2`). The release
     image lacks verification-only commands such as `GET_GVMI`, and utopx then dies at
     `DeviceInfo.cpp:37 "Unknown device"` — `GetDevType()` returns `cmd_get_gvmi.device_id`, which
     is 0 on a release image, so the switch falls through to `default`. Same version string and
     same PSID on both, so `flint q` cannot tell them apart. Re-burn with the `.mfa2` once the
     card enumerates normally (that path writes device data properly, unlike `-ignore_dev_data`).
  3. **NV config** — erasing the flash returns the board to its factory personality (an `IB_2P`
     board comes back as IB), so re-apply `LINK_TYPE` and friends.
- **Burn FW first, set NV config second.** In the other order the new firmware's defaults overwrite
  what you just configured.
- Bind one PF back to `mlx5_core` before a normal burn. From a udriver-only state flint warns
  `BME is not set, DMA access is not supported` and the burn takes minutes instead of seconds.
- After recovery the mst nodes go back to `mt4133_pciconf*`, and **the pciconf↔BDF mapping may
  differ from before**. Always re-check with `mst status -v` before configuring or burning.
- The burn rewrites the whole flash, **wiping the NV config with it** — exactly what you want when
  a bad mlxconfig is what broke the card. Note this also means the board reverts to its factory
  personality (an `IB_2P` board comes back as IB), so re-apply `LINK_TYPE` etc. afterwards.
- In livefish the device cannot report its PSID, so flint cannot pick an image out of an `.mfa2`
  archive. **A raw `.bin` is mandatory.**
- Run `flint ... -ocr hw query` first: it prints flash type/size and `Flash0.WriteProtected`. Only
  issue `hw set Flash0.WriteProtected=Disabled` if it actually reads enabled.

### The mlxconfig rule this exists to prevent

**Never bulk-transplant a whole mlxconfig dump onto another box.** Diff the two and set only the
handful of parameters that bear on what you are chasing. Replaying a 457-parameter dump from a
reference box in one `mlxconfig set`, followed by a cold boot, took out three cards in one day.

Be honest about what is and is not known here:

- The two boards were **identical** (`900-9X91E-00EB-ST0_IB_2P_CORE_INT_DK_Ax`, same PSID), so
  this was *not* an SKU mismatch — an earlier write-up of this incident claimed it was, wrongly.
- The dump contained only 2 read-only parameters and neither was written, so that is not it either.
- **The actual mechanism was never established.** One untested theory is that a single `set`
  transaction that large leaves the NV section inconsistent. Nobody should brick a fourth card to
  find out.

What is certain is the empirical rule: apply a few parameters at a time, read back Next Boot after
each, and verify Current after the cold boot. Treat anything that re-lays the PCI/BAR map with
extra care — `PF_LOG_BAR_SIZE`, `NUM_PF_MSIX` / `NUM_VF_MSIX`, `MEMIC_BAR_SIZE`, `PF_BAR2_*`,
`PCI_SWITCH_EMULATION_*`, `*_EMULATION_ENABLE`.

**Stop at the first anomaly.** After one cold boot the card was still present but its FW had
reverted and `LINK_TYPE` had moved **in the Default column** — a Default can only change if the
running FW changed, i.e. the device was already unwell. Reading that as "the config didn't take"
and pushing another burn + cold boot is what finished it off.

## Example: rebuilding the sat-PF test env on l-fwreg-171

Concrete application of the loop above. `l-fwreg-171` (BF-3, PSID `MT_0000000998`) is currently
the only turnkey box for this feature.

`mars_reg` always hands the box back re-burned (typically FW `32.50.xxxx`, `LINK_TYPE=IB`, an
odd `bus81` count), so rebuild unconditionally after taking the lock:

```bash
bash /auto/fwgwork1/pexiang/bugZilla/OCI_EMU/tools/env_rebuild_171.sh
# parameterised for other 998 boxes:
# HOST=<box> ARM_IP=<arm ip> EMU_BUS=<bus> bash env_rebuild_171.sh
```

It burns the FUR `.mlx` + the 998 gate INI, writes the x86 NV set, sets `PF_NUM_SAT_PF=1` on
both ARM ECPFs, and power-cycles (~10–15 min). Then verify independently:

| Check | Expected |
|---|---|
| `flint -d /dev/mst/mt41692_pciconf0 q` | FW `32.48.6007` |
| `mlxconfig -e q LINK_TYPE_P1 LINK_TYPE_P2` | `current=ETH(2) next=ETH(2)` on both |
| `mlxconfig -e q VIRTIO_NET_EMULATION_NUM_PF` | `current=3 next=3` |
| `lspci \| grep -c '^81:'` | **8** = 2 CX7 + 2 NVMe SNAP + 3 virtio-net + 1 SoC-mgmt |

ARM `PF_NUM_SAT_PF` normally reads back as unreadable — the DOCA sshd does not come up once
sat-PF materializes. Known and non-blocking; `bus81=8` together with ETH links is the proof.

Then run a test with:

```bash
ssh root@l-fwreg-171 'bash /auto/fwgwork1/pexiang/bugZilla/OCI_EMU/tools/per_run_reset.sh \
    -U <utopx repo> --seed 3975318385 --iter 300'
```

It gates on FW `32.48.6007` (`--fw` / `--any-fw` to override) and on `bus81=8`, refusing to
launch off-baseline rather than producing junk results.

### Firmware-config traps worth carrying to any BlueField box

- **`mlxconfig "Applying... Done!"` does not mean the write landed.** Right after a burn the NV
  set can report Done while next-boot stays unchanged. Always read next-boot back.
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

### Machine pool for this PSID

```bash
/mswg/projects/fw/fw_ver/hca_fw_tools/noga_allocation/get_setups_info.py \
    --team_name hca_fw --where "psid MT_0000000998"
```

26 boxes, but effectively only 171 is usable:

- **171** — Ubuntu 20.04, ARM eMMC carries DOCA. The only turnkey box, hence the daily contention.
- **183** — the only box where satellite PFs actually materialize (ARM `00:00.2/.3`), but it runs
  RHEL 7.4 (glibc 2.17) and **cannot execute utopx** (the binary needs glibc ≥2.29 /
  GLIBCXX_3.4.26 and only a `ubuntu/20.04` build exists). Reference box only. Its tmfifo is
  mirrored (ARM=`.2`), PCI lands on bus 83, and its ARM `/dev/mst` nodes are stale — address its
  ECPFs as `mlxconfig -d pciconf-00:00.0`.
- **147 / 149 / 178 / 179 / 180** — Ubuntu, so utopx would run, but their ARM eMMC has no OS
  (`UP_TIME` climbs with no `DPU is ready` / `Linux up`, console silent). That is why they sit
  idle. Enabling one costs a BFB push (~30 min; `tools/bf_171.cfg` is a working config).
- The `VirtIO` partition is tagged `INCOMPATIBLE_UTOPX` — skip it.
