# Commit shaping, review ecology, merge order

Read this in Phase 2 (before writing code) and Phase 5–6 (while in review). Every case below is
from a real feature review round.

## 1. Shaping the commits

### Interface first, logic second

PRM / adabe struct changes are their own change and land early. The logic change then rebases
onto a merged interface instead of carrying it.

> PSF: the adabe/PRM change merged 2026-08-06. The logic change built on it was still in review
> six weeks later. Had they been one change, nothing would have landed.

### A pure code-move needs its own cosmetic commit

A diff that both **moves** a function and **changes** it is unreviewable, and a reviewer will say
so and stop:

> *"please create cosmetic commit that just move the function then we can review the diff"*

Two ways this goes wrong:

- you never split it — review stalls indefinitely on the largest file;
- you split it, then **abandon the cosmetic commit** while the request is still open, leaving the
  requirement dangling. (PSF did exactly this: the `Relocate PSF pool helpers` cosmetic change was
  abandoned, and the reviewer's request stayed unresolved with nothing left to satisfy it.)

If you abandon a change that was created to satisfy review feedback, say so in that comment
thread the same day.

### The enabling gate is the last commit

See SKILL.md Phase 3. Merge order is **interface → implementation → gate**.

### Fold when asked

A reviewer asking you to merge two changes into one is telling you the split failed. PSF's owner
did it within four hours: folded the follow-up change into the base one, abandoned the follow-up,
uploaded two patchsets the same afternoon. That is the right speed.

## 2. Review ecology

### The formal reviewer is often not the reviewer

Check who is *writing comments*, not who holds the slot.

> PSF, utopx side: the listed reviewer voted `-1` three times early, gave a `+1` that was
> invalidated by the next patchset, and then went quiet. Nearly all subsequent review came from an
> engineer who was only **CC'd**. Addressing the slot-holder would have been addressing nobody.
>
> PSF, FW side: three human reviewers plus `svc-sw-hca-bot`, and **the bot raised both `⛔
> Critical` findings**. Do not skim bot comments because they are automated.

### `unresolved` is a conversation counter, not a defect counter

It includes your own replies and threads where you pushed back. It moves in both directions: on
PSF it went 23 → 8 when the owner answered a batch, then back to 17 the same morning when the
reviewer answered those. Judge progress by **which** threads are open, never by the number.

### Read the review bookmark

Reviewers leave markers when they stop mid-file — PSF's reviewer left literally `***9.9 got
here***` at a line number. That tells you the rest of the file was **never reviewed**, which is
very different from "reviewed and fine". Look for it before assuming coverage.

### Never adopt a reviewer's code snippet unverified

Reviewers paste suggested code into comments; owners paste it into the patch. Compile it, or at
minimum grep the symbol's definition, first.

> Both sides of PSF carried a bug of exactly this origin:
> - utopx — a reviewer's snippet assigned `BuildOp()`'s `UtopxOp*` straight into a
>   `CmdManagePages*`. Does not compile (base → derived).
> - FW — a reviewer's snippet OR-ed `HCA_STATE_INIT_HCA_DONE` (an `hca_state_t`, `0xff`) into a
>   `CMDIF_MISSION_*` bitmask, setting bits 0–7 and marking unrelated missions complete.

When you report such a defect, **name its origin**. Otherwise it reads as the owner being sloppy,
and the reviewer repeats the suggestion.

### Cross-layer consistency is nobody's job unless you take it

A config key, the adabe node it binds to, and the code reading it must agree. Nothing enforces
this — not the compiler, not CI, not review.

> PSF: `config/common_constraints.conf` defined `icm_mng_global_keeps.max_manage_pages_op_count`,
> while the adabe node and the code both used `manage_pages_op_count`. The `[1-6]` constraint
> silently never applied; `.Gen()` returned a default-range value, and a `0` would have tripped a
> `UFATAL` at runtime. Both owner and reviewer had argued *about the name* in review without
> noticing the two sides did not match.

Check all three layers by grep whenever you add or rename a constrained field.

## 3. Merge and after

### Order

**interface → implementation → gate.** A gate merged early exposes a half-built path; a gate left
unmerged means the feature is dead code and no lab run can exercise it.

Also check the FW/test-tool dependency: if the test tool consumes a capability the FW change
introduces, the FW change must land (and be in the FW image you burn) first. Record the coupling
in the ledger; it decides what can be tested when.

### The landed SHA is not the pushed SHA

Changes are rebased on submit, so record the SHA **on the branch** — looked up by Change-Id
(command in SKILL.md Phase 4), never by subject. Subjects get edited during review; Change-Ids
do not.

### Propagation

Cherry-picking to ES / master / GA branches: skill `gerrit-change` — it covers the footer and
Change-Id rules as well as pushing a dependent series atomically. Keep a propagation table in
the ledger — which change reached which branch, with the landed SHA per branch. Zero-conflict
cherry-pick does **not** mean it compiles there.

### Then verify the Req list

SKILL.md Phase 6. Code on both sides is not verification; only an assertion that can fail is.
