---
name: gerrit-change
description: Write gerrit commit messages and cherry-pick changes between branches on git-nbu.nvidia.com (fw_ver/golan_fw, fw_ver/utopx, hca_fw). Covers the Title/Description/Issue/Reviewed By/Change-Id block format, per-project continuation-line style, Change-Id reuse rules, and the cherry-picked-from footer. Use when writing or amending a commit message for gerrit, cherry-picking or back-porting a change to another branch, propagating a fix to an ES/review branch, or when a push is rejected with "change ... closed" or "multiple Change-Id".
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

Reviewed By: AI, yanku

(cherry picked from commit <full 40-char sha>)

Change-Id: I<40 hex>
```

Rules that actually matter:

- **Continuation-line style is per-project. Do not carry one project's style to another.**
  - `fw_ver/utopx` — **hanging indent** (Peter's standard as of 2026-08-05): continuation
    lines aligned under the text after `Description: ` (13 spaces), `Issue:` lines tight
    below with no blank line, blank line only before `Change-Id:`.
  - `fw_ver/golan_fw` — continuation lines at **column 0**. Gerrit re-wrapped hand-aligned
    text there: the first line wraps, padded ones don't.
  - Unsure? Read a recently merged commit on that branch and copy its shape.
- **Keep every line ≤ 72 chars.** The `Title:` line may exceed it — gerrit only warns
  `subject >50 characters`, which is harmless. Wrap prose yourself; do not rely on the renderer.
- **Blank line between every block**: Title / Description / Issue / Reviewed By /
  cherry-pick note / Change-Id.
- `Change-Id` must be the **last** block. A `(cherry picked from …)` line goes in its own
  block **before** it, or gerrit stops parsing the footer.
- Take the cherry-pick sha from `git rev-parse <short>` — never hand-type it.

Verify before pushing:

```bash
git log -1 --format=%B <sha> | awk '{print length($0), $0}'
```

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

## Related

- Pushing more than one commit at a time → skill `gerrit-stack` (topics are **mandatory**, not
  an optimisation).
- Re-running CI after a push → skill `utopx-ci-rerun`.
