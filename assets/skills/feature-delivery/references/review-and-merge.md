# Review ecology, merge order, propagation

Read in Phase 5–6, while in review. Commit shaping is SKILL.md Phase 2; the two review rules that
hold everywhere (reviewer snippets, cross-layer consistency) are SKILL.md Phase 5.

## 1. Review ecology

### The formal reviewer is often not the reviewer

Check who is *writing comments*, not who holds the slot. The listed reviewer may vote early, see
the vote invalidated by the next patchset and go quiet, while nearly all of the review comes from
an engineer who is only **CC'd** — addressing the slot-holder is then addressing nobody.

Read bot comments as carefully as human ones: `svc-sw-hca-bot` raised both `⛔ Critical` findings on
PSF's FW side. Do not skim them because they are automated.

### `unresolved` is a conversation counter, not a defect counter

It includes your own replies and threads where you pushed back, and it moves in both directions —
it drops when the owner answers a batch and climbs back the same morning when the reviewer answers
those. Judge progress by **which** threads are open, never by the number.

### Read the review bookmark

Reviewers leave markers where they stopped mid-file — e.g. literally `***9.9 got here***` at a line
number. The rest of that file was **never reviewed**, which is very different from "reviewed and
fine". Look for one before assuming coverage.

## 2. Merge and after

### Order

**interface → implementation → gate** (SKILL.md Phase 3). A gate merged early exposes a half-built
path; a gate left unmerged means the feature is dead code and no lab run can exercise it.

Also check the FW/test-tool dependency: if the test tool consumes a capability the FW change
introduces, the FW change must land (and be in the FW image you burn) first. Record the coupling
in the ledger; it decides what can be tested when.

### Propagation

Cherry-picking to ES / master / GA branches: skill `gerrit-change` — the footer and Change-Id
rules, and pushing a dependent series atomically. Keep a propagation table in the ledger — which
change reached which branch, with the landed SHA per branch (looked up by Change-Id, SKILL.md
Phase 4). A zero-conflict cherry-pick does **not** mean it compiles there.

## 3. PSF instances (`ICM Page supplier: support global pool delegation`)

Concrete cases of the rules above, from the PSF feature:

- **Reviewer snippets adopted unverified** (SKILL.md Phase 5) shipped a bug on both sides:
  - utopx — a snippet assigned `BuildOp()`'s `UtopxOp*` straight into a `CmdManagePages*`. Does
    not compile (base → derived).
  - FW — a snippet OR-ed `HCA_STATE_INIT_HCA_DONE` (an `hca_state_t`, `0xff`) into a
    `CMDIF_MISSION_*` bitmask, setting bits 0–7 and marking unrelated missions complete.
- **Cross-layer mismatch** (SKILL.md Phase 5): `config/common_constraints.conf` defined
  `icm_mng_global_keeps.max_manage_pages_op_count`, while the adabe node and the code both used
  `manage_pages_op_count`. The `[1-6]` constraint silently never applied; `.Gen()` returned a
  default-range value, and a `0` would have tripped a `UFATAL` at runtime.
- **Abandoned cosmetic commit** (SKILL.md Phase 2): the `Relocate PSF pool helpers` cosmetic change
  was abandoned while the reviewer's move-only request was still open, leaving that request with
  nothing to satisfy it.
- **Req holes** (SKILL.md Phase 6), found by walking the FW↔utopx interface field by field after
  both sides had shipped code: `Req 4` ("device must not issue page-request events") had only an
  indirect relaxation on the utopx side and **no assertion on the capability bit**; `Req 5`
  (`fast_teardown` must be 1) had **no assertion at all**.
