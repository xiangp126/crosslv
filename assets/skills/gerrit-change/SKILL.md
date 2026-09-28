---
name: gerrit-change
description: Get a change onto gerrit (git-nbu.nvidia.com - fw_ver/golan_fw, fw_ver/utopx, hca_fw) - commit-message format, cherry-picks between branches, and pushing a dependent stack atomically. Covers the Title/Description/Issue/Reviewed By/Change-Id block, per-project continuation style, Change-Id reuse rules, the cherry-picked-from footer, and the RELATED_CHANGES/IGNORE topics a multi-commit push needs. Use when writing or amending a commit message, cherry-picking or back-porting to another branch, propagating a fix to an ES/review branch, pushing more than one commit at once, when the CI stage "Related Changes Check" fails, or when a push is rejected with "change ... closed" or "multiple Change-Id".
---

# Gerrit commit messages & cherry-picks (git-nbu.nvidia.com)

Getting the message shape wrong wastes a review round every time.

## Message format

```
Title: [<Tag>]<Area> short summary

Description: first line of prose starts right after the label
continuation lines start at column 0 — NOT indented to align under
"Description:"

Issue: 5149895

Reviewed By: AI, Jinbow(+1), Yanku(+2)

(cherry picked from commit <full 40-char sha>)

Change-Id: I<40 hex>
```

Rules that actually matter:

- **Continuation-line style is per-project. Do not carry one project's style to another.**
  - `fw_ver/utopx` — **hanging indent** (Peter's standard as of 2026-08-05): continuation
    lines aligned under the text after `Description: ` (13 spaces). Blank line above
    `Issue:`; `Reviewed By:` sits tight under `Issue:` with **no** blank line between
    them; blank line above `Change-Id:`. So the tail is exactly:

    ```
    Fix:         <last line of the fix prose>
                                              <- blank
    Issue: 5257102
    Reviewed By: AI, Jinbow(+1), Yanku(+2)
                                              <- blank
    Change-Id: I...
    ```

    (Settled 2026-09-04 on 5257102. Earlier revisions of this file had the blank line on
    the wrong side of `Issue:` — `Issue:`/`Reviewed By:` are one block, and the blank line
    separates that block from `Fix:`.)
  - `fw_ver/golan_fw` — continuation lines at **column 0**. Gerrit re-wrapped hand-aligned
    text there: the first line wraps, padded ones don't.
  - Unsure? Read a recently merged commit on that branch and copy its shape.
- **Keep every line ≤ 72 chars.** The `Title:` line may exceed it — gerrit only warns
  `subject >50 characters`, which is harmless. Wrap prose yourself; do not rely on the renderer.
  - On a hanging-indent project the budget is **72 minus the indent**: under `Description: `
    (13 spaces) prose must be **≤ 59 chars**. Forgetting this is the usual cause of
    `warning: too many message lines longer than 72 characters` — and the web UI then
    re-wraps the overflow to column 0, so every second line is flush-left and the message
    reads as garbage even though the raw text looked aligned. 2026-09-02 on 1494424.
  - A **verbatim quote that cannot fit in 59** (a FATAL line, a syndrome string) still stays
    at the hanging indent — **break it at a natural boundary** (`;;`, `:`, `[`) across two or
    three lines. Do NOT dedent the quote to buy width: Peter reviews the rendered message and
    a block that is not vertically aligned with the rest of the Description gets bounced.
    2026-09-02 on 1494424 — PS2 put the quote at 4 spaces to keep it in one piece, PS3 had to
    re-align it. Alignment beats keeping the string on one line.
- **Several tickets → one `Issue:` line each. Never a comma-separated list.**

  ```
  Issue: 4690480
  Issue: 4284608
  ```

  `Issue: 4690480, 4284608` is wrong; it was pushed that way on 1501505 (2026-09-10) and had
  to be corrected in a second patchset. The lines stay in the same block as each other and as
  `Reviewed By:` — no blank line between them.

- **Default reviewer line — write it, do not ask and do not omit it:**

  ```
  Reviewed By: AI, Jinbow(+1), Yanku(+2)
  ```

  `AI` credits this session. The `(+1)` / `(+2)` are the votes those reviewers are expected to
  give, so the line goes in from the first push, before anyone has actually voted. Only
  deviate when Peter names different reviewers for that change.
- **Blank line between every block**: Title / Description / Issue / Reviewed By /
  cherry-pick note / Change-Id.
- `Change-Id` must be the **last** block. A `(cherry picked from …)` line goes in its own
  block **before** it, or gerrit stops parsing the footer.
- Take the cherry-pick sha from `git rev-parse <short>` — never hand-type it.

Verify before pushing — **including before every amend-and-repush**, not just the first push:

```bash
git log -1 --format=%B | awk 'length($0)>72 {print length($0), $0}'   # must print nothing
git log -1 --format=%B | grep -c '^Change-Id'                         # must print 1
```

Run it on the message **file** before committing, so a bad message never reaches gerrit:

```bash
awk 'length($0)>72' /path/to/commit_msg.txt | wc -l                   # must print 0
```

## What the message carries, and what the code must not

Peter reviews the rendered message, not the diff comments. Two standing preferences, both
from 5257102 (2026-09-04):

- **No explanatory comments in the code change.** A fix that needed a seven-line comment
  block explaining which FW function it mirrors, which syndrome it stops, and why a field
  was added got the whole block deleted: "remove all the comments in the code". Every one
  of those facts belongs in the `Description:`. Ship the diff as pure logic — the reviewer
  reads the *why* above it, not beside it.
- **Write the Description in plain prose, not in implementation terms.** Naming the
  functions on both sides and saying one "ANDs that group with" the other reads as a
  transcript of the code. Say what the tool did, what FW wanted instead, and why it used
  to work. Keep verbatim FATAL/syndrome text and real cap field names — those are what a
  reviewer greps for; drop internal function names, and prefer the domain verb (the ECPF
  **delegates** a cap; it does not "hand" it).

## Two failures that reject a push

- **Duplicate Change-Id.** The commit-msg hook appends a **second** Change-Id when the message
  contains a non-standard trailer like `Reviewed By:` (note the space). Bypass it:
  `git commit --no-verify`, or build the commit with `commit-tree`. Check: exactly one
  `Change-Id:` per commit.
- **Reusing a Change-Id that belongs to a closed change on the same branch** →
  `change ... closed`. Mint a fresh one: `NEWCID="I$(git rev-parse HEAD)"`.

## Cherry-picking to another branch

Two things decide whether a pick is clean: which commit you take as the source, and what you
do with the Change-Id.

### Source = the commit as it exists in the branch it merged into

Never the local commit you pushed. Gerrit rebases on submit, so the two differ:

```bash
git fetch origin <source branch>
SRC=$(git log FETCH_HEAD --format=%H --grep=<Change-Id of the source change> | head -1)
```

Taking the pre-push SHA produces a `(cherry picked from …)` footer pointing at a commit that
exists on no branch. Also `git fetch` the **target** branch before picking and check
`git merge-base --is-ancestor` — a local propagation branch can sit dozens of commits behind
with no visible sign.

### Change-Id: reuse across branches, never within one

A gerrit change is identified by the triplet `project ~ branch ~ Change-Id` (visible as
`triplet_id` in the REST API). The same Change-Id on a **different** branch is simply a
different change — and a useful one: gerrit's UI links the propagations together and
`git log --grep=<Change-Id>` finds the commit on every branch.

The only failure mode is a **closed** (abandoned or merged) change already holding that
Change-Id **on the target branch**; gerrit refuses to append a patchset (`change ... closed`).
Check before picking, don't guess:

```
gerrit query:  branch:<target> AND change:<Change-Id>
```

Hit → mint a fresh one (`NEWCID="I$(git rev-parse HEAD)"`). No hit → reuse.

### Always add the footer — it is mandatory, not a nicety

```
(cherry picked from commit <full 40-char sha>)
```

Peter, 2026-09-22: *"when doing cherry pick, the new commit description must contain sth.
like `(cherry picked from commit a3f49e70bd1ceb20d602726fd9bbfe971e1cc1e0)`"*. Every
cherry-picked commit carries it. No exceptions.

The Change-Id says *which change* but not *which patchset* was taken; the 40-char SHA removes
that ambiguity — it matters the moment a change is re-pushed with real content differences
between patchsets. Adding a footer afterwards is a message-only amend: the tree is unchanged,
nothing needs rebuilding, and gerrit confirms with `no files changed, message updated`.

**Let git write it — `-x` exists for exactly this:**

```bash
git cherry-pick -x <sha>          # appends the footer automatically, full 40-char sha
```

Use `-x` whenever the message needs no other change. The one case where you cannot is **ours**:
propagating to a sibling branch reuses the *same* Change-Id, so the message has to be rebuilt
(strip the picked commit's `Change-Id:` and any older `(cherry picked from …)` line, append the
reused `Change-Id:` and a fresh footer). That is the `cherry-pick -n` + hand-assembled message
path. It works, but the footer is now something *you* wrote, so it is something you can forget.

**Which SHA goes in the footer:** the commit you actually picked from. If the source change is
already merged, that is its SHA on the target branch (see the section above on taking the source
from the branch it merged into). If it is still open — propagating ahead of the master merge —
it is the local SHA you picked, and gerrit may later rebase that change to a new patchset with a
different SHA. That is fine and expected: the footer records *what was taken*, not what the
source change looks like today.

**Verify before pushing, every branch, one line:**

```bash
git log -1 --format=%B <branch> | grep -c '^(cherry picked from commit [0-9a-f]\{40\})$'
```

`1` = good. `0` = the footer is missing or malformed (short SHA, wrong wording, trailing text).
Put this next to the build check in a propagation script — a missing footer is invisible in the
diff and only surfaces in review, after all three branches are already pushed.

**And check the message is byte-identical to the source, not that it is well-formatted.** A
cherry-pick reproduces; it does not re-edit. Strip the `Change-Id:` line and the footer from
both and compare:

```bash
strip() { git log -1 --format=%B "$1" | sed '/^Change-Id: /d;/^(cherry picked from commit /d'; }
diff <(strip <source-sha>) <(strip <branch>)      # must be empty
```

⚠ **Do not gate a cherry-pick on line length.** A propagation script on 2026-09-23 carried a
"no line over 72 chars" check and aborted the whole run on the *source commit's own title*
(`Title: [Test Bug] <Hotplug> Modify host-awareness only on hotplug devices`, 73 chars) — a
commit already merged to master with a green CI. The 72-column rule is for a message you are
**writing**; on a pick, re-wrapping the title would make the branches disagree with master,
which is worse than a long line.

## Two mechanical traps, one full build cycle each

- **Cherry-picked someone else's change to test it, and it is broken?** Do not edit it, and do
  not leave the fix in the working tree — stack a `[Local-Only]` commit on top, so their next
  patchset is a rebase instead of an archaeology session. Shape and message: skill
  `feature-delivery` Phase 3b.
- **Never `git add -A` while resolving a cherry-pick conflict.** It silently sweeps in
  submodule pointer changes and untracked build artifacts. `git checkout -B <branch> <base>`
  does *not* move submodule working trees, so they show as modified and get committed at the
  wrong revision — the resulting build errors appear inside the submodule sources and look
  exactly like "the baseline is broken". **Add by path.**
- **Re-sync submodules after any base change**: `git submodule update --init --recursive`.
  After committing, verify: the changed-file list must match the source commit's `--stat`,
  and every submodule pointer must be identical to the base.

## Reading a conflict

**A conflict is usually not the change's own content.** Before resolving, run
`git show <source> -- <file>` to see what the change actually touched; the rest of the conflict
is baseline drift between the two branches and must be preserved as-is.

**Zero conflicts does not mean it compiles.** A rename landed upstream will apply cleanly and
then fail to build. Build the stack top before pushing.

## Propagating one fix to several branches — one track at a time

A fix that lands on one branch usually has to reach the others. Do **one branch end to end,
then the next**. Five steps per track, and you do not start the next track until the current
one has been pushed:

```
checkout → cherry-pick → build → verify the build is clean → push → next track
```

**Never restructure this into "pick all, then build all, then push all".** Three reasons:

- A broken pick on track 1 must stop the run. If the three picks are done up front, the second
  and third are built on an assumption that already failed.
- Each track has its own baseline. A conflict or a build break is track-specific, and you want
  it surfaced against the track that caused it, not mixed into a batch result.
- Peter's rule, stated directly: *"你还是要挨个 checkout，然后 cherry pick，build，确认 build
  成功再 push，然后下一个"*.

If you script it, make failure of any step abort the **whole** run — a script that calls the
per-track function three times in a row without chaining will happily keep going after the
first one fails. That mistake was made on BF10 (2026-09-22).

**Conflicts get fixed, not reported.** A conflict is an expected part of a pick; resolve it
(by path — see the `git add -A` trap above), keeping baseline drift as-is. Only stop and ask
when the resolution would change the change's own semantics.

### The per-track gate

Check all of these before the build, and treat any failure as a stop:

| Check | Why |
|---|---|
| new-line `md5sum` of the pick == the source's | proves the content arrived intact, independent of line numbers |
| submodule pointer changes == 0 | `checkout -B` leaves submodule working trees behind; they get committed at the wrong revision and the build error then appears *inside* the submodule |
| commits between upstream and HEAD == 1 | catches a stale branch or a double pick |
| exactly one `Change-Id:` line | `Reviewed By:` makes the commit-msg hook regenerate one; commit with `--no-verify` |
| no line in the message over 72 chars | gerrit rejects it |

Then build, and gate the push on **all** of: `rc == 0`, zero `error:` lines, zero
`undefined reference`, at least one `BUILD SUCCESS`. jmake prints `BUILD SUCCESS` and exits 0
even when a sub-stage died, so one signal is not enough.

### Three traps that only bite when you script this

All three are documented elsewhere in these skills, and all three were still hit on BF10
(2026-09-22) — then the third one was hit *again* on 2026-09-23 in a different disguise, by a
script whose author had read this very table. The first track failed with
`hca_fwv_shared/autogen/PacketFields.cpp: error: 'hca_fwv_ib_pkt_hdr_boeth' was not declared` —
which reads exactly like "the baseline is broken" and is not.

| Trap | How it shows up | Fix |
|---|---|---|
| `grep` without `-a` | jmake logs contain binary bytes, so grep reports `Binary file matches` and counts are unreliable — a run was scored `error:=48` while the log tail said `BUILD SUCCESS` and the recorded time (1m43s) contradicted the log's own `total build time 11:00` | every grep over a build log takes `-a` |
| `jmake -o` instead of `-c -o` | `autogen/` is gitignored, so **`checkout -B` leaves the previous branch's generated sources in place**; the stale `.cpp` meets the new submodule headers | clean-build after any base change |
| not scrubbing the base per track | `git submodule status` shows `+` entries — `checkout -B` does not move submodule working trees | the exact sequence below; anything less leaves stale generated headers |

Cleaning by hand after that failure removed **52** generated files before all three submodules
came back in sync. Budget for it: a clean build per track is ~8-10 min, so a three-track
propagation is roughly 30 minutes of build time.

**The scrub, verbatim — copy it, do not paraphrase it:**

```bash
git -C "$W" submodule update --init --recursive --force
for d in hca_fwv_shared steering_ul hca_fw_core_platform; do
    [ -d "$W/$d" ] && git -C "$W/$d" clean -fdxq          # note: -C into the submodule
done
( cd "$W" && git clean -fdxq -- 'src/cmdif/include/autogen' 'autogen' )
[ "$(git -C "$W" submodule status --recursive | grep -c '^[+-]')" -eq 0 ] || exit 1
```

⚠ **`git clean -fdx -- hca_fwv_shared/` does NOT clean that submodule.** `git clean` will not
descend into a nested repository when you merely name its path; you have to run it *inside*,
with `git -C <submodule>`. Written the wrong way on 2026-09-23, this left the previous branch's
`hca_fwv_shared/autogen/enum2str/GlobalEnum2Str.h` in place against the new submodule's types
and produced **504** `... has not been declared` errors — again reading like a broken baseline.
Note the failure mode of the wrong form is *silence*: the command succeeds, cleans nothing, and
the damage only appears eight minutes later in the compiler.

Also note the whitelist: the autogen paths are named explicitly rather than cleaning the repo
root, because the working tree may hold other people's artifacts (`genid_dump`, `nvmf_dump`) that
a blanket `git clean -fdx` would take out.

### You do not need a worktree per branch

`git push` does not need a checkout — the branch only has to exist in `.git`:

```bash
git push origin fix_5273244_emuhost_ES:refs/for/FUR_2026_Jan_VR_Fractal_ES_from_48_0386
```

So one borrowed working tree can serve every track in turn, and can be discarded afterwards;
the private branches survive it. Only the **build** needs a working tree. Do not stand up a
long-lived worktree per branch for propagation work — Peter removed all of them on 2026-09-18
with *"删了就删了呗"*.

### Naming the private branch — the track must be readable off the name

```
fix_<ticket>_<topic>_<track>          fix_5273244_emuhost_ES
                                      fix_5273244_emuhost_June
                                      fix_5273244_emuhost_master
xcheck_<ticket>_<what>                a branch for investigating, not for pushing
```

`<track>` is **copied out of the target branch name** — take the one token that identifies it
and nothing else:

| target branch | `<track>` |
|---|---|
| `master` | `master` |
| `FUR_2026_Jan_VR_Fractal_ES_from_48_0386` | `ES` |
| `FUR_2026_June_PRDMA_CSP_main_from_48_1642` | `June` |
| `FUR_2026_Sep_PRDMA_CSP_08_from_48_6132` | `Sep` |

Do **not** invent your own abbreviation. `prop-bf10-csp` / `prop-bf10-csp08` were used on
2026-09-22 and are exactly the failure mode: `csp` vs `csp08` needs a mapping table kept in
someone's head, and that table breaks the day a third CSP branch is cut. The token above is
already on screen — it sits in the `refs/for/<target>` you are about to type.

⚠ **The token is not guaranteed unique — check before you use it.** This rule was written on
2026-09-22 with `June` as the example; on 2026-09-23 `ls-remote` returned **two** June branches:

```
FUR_2026_June_PRDMA_CSP_main_from_48_1642    active
FUR_2026_June_PRDMA_CSP_main_from_48_6132    frozen, tip stopped 09-09
```

What separates them is the trailing baseline `48_<NNNN>`. So: **list the branches first, and
only then pick the token.** One command, and it doubles as the branch-name check:

```bash
git ls-remote --heads origin | grep -oE 'FUR_[A-Za-z0-9_]+'
```

If the month token is ambiguous, append the baseline (`June1642`). If one of the two is frozen,
say so in the ledger rather than silently ignoring it — "which branches does this fix belong on"
is a separate question from "what do I call the branch", and a frozen branch usually answers
itself (check whether the recent fixes are on it: a branch that is missing the last two is not
being maintained).

Equally, do not name the branch after the *shape of the fix*
(`5285522_macro_shape`, `5285522_satpf_macro_guard`). Peter, 2026-09-22: those say which
variant you tried, never which branch it lands on, and the landing branch is the thing you
need when there are four of them in flight. Variants are what `git log` and gerrit patchsets
are for; if two candidate approaches really must coexist, they go in `<topic>`, with
`<track>` still last.


## Pushing a stack of dependent changes

Pushing a chain — `git push origin <tip>:refs/for/<branch>` — creates one change per commit and
gerrit records the parent/child dependency. That guarantees **order** (a child never merges before
its parent) but **not atomicity**: by default each change gets its own CI round and its own
submission, so a 4-deep stack costs 4 CI rounds spread over days.

### Set the topics — mandatory, not an optimisation

```bash
for c in <lower changes>; do
  ssh -p 12023 git-nbu.nvidia.com gerrit set-topic $c --topic IGNORE
done
ssh -p 12023 git-nbu.nvidia.com gerrit set-topic <top change> --topic RELATED_CHANGES
```

Setting a topic creates no patchset and outdates no vote.

The CI runs `fw_automations/ci/utopx/scripts/check_for_related_changes.py` in a stage called
**`Related Changes Check`**, and it fails the build unless one of these holds:

- the top change's topic contains `RELATED_CHANGES` **and** every related change's topic
  contains `IGNORE`; or
- there are no related changes at all (the stack was rebased apart).

Its own error text: *"Your change has related changes, but the topic in your top change doesn't
contain RELATED_CHANGES … if not please rebase and break the related changes chain"*.
Reference: `https://confluence.nvidia.com/display/FW/Setting+The+Gerrit+Topic`

Once the topics are in place, `submission_id` becomes `<topChangeNum>-RELATED_CHANGES` and every
change in the stack carries that same id with an identical `submitted` timestamp — verified on
`fw_ver/utopx` with `1467618 + 1455654/55/56` and with `1463162 + 1463160/61`.

### The measurement that settles the argument

Same four-deep stack, same commits, same reviewers, pushed to two branches on 2026-08-13:

| | topics set | outcome |
|---|---|---|
| review branch | no | 3 separate CI rounds, 3 submissions, spread over two days |
| ES branch | yes | **one CI round, all four merged the same day** |

The only difference was the topics.

### Habits that go with a stack

- **Collect every `+2` at once.** Voting does not merge anything; submission does, and submission
  respects the chain. There is no risk in approving a whole stack in one pass.
- **Stop hand-editing the stack once votes are in.** When a parent merges, gerrit rebases the
  children automatically and copies votes whose copy condition allows it (`TRIVIAL_REBASE` keeps
  them, `REWORK` drops them). A manual rebase to resolve a conflict is a `REWORK` and costs you
  every vote on the stack.
- To find out whether a project ever submits stacks atomically, look at `submission_id` on
  already-merged changes (the REST search returns it; the ssh `gerrit query` output does not).
  `<num>-<topic>` means an atomic stack submit; `submission_id == the change's own number` means
  it went in alone.

## Related

- Re-running CI after a push → skill `utopx-ci-rerun` (CR+2 must be in place **before** a re-run).
- Driving the feature these changes belong to → skill `feature-delivery`.
