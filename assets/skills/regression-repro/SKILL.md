---
name: regression-repro
description: Work a firmware/utopx bug ticket end to end - reproduce a regression, CI or DoA failure locally bit-for-bit from a Redmine URL or MARS session id, root-cause it in the FW (golan_fw) or test-tool (utopx) source, verify a candidate fix on the lab box, and produce the final FINDINGS report. This is what Peter means by "regression repro template". Also carries the hard rule that l-fwminireg-* CI machines must never be touched. Use when asked to reproduce a failure locally, repro a bug, chase a DoA/minireg failure on a lab box, when someone says "regression repro template", AND equally when asked to investigate a ticket, find or explain the root cause of a failure, say why a test or case fails, propose or verify a fix for a Redmine bug, or write up a root-cause / findings report.
---

# Regression repro

Turns a single Redmine URL (or a MARS session id) into a bit-for-bit local reproduction.
When Peter says **"regression repro template"**, this is what he means.

Before opening SSH sessions or starting long-running work, read
`references/hosts/claude.md` in Claude Code or `references/hosts/codex.md` in Codex. The
reproduction method is shared; permission handling and background-process control are not.

## Where everything lives

| File | What it is | When to open it |
|---|---|---|
| `templates/repro_plan.md` | the **per-ticket skeleton** — frontmatter, todo list, Goal, Environment table, **Investigation log (append to it LIVE, as findings happen)**, Run log | **first** — copy it to `/auto/fwgwork1/$USER/bugZilla/<ticket#>_<core>/repro_plan_<ticket#>.md` and fill it in as you go |
| `references/procedure.md` | Phases 1–11: decode the ticket → extract versions from the tarball → allocate the box → pin repos → burn → bring up → run → confirm → **verify the fix on the box (9.5)** → codify → commit | while working a phase; read the phase you are on, not all of it |
| `references/key-learnings.md` | accumulated traps + a worked example (#5090131, BRONCO/BF4) | when something behaves oddly, and before declaring a verdict |
| `templates/findings.md` | the **final-report skeleton** — issue summary, root cause w/ code evidence + attribution, proposed fix, verification results, next steps | copy to `.../<ticket#>_<core>/FINDINGS_<ticket#>.md` as soon as a root-cause hypothesis exists; **mandatory deliverable**, kept as a living document |
| the rules below | things that must fire *without* anyone opening a file | always |
| skill `task-tracking-doc` | **only when this ticket belongs to a bigger task** (spanning weeks, several commits/branches/tickets) — that task gets a `TRACKING.md` and this ticket's `repro_plan` / `FINDINGS` are registered in it | when the ticket is one of several under one long-running effort |

The paths above are relative to this skill's directory.

### Which clone — repro gets the `*2` pair

`/auto/fwgwork1/$USER/golan_fw2` + `utopx2`, never the feature pair. A repro pins repos to an old
commit and may `git stash -u` whatever it finds, which would wreck feature work sharing the clone.
Full rule: `CLAUDE.md` → **Repos**. Worktree path constraints `jmake` imposes: skill
`fw-build-burn-utopx` §1.

## Phase 0 — query `fsearch` BEFORE you allocate a box

One query, a few seconds, no hardware. It decides what kind of problem you have and often
changes the plan. **Do this before Phase 1 of `references/procedure.md`.** Full tool docs
and its three silent traps: skill `fsearch-failures`.

```bash
S=/auto/sw/work/hca_fw/projects/mars_analytics/search.py
python3.8 $S --errlike "<signature>"
python3.8 $S --errlike "<term you know occurs>"     # control — MUST come back non-empty
```

Read the answer like this:

| What fsearch shows | What it means for the repro |
|---|---|
| **One setup only** | machine/config signal first. Diff that box against a healthy one **before** burning a device cycle on code. |
| **Many setups / branches** | genuine code signal — the repro is worth the hardware. |
| **"Starts" at a date** | ⚠ almost always the **~8-day retention edge**, not a real first occurrence. Never read it as "the bug landed then". |
| **Zero rows, control also zero** | the tool is broken (usually the dead old path) — not evidence of anything. |
| **Zero rows, control non-zero** | it never reached case level: died in setup/init, or it is a CI build/packaging failure, which fsearch does not record at all. Different hunt entirely. |

Every row carries the **utopx commit**. Take it straight to git to see whether a suspect
change was even present in that run:

```bash
git -C <worktree> merge-base --is-ancestor <suspect-commit> <commit-from-fsearch> \
    && echo "that run contained it"
```

This is the cheapest form of the control that hard rule 6 demands ("it passed before, it
fails now → get the control BEFORE theorising"). It does not replace a device A/B when the
suspect landed outside the retention window — but it tells you that in seconds instead of
after a 15-minute device cycle.

## The parts that get skipped most often, and shouldn't be

- **Write findings down AS YOU FIND THEM, in `repro_plan_<ticket#>.md`'s Investigation log.** The
  chat transcript is not a record; it is gone next session. Code reads, `git blame` attribution and
  killed hypotheses go in the file *while you work*, not in a reconstructed write-up at the end.
  Keep superseded conclusions, marked `SUPERSEDED` — never delete them.
- **A fix that has not run on the box is a PROPOSAL, not a fix (Phase 9.5).** Build it, deploy it,
  rerun the exact pinned command + seed, confirm the signature is gone *and* the run ended cleanly,
  then run the control with the patch removed. Only then does Phase 11 (commit) apply. The fix may
  live in `golan_fw2`, `utopx2`, or both — never assume FW-only.
- **`FINDINGS_<ticket#>.md` is the deliverable**, not the chat answer. From `templates/findings.md`.
- **The signature disappearing is NOT the same as the bug being fixed.** Read the *new* fatal before
  claiming anything. On #5285522 the patch drove `0xac5816` to 0 occurrences with the test running
  properly (`LOG_OP` 252) — and the run still ended `TEST FAILED`, on a different fatal, because the
  defect had two halves: the **admission check** (may the query proceed) and the **data fill** (what
  gets written back). Both read the same tightened helper, so fixing only the gate turned "refused"
  into "answered with zeros". When you change a shared cap/feature helper, grep every caller before
  calling the fix complete.
- **The device does NOT reset itself between your runs — the regression's `clear_nv_data` does.**
  Back-to-back local runs accumulate NV state the nightly session never carries. On #5285522 two
  consecutive runs left enough NV TLVs that utopx died in init
  (`GoldenTlv: data length exceeds maximum supported size`, 516 > 255, zero `LOG_OP` lines) and the
  bug became unreproducible — on the *official* FW that had reproduced it an hour earlier. If a
  previously-reproducing setup stops reproducing after a run or two, suspect accumulated NV state
  before you suspect your build.
- **Success = the SAME failure signature appears locally.** A green run means you did NOT
  reproduce it — never report a pass as progress.
- **Reproduce on the exact box from `setup_id`.** Substituting a host needs Peter's explicit
  approval (§3b-bis); the substitute must then match the **PSID**, not just the chip family.
  Authoritative inventory: `noga_manage.py -q -t nic -e "psid:<PSID>"`.
- **MANDATORY platform check on any substitute: utopx setups are Supermicro-only.** Require
  `Server_Model = Supermicro` and no `noga_alloc_note:[INCOMPATIBLE_UTOPX]` in `Free_text`.
  A conveniently idle box is often idle *because* of that flag; ignoring it hung an HP box in
  BIOS POST, unrecoverable remotely.
- **Three artifacts must ALL match: FW build + burned INI + test-tool commit/command/seed.**
  Matching one or two yields look-alike failures that are not the bug.
- Mirror the regression's own bring-up steps (`mlxconfig_set` / `fw_reset` / `modprobe udriver` /
  `check_arm_agent`) read out of the session tarball — not a "cleaner" equivalent.
- Per-ticket work goes in `/auto/fwgwork1/$USER/bugZilla/<ticket#>_<core>/`; the
  repro-dedicated clones are `golan_fw2` / `utopx2`, **not** the primary feature repos.

## Rules that must fire without opening the template

The template is a ~1300-line per-ticket artifact you copy and fill in — these are the rules that
cost a day each when skipped, so they live here too instead of only there.

### Never edit source in `/tmp/mars_tests/<test-DB>/tests/`

That tree is **MARS's own deployment, and mars_reg runs the nightly regression out of it.** Reuse
it read-only — run its `utopx.exe`, read its configs, check its commit. Never patch a file, add a
probe, or rebuild in place, not even "temporarily, with a backup": if the lease expires or the box
is grabbed before you restore, the next regression runs on your binary and nothing in the archive
points back at you.

Source edits — a candidate fix *or* a read-only debug probe — go in the repro clone on a named
private branch, or in a worktree per skill `fw-build-burn-utopx`. Run that binary on the box over
NFS; no copying needed.

### A branch checkout does not give you a clean tree

Two things survive `git checkout` and will silently poison a build:

- **submodule working trees** — always `git submodule update --init --recursive`.
- **gitignored generated files**, e.g. `hca_fwv_shared/autogen/`. Nothing regenerates them
  (the CMakeLists only globs what is on disk) and `--git-clean` preserves submodules. Otherwise
  you link a weeks-old library, the reproduction stops reproducing, and every run segfaults.
  Wipe with `git clean -fdx` on **every** autogen tree, not a `*.cpp` glob — the layout differs
  per submodule revision, so a glob leaves the other branch's subdirectories behind.

Build with **`jmake -c -o`** — clean, then build. Then **read the log**: jmake prints
`BUILD SUCCESS` and exits 0 even when the `shared` stage died. Details in skill
`fw-build-burn-utopx`.

### Judge a run by how it ENDED, not by the signature counters

Check `To rerun use seed` / `TEST PASSED|FAILED` / `terminate called` / `SEGMENTATION FAULT`
before reading any counter. A run that scores 0 on every target signature and then crashes is not
a pass. Missed twice in two days (2026-09-15/16).

### The control must differ by exactly ONE variable

Always rerun the unmodified build on the same seed, or a pre-existing failure and one you
introduced look identical. The control must be *the same tree, same configs, same command, patch
removed*. Comparing "my clone + patch" against "the deployed binary" changes two things at once;
on 2026-09-16 that made an environment artifact look like a segfault in the patch and cost three
rounds of rewriting correct code.

### Do not "improve" a verified patch on the way to gerrit

Whatever expression you verified on the box is what you push. A cleaner or more general form is a
**new, unverified change** that needs its own run; "strictly better" reasoning is not evidence.

## NEVER touch `l-fwminireg-*` — they are dedicated CI machines

Hard rule, no exceptions: do not lock, ssh-run, burn, mlxconfig, fw-reset, or in any way use an
`l-fwminireg-*` box. They exist to run CI/DoA and nothing else. Claude Code additionally enforces
this through `~/myGit/crosslv/assets/claude/hooks/guard.py`; that hook does not intercept Codex,
so Codex must enforce the rule directly from this skill and `AGENTS.md`.

**NOGA is not authoritative for this pool and will actively mislead you:**

- The boxes are absent from NOGA's NIC inventory entirely
  (`noga_manage.py -q -t nic -e "name:l-fwminireg"` → no results).
- The host-level query *does* answer, and happily reports `Status.status = Release` / empty
  `lock_owner` for a box that is **running a live CI session right now**.
- A NOGA lock on one of these does **not** stop the MARS scheduler from dispatching to it.

Verified the hard way on 2026-08-12: `l-fwminireg-064` read `Release`/no owner, so it was locked
and a repro was launched on it — it collided with live regression session `11366827` over the
VSEC mailbox. The repro died with `Vsec.cpp:107 VsecSpace status mismatch` (nothing to do with
the bug being chased) and the regression could have been corrupted.

### Why a substitute box cannot fake it

The 9 boxes carrying the `LOOPBACK_FPP_MUSTANG_ETH` topology —
`l-fwminireg-{014,024,034,044,054,064,074,084,094}` — are all in this pool. That topology (two
cabled ports, paired entry points, per-box `topology_<mode>.xml`) is exactly what a dev/reg box
cannot reproduce: on a substitute the vports come up DOWN (measured: CI 11 UP / 0 DOWN vs
substitute 2 UP / 9 DOWN incl. ECPFs), so any traffic-path failure simply will not reproduce.

**When a repro genuinely needs that topology, do NOT grab a box.** Either let CI itself run the
experiment (push a patchset and read the DoA result), or ask the minireg pool owner to take a box
out of rotation. Both are cheaper than corrupting someone's CI result.

## Related

- Failure history / frequency / commit attribution, **run this first**: skill `fsearch-failures`.
- **Driving a FEATURE rather than chasing a bug** → skill `feature-delivery`, the mirror of
  this one. It reuses Phase 9b's script pair but inverts two rules (no PRE-fix binary guard; the
  verdict asks whether the new code path executed, not whether a defect reproduced).

- Getting the failure signature to match against: skill `ci-forensics`.
- Taking a lab box for the repro: skill `noga-lock`.
- BlueField mlxconfig / ARM-liveness traps: skill `bluefield-fwconfig`.
