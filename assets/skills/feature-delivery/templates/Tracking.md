# <Feature name> — feature progress

> Last updated: <YYYY-MM-DD HH:MM CST> · test side: <owner> · FW side: <owner>
> Status and progress of this feature, for Peter, the owners and the reviewers. Step-by-step records: [Ledger.md](Ledger.md).

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

### 1.1 Test-tool commits

`<project>`, owner: <owner(s)>.

**Not merged** (the owner's current plan, not every open change in gerrit)

| Change | Content | Owner | Now | Status |
|---|---|---|---|---|
| [<num>](https://git-nbu.nvidia.com/r/c/<project>/+/<num>) | `<title>` | <user> | PS<n>, topic `<topic>` | <CI and review state> |

**Merged** (by gerrit submit date)

| Change | Content | Owner | Merged |
|---|---|---|---|
| [<num>](https://git-nbu.nvidia.com/r/c/<project>/+/<num>) | `<title>` | <user> | <MM-DD> |

### 1.2 FW commits

`golan_fw`, <branch>, owner: <owner>.

**Not merged**

| Change | Content | Now | Version under test | Status |
|---|---|---|---|---|
| [<num>](https://git-nbu.nvidia.com/r/c/golan_fw/+/<num>) | `<title>` | PS<n> (<MM-DD>) | PS<m> | <...> |

**Merged** (by gerrit submit date)

| Change | Content | Owner | Merged |
|---|---|---|---|
| [<num>](https://git-nbu.nvidia.com/r/c/golan_fw/+/<num>) | `<title>` | <user> | <MM-DD> |

FW image under test: <base SHA (version)> + <changes and patchsets>; image `<path>` (md5 `<md5>`).

### 1.3 Waiting for

1. **<person or team>**: <what, since when; path of the draft or message>

### 1.4 Next steps

- <action> — <who>

### 1.5 Decisions needed from Peter

| Decision | Background |
|---|---|
| <question> | <facts and options; the section with the details> |

### 1.6 Requirements

[FR #<n>](https://redmine.nvidia.com/issues/<n>).

| Req | Requirement | Assertion in the test tool | Verified? |
|---|---|---|---|
| <n> | <text> | [<file>:<line>](<path>#L<line>), or none | <✅ run <MM-DD> / ⬜ no assertion yet> |

## 2. Test campaigns

Newest first.

| Date | Box / FW | Test-tool tree | Result | Report |
|---|---|---|---|---|
| <MM-DD> | <box> / <FW version> | `<sha>` | <n of m PASS; failures attributed> | [report_<MMDD>_<box>_<sha>.md](report_<MMDD>_<box>_<sha>.md) |

## 3. Defects and fixes

The status of every defect lives in this table; how to hit it, the evidence and the fix are in [Defects.md](Defects.md), or for a defect worked as a ticket in its `Rc` (§6).

| # | Problem | Side | Status |
|---|---|---|---|
| <n> | <one line> | <test tool / FW / udriver / existing code> | <✅ fixed in [<num>](<change URL>) / 🔵 fixed in local commit `<sha>`, not pushed / 🟡 worked around: <how> / 🔵 waiting for <who> / ⬜ not hit> |

## 4. Timeline

Newest first, one line per day.

| Date | Progress |
|---|---|
| <MM-DD> | <what changed for the feature that day> |

## 5. Environment and how to run

- **Boxes**: <box(es) and their constraints, e.g. nightly takeover times>
- **FW, INI and NV**: <image, INI, NV recipe; the single source is [tools/lab.conf](tools/lab.conf)>
- **Code**: <worktree paths and branches>
- **Rebuild the box**: `bash <task dir>/tools/env_rebuild.sh --burn --yes`
- **One run**: `ssh -o BatchMode=yes <box> 'bash <task dir>/tools/per_run.sh --seed <N> <-e args>'` — exit 0 means the
  new path ran and the run is clean
- **Build the FW and the INI**: <commands>

## 6. Documents

| Document | Content |
|---|---|
| [Defects.md](Defects.md) | every defect: how to hit it, verbatim evidence, root cause, fix, rejected alternatives |
| [report_<MMDD>_<box>_<sha>.md](report_<MMDD>_<box>_<sha>.md) | one test campaign each |
| [Ledger.md](Ledger.md) | step-by-step record of the work |
| [<document>](<relative path>) | <content> |
| [tools/lab.conf](tools/lab.conf) | <the box, image, INI, NV recipe and hooks of this task> |
| [tools/env_rebuild.sh](tools/env_rebuild.sh) | rebuilds the lab-box environment (run on the dev box) |
| [tools/per_run.sh](tools/per_run.sh) | one run on the box, with the verdict |
| [tools/<file>](tools/<file>) | <one row per further file in tools/> |

Logs the documents cite are in [logs/](logs/).

External: <Feature Request, HLD, MAS, FWV uArch, Redmine tickets — each as `[short name](URL)`, e.g. `[FR #<n>](https://redmine.nvidia.com/issues/<n>)`>
