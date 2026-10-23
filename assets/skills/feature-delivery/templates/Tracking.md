# <Feature name> — feature progress

> Last updated: <YYYY-MM-DD HH:MM CST> · test side: <owner> · FW side: <owner>
> Status and progress of this feature. Every run and the step-by-step record: [Ledger.md](Ledger.md).

**What the feature is**: <2-4 plain sentences — the new behaviour, the function or command it adds, the repos
involved; e.g. "CX8 gets a page-supplier PCI function (PSF) that hands one large host-memory range to FW, and the
PFs take their ICM pages from that pool">

## 1. Current status

**In one sentence**: <where the feature stands and what it is waiting for>

| Part | Status | Detail |
|---|---|---|
| Test tool | <🔵 waiting for CI and review> | <changes not merged; CI state> |
| FW | <🟡 N changes not merged> | <...> |
| Gates | <both closed / opened locally only / open on master> | <the switch that keeps the new path dark on each side> |
| Device verification | <✅ main path runs> | <latest campaign, §2> |
| Requirements ([FR #<n>](https://redmine.nvidia.com/issues/<n>)) | <x of y verified> | §1.6 |

Status marks: ✅ done · 🟡 partial or worked around · 🔵 in progress or waiting · 🔴 blocked · ⬜ not started or not hit.

### 1.1 Commit status

#### 1.1.1 FW commit

Repository `golan_fw`, branch <branch>, owner: <owner>.

**Not merged** (the owner's current plan, not every open change in gerrit)

| Change | Content | Now | Version under test | Status |
|---|---|---|---|---|
| [<num>](https://git-nbu.nvidia.com/r/c/golan_fw/+/<num>) | <the gerrit title after "Title:", verbatim, a `<TAG>` in backticks> | PS<n> (<MM-DD>) | PS<m>, local `<sha>`; <result>, on <the other side's version when the result depends on it> ([Run log #<n>](Ledger.md#run-<n>)) | <what it does or fixes (§3 #<n>); unresolved comments; Code-Review and CI> |

**Merged** (by gerrit submit date)

| Change | Content | Now | Version under test | Status |
|---|---|---|---|---|
| [<num>](https://git-nbu.nvidia.com/r/c/golan_fw/+/<num>) | <the gerrit title, verbatim> | PS<n> (merged <MM-DD>; same content as PS<m>) | <in the base `<sha>` of the image under test; or PS<k>, local `<sha>`, same code as merged or not; or not in the image under test, and whether that matters> | <what it does or fixes; unresolved comments> |

FW image under test: <base SHA (version)> + <changes and patchsets>; image `<path>` (md5 `<md5>`).

#### 1.1.2 Utopx commit

Repository `fw_ver/utopx`, branch master, owner: <owner(s)>; <changes in another repository, e.g. `hca_fw/udriver`, named here>.

**Not merged** (the owner's current plan, not every open change in gerrit)

| Change | Content | Now | Version under test | Status |
|---|---|---|---|---|
| [<num>](https://git-nbu.nvidia.com/r/c/fw_ver/utopx/+/<num>) | <the gerrit title, verbatim> | PS<n> (<MM-DD>), topic `<topic>` | <the patchset that ran on the box, as in 1.1.1> | <what it does or fixes; unresolved comments; Code-Review and CI> |

**Merged** (by gerrit submit date)

| Change | Content | Now | Version under test | Status |
|---|---|---|---|---|
| [<num>](https://git-nbu.nvidia.com/r/c/fw_ver/utopx/+/<num>) | <the gerrit title, verbatim> | PS<n> (merged <MM-DD>; same content as PS<m>) | <as in 1.1.1: in the tree under test, or the patchset that ran and whether it is the merged code, or not in the tree> | <what it does or fixes; unresolved comments> |

### 1.2 Waiting for

1. **<person or team>**: <what, since when; path of the draft or message; the row whose status it holds up, e.g. §1.1 [<num>](<change URL>)>

### 1.3 Next steps

- <action> — <who>

### 1.4 Decisions needed from Peter

| Decision | Background |
|---|---|
| <question> | <facts and options; the section with the details> |

### 1.5 Redmine Ticket

<The Feature Request in one line: [FR #<n>](https://redmine.nvidia.com/issues/<n>), its state. Then: a ticket's status is kept here only, other sections link here; when Redmine was checked.>

#### 1.5.1 FW

| Ticket | Title | Opened by / assigned to | Opened | Status | Sprint | Relation and where |
|---|---|---|---|---|---|---|
| [<n>](https://redmine.nvidia.com/issues/<n>) | <subject> | <author> / <assignee> | <MM-DD> | <status, priority> | <sprint> | <the feature's own ticket first, then tickets others opened that the work touched; the Defects.md / Ledger.md section, linked> |

#### 1.5.2 Utopx

| Ticket | Title | Opened by / assigned to | Opened | Status | Sprint | Relation and where |
|---|---|---|---|---|---|---|
| [<n>](https://redmine.nvidia.com/issues/<n>) | <subject> | <author> / <assignee> | <MM-DD> | <status, priority> | <sprint> | <as above> |

### 1.6 Requirements

[FR #<n>](https://redmine.nvidia.com/issues/<n>).

| Req | Requirement | Assertion in the test tool | Verified? |
|---|---|---|---|
| <n> | <text> | [<file>:<line>](<path>?v=<commit>#L<line>), or none | <✅ run <MM-DD> / ⬜ no assertion yet> |

## 2. Test campaigns

Newest first.

| Date | Box / FW | Test-tool tree | Result | Report |
|---|---|---|---|---|
| <MM-DD> | <box> / <FW version> | `<sha>` | <n of m PASS; failures attributed> | [report_<MMDD>_<box>_<sha>.md](reports/report_<MMDD>_<box>_<sha>.md) |

## 3. Defects and fixes

The status of every defect lives in this table; how to hit it, the evidence and the fix are in [Defects.md](Defects.md). A defect worked as a ticket keeps its status in the ticket's own `Tracking.md`, which its row links.

| # | Problem | Side | Status |
|---|---|---|---|
| <n> | <one line> | <test tool / FW / udriver / existing code> | <✅ fixed in [<num>](<change URL>) / 🔵 fixed in local commit `<sha>`, not pushed / 🟡 worked around: <how> / 🔵 waiting for <who> / ⬜ not hit> |
| <n> | <one line> | <side> | ticket [<ticket#>](https://redmine.nvidia.com/issues/<ticket#>): [Tracking.md](../<ticket#>_<core>/Tracking.md) |

## 4. Timeline

Newest first, one line per day.

| Date | Progress |
|---|---|
| <MM-DD> | <what changed for the feature that day> |

## 5. Environment

<Where these facts were checked: the lab conf, the logs, the box.>

| Item | Value | Source |
|---|---|---|
| Box | <box; when mars_reg takes it back each night> | NOGA, MARS |
| Dev / build box | <the box the commands below run on> | — |
| Card | <card, PSID, the PCI functions> | `flint q`, `lspci` |
| MST device | <device> | `mst status` |
| MARS setup id | <the box's setup id, for the session check before touching it> | MARS results |
| FW image | <path, md5, FW Release Date> | [tools/lab.conf](tools/lab.conf) |
| INI and NV | <INI path; the NV recipe> | [tools/lab.conf](tools/lab.conf) |
| Test tool | <worktree, branch and commit; binary md5> | `git rev-parse`, the run log |
| FW source | <worktree, branch and commit> | `git rev-parse` |
| Feature gate | <the key `per_run.sh` passes as `-e <key>=1`; `--feature-off` passes 0> | [tools/lab.conf](tools/lab.conf) |
| Seed and arguments | <the seed and the -e arguments of the reference run> | [Run log #<n>](Ledger.md#run-<n>) |
| Logs | <where each step's log goes> | — |

## 6. Test steps

<Run on <dev box> as <user>, copied one command at a time from top to bottom; a command for the box
carries its own `ssh -o BatchMode=yes <user>@<box>`, and no variable is set beforehand. Check each
step's "Expected" before the next one. About <minutes> in all. The same steps with the scripts: 6.N.
mars_reg re-provisions the box every night, so every session starts at 6.1 and rebuilds it.>

### 6.1 Lock the box

```bash
~/myGit/crosslv/assets/skills/noga-lock/scripts/noga_watchdog.sh <box> --until-locked
python3 /.autodirect/sw_tools/Internal/Noga/RELEASE/latest/cli/noga_manage.py -q -t server -n <box> | grep lock_owner
mkdir -p <task dir>/logs/lock
nohup bash ~/myGit/crosslv/assets/skills/noga-lock/scripts/noga_watchdog.sh <box> >> <task dir>/logs/lock/watchdog_<box>.log 2>&1 &
```

Expected: `LOCK_ACQUIRED <time>` (or `ALREADY_OURS <time>`), then `Status.lock_owner = <user>`,
then the watchdog's first heartbeat line in its log. While someone else holds the box, the first
command waits for it, checking every 15 s; it never locks over a live lease.

### 6.2 Check the box before touching it

```bash
ls -td /auto/sw_regression/host_fw/HCA_CORE_FWV/MARS/conf/results/<setup_id>/*/ | head -1 | xargs -I{} sh -c 'echo {}; ls {}*.tgz'
ssh -o BatchMode=yes <user>@<box> 'ps -eo cmd | grep -cE "[u]topx\.exe|[R]egTools|[m]ars_tests|[F]wreset|[m]lxburn"'
ssh -o BatchMode=yes <user>@<box> 'sudo mst start >/dev/null; sudo flint -d <MST device> q full' > <task dir>/logs/flint_before_manual.log
```

Expected: <the newest MARS session has its `.tgz` — without it a session still runs on the box,
whatever NOGA shows; 0 processes; the FW the flash holds>.

### 6.3 <The first rebuild step>

<One subsection per rebuild step, in the order `env_rebuild.sh` runs them — the image gate, the NV
reset and recipe, the burn, making the box live (power-cycle or fw-reset), the driver binding, the
checks it prints — each with its full command and the expected output. A step done twice is written
out twice.>

```bash
<full command>
```

Expected: <the line that shows the step worked, verbatim, and the log it comes from>.

### 6.<k> One run with the feature on

```bash
<the pre-run reset, full command>
ssh -o BatchMode=yes <user>@<box> "cd <test-tool tree> && <the run command, with -e <gate>=1>" > <task dir>/logs/<label>.log 2>&1; echo "rc=$?"
```

Expected: <verbatim lines from a real run's log>.

### 6.<k+1> The control run with the feature off

```bash
<the same reset and run command, with -e <gate>=0, written out again>
```

### 6.<k+2> Check the result

```bash
grep -c '<fingerprint of the new path>' <task dir>/logs/<label>.log
grep -aoE 'TEST (PASSED|FAILED)' <task dir>/logs/<label>.log | tail -1
```

Expected: <the fingerprint count above 0 and `TEST PASSED` for the run with the feature on; a count
of 0 for the control; the reference run's numbers>.

### 6.<k+3> Build (when the code changed)

```bash
<the FW build, full command; where the image goes and its md5>
<the test-tool build, full command>
```

### 6.N The same steps with the scripts

<Which of the steps above each script does, and which it leaves out.>

```bash
bash <task dir>/tools/env_rebuild.sh --burn --yes
ssh -o BatchMode=yes <user>@<box> 'bash <task dir>/tools/per_run.sh --seed <N>'
ssh -o BatchMode=yes <user>@<box> 'bash <task dir>/tools/per_run.sh --seed <N> --feature-off'
```

Expected:

- env_rebuild.sh: <its last OK lines>, then `ENV_REBUILD_RC=0`.
- per_run.sh with the feature on: `NEW PATH EXERCISED (<n>), run clean` and exit 0 (5 OLD PATH ONLY,
  3 RUN VOID, 6 not clean); the control: `CONTROL PASSED - new path dark, run clean` and exit 0
  (4 CONTROL INVALID, 6 not clean). Where each run's files go.

## 7. Documents

| Document | Content |
|---|---|
| [Defects.md](Defects.md) | every defect: how to hit it, verbatim evidence, root cause, fix, rejected alternatives |
| [Ledger.md](Ledger.md) | every device run, and the step-by-step record of the work |
| [report_<MMDD>_<box>_<sha>.md](reports/report_<MMDD>_<box>_<sha>.md) | one test campaign each |
| [<document>](<relative path>) | <content> |
| [tools/lab.conf](tools/lab.conf) | <the box, image, INI, NV recipe and hooks of this task> |
| [tools/env_rebuild.sh](tools/env_rebuild.sh) | rebuilds the lab-box environment (run on the dev box) |
| [tools/per_run.sh](tools/per_run.sh) | one run on the box, with the verdict |
| [tools/<file>](tools/<file>) | <one row per further file in tools/> |

Directories: run logs in [logs/](logs/), with the environment, CI, fwtrace, lock and build logs in
[logs/env_rebuild/](logs/env_rebuild/), [logs/ci/](logs/ci/), [logs/fwtrace/](logs/fwtrace/),
[logs/lock/](logs/lock/), [logs/build/](logs/build/); FW images in [fw/](fw/); INI files in
[ini/](ini/); diffs of uncommitted trees in [patches/](patches/); reports in [reports/](reports/);
drafts in [drafts/](drafts/).

External: <Feature Request, HLD, MAS, FWV uArch, Redmine tickets — each as `[short name](URL)`, e.g. `[FR #<n>](https://redmine.nvidia.com/issues/<n>)`>
