---
name: feature-delivery
description: >-
  Deliver a firmware/utopx FEATURE end to end, from scratch or taken over mid-flight - tickets and
  HLD/MAS design documents, commit shaping, coding in golan_fw and utopx, lab verification, gerrit
  review, merge order, branch propagation - and keep its documents (the Tracking.md status page,
  Ledger.md, Defects.md, test reports), created from this skill's templates on day 0. Use when
  starting, taking over, driving, recording or reporting on a feature (not a bug), when asked where
  a feature stands or to update its Tracking.md, splitting or ordering its commits, when it is stuck
  in review, when a test says PASSED but you cannot tell the feature ran, or for any multi-week task
  that needs a Tracking.md.
---

# Feature delivery — arch request to merged, across two repos

The feature counterpart of skill `regression-repro`, which takes **one bug** and proves it
reproduces, then that a fix kills it. This skill takes **one feature** — spanning `golan_fw` and
`fw_ver/utopx`, two owners, several design documents and two review threads — from the
architecture request to merged code **with evidence that the new path actually ran**.
Build/burn/run mechanics are not here (skill `fw-build-burn-utopx`); this is the lifecycle around
them.

## Documents — set up on day 0

A feature gets one directory, `/auto/fwgwork1/$USER/bugZilla/<feature>/`, and the same file set
every time. Create it the day the feature starts or is taken over, before the first build:

```bash
S=~/myGit/crosslv/assets/skills
D=/auto/fwgwork1/$USER/bugZilla/<feature>
mkdir -p $D/tools $D/logs
cp $S/feature-delivery/templates/{Tracking.md,Ledger.md,Defects.md} $D/
cp $S/regression-repro/templates/lab-box/* $D/tools/     # then fill tools/lab.conf, MODE=feature
```

| File | What it is | Reader | Created |
|---|---|---|---|
| `Tracking.md` | the status page: verdict, status per part, commits per repository (owners only), what it waits for, next steps, decisions for Peter, requirements, test campaigns, defect status, timeline, how to run | Peter, owners, reviewers | day 0, `templates/Tracking.md` |
| `Ledger.md` | the step-by-step record: dated entries, commands, SHAs, CI and MARS ids, Peter's instructions verbatim, corrections struck through | whoever continues | day 0, `templates/Ledger.md` |
| `Defects.md` | one section per defect in reproduction order: how to hit it, verbatim evidence, root cause, fix diff, rejected alternatives | owners, reviewers | day 0, `templates/Defects.md` |
| `report_<MMDD>_<box>_<sha>.md` | one test campaign, written once | Peter | end of each campaign, `templates/report.md` |
| `tools/`, `logs/` | the lab-box scripts and `lab.conf`; logs the documents cite | — | day 0 |

**Every fact has one home**; other files link to it and never copy it. What changes the current
state goes into `Tracking.md`, as its result; what was done, how, and where the evidence is goes
into `Ledger.md`. Most events touch both, at different depth — in the same step as the event:

| Event | `Tracking.md` (edit the section) | `Ledger.md` (append an entry) |
|---|---|---|
| Peter gives an instruction | — | his words, verbatim |
| a build or long command ends | only when it changes the state (§1.2: "the new FW builds") | SUCCESS / FAILED, rc, `error:` count, elapsed, log path |
| a push, or a new patchset from the owner | the §1.1 / §1.2 row (patchset); a §4 line | change URL, patchset, what the server echoed |
| a CI verdict | the §1 status row; §1.3 when it blocks | build URL, failed stage, downstream jobs, MARS session id and archive path |
| a merge | the row moves to "merged", dated by the gerrit `SUBM` approval; a §4 line | the date and the SHA on the branch after landing |
| a review comment | §1.3 only when it blocks | who, file and line, how it was resolved |
| device runs | when a campaign ends: a §2 row linking its report; new defects into §3 | per run: box, FW, tree SHA, seed, result, the control, log paths |
| a defect found, fixed or no longer seen | its §3 status (the defect itself: `Defects.md`) | how it was found, the evidence |
| a blocker appears or clears; an owner promises something | §1.3 / §1.4, and the verdict sentence when it changes | the source, in its own words |
| a decision is needed / Peter decides | a §1.5 row / the row leaves §1.5 | the decision, verbatim |
| a gate opens | the "Gates" row of §1 | how it was opened |
| a judgement turns out wrong | simply corrected — the page shows the present | struck through in place, with the correction, its date and the criterion for next time |
| the session is interrupted | — | what is in flight, and the next step |
| a document, script or image is replaced; a campaign's report is written | the §6 row | delete the replaced file and the campaign's logs no document cites — nothing is archived |

Two checks: `Tracking.md` alone answers "where is it, what blocks it, what comes next" — if not, a
section was not updated; and it holds no commands, SHA lists or per-run results outside §5 — if
it does, that is ledger content in the wrong file.

`Tracking.md` is a current-state page for people: edit it in place, keep it to one or two screens
before §2, most important first, and never put rules for agents in it. Every section in detail,
the writing rules (language, links, code fences), what not to create, and how to move an old
document set over: `references/documents.md`. The bar a conclusion must clear:
`references/evidence.md`.

## Where everything lives

| Thing | Where | When |
|---|---|---|
| the feature's documents | "Documents" above; `templates/`, `references/documents.md` | **day 0** |
| evidence rules: controls, attribution | `references/evidence.md` | before writing any conclusion |
| documents, tickets, who approves what | `references/design-and-tickets.md` | Phase 0–1 |
| publishing the design documents | skill `managing-confluence` | Phase 1 |
| review ecology, merge order, propagation, PSF instances | `references/review-and-merge.md` | Phase 5–6 |
| build / burn / run mechanics, `jmake` worktree path rules | skill `fw-build-burn-utopx` | Phase 4 |
| `env_rebuild` + `per_run` script pair | skill `regression-repro` `templates/lab-box/` (its Phase 9b), `MODE=feature` (Phase 4) | before the first lab run |
| box reservation, waiting out `mars_reg` | skill `noga-lock` | before anything touches hardware |
| commit message format, cherry-picks, stack push | skill `gerrit-change` | Phase 5–6 |
| re-triggering CI | skill `utopx-ci-rerun` | Phase 5 |

## Phase 0 — Establish the object: request, tickets, owners

Before designing anything, pin down what exists. A feature is normally **one architecture Feature
Request + two Redmine tickets** (FW side and `[Ver]` side) + an owner in each repo.

- The **Feature Request** (SharePoint, `NBU-Architecture/SWArch`) is the contract: its numbered
  requirements are what Phase 6 judges you against. Get its number and read the Req list **in
  full, early** — not just the requirements someone quoted at you.
- Redmine: an FW ticket and a separate `[Ver]` ticket. Both must exist; gerrit's `Redmine-Issue`
  label blocks submit without one.
- Owners: the FW and test-tool sides usually have different people. Identify both, and find out
  who actually reviews — rarely the person in the reviewer slot (`references/review-and-merge.md`).

**Taking over rather than starting?** The handover always undercounts. Survey both repos by owner
and take the whole set — including already-merged changes (one may be the direct counterpart of
the change under review) and `ABANDONED` ones (you will hit them in the review history).

```bash
# gerrit MCP: search_changes_by_criteria(owner=<user>, limit=40)
```

Write the result into `Tracking.md` §1.1 / §1.2 as you go, under three rules: only the feature's
owners' changes (current and former owners; other people's commits in the same area are not this
feature's); "not merged" is the owner's current plan — ask them or read their own list — not every
open change in gerrit; merged dates from the gerrit submit approval
(`gerrit query --all-approvals`, type `SUBM`). Abandoned and stale changes stay out of the table.

## Phase 1 — Design documents before code

For a feature of any size the documents come first and are reviewed on their own: Feature Request
(SharePoint); HLD, MAS, FWV uArch, design plan / MTBC (Confluence). What each settles, its
audience, and the superseded-set trap: `references/design-and-tickets.md`.

- **The FWV uArch is load-bearing for the test side and blocks review.** A reviewer will suspend
  review of the largest file until document and code agree — signature: *"will review after
  aligning with uArch"* + a link to the uArch page. No number of patchsets clears that comment: if
  the uArch is missing, stale or contradicts the code, fixing the document **is** the work and the
  fastest path forward.
- Record meeting recordings and recaps in `Ledger.md` — design decisions get made there and
  are otherwise unrecoverable; a decision that changes the plan also updates `Tracking.md` §1.

## Phase 2 — Shape the commits before writing them

How the work is split decides how reviewable it is:

- **Interface first, logic second.** PRM/adabe struct changes go in their own change and land
  early; the logic change then rebases onto a merged interface instead of carrying it — combined,
  nothing lands until the logic change clears review.
- **A pure code-move goes in its own cosmetic commit.** A diff that both moves a function and
  changes it is unreviewable; the reviewer stops (*"please create cosmetic commit that just move
  the function then we can review the diff"*) and review of the largest file stalls until you
  split it. Do not then abandon the cosmetic commit while that request is open — it leaves the
  requirement dangling with nothing to satisfy it. If you abandon a change created to satisfy
  review feedback, say so in that comment thread the same day.
- **The enabling gate is a separate, last commit** — Phase 3.
- Do not carry a stack longer than the reviewer will hold in their head. A request to fold two
  changes into one means the split failed: fold promptly — fold the follow-up into the base change,
  abandon the follow-up, upload the same day.

## Phase 3 — Gates: a feature normally ships dark first

Features land **gated off on each side independently**, so the whole path is dead code until the
gates open:

| Side | Typical gate |
|---|---|
| FW | a capability function hard-wired to `return FALSE`, usually with a `todo: delete this line after all code is merged` comment |
| utopx | a constraint in `config/common_constraints.conf` pinned to `0`, the random variant commented out behind a patch id |

- **The gate commit merges last**, after the implementation it switches on; opening it first ships
  a path that half-exists. Merge order: **interface → implementation → gate**.
- Keep the "Gates" row of `Tracking.md` §1 current: **which gate is open right now**, on which side,
  and whether only locally. With either gate shut, every lab run exercises the old path only — a
  green run proves nothing about the feature. Do not plan lab time around a feature whose gates
  are still closed; plan the gate merge first.

## Phase 3b — Testing someone else's change: never edit it in place

A cherry-picked colleague's change that does not compile or does not run is the normal case.
**Fix it in a separate `[Local-Only]` commit stacked on top — never by editing the cherry-picked
commit or leaving changes in the working tree.** The owner uploads new patchsets while you test;
an edited tree can no longer tell you what was theirs and what was yours. With the fixes stacked,
adopting a new patchset is: reset to it, re-apply the stack, drop the hunks the new patchset made
unnecessary.

```
[Local-Only] Lab config: force <gate> on          <- survives; it is how the lab runs
[Local-Only] Make <change> build and run          <- dies when the owner fixes these
<their patchset, byte-for-byte as fetched>
<base>
```

- **Split by lifetime, not by topic.** Workarounds for their defects and your own lab
  configuration disappear on different schedules — one commit each. The config commit survives
  every rebase (upstream pins the gate to 0, so without it every run tests the old path); the
  workaround commit is pure debt.
- **Write the message so the next rebase is mechanical**: one entry per hunk, each naming the
  upstream defect it works around and quoting the failure verbatim. That lets you walk a new
  patchset hunk by hunk and delete exactly the ones now fixed — and it is the report you owe the
  owner, already written.
- **FW side, where this is absolute**: never modify `golan_fw` carries at all — keep them
  byte-identical to the gerrit patchset and report defects instead.
- **Once the change is yours, its defects still go into separate commits.** After taking a change
  over, fixes for defects that testing finds in its own code stay `[Local-Only]` carries on the test
  stack; they are not amended into the change's patchset, and they are not proposed as "fold into
  PSn". They go up later as a separate commit, when Peter decides, so the review history keeps the
  feature and its fixes apart.
- **Keep lines that depend on each other in one commit, even when they cure different defects.**
  The dependency can sit outside the diff: setting one field early can make later code skip the
  block that sets the others, so the commit holding only some of the lines fails in a new way. Each
  commit of a carry stack must build and run on its own; after reshuffling a stack, re-run the test
  step of every commit whose content changed, not only the tip.

### The base is frozen too — never advance it on your own initiative

**Do not sync a test worktree to the latest master unless the task owner asks for it.** A test
worktree is a measuring instrument: everything other than the change under test is a control that
must stay fixed. `origin/master` carries everybody's newest, least-exercised code — after pulling
it any new failure has two possible authors, and one broken commit there burns lab hours on
somebody else's bug while the feature sits untested. "The base is old" is an observation, not a
defect: the change was written against some base, and testing it there is the point.

- Sync only with a reason and the owner's agreement — the change no longer applies, a fix you
  actually need has landed, or you were told to. Then say what moved and how far.
- **Before resetting anything, save the stack**: `git branch -f <topic>-carries-<date> HEAD`.
  Carries are cheap to keep and expensive to reconstruct.
- **A carry is not obsolete until the owner uploads a patchset that removes its need.** Check the
  patchset number first — if the newest patchset is the one you already had, every carry still
  applies and goes straight back on.
- After any base change: `git submodule update --init --recursive`. Pins move with the base, and a
  mixed tree fails in ways that look like a broken baseline.

⚠ **In a worktree, `FETCH_HEAD` is not shared.** Worktrees share objects and branches, but each has
its own git dir — `<main>/.git/FETCH_HEAD` and `<main>/.git/worktrees/<wt>/FETCH_HEAD` are
different files. Fetching in the main clone and then `cherry-pick FETCH_HEAD` inside the worktree
silently picks whatever that worktree fetched last — possibly master itself. Fetch in the worktree
you cherry-pick in, and verify before picking:

```bash
git -C $WT fetch origin refs/changes/<nn>/<change>/<ps>
git -C $WT log -1 --format='%h %s' FETCH_HEAD    # must be the change's subject
git -C $WT cherry-pick FETCH_HEAD
```

## Phase 4 — Build, lab environment, and the run verdict

Workspace — feature work uses the **primary** clones (`golan_fw`, `utopx`); `*2` is the repro
pair. One worktree per feature or ticket in each repo — not one per sub-task:

```bash
git -C /auto/fwgwork1/$USER/utopx    worktree add -b <task>-track /auto/fwgwork1/$USER/utopx-<task>    origin/master
git -C /auto/fwgwork1/$USER/golan_fw worktree add -b <task>-track /auto/fwgwork1/$USER/golan_fw-<task> origin/master_rc
```

- **Sub-tasks share the feature's worktree.** Controls, A/B variants and ladder steps are commits
  switched inside it. A utopx worktree with a build is ~9 GB of the 200 GB `/vol/fwgwork1` all
  sessions share — check `df -h /auto/fwgwork1/$USER` before adding one.
- **Do not delete the worktree when the feature lands or pauses** without asking; it is reused for
  follow-ups and new patchsets. Short of space, remove its `cmakeBuild/` first.
- **Check how stale the base ref is before branching.** A local `origin/*` can be weeks behind and
  miss already-merged changes of this very feature; reading code there produces confident, wrong
  conclusions.
- **`git fetch` writes shared refs** — even `fetch origin <one-branch>` moves other remote-tracking
  refs through the remote's refspec, and other worktrees see it. Say so before running it.
- **A merged change's SHA on the branch ≠ its SHA on gerrit** (rebased on submit). Record the
  landed one, found by Change-Id — never by subject; subjects get edited during review, Change-Ids
  do not:
  `git -C <wt> log --grep="Change-Id: I<...>" --format='%h %ci' -1`

Lab environment — `mars_reg` re-provisions the regression server **daily**, so the environment is
rebuilt every session, not once. Copy skill `regression-repro`'s `templates/lab-box/` into
`<task dir>/tools/` and fill in `lab.conf` (its Phase 9b explains every part); the scripts keep every
guard. `MODE=feature` changes exactly the two repro rules that are backwards for a feature: no
pre-fix-binary check (`FIX_COMMIT` stays empty — a feature run wants the new code), and the verdict
asks whether the new code path ran instead of whether a defect signature appeared.

**The verdict.** `TEST PASSED` answers "did the tool survive", not "was the feature exercised".
`count_signal` in `lab.conf` counts the feature's own fingerprints. `FEATURE_GATE` names the utopx
key that opens the new path; `per_run.sh` passes it as `-e KEY=1`, and `--feature-off` passes `KEY=0`
for a cheap control run that must stay dark:

| Outcome | Exit | Meaning |
|---|---|---|
| `RUN VOID` | 3 | tool never initialised, or did no work — says nothing either way |
| `OLD PATH ONLY` | 5 | ran, fingerprints **0** — **proves nothing about the feature**, however green |
| `NEW PATH EXERCISED`, run clean | 0 | only now is the result about this feature |
| `NEW PATH EXERCISED`, run not clean | 6 | the feature ran and something failed |
| `CONTROL INVALID` | 4 | a control run (`--feature-off`, or a conf with `CONTROL=1`) entered the new path |

- Pick fingerprints from the code you wrote — a new opcode / `op_mod` on executed-operation
  (`LOG_OP`) lines, a log line only the new branch emits — never the feature's name or its config
  key: those appear in the config dump of every run, so their count is never zero. Count with
  `grep -c ... || true`, never `|| echo 0`: `grep -c` already prints `0`, and the second line makes
  the value `"0\n0"`, which is not `0`.
- **Count progress too, not just errors.** A tool hung inside a driver ioctl reports zero errors
  forever, so `FATAL == 0` plus a long runtime reads as the best run you have had. `per_run.sh`
  requires `LOG_OP` lines before it believes a pass — full case in skill `regression-repro`
  Phase 9b.

## Phase 5 — Review

Commit messages, cherry-picks, stack pushes: skill `gerrit-change`. CI re-triggering: skill
`utopx-ci-rerun`. Who really reviews, how to read an `unresolved` count, review bookmarks:
`references/review-and-merge.md`. Two rules hold everywhere:

- **Never adopt a reviewer's code snippet without verifying it yourself** — compile it, or at
  minimum grep the symbol's definition. When you report a defect of that origin, **name the
  origin**; otherwise it reads as the owner being sloppy, and the reviewer repeats the suggestion.
- **Cross-layer consistency is nobody's job unless you take it.** A config key, the adabe node it
  binds to and the code reading it must agree; nothing catches a mismatch — not the compiler, not
  CI, not review. Grep all three layers whenever you add or rename a constrained field.

Known instances of both: `references/review-and-merge.md` §3.

## Phase 6 — Merge, then prove the Req list

- Merge in the Phase 3 order (**interface → implementation → gate**), with an FW change landing
  before the test-tool change that consumes its capability; then propagate to ES / master / GA
  branches (skill `gerrit-change`; one column or table per target branch in `Tracking.md`
  §1.1 / §1.2). Reasons and details: `references/review-and-merge.md` §2.
- Then close the loop against the Feature Request from Phase 0. For **each numbered Req**, find the
  assertion in the test tool that would fail if it were violated — walk the FW↔utopx interface
  field by field — and record it in `Tracking.md` §1.6, whose "Verified?" column makes the holes
  show. "Code exists on both sides" is not "the requirement is verified"; only an assertion that
  can fail is verification.

## Rules that must fire without opening a reference

- **To decide whether a bug is still present, read the file on the branch**, not a change's diff
  context; later commits may have rewritten the function entirely.
- **To decide whether someone is still working a change, read `list_patchsets`**, not `updated` —
  that field lags by minutes. And before saying "N days without activity", run `date -u`.
- **An unrecorded action counts as not done** — in the same step as the action, add the
  `Ledger.md` entry and update the `Tracking.md` sections the event table names. An
  overturned conclusion is struck through in the ledger, not deleted; `Tracking.md` is simply
  corrected, because it describes the present.
