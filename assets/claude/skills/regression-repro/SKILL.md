---
name: regression-repro
description: Reproduce a regression, CI or DoA failure locally, bit-for-bit, from a Redmine URL or a MARS session id. This is what Peter means by "regression repro template". Also carries the hard rule that l-fwminireg-* CI machines must never be touched. Use when asked to reproduce a failure locally, repro a bug, chase a DoA/minireg failure on a lab box, or when someone says "regression repro template".
---

# Regression repro

Turns a single Redmine URL (or a MARS session id) into a bit-for-bit local reproduction.
When Peter says **"regression repro template"**, this is what he means.

## Where everything lives

| File | What it is | When to open it |
|---|---|---|
| `templates/repro_plan.md` | the **per-ticket skeleton** — frontmatter, todo list, Goal, Environment table, Run log | **first** — copy it to `/auto/fwgwork1/<user>/bugZilla/<ticket#>_<core>/repro_plan_<ticket#>.md` and fill it in as you go |
| `references/procedure.md` | Phases 1–11: decode the ticket → extract versions from the tarball → allocate the box → pin repos → burn → bring up → run → confirm → codify → commit | while working a phase; read the phase you are on, not all of it |
| `references/key-learnings.md` | accumulated traps + a worked example (#5090131, BRONCO/BF4) | when something behaves oddly, and before declaring a verdict |
| the rules below | things that must fire *without* anyone opening a file | always |

The paths above are relative to this skill's directory.
`/auto/fwgwork1/pexiang/bugZilla/template/regression_repro_plan.md` is the original single-file
version these were split out of — kept for reference, no longer the source of truth.

## The parts that get skipped most often, and shouldn't be

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
- Per-ticket work goes in `/auto/fwgwork1/pexiang/bugZilla/<ticket#>_<core>/`; the
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
`l-fwminireg-*` box. They exist to run CI/DoA and nothing else. (A PreToolUse hook enforces this;
see `~/myGit/crosslv/assets/claude/hooks/guard.py`.)

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

- Getting the failure signature to match against: skill `ci-forensics`.
- Taking a lab box for the repro: skill `noga-lock`.
- BlueField mlxconfig / ARM-liveness traps: skill `bluefield-fwconfig`.
- Rebuilding the BF-3 sat-PF env on l-fwreg-171 (environment state, not a skill):
  `/auto/fwgwork1/pexiang/bugZilla/OCI_EMU/SATPF_171_ENV.md`.
