# Redmine #<ticket#> — Findings (living document)

> `<one-line failure signature>` — `<branch/tag>` / `<device family>` / `<box>`
> **Status:** `<IN PROGRESS | ROOT-CAUSE FOUND | FIX VERIFIED | VOID | COMMITTED>`
> Last updated: `<date>`

NOTE: this is the **mandatory deliverable** for a ticket investigation — the thing handed to
Peter / a reviewer / the code owner. It is written from the live `## Investigation log` section of
`repro_plan_<ticket#>.md`, not from memory or a chat transcript. Start it as soon as a root-cause
hypothesis exists (Status: IN PROGRESS); do not defer it to "the write-up later".

If this ticket is one of several under a longer-running task, register this file in that task's
`TRACKING.md` sibling-documents table — see skill `task-tracking-doc`.

It is a **living document**: a conclusion that turns out wrong gets a NEW dated entry, and the old
one is marked `SUPERSEDED` and left in place. Never delete a superseded finding — the record of
what was ruled out (and why) is most of this document's value to the next person.

**Paths: plain backticks. Do NOT wrap them in markdown links.** The terminal these reports are read
in already detects a bare path and makes it clickable, so `` `/auto/.../file.log` `` is directly
openable as-is. Wrapping it — `[`path`](file://path)` or `[`path`](./path)` — *removes* that: the
click now targets the link syntax instead of the path, and fails with "file not found". Verified on
#5285522 by trying `file://`, relative and protocol-less forms; all three were worse than doing
nothing. (The MARS `view_log` URL is the one real link in the report, because it is `https://`.)

**Fence every code block with the right language** — this report is read in a browser, and a
mislabelled block is harder to read than an unlabelled one:

| Content | Fence |
|---|---|
| FW / utopx source being quoted or explained | `cpp` |
| the patch itself, or a small before/after | `diff` |
| shell / git / jmake / fsearch commands | `bash` |
| **log output — UFATAL, field mismatches, burn output** | `text` (never `cpp` — it is not code, and the highlighter mangles it) |

For a large rewrite, or a signature too long to compare side by side, `diff` stops being readable
(two ~180-char lines). State the signature change in one sentence and show the **final form** in a
`cpp` block; keep `diff` for small local edits where `-`/`+` genuinely helps.

---

## 1. Issue summary

- Redmine: [#<ticket#>](https://redmine.nvidia.com/issues/<ticket#>)
- Failure signature (verbatim):
  ```text
  <exact fatal / UFATAL / mismatch string>
  ```
- What actually goes wrong, in plain English: <2-4 sentences, no jargon dump. A reader who has
  never seen this subsystem should understand what broke.>
- Reported by / first seen: <who filed it, which nightly session>

## 2. Where it happens

Group the facts so a reader can find one without reading all of them. Give real values — a vague
`32.51.xxxx` is not an answer. The line THIS TICKET ran on goes here; the defect's full blast
radius is a different question and belongs in section 7 (back-port).

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
| Box | <original box; substitute + why, if one was approved> |
| Topology mode | <e.g. `eth_ARM_AGENT`> |
| entry points | <e.g. `<box>-rocep129s0f0-P1` / `-f1-P1`> |
| **NV knobs that arm the bug** | <the config that must be set for it to fire — this is what explains "why only setup X"> |

| MARS coordinates (the way back to the raw logs) | |
|---|---|
| setup_id | <...> |
| session_id | <...> |
| key_id (failing step) | <...> |
| test / case name | <...> |
| time of failure | <...> |
| view_log | <the view_log.php URL from the ticket> |

| Repro execution | |
|---|---|
| Exact command | `<command>` |
| seed | `<N>` |
| Where it failed | <e.g. VHCA/GVMI, HCA stage, the operation that tripped> |
| Deviations from the recorded command | <any argument dropped/added, and why — e.g. `--coverage_dir` omitted because it writes into the production coverage tree> |

### Every path used (so someone else can redo this)

Names and tags are not enough — a reviewer reproducing this needs the paths. Fill all three tables.

**Official artifacts (read-only, never modified)**
| Purpose | Full path |
|---|---|
| Official FW image | `/auto/sw/release/host_fw2/fw-<devid>/fw-<devid>-rel-<ver>-build-001/dist/<image>.mlx` |
| Release default INI (diff reference only) | `.../dist/<psid>.ini` |
| INI the regression actually burned | `/auto/sw/work/hca_fw/data/burn_fw/ini_files/..._session_<sid>_version_<ver>_psid_<PSID>.ini` |
| MARS session tarball | `<results_dir>/<setup_id>/<sid>/<sid>.tgz` |
| Regression per-case reset script | `/mswg/projects/fw/fw_ver/regression/HcaCoreRegression/RegTools/Fwreset.py` |
| Topology file | `/auto/mswg/projects/fw/fw_ver/MARS_HCA_CORE/MARS_conf/topo/<box>/topology_<mode>.xml` |

**Private branches (the repro-dedicated clones, NOT the primary feature repos)**
| Repo path | Branch | Based on | Purpose |
|---|---|---|---|
| `/auto/fwgwork1/$USER/golan_fw2` | `<ticket#>_<topic>_<you>` | `<tag> @ <sha>` | root-cause analysis at the ticket's version |
| `/auto/fwgwork1/$USER/golan_fw2` | `<ticket#>_<topic>_<you>_<oddver>` | `<next odd tag>` | the branch the patch lives on (even ver cannot be built locally) |
| `/auto/fwgwork1/$USER/utopx2` | `fix_<ticket#>_<topic>_<line>` | `<sha>` | test tool — state explicitly whether it was modified |

**Local artifacts produced** (all under the ticket dir) — for every built image record **its md5**.

> `jmake` always writes to the same `<repo>/fw-<device>.mlx` and **overwrites it every build**. Save
> a named copy of each build (control / patched) and record md5s, or the two builds silently
> clobber each other and the control is worthless.

- **Regression window** (from the `fsearch-failures` skill, if run): first occurrence, how many
  sessions/setups affected, and whether that lines up with a suspect commit landing.
  ⚠ Remember fsearch retains only ~8 days — a "first seen" date is usually the retention edge,
  and a commit older than that cannot be A/B'd with it at all.
- **Exposure condition**: what has to be true for the bug to fire (NV config knob, topology mode,
  device type). This is what explains "why only setup X shows it" — and distinguishes a
  config-gated code defect from an actual machine problem.
- **Affected release span**: <which branches/releases carry the defect — matters for back-porting.>

## 3. Root cause

Numbered, **dated** sub-investigations in chronological order. Each entry:

### 3.1 <date> — <what was investigated>
- **Hypothesis:** <...>
- **Code evidence:** `<file:line>` — <what the code does vs what it should do>
- **Attribution:** `git blame` → <commit, author, date>; `git log --author=<name> -- <path>` →
  <the change that altered behavior>
- **Verdict:** <confirms / refutes / inconclusive>

### 3.2 <date> — <...>
<...>

> Mark a superseded entry inline: `**SUPERSEDED by §3.N (<date>)** — <why it was wrong>`

### Accepted root cause

<State it once, unambiguously, in a short paragraph. Name the offending commit/author if the
defect was introduced by a specific change, and quote the line of its commit message that shows
the intent vs what was actually done, if relevant. If it is a latent/original defect rather than a
regression, say so explicitly — "not introduced by a recent change" is a finding, not a gap.>

## 4. False positives / dead ends

Things that looked like the bug but were not, so the next investigator does not re-walk them.
Include env artifacts, misleading counters, search terms that returned nothing, and any conclusion
reversed during the investigation.

- <dead end> — why it was misleading, how it was ruled out.

## 5. Proposed fix

- **Repo(s) touched:** `golan_fw2` and/or `utopx2` — state explicitly; **never assume FW-only**.
  A test-tool-side defect (wrong expectation, stale assumption) is an equally valid outcome.
- **Branch:** <the named private branch the fix lives on>
- **Diff:**
  ```diff
  <the patch, or a path to the .patch file kept in the ticket dir>
  ```
- **Why this fixes §3:** <tie each hunk back to the accepted root cause.>
- **Scope deliberately NOT covered:** <sibling call sites / related cases left untouched because
  the pinned repro does not exercise them — flag them as follow-ups rather than patching blind.>
- **Rejected / VOID attempts:** <kept with the reason they failed — see the "do not 'improve' a
  verified patch" rule in key-learnings.md.>

## 6. Verification results (on-box fix verification)

| Run | Build | Seed | Signature present? | Ended how | Verdict |
|---|---|---|---|---|---|
| Original regression | <FW/tool pin> | <N> | yes | TEST FAILED | baseline |
| Local repro | <pin> | <N> | yes (same) | TEST FAILED | repro confirmed |
| **Control** (patch removed) | <pin> | <N> | <yes/no> | <...> | <...> |
| **Patched** | <pin> | <N> | <no = good> | <...> | <VERIFIED / VOID> |

- Before (log pointer): `<path>`
- After  (log pointer): `<path>`
- **Control discipline:** the control must differ from the patched run by *exactly one variable*
  — same tree, same tag, same configs, same command, same seed, patch removed. If the control
  does not reproduce the signature, the run proves nothing about the patch.
- **Even-subminor note:** verifying an FW fix against an even release tag requires building the
  next odd tag; the control must be built from that same odd tag.
- Adjacent-case / sanity pass: <what else was run to catch a regression the fix introduces.>
- **Verdict:** `<VERIFIED | VOID — reason | NOT REPRODUCED | PARTIAL>`
  (A run that scores zero on the signature and then crashes or dies at init is **VOID, not a pass**.)

## 7. Next steps

- [ ] Gerrit change: <link once pushed — push only when Peter asks>
- [ ] Open questions for the feature/code owner: <...>
- [ ] Follow-up tickets: <e.g. sibling cases sharing the same defect, left unpatched here>
- [ ] **Back-port range — measure it, don't estimate.** With the introducing commit known:
  ```bash
  git tag    --contains <bad-sha> | grep -E '^rel-' | sort -t_ -k2,2n -k3,3n | head -3  # first affected release
  git tag    --contains <bad-sha> | grep -cE '^rel-'                                    # how many releases
  git branch -r --contains <bad-sha>                                                    # which branches
  ```
  Report: first affected release tag, total count, and which *active* lines are hit (filter out
  throwaway test branches). ⚠ **fsearch cannot answer this** — its ~8-day retention makes the
  oldest row look like a start date when it is just the retention edge.
  Also state whether "carries the defect" equals "will fail": if the bug needs a config/topology
  precondition, back-port priority follows *which lines run that config*, not the raw tag count.

## 8. Artifact inventory

Everything lives in `/auto/fwgwork1/$USER/bugZilla/<ticket#>_<core>/`:

| File | What it is |
|---|---|
| `repro_plan_<ticket#>.md` | the working plan + **live Investigation log** + Run log |
| `FINDINGS_<ticket#>.md` | this document |
| `regression_ini/` | the regression's burned INI + release default, and their diff |
| `tools/` | `env_rebuild_<box>.sh`, `per_run_reset.sh`, provisioning scripts |
| `FIX_<topic>.patch` | **the fix** — exactly one file may carry this prefix |
| `REJECTED_<vN>_<why>.patch` | a candidate that was tried and disproved, kept as the record |
| `*.log` | repro / control / verification run logs |
| built images | one named copy per build (control / patched / each candidate), md5 recorded |

> **Name patches by verdict, not by intent.** A rejected first attempt called
> `fix_<something>.patch` reads like the deliverable — on #5285522 that is exactly what happened and
> the reviewer had to ask which patch was the real one. Use the `FIX_` / `REJECTED_` prefixes, keep
> **one** `FIX_`, and rename the moment a candidate is superseded rather than at the end. Do not
> delete a rejected patch: §5 cites it, and it is what stops the next person re-running a dead end.
