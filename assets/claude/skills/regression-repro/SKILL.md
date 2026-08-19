---
name: regression-repro
description: Reproduce a regression, CI or DoA failure locally, bit-for-bit, from a Redmine URL or a MARS session id. This is what Peter means by "regression repro template". Also carries the hard rule that l-fwminireg-* CI machines must never be touched. Use when asked to reproduce a failure locally, repro a bug, chase a DoA/minireg failure on a lab box, or when someone says "regression repro template".
---

# Regression repro

When Peter says **"regression repro template"** — or asks to reproduce a regression / CI / DoA
failure locally — he means this file:

**`/auto/fwgwork1/pexiang/bugZilla/template/regression_repro_plan.md`**

Read it first and follow its phases. It turns a single Redmine URL (or a MARS session id) into a
bit-for-bit local reproduction.

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
- Rebuilding a sat-PF environment: skill `satpf-171`.
