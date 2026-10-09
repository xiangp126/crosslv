---
name: regression-repro
description: >-
  Work a firmware/utopx bug ticket end to end - reproduce a regression, CI or DoA failure locally
  from a Redmine URL or MARS session id, root-cause it in golan_fw or utopx, verify a fix on the
  lab box, and write the FINDINGS report; what Peter calls the "regression repro template", and
  home of the rule never to touch l-fwminireg-* boxes. Use to repro a failure, investigate a
  ticket, find or explain a root cause, say why a test or case fails, or propose or verify a fix.
---

# Regression repro

Turn a single Redmine URL (or MARS session id) into a bit-for-bit local reproduction, root-cause
it, verify the fix on the box, and deliver `FINDINGS_<ticket#>.md`. When Peter says
**"regression repro template"**, he means this skill.

Before opening SSH sessions or starting long-running work, read the runtime adapter:
`references/hosts/claude.md` in Claude Code, `references/hosts/codex.md` in Codex. The
reproduction method is shared; permission handling and background-process control are not.

## Where everything lives

Paths are relative to this skill's directory.

| File | What it is | When to open it |
|---|---|---|
| `templates/repro_plan.md` | per-ticket skeleton: frontmatter, todo list, Goal, Environment table, **Investigation log (append LIVE, as findings happen)**, Run log | **first** — copy to `/auto/fwgwork1/$USER/bugZilla/<ticket#>_<core>/repro_plan_<ticket#>.md` and fill it in as you go |
| `references/procedure.md` | Phases 1–11: decode the ticket → extract versions from the tarball → allocate the box → pin repos → burn → bring up → run → confirm → **verify the fix on the box (9.5)** → codify → commit | while working a phase; read only the phase you are on |
| `references/key-learnings.md` | accumulated traps + a worked example (#5090131, BRONCO/BF4) | when something behaves oddly, and before declaring a verdict |
| `references/lab-credentials.md` | shared lab credentials (ARM / BMC) — **local only, gitignored**; create it from `lab-credentials.md.example`, filled from the authoritative sources it names | when a box rejects the credentials a procedure assumes |
| `templates/findings.md` | final-report skeleton: issue summary, root cause with code evidence + attribution, proposed fix, verification results, next steps | copy to `.../<ticket#>_<core>/FINDINGS_<ticket#>.md` as soon as a root-cause hypothesis exists; **mandatory deliverable**, kept as a living document |
| skill `task-tracking-doc` | only when this ticket is one of several under a long-running task (weeks, several commits/branches/tickets): that task gets a `TRACKING.md`, and this ticket's `repro_plan` / `FINDINGS` are registered in it | when the ticket belongs to a bigger effort |

The rest of this file must fire without opening any of them.

### Which clone — repro gets the `*2` pair

Work off `/auto/fwgwork1/$USER/golan_fw2` + `utopx2`, never the feature pair: a repro pins repos
to an old commit. Give the ticket its own worktree off each clone it needs
(`golan_fw_<ticket#>` / `utopx_<ticket#>`, procedure.md Phase 4) — never work in a clone's own
checkout. Per-ticket files go in `/auto/fwgwork1/$USER/bugZilla/<ticket#>_<core>/`. Full rule:
`CLAUDE.md` → **Repos**. Worktree path constraints `jmake` imposes: skill `fw-build-burn-utopx` §1.

## Phase 0 — query `fsearch` BEFORE you allocate a box

Run it before Phase 1 of `references/procedure.md`: one query, a few seconds, no hardware, and it
often changes the plan. Tool docs and its three silent traps: skill `fsearch-failures`.

```bash
S=/auto/sw/work/hca_fw/projects/mars_analytics/search.py
python3.8 $S --errlike "<signature>"
python3.8 $S --errlike "<term you know occurs>"     # control — MUST come back non-empty
```

| fsearch shows | Meaning for the repro |
|---|---|
| one setup only | machine/config signal first: diff that box against a healthy one **before** spending a device cycle on code |
| many setups / branches | genuine code signal — the repro is worth the hardware |
| "starts" at a date | almost always the **~8-day retention edge**, not a first occurrence; never read it as "the bug landed then" |
| zero rows, control also zero | the tool is broken (usually the dead old path) — not evidence of anything |
| zero rows, control non-zero | it never reached case level: died in setup/init, or a CI build/packaging failure, which fsearch does not record at all — a different hunt |

Every row carries the **utopx commit**. Check whether a suspect change was in that run:

```bash
git -C <worktree> merge-base --is-ancestor <suspect-commit> <commit-from-fsearch> \
    && echo "that run contained it"
```

This is the cheapest form of the control hard rule 6 demands ("it passed before, it fails now →
get the control BEFORE theorising"): seconds instead of a 15-minute device cycle. It does not
replace a device A/B when the suspect landed outside the retention window.

## Records and deliverables

- **Write findings into `repro_plan_<ticket#>.md`'s Investigation log as you find them** — code
  reads, `git blame` attribution, killed hypotheses — not in a write-up reconstructed at the end.
  The chat transcript is gone next session. Keep superseded conclusions in place, marked
  `SUPERSEDED`; never delete them.
- **`FINDINGS_<ticket#>.md` (from `templates/findings.md`) is the deliverable**, not the chat
  answer.
- **Posting an RCA on the ticket:** draft it locally in HTML (skill `utopx-regression-ticket` →
  "Writing to Redmine"), get Peter's approval, then post the approved text unchanged. Correct a posted comment by editing it in place (skill
  `utopx-regression-ticket` → "Writing to Redmine").

## Reproduction fidelity

- **Success = the SAME failure signature appears locally.** A green run means you did NOT
  reproduce it; never report a pass as progress.
- **Reproduce on the exact box from `setup_id`.** A substitute host needs Peter's explicit
  approval (procedure.md §3b-bis) and must match the **PSID**, not just the chip family.
  Authoritative inventory: `noga_manage.py -q -t nic -e "psid:<PSID>"`.
- **Mandatory platform check on any substitute — utopx setups are Supermicro-only.** Require
  `Server_Model = Supermicro` and no `noga_alloc_note:[INCOMPATIBLE_UTOPX]` in `Free_text`. An idle
  box is often idle *because* of that flag; ignoring it can hang the box in BIOS POST,
  unrecoverable remotely.
- **All three artifacts must match: FW build + burned INI + test-tool binary (commit) with its
  exact command and seed.** Matching one or two yields look-alike failures that are not the bug.
  The burned INI is the session's own
  (`/auto/sw/work/hca_fw/data/burn_fw/ini_files/*_session_<sid>_*.ini`), not the release INI — the
  regression injects extra lines.
- **The same three are the candidate causes.** When history says "started at FW X", diff the
  session INIs across that boundary before blaming FW (skill `fsearch-failures`). If FW and INI
  changed in the same window, only a box run with one of them swapped tells them apart.
- **Mirror the regression's own bring-up steps** (`mlxconfig_set` / `fw_reset` /
  `modprobe udriver` / `check_arm_agent`) as read from the session tarball — not a "cleaner"
  equivalent.
- **The device does NOT reset itself between your runs — the regression's `clear_nv_data` does.**
  Back-to-back local runs accumulate NV state the nightly session never carries, until utopx dies
  in init (`GoldenTlv: data length exceeds maximum supported size`, 516 > 255, zero `LOG_OP` lines)
  — even on the official FW that reproduced an hour earlier. If a reproducing setup stops
  reproducing after a run or two, suspect accumulated NV state before your build (clear-NV loop:
  procedure.md Phase 10).

## Never edit source in `/tmp/mars_tests/<test-DB>/tests/`

That tree is **MARS's own deployment, and mars_reg runs the nightly regression out of it.** Use it
read-only: run its `utopx.exe`, read its configs, check its commit. Never patch a file, add a
probe, or rebuild in place — not even temporarily with a backup: if the lease expires or the box
is grabbed before you restore, the next regression runs your binary and nothing in the archive
points back at you.

Put every source edit — a candidate fix *or* a read-only debug probe — on a named private branch
in a per-ticket worktree off the repro clone (procedure.md §4b; worktree mechanics: skill
`fw-build-burn-utopx` §1). Run that binary on the box over NFS; no copying needed.

## A branch checkout does not give you a clean tree

Two things survive `git checkout` and silently poison a build:

- **submodule working trees** — always run `git submodule update --init --recursive`.
- **gitignored generated files**, e.g. `hca_fwv_shared/autogen/`. Nothing regenerates them (the
  CMakeLists only globs what is on disk) and `--git-clean` preserves submodules; otherwise you link
  a weeks-old library, the repro stops reproducing, and every run segfaults. Wipe with
  `git clean -fdx` on **every** autogen tree, never a `*.cpp` glob — the layout differs per
  submodule revision, so a glob leaves the other branch's subdirectories behind.

Build with **`jmake -c -o`** (clean, then build), then **read the log**: jmake prints
`BUILD SUCCESS` and exits 0 even when the `shared` stage died. Details: skill
`fw-build-burn-utopx`.

## Verifying a fix

- **A fix that has not run on the box is a PROPOSAL (procedure.md Phase 9.5).** Build it, deploy
  it, rerun the exact pinned command + seed, confirm the signature is gone *and* the run ended
  cleanly, then run the control with the patch removed. Only then does Phase 11 (commit) apply. The
  fix may live in `golan_fw2`, `utopx2`, or both — never assume FW-only.
- **Judge a run by how it ENDED, before reading any counter:** `To rerun use seed` /
  `TEST PASSED|FAILED` / `terminate called` / `SEGMENTATION FAULT`. A run that scores 0 on every
  target signature and then crashes is not a pass.
- **The signature disappearing is NOT the bug being fixed.** Read the *new* fatal before claiming
  anything. A cap/feature defect can have two halves — the **admission check** (may the query
  proceed) and the **data fill** (what gets written back); when both read the same helper, fixing
  only the gate turns "refused" into "answered with zeros". When you change a shared cap/feature
  helper, grep every caller before calling the fix complete.
- **The control differs by exactly ONE variable:** same tree, same configs, same command, same
  seed, patch removed. Always run it — without it a pre-existing failure and one you introduced look
  identical. "My clone + patch" vs "the deployed binary" changes two things at once and can make an
  environment artifact look like a crash in the patch.
- **Do not "improve" a verified patch on the way to gerrit.** Push exactly the expression you
  verified on the box. A cleaner or more general form is a **new, unverified change** that needs
  its own run; "strictly better" reasoning is not evidence.
- **Size a utopx fix for review before you build it.** When the trigger is a regression-config
  change, offer the config-side fix first. When utopx must change, bring the smallest form of the
  rule as a diff and get Peter's nod before spending box time — a 3-file +46/−4 change adding new
  sysfs probing and a per-host map was rejected as "changed tool much".

## Code shape is not runtime evidence — grep the log

A fact about the source ("this switch ignores `cap_type`", "this signature takes an `input_gvmi`,
so someone else must be querying") is not a fact about the run.

- **Any "who did what, when" claim → grep the log first.**
- **"Is this a bug or by design?" cannot be answered by reading code** — find the HLD, or ask the
  architect early; it does not get cheaper by reading more code.

Examples and the peer-analysis rules: `references/key-learnings.md` → "Evidence discipline".

## `git status` before you read source, and again before you commit

- **Before reading source for analysis** (not just before building): `git status` /
  `git diff --stat`. A rejected patch left in the tree becomes "the code" days later. When a patch
  is rejected, save it as `REJECTED_<what>.patch`, `git checkout --` the files the same day, and
  rename anything still called `FIX_*`.
- **Before committing a verified fix, close the chain source → binary → run → commit**; each link
  needs its own evidence:

| Check | Proves |
|---|---|
| `git status --short` shows no `MM` (staged ≠ working tree) and `git diff --cached` has no probe marker | no debug probe escapes through the index — a plain `git commit` pushes what is staged |
| source mtime **<** build-completion time in the build log | the binary came from this source |
| `git diff HEAD` == the verified `.patch` (compare the `+`/`-` lines) | you push what you tested — the check that matters most |
| the verification log contains **zero** probe output | the verified run used the clean binary |

## NEVER touch `l-fwminireg-*` — they are dedicated CI machines

Hard rule, no exceptions: do not lock, ssh-run, burn, mlxconfig, fw-reset, or in any way use an
`l-fwminireg-*` box. They exist to run CI/DoA and nothing else. Claude Code also enforces this
through `~/myGit/crosslv/assets/claude/hooks/guard.py`; that hook does not intercept Codex, so
Codex must enforce the rule directly from this skill and `AGENTS.md`.

**NOGA is not authoritative for this pool and actively misleads:**

- The boxes are absent from NOGA's NIC inventory
  (`noga_manage.py -q -t nic -e "name:l-fwminireg"` → no results).
- The host-level query *does* answer, and reports `Status.status = Release` / empty `lock_owner`
  for a box that is running a live CI session right now.
- A NOGA lock does **not** stop the MARS scheduler from dispatching to it. A repro colliding with a
  live session over the VSEC mailbox dies with `Vsec.cpp:107 VsecSpace status mismatch` (unrelated
  to the bug being chased) and can corrupt the regression.

### Why a substitute box cannot fake it

All 9 boxes with the `LOOPBACK_FPP_MUSTANG_ETH` topology —
`l-fwminireg-{014,024,034,044,054,064,074,084,094}` — are in this pool. That topology (two cabled
ports, paired entry points, per-box `topology_<mode>.xml`) cannot be reproduced on a dev/reg box:
there the vports come up DOWN (CI 11 UP / 0 DOWN vs substitute 2 UP / 9 DOWN incl. ECPFs), so a
traffic-path failure will not reproduce.

**When a repro genuinely needs that topology, do NOT grab a box.** Either let CI run the experiment
(push a patchset and read the DoA result), or ask the minireg pool owner to take a box out of
rotation.

## Related

- Failure history / frequency / commit attribution — **run first**: skill `fsearch-failures`.
- Driving a FEATURE rather than chasing a bug: skill `feature-delivery`, the mirror of this one. It
  reuses Phase 9b's script pair but inverts two rules (no PRE-fix binary guard; the verdict asks
  whether the new code path executed, not whether a defect reproduced).
- The failure signature to match against: skill `ci-forensics`.
- Taking a lab box for the repro: skill `noga-lock`.
- BlueField mlxconfig / ARM-liveness traps: skill `bluefield-fwconfig`.
