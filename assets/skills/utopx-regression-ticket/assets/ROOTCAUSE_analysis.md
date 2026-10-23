# Redmine #<ticket#> — Root cause analysis

> `<one-line failure signature>` — `<branch/tag>` / `<device family>` / `<box>`
> **Status at upload:** `<ROOT-CAUSE FOUND | FIX VERIFIED | COMMITTED>` · `<YYYY-MM-DD>`

## 1. Issue summary

- Redmine: [<ticket#>](https://redmine.nvidia.com/issues/<ticket#>)

**Failure signature** (verbatim):

```text
<exact fatal / UFATAL / mismatch string>
```

- What actually goes wrong, in plain English: <2-4 sentences a reader new to this subsystem
  understands>
- Reported by / first seen: <who filed it, which nightly session>

## 2. Where it happens

| Software versions | |
|---|---|
| FW branch / release line | <e.g. `master` (golan_fw `master_rc`)> |
| Test-tool branch / tag | <e.g. `master`; tag `host_fwv_<date>_FW_version_<ver>_branch_<line>`> |
| FW version | <e.g. 32.51.0290 (source `rel-12_51_0290` @ `<sha>`)> |
| Test-tool commit | <e.g. `46d115e`> |
| Target release (ticket fixed_version) | <e.g. Host FW - 51.1000 GA Release> |

| Hardware / environment | |
|---|---|
| Device / chip family | <e.g. MUSTANG / BlueField-3 (`fw-<devid>`), PSID> |
| MST device | <e.g. `/dev/mst/mt41692_pciconf0` (PCI `0000:81:00.0`)> |
| Box | <the original box; a substitute and why, if one was approved> |
| Topology mode | <e.g. `eth_ARM_AGENT`> |
| Entry points | <e.g. `<box>-rocep129s0f0-P1` / `-f1-P1`> |
| NV knobs that arm the bug | <the config that must be set for it to fire> |

| MARS coordinates | |
|---|---|
| setup_id | <...> |
| session_id | <...> |
| key_id (failing step) | <...> |
| Test / case name | <...> |
| Time of failure | <...> |
| view_log | [view_log](<the view_log.php URL from the ticket>) |

| Repro execution | |
|---|---|
| Exact command | `<command>` |
| Seed | `<N>` |
| Where it failed | <VHCA/GVMI, HCA stage, the operation that tripped> |
| Deviations from the recorded command | <each argument dropped or added, and why> |

### Every path used

**Official artifacts (read-only)**

| Purpose | Full path |
|---|---|
| Official FW image | `/auto/sw/release/host_fw2/fw-<devid>/fw-<devid>-rel-<ver>-build-001/dist/<image>.mlx` |
| Release default INI (diff reference only) | `.../dist/<psid>.ini` |
| INI the regression actually burned | `/auto/sw/work/hca_fw/data/burn_fw/ini_files/..._session_<sid>_version_<ver>_psid_<PSID>.ini` |
| MARS session tarball | `<results_dir>/<setup_id>/<sid>/<sid>.tgz` |
| Regression per-case reset script | `/mswg/projects/fw/fw_ver/regression/HcaCoreRegression/RegTools/Fwreset.py` |
| Topology file | `/auto/mswg/projects/fw/fw_ver/MARS_HCA_CORE/MARS_conf/topo/<box>/topology_<mode>.xml` |

**Private branches**

| Worktree path | Branch | Based on | Purpose |
|---|---|---|---|
| `/auto/fwgwork1/<user>/golan_fw_<ticket#>` | `<ticket#>_<topic>` | `<tag> @ <sha>` | root-cause analysis at the ticket's version |
| `/auto/fwgwork1/<user>/golan_fw_<ticket#>` | `<ticket#>_<topic>_<oddver>` | `<next odd tag>` | the branch the patch lives on |
| `/auto/fwgwork1/<user>/utopx_<ticket#>` | `fix_<ticket#>_<topic>_<track>` | `origin/<full-branch-name> @ <sha>` | test tool — modified or not |

**Local artifacts** (under `/auto/fwgwork1/<user>/bugZilla/<ticket#>_<core>/`)

| Artifact | Path | md5 |
|---|---|---|
| <control build / patched build> | `fw/fw_archive_<MMDD>_<sha>/<image>` | `<md5>` |
| the fix | `patches/FIX_<topic>.patch` | |
| a candidate that was tried and disproved | `patches/REJECTED_<vN>_<why>.patch` | |
| the regression's burned INI, the release default, their diff | `ini/` | |
| repro, control and verification run logs | `logs/` | |

- Regression window (fsearch): <first occurrence, sessions and setups affected, the suspect
  commit>
- Exposure condition: <what has to be true for the bug to fire — NV knob, topology, device type>

## 3. Root cause

<The accepted root cause, stated once in a short paragraph: what the thing is, what it does
wrong, and where (`file:line`, or a link to gerrit's file view or gitiles). Name the commit and author when a
change introduced it; say so when it is a latent defect rather than a regression.>

Evidence: <`file:line`; attribution (`git blame` → commit, author, date); the deciding run>.

## 4. Rejected hypotheses and dead ends

- <looked like …; ruled out by …>

## 5. Fix

- Repo(s): <`golan_fw2` and/or `utopx2`>
- Branch: <the private branch the fix lives on>
- Gerrit: [<num>](<change URL>), or not pushed

```diff
<the patch>
```

- Why it fixes §3: <each hunk tied back to the root cause>
- Deliberately not covered: <sibling call sites or cases the pinned repro does not exercise>
- Rejected attempts: <`REJECTED_<vN>_<why>.patch` — why it failed>

## 6. Verification

| Run | Build | Seed | Signature present? | Ended how | Verdict |
|---|---|---|---|---|---|
| Original regression | <FW / tool pin> | <N> | yes | TEST FAILED | baseline |
| Local repro | <pin> | <N> | yes (same) | TEST FAILED | repro confirmed |
| Control (patch removed) | <pin> | <N> | <yes / no> | <...> | <...> |
| Patched | <pin> | <N> | <no> | <...> | <VERIFIED / VOID> |

- Logs: before `<path>`, after `<path>`
- Adjacent cases run: <what else ran to catch a regression the fix introduces>
- Verdict: `<VERIFIED | VOID — reason | NOT REPRODUCED | PARTIAL>`

## 7. Next steps

- Open questions for the code owner: <...>
- Follow-up tickets: <sibling cases sharing the defect>
- Back-port range: first affected release <tag>; <n> releases; active lines hit: <...>;
  <whether carrying the defect means failing>
