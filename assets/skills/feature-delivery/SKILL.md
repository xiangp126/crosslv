---
name: feature-delivery
description: >-
  Deliver a firmware/utopx FEATURE end to end — arch request and Redmine tickets, HLD/MAS/uArch
  documents, commit shaping, coding across golan_fw and utopx, local build and lab verification,
  gerrit review, merge order, and branch propagation. Covers both a feature you start from
  scratch and one handed over mid-flight. Use when starting, taking over, driving, or reporting
  on a feature (not a bug); when deciding how to split it into commits or in what order to merge
  them; when a feature change is stuck in review; or when a test says PASSED but you cannot tell
  whether the feature was exercised at all.
---

# Feature delivery — arch request to merged, across two repos

The feature-side counterpart of skill `regression-repro`. Same shape, opposite object:

> `regression-repro` takes **one bug** and proves it reproduces, then that a fix kills it.
> `feature-delivery` takes **one feature** — spanning `golan_fw` and `fw_ver/utopx`, two owners,
> several design documents and two review threads — from the architecture request to merged code
> with evidence that the new path actually ran.

Mechanical build/burn/run steps are **not** here; they stay in skill `fw-build-burn-utopx`.
This skill is the lifecycle around them.

## Where everything lives

| Thing | Where | When |
|---|---|---|
| the task's ledger | `TRACKING.md`, skill `task-tracking-doc` | **day 0** — a feature spans weeks and two repos, exactly that skill's trigger |
| documents, tickets, who approves what | `references/design-and-tickets.md` | Phase 0–1 |
| commit shaping, review ecology, merge order, propagation | `references/review-and-merge.md` | Phase 2, 5–6 |
| build / burn / run mechanics, worktree path rules | skill `fw-build-burn-utopx` | Phase 4 |
| `env_rebuild` + `per_run` script pair | skill `regression-repro` Phase 9b / 9b-bis, **two rules inverted** (Phase 4) | before the first lab run |
| box reservation, waiting out `mars_reg` | skill `noga-lock` | before anything touches hardware |
| commit message format, cherry-picks, stack push | skill `gerrit-change` | Phase 5–6 |

## Phase 0 — Establish the object: request, tickets, owners

Before designing anything, pin down what exists. A feature here is normally **one architecture
Feature Request + two Redmine tickets** (FW side and `[Ver]` side) + an owner in each repo.

- The **Feature Request** (SharePoint, `NBU-Architecture/SWArch`) is the contract: it carries the
  numbered requirements you are judged against in Phase 6. Get its number and read the Req list
  **in full, early** — not the two requirements someone quoted at you.
- Redmine: an FW ticket and a separate `[Ver]` ticket. Both must exist; gerrit's `Redmine-Issue`
  label blocks submit without one.
- Owners: the FW and test-tool sides usually have different people. Identify both, and find out
  who actually reviews — rarely the person in the reviewer slot
  (`references/review-and-merge.md`).

**Taking over rather than starting?** Survey both repos by owner and take the whole set — the
handover always undercounts. On PSF the handover named 3 FW changes; the real stack was 12+
(7 already merged, one of them the direct counterpart of the utopx change under review). Include
`ABANDONED` ones; you will hit them in the review history.

```bash
# gerrit MCP: search_changes_by_criteria(owner=<user>, limit=40)
```

## Phase 1 — Design documents before code

For a feature of any size the documents come first and are reviewed on their own. The full set,
with the PSF example, is in `references/design-and-tickets.md`; the shape is:

| Document | Lives in | What it settles |
|---|---|---|
| Feature Request | SharePoint | the requirements (`Req N`) — the acceptance contract |
| HLD | Confluence | how it will work; reviewed before coding |
| MAS | Confluence | the FW-side architecture spec |
| FWV uArch | Confluence | **verification** micro-architecture — what the test tool must do |
| design-plan / MTBC | Confluence | schedule and scope |

> **The uArch document is load-bearing for the test side and blocks review.** On PSF the
> reviewer's stance on the largest file was literally *"will review after aligning with uArch"* —
> the change could not progress until document and code agreed. If the uArch is missing or stale,
> fixing that is the fastest path forward, not more patchsets.

Log meeting recordings/recaps in the ledger too — design decisions get made there and are
otherwise unrecoverable.

## Phase 2 — Shape the commits before writing them

How the work is split decides how reviewable it is. These came out of real review rounds
(cases in `references/review-and-merge.md`):

- **Interface first, logic second.** PRM/adabe struct changes go in their own change and land
  early; the logic change then rebases onto a merged interface. (PSF: the adabe change merged five
  weeks before the logic change was still in review.)
- **A pure code-move goes in its own cosmetic commit.** A reviewer cannot read a diff that both
  moves a function and changes it, and will stop reviewing until you split it.
- **The enabling gate is a separate, last commit** — see Phase 3.
- Do not carry a stack longer than the reviewer will hold in their head. Being asked to fold two
  changes into one is a reviewer telling you the split failed; fold them.

## Phase 3 — Gates: a feature normally ships dark first

Features land **gated off on each side independently**, so the whole path is dead code until the
gates open:

| Side | Typical gate |
|---|---|
| FW | a capability function hard-wired to `return FALSE`, usually with a `todo: delete this line after all code is merged` comment |
| utopx | a constraint in `config/common_constraints.conf` pinned to `0`, the random variant commented out behind a patch id |

Design this deliberately: **the gate commit merges last**, after the implementation it switches
on. Opening the gate first ships a path that half-exists.

State plainly in the ledger **which gates are open right now**, because:

> With either gate shut, every lab run exercises the old path only — a green run proves nothing
> about the feature. Do not plan lab time around a feature whose gates are still closed; plan the
> gate merge first.

## Phase 3b — Testing someone else's change: never edit it in place

Cherry-picking a colleague's change to test it, then finding it does not compile or does not
run, is the normal case — not the exception. **Fix it in a separate `[Local-Only]` commit
stacked on top, never by editing the cherry-picked commit or leaving changes in the working
tree.** You are not the owner; they upload new patchsets while you test, and the moment they
do, an edited tree cannot tell you what was theirs and what was yours.

With the fixes stacked, adopting a new patchset is: reset to it, re-apply the stack, and drop
whatever hunks the new patchset made unnecessary. With them smeared into the working tree, it
is an archaeology session.

```
[Local-Only] Lab config: force <gate> on          <- survives; it is how the lab runs
[Local-Only] Make <change> build and run          <- dies when the owner fixes these
<their patchset, byte-for-byte as fetched>
<base>
```

**Split by lifetime, not by topic.** Workarounds for their defects and your own lab
configuration disappear on completely different schedules; one commit each. On PSF the config
commit had to survive every rebase (upstream pins the gate to 0, so without it every run tests
the old path), while the workaround commit is pure debt.

**Write the message so the next rebase is mechanical**: one entry per hunk, each naming the
upstream defect it works around and quoting the failure verbatim. That message is what lets
you walk a new patchset hunk by hunk and delete exactly the ones that are now fixed — and it
is the report you owe the owner anyway, already written.

The same discipline applies to the FW side, where it is absolute: never modify `golan_fw`
carries at all — keep them byte-identical to the gerrit patchset and report defects instead.

## Phase 4 — Build, lab environment, and the run verdict

Workspace — feature work uses the **primary** clones (`golan_fw`, `utopx`); `*2` is the repro
pair. One worktree per task in each repo:

```bash
git -C /auto/fwgwork1/$USER/utopx    worktree add -b <task>-track /auto/fwgwork1/$USER/utopx-<task>    origin/master
git -C /auto/fwgwork1/$USER/golan_fw worktree add -b <task>-track /auto/fwgwork1/$USER/golan_fw-<task> origin/master_rc
```

- **Check how stale the base ref is before branching.** A local `origin/*` can be weeks behind. On
  PSF the golan_fw base was 19 days old and missing 4 already-merged changes *of this feature*;
  reading code there would have produced confident, wrong conclusions.
- **`git fetch` writes shared refs** — even `fetch origin <one-branch>` moves other
  remote-tracking refs through the remote's refspec. Other worktrees see it. Say so before running.
- **A merged change's SHA on the branch ≠ its SHA on gerrit** (it was rebased). Record the landed
  one, found by Change-Id, never by subject:
  `git -C <wt> log --grep="Change-Id: I<...>" --format='%h %ci' -1`

Lab environment — `mars_reg` re-provisions the regression server **daily**, so the environment is
rebuilt every session, not once. Write the script pair specified in skill `regression-repro`
Phase 9b / 9b-bis (`tools/env_rebuild_<box>.sh` from the dev box once per lock;
`tools/per_run_<task>.sh` on the box per attempt) and **keep every guard it specifies** — they
apply unchanged to feature work.

**Invert exactly two of its rules** — those two are written for repro and are backwards here:

| Phase 9b rule (repro) | For a feature |
|---|---|
| assert the tool binary is the **PRE-fix** commit; abort if the fix is present | **drop it** — a feature run wants the new code |
| verdict `REPRO SUCCESS` / `NOT REPRODUCED`, keyed on a defect signature | **replace it** — see below |

The verdict — `TEST PASSED` answers "did the tool survive", not "was the feature exercised". Have
the run script count the feature's own fingerprints and report them as first-class factors:

```bash
# `|| true`, NOT `|| echo 0`: grep -c already prints 0 on no match and exits 1, so `|| echo 0`
# appends a SECOND line, the value becomes "0\n0", every `= 0` test below takes the else branch,
# and the verdict flips to NEW PATH EXERCISED on a run that entered nothing.
F_HITS=$(grep -c "<capability field>"      "$LOG" || true)   # e.g. icm_mng_global
F_PATH=$(grep -c "<new enum / new op_mod>" "$LOG" || true)   # e.g. PROVIDE_PAGES_RANGE
```

| Outcome | Meaning |
|---|---|
| `RUN VOID` | tool never initialised — says nothing either way |
| `OLD PATH ONLY` | ran and passed, fingerprints **0** — **proves nothing about the feature** |
| `NEW PATH EXERCISED` | fingerprints > 0 — only now is the result about this feature |

Pick fingerprints from the code you wrote (capability field, new opcode/`op_mod`, a log line only
the new branch emits) — never from the feature's name.

**Count progress too, not just errors.** A tool hung inside a driver ioctl reports zero errors
forever, so `FATAL == 0` plus a long runtime reads as the best run you have had. Add a counter
that only moves when work happens (operations logged, iterations reached) and require it to be
non-zero before believing any verdict — skill `regression-repro` Phase 9b has the full case.

## Phase 5 — Review

Commit messages, cherry-picks and stack pushes: skill `gerrit-change`. CI re-triggering: skill
`utopx-ci-rerun`. Review ecology — who really reviews, how to read an `unresolved` count, what to
do with a reviewer's suggested code — is in `references/review-and-merge.md`. Two rules are severe
enough to sit here:

- **Never adopt a reviewer's code snippet without verifying it yourself** — compile it, or at
  minimum grep the symbol's definition. Both sides of PSF shipped a bug of exactly this origin.
- **Cross-layer consistency is nobody's job unless you take it** — a config key, the adabe node it
  binds to, and the code reading it must agree. Nothing catches a mismatch: not the compiler, not
  CI, not review.

## Phase 6 — Merge, then prove the Req list

Merge order follows the gate design (Phase 3): **interface → implementation → gate**. Propagating
to ES/master branches afterwards: skill `gerrit-change` (cherry-pick footer rules) plus the
ledger's propagation table.

Then close the loop against the Feature Request from Phase 0. For **each numbered Req**, find the
assertion in the test tool that would fail if it were violated, and record it with an explicit
"verified?" column so the holes show:

> **PSF.** Walking the FW↔utopx interface field by field found two holes: `Req 4` ("device must
> not issue page-request events") had only an indirect relaxation on the utopx side and **no
> assertion on the capability bit**; `Req 5` (`fast_teardown` must be 1) had **no assertion at
> all**. Both sides had shipped code; neither requirement was actually checked. Nobody noticed,
> because the change "looked complete".

"Code exists on both sides" is not "the requirement is verified". Only an assertion that can fail
is verification.

## Rules that must fire without opening a reference

- **To decide whether a bug is still present, read the file on the branch**, not a change's diff
  context; later commits may have rewritten the function entirely.
- **To decide whether someone is still working a change, read `list_patchsets`**, not `updated` —
  that field lags by minutes. And before saying "N days without activity", run `date -u`.
- **An unrecorded action counts as not done** — keep `TRACKING.md` current in the same step as the
  action, with overturned conclusions struck through rather than deleted.

## Related

- Build / burn / run mechanics, `jmake` worktree path rules → skill `fw-build-burn-utopx`
- The bug-side counterpart of this workflow → skill `regression-repro`
- The ledger this workflow writes into → skill `task-tracking-doc`
- Lab box reservation, waiting out `mars_reg` → skill `noga-lock`
- Commit messages, cherry-picks, dependent-stack pushes → skill `gerrit-change`
- Re-triggering CI → skill `utopx-ci-rerun`
- Publishing the design documents → skill `managing-confluence`
