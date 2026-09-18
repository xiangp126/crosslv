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

### Always add the footer

```
(cherry picked from commit <full 40-char sha>)
```

The Change-Id says *which change* but not *which patchset* was taken; the 40-char SHA removes
that ambiguity — it matters the moment a change is re-pushed with real content differences
between patchsets. Adding a footer afterwards is a message-only amend: the tree is unchanged,
nothing needs rebuilding, and gerrit confirms with `no files changed, message updated`.

## Two mechanical traps, one full build cycle each

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
