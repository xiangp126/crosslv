---
name: gerrit-change
description: >-
  Get a change onto gerrit (git-nbu: fw_ver/golan_fw, fw_ver/utopx, hca_fw) - commit-message
  format, Change-Id and cherry-pick footer rules, and pushing a dependent stack with
  RELATED_CHANGES/IGNORE topics. Use when writing or amending a commit message, cherry-picking,
  back-porting or propagating to another branch, pushing several commits, when "Related Changes
  Check" fails, or a push is rejected with "change ... closed" or "multiple Change-Id".
---

# Gerrit commit messages, cherry-picks and stacks (git-nbu.nvidia.com)

## Commit message format

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

### Continuation lines are per project — never carry one project's style to another

- **`fw_ver/utopx` — hanging indent.** Continuation lines align under the text after
  `Description: ` (13 spaces). `Issue:` and `Reviewed By:` form one block (no blank line between
  them) that follows the last body line directly; a blank line separates it from `Change-Id:`
  below (as merged utopx messages show). The tail is exactly:

  ```
  Fix:         <last line of the fix prose>
  Issue: 5257102
  Reviewed By: AI, Jinbow(+1), Yanku(+2)
                                            <- blank
  Change-Id: I...
  ```
- **`fw_ver/golan_fw` — column 0.** Gerrit re-wraps hand-aligned text there: the first line
  wraps, padded ones don't.
- Unsure → read a recently merged commit on that branch and copy its shape.

### Line length

- **Every line ≤ 72 chars, except the `Title:` line.** Gerrit never rejects a message for line
  length, it only warns: `subject >50 characters` on the title (harmless) and the body warning
  below. Wrap prose yourself; do not rely on the renderer.
- **Hanging-indent projects: the budget is 72 minus the indent** — prose under `Description: `
  (13 spaces) must be **≤ 59 chars**. Overflow triggers
  `warning: too many message lines longer than 72 characters`, and the web UI re-wraps it to
  column 0, so every second line renders flush-left even though the raw text looked aligned.
- **A verbatim quote that cannot fit in 59** (a FATAL line, a syndrome string) stays at the
  hanging indent: break it at a natural boundary (`;;`, `:`, `[`) across two or three lines.
  Never dedent it to buy width — Peter reviews the rendered message and bounces a block that is
  not vertically aligned with the rest of the Description. Alignment beats keeping the string on
  one line.

### Block rules

- **`Issue:` and `Reviewed By:` are one block — no blank line between them — in both
  `fw_ver/golan_fw` and `fw_ver/utopx`**, as merged messages on both show.
- **Several tickets → one `Issue:` line each, never a comma-separated list**
  (`Issue: 4690480, 4284608` is wrong). They stay in that block:

  ```
  Issue: 4690480
  Issue: 4284608
  Reviewed By: AI, Jinbow(+1), Yanku(+2)
  ```

- **Default reviewer line — write it; do not ask, do not omit it:**

  ```
  Reviewed By: AI, Jinbow(+1), Yanku(+2)
  ```

  `AI` credits this session. `(+1)` / `(+2)` are the votes those reviewers are expected to give,
  so the line goes in from the first push, before anyone has voted. Deviate only when Peter names
  different reviewers for that change.
- **Blank line between every block**: Title / Description / `Issue:` + `Reviewed By:` /
  cherry-pick note / Change-Id. Exception, `fw_ver/utopx`: the `Issue:` block follows the last
  body line directly (see the utopx tail above).
- **`Change-Id` is the last block.** A `(cherry picked from …)` line goes in its own block
  **before** it, or gerrit stops parsing the footer.
- Take the cherry-pick sha from `git rev-parse <short>` — never hand-type it.

### Verify — before the first push and before every amend-and-repush

On the message **file**, before committing, so a bad message never reaches gerrit:

```bash
awk '!/^Title:/ && length($0)>72' /path/to/commit_msg.txt | wc -l    # must print 0
```

On the commit:

```bash
git log -1 --format=%B | awk '!/^Title:/ && length($0)>72 {print length($0), $0}'  # must print nothing
git log -1 --format=%B | grep -c '^Change-Id'                         # must print 1
```

## What goes in the message, not in the code

Peter reviews the rendered message, not comments in the diff.

- **No explanatory comments in the code change.** Which FW function the fix mirrors, which
  syndrome it stops, why a field was added — all of it goes in `Description:`. Ship the diff as
  pure logic.
- **Write the Description in plain prose, not in implementation terms.** Say what the tool did,
  what FW wanted instead, and why it used to work. Do not transcribe the code (naming the
  functions on both sides, saying one "ANDs that group with" the other). Keep verbatim
  FATAL/syndrome text and real cap field names — reviewers grep for those; drop internal function
  names; use the domain verb (the ECPF **delegates** a cap; it does not "hand" it).

## Push rejections

| Rejection | Cause | Fix |
|---|---|---|
| Duplicate Change-Id ("multiple Change-Id") | The commit-msg hook appends a **second** Change-Id when the message contains a non-standard trailer like `Reviewed By:` (note the space) | `git commit --no-verify`, or build the commit with `commit-tree`. Check: exactly one `Change-Id:` per commit |
| `change ... closed` | The Change-Id belongs to a closed change on the same branch | Mint a fresh one: `NEWCID="I$(git rev-parse HEAD)"` |

## Cherry-picking to another branch

### Source: the commit as it exists in the branch it merged into

Never the local commit you pushed — gerrit rebases on submit, so the two differ, and the pre-push
SHA gives a `(cherry picked from …)` footer pointing at a commit that exists on no branch.

```bash
git fetch origin <source branch>
SRC=$(git log FETCH_HEAD --format=%H --grep=<Change-Id of the source change> | head -1)
```

Also `git fetch` the **target** branch before picking and check `git merge-base --is-ancestor` —
a local propagation branch can sit dozens of commits behind with no visible sign.

### Change-Id: reuse across branches, never within one

A gerrit change is identified by `project ~ branch ~ Change-Id` (`triplet_id` in the REST API).
The same Change-Id on a **different** branch is a different change, so reuse it: gerrit's UI links
the propagations, and `git log --grep=<Change-Id>` finds the commit on every branch.

The only failure: a **closed** (abandoned or merged) change already holds that Change-Id **on the
target branch** → gerrit refuses the patchset (`change ... closed`). Check before picking:

```
gerrit query:  branch:<target> AND change:<Change-Id>
```

Hit → mint a fresh one (`NEWCID="I$(git rev-parse HEAD)"`). No hit → reuse.

### The footer is mandatory on every cherry-pick

```
(cherry picked from commit <full 40-char sha>)
```

e.g. `(cherry picked from commit a3f49e70bd1ceb20d602726fd9bbfe971e1cc1e0)`. No exceptions. The
Change-Id says *which change* but not *which patchset* was taken; the 40-char SHA pins it, which
matters once patchsets differ in content. Adding a missing footer is a message-only amend: the tree
is unchanged, nothing needs rebuilding, and gerrit confirms with `no files changed, message updated`.

- **Let git write it** whenever the message needs no other change:

  ```bash
  git cherry-pick -x <sha>          # appends the footer automatically, full 40-char sha
  ```

- **Propagating to a sibling branch with the reused Change-Id cannot use `-x`** — the message has
  to be rebuilt: `cherry-pick -n`, then assemble the message by hand (strip the picked commit's
  `Change-Id:` and any older `(cherry picked from …)` line, append the reused `Change-Id:` and a
  fresh footer). The footer is then hand-written, so verify it (below).
- **Which SHA goes in the footer:** the commit you actually picked from. Source change already
  merged → its SHA on the target branch, i.e. the branch it merged into (see "Source" above).
  Still open (propagating ahead of the master merge) → the local SHA you picked; gerrit may later
  rebase that change to a new SHA — fine, the footer records *what was taken*.

**Verify on every branch before pushing** — put it next to the build check in a propagation
script; a missing footer is invisible in the diff and only surfaces in review:

```bash
git log -1 --format=%B <branch> | grep -c '^(cherry picked from commit [0-9a-f]\{40\})$'
```

`1` = good. `0` = footer missing or malformed (short SHA, wrong wording, trailing text).

**Check the message is byte-identical to the source**, not merely well-formatted — a cherry-pick
reproduces, it does not re-edit:

```bash
strip() { git log -1 --format=%B "$1" | sed '/^Change-Id: /d;/^(cherry picked from commit /d'; }
diff <(strip <source-sha>) <(strip <branch>)      # must be empty
```

**Do not gate a cherry-pick on line length.** The 72-column rule is for a message you are
**writing**. A source commit already merged to master may carry a longer line; re-wrapping it on
a pick makes the branches disagree with master, which is worse than a long line.

## Cherry-pick mechanics

- **Testing someone else's change and it is broken?** Do not edit it and do not leave the fix in
  the working tree — stack a `[Local-Only]` commit on top, so their next patchset is a rebase.
  Shape and message: skill `feature-delivery` Phase 3b.
- **Never `git add -A` while resolving a cherry-pick conflict — add by path.** It sweeps in
  submodule pointer changes and untracked build artifacts: `git checkout -B <branch> <base>` does
  *not* move submodule working trees, so they show as modified and get committed at the wrong
  revision; the build errors then appear inside the submodule sources and look exactly like "the
  baseline is broken".
- **Re-sync submodules after any base change**: `git submodule update --init --recursive`. After
  committing, verify that the changed-file list matches the source commit's `--stat` and every
  submodule pointer is identical to the base.
- **A conflict is usually not the change's own content.** Before resolving, run
  `git show <source> -- <file>` to see what the change actually touched; the rest of the conflict
  is baseline drift between the two branches — preserve it as-is.
- **Zero conflicts does not mean it compiles** — an upstream rename applies cleanly and then fails
  to build. Build the stack top before pushing.

## Propagating one fix to several branches

### One track at a time

Do one branch end to end, then the next; do not start a track until the current one is pushed:

```
checkout → cherry-pick → build → verify the build is clean → push → next track
```

- **Never restructure this into "pick all, then build all, then push all".** A broken pick on
  track 1 must stop the run, and each track has its own baseline — a conflict or build break must
  surface against the track that caused it, not in a batch result.
- **Scripted: failure of any step aborts the whole run.** Chain the per-track calls — calling the
  per-track function three times in a row without chaining keeps going after the first fails.
- **Conflicts get fixed, not reported.** Resolve them (by path — see "Cherry-pick mechanics"),
  keeping baseline drift as-is. Stop and ask only when the resolution would change the change's
  own semantics.

### The per-track gate

Check all of these before the build; any failure is a stop, except line length, which never
blocks a pick:

| Check | Why |
|---|---|
| new-line `md5sum` of the pick == the source's | proves the content arrived intact, independent of line numbers |
| submodule pointer changes == 0 | `checkout -B` leaves submodule working trees behind; they get committed at the wrong revision and the build error then appears *inside* the submodule |
| commits between upstream and HEAD == 1 | catches a stale branch or a double pick |
| exactly one `Change-Id:` line | `Reviewed By:` makes the commit-msg hook regenerate one; commit with `--no-verify` |
| lines ≤ 72 chars except `Title:` — report a longer one, never stop on it | gerrit only warns on a long line, and a pick keeps the source's message as it is ("Do not gate a cherry-pick on line length") |

Then build, and gate the push on **all** of: `rc == 0`, zero `error:` lines, zero
`undefined reference`, at least one `BUILD SUCCESS`. jmake prints `BUILD SUCCESS` and exits 0 even
when a sub-stage died, so one signal is not enough.

### Scripting traps

When they hit, the track fails with
`hca_fwv_shared/autogen/PacketFields.cpp: error: 'hca_fwv_ib_pkt_hdr_boeth' was not declared` —
which reads exactly like "the baseline is broken" and is not.

| Trap | How it shows up | Fix |
|---|---|---|
| `grep` without `-a` | jmake logs contain binary bytes, so grep reports `Binary file matches` and counts are unreliable (an `error:` count can contradict a log that ends in `BUILD SUCCESS`) | every grep over a build log takes `-a` |
| `jmake -o` instead of `-c -o` | `autogen/` is gitignored, so **`checkout -B` leaves the previous branch's generated sources in place**; the stale `.cpp` meets the new submodule headers | clean-build after any base change |
| not scrubbing the base per track | `git submodule status` shows `+` entries — `checkout -B` does not move submodule working trees | the exact scrub below; anything less leaves stale generated headers |

Budget a clean build per track at ~8-10 min — a three-track propagation is roughly 30 minutes of
build time.

**The scrub, verbatim — copy it, do not paraphrase it:**

```bash
git -C "$W" submodule update --init --recursive --force
for d in hca_fwv_shared steering_ul hca_fw_core_platform; do
    [ -d "$W/$d" ] && git -C "$W/$d" clean -fdxq          # note: -C into the submodule
done
( cd "$W" && git clean -fdxq -- 'src/cmdif/include/autogen' 'autogen' )
[ "$(git -C "$W" submodule status --recursive | grep -c '^[+-]')" -eq 0 ] || exit 1
```

- **`git clean -fdx -- hca_fwv_shared/` does NOT clean that submodule.** `git clean` does not
  descend into a nested repository named by path; run it *inside*, with `git -C <submodule>`. The
  wrong form fails silently: it succeeds, cleans nothing, and ~8 minutes later the compiler reports
  hundreds of `... has not been declared` errors (a stale
  `hca_fwv_shared/autogen/enum2str/GlobalEnum2Str.h` against the new submodule's types) — again
  reading like a broken baseline.
- **The autogen paths are whitelisted on purpose** instead of cleaning the repo root: the working
  tree may hold other people's artifacts (`genid_dump`, `nvmf_dump`) that a blanket
  `git clean -fdx` would take out.

### One working tree serves every track

`git push` does not need a checkout — the branch only has to exist in `.git`:

```bash
git push origin fix_5273244_emuhost_ES:refs/for/FUR_2026_Jan_VR_Fractal_ES_from_48_0386
```

One borrowed working tree can serve every track in turn and be discarded afterwards; the private
branches survive it. Only the **build** needs a working tree. Do not stand up a long-lived worktree
per branch for propagation work.

### Naming the private branch — the track must be readable off the name

```
fix_<ticket>_<topic>_<track>          fix_5273244_emuhost_ES
                                      fix_5273244_emuhost_June
                                      fix_5273244_emuhost_master
xcheck_<ticket>_<what>                a branch for investigating, not for pushing
```

`<track>` is **copied out of the target branch name** — the one token that identifies it, and
nothing else. It is already in the `refs/for/<target>` you are about to type:

| target branch | `<track>` |
|---|---|
| `master` | `master` |
| `FUR_2026_Jan_VR_Fractal_ES_from_48_0386` | `ES` |
| `FUR_2026_June_PRDMA_CSP_main_from_48_1642` | `June` |
| `FUR_2026_Sep_PRDMA_CSP_08_from_48_6132` | `Sep` |

- **Do not invent abbreviations** (`prop-bf10-csp` / `prop-bf10-csp08`): `csp` vs `csp08` needs a
  mapping table kept in someone's head, and it breaks the day a third CSP branch is cut.
- **The token is not guaranteed unique — list the branches first, then pick it.** Two June
  branches have coexisted, separated only by the trailing baseline `48_<NNNN>`:

  ```
  FUR_2026_June_PRDMA_CSP_main_from_48_1642    active
  FUR_2026_June_PRDMA_CSP_main_from_48_6132    frozen, tip stopped 09-09
  ```

  One command, which doubles as the branch-name check:

  ```bash
  git ls-remote --heads origin | grep -oE 'FUR_[A-Za-z0-9_]+'
  ```

  Ambiguous month token → append the baseline (`June1642`). If one of the two is frozen, say so in
  the ledger rather than silently ignoring it. "Which branches does this fix belong on" is a
  separate question from naming; a frozen branch usually answers itself — check whether the recent
  fixes are on it (a branch missing the last two is not being maintained).
- **Do not name the branch after the shape of the fix** (`5285522_macro_shape`,
  `5285522_satpf_macro_guard`): that says which variant you tried, never which branch it lands on —
  and the landing branch is what you need with several in flight. Variants are what `git log` and
  gerrit patchsets are for; if two candidate approaches must coexist, they go in `<topic>`, with
  `<track>` still last.

## Pushing a stack of dependent changes

`git push origin <tip>:refs/for/<branch>` creates one change per commit and records the
parent/child dependency. That guarantees **order** (a child never merges before its parent) but
**not atomicity**: by default each change gets its own CI round and its own submission, so an
N-deep stack costs up to N CI rounds spread over days.

### Set the topics — mandatory

```bash
for c in <lower changes>; do
  ssh -p 12023 git-nbu.nvidia.com gerrit set-topic $c --topic IGNORE
done
ssh -p 12023 git-nbu.nvidia.com gerrit set-topic <top change> --topic RELATED_CHANGES
```

Setting a topic creates no patchset and outdates no vote. With the topics set, the whole stack goes
through **one CI round and merges the same day**; without them a 4-deep stack took 3 separate CI
rounds and 3 submissions over two days.

The CI runs `fw_automations/ci/utopx/scripts/check_for_related_changes.py` in a stage called
**`Related Changes Check`**, which fails the build unless:

- the top change's topic contains `RELATED_CHANGES` **and** every related change's topic contains
  `IGNORE`; or
- there are no related changes at all (the stack was rebased apart).

Its error text: *"Your change has related changes, but the topic in your top change doesn't
contain RELATED_CHANGES … if not please rebase and break the related changes chain"*.
Reference: `https://confluence.nvidia.com/display/FW/Setting+The+Gerrit+Topic`

Confirm an atomic submit: `submission_id` becomes `<topChangeNum>-RELATED_CHANGES`, and every
change in the stack carries that same id with an identical `submitted` timestamp.

### Habits that go with a stack

- **Collect every `+2` at once.** Voting does not merge anything; submission does, and submission
  respects the chain — approving a whole stack in one pass is safe.
- **Stop hand-editing the stack once votes are in.** When a parent merges, gerrit rebases the
  children automatically and copies votes whose copy condition allows it (`TRIVIAL_REBASE` keeps
  them, `REWORK` drops them). A manual rebase to resolve a conflict is a `REWORK` and costs every
  vote on the stack.
- **To see whether a project ever submits stacks atomically**, read `submission_id` on
  already-merged changes (the REST search returns it; the ssh `gerrit query` output does not).
  `<num>-<topic>` = atomic stack submit; `submission_id == the change's own number` = it went in
  alone.

## Related

- Re-running CI after a push → skill `utopx-ci-rerun` (CR+2 must be in place **before** a re-run).
- Driving the feature these changes belong to → skill `feature-delivery`.
