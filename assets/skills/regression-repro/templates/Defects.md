# Redmine #<ticket#> — root cause and fix

> Last updated: <YYYY-MM-DD HH:MM CST>
> The failure, its root cause, the fix and its verification. Status: [Tracking.md §1](Tracking.md#<id of its §1 heading>). How it was
> found: [Ledger.md](Ledger.md). What goes to Redmine is written from this file, in English, under `redmine/`.

## 1. The failure

**Signature** (verbatim):

```text
<exact fatal / UFATAL / mismatch string>
```

**What goes wrong**: <2-4 plain sentences a reader new to this subsystem understands>

**Reported**: <who filed it, which nightly session — [session <id>](https://mars.nvidia.com/ui/view/monitor/Amonitor.php?session_id=<id>), [view_log](<the view_log.php URL from the ticket>)>

## 2. Where it happens

What decides whether the bug fires; the whole environment is in [Tracking.md §3](Tracking.md#<id of its §3 heading>).

| Item | Value |
|---|---|
| FW and test-tool version | <...> |
| Device, topology | <...> |
| NV knobs that arm it | <...> |
| Exposure condition | <what has to be true for it to fire> |
| Regression window (fsearch) | <first occurrence, sessions and setups affected, the suspect commit> |
| Local repro vs the ticket | <each argument dropped or added, each artifact that is not byte-identical to the ticket's, and why it does not matter> |

## 3. Root cause

<The accepted root cause, stated once: what the thing is, what it does wrong, and where
([<file>:<line>](<path>?v=<commit>#L<line>)). Name the commit and author when a change introduced it; say so when it is a latent
defect rather than a regression.>

**Evidence**: <source lines; attribution (`git blame` → commit, author, date); the deciding run,
`[Ledger.md Run log #<n>](Ledger.md#run-<n>)`>.

## 4. Rejected hypotheses

- <looked like …; ruled out by …> ([Ledger.md §<n>](Ledger.md#<id of entry n's heading>))

## 5. Fix

Repo and branch: <`golan_fw2` and/or `utopx2`; the private branch>. Gerrit: [<num>](<change URL>) PS<n>, or not pushed.

The patch, also in [FIX_<topic>.patch](patches/FIX_<topic>.patch):

```diff
<the patch>
```

**Why it fixes §3**: <each hunk tied back to the root cause>

**Deliberately not covered**: <sibling call sites or cases the pinned repro does not exercise>

**Rejected attempts**: <[REJECTED_<vN>_<why>.patch](patches/REJECTED_<vN>_<why>.patch) — why it failed>

## 6. Verification

| Run | Build | Seed | Signature present? | Ended how | Verdict |
|---|---|---|---|---|---|
| Original regression | <FW / tool pin> | <N> | yes | TEST FAILED | baseline |
| Local repro | <pin> | <N> | yes (same) | TEST FAILED | repro confirmed |
| Control (patch removed) | <pin> | <N> | <yes / no> | <...> | <...> |
| Patched | <pin> | <N> | <no> | <...> | <VERIFIED / VOID> |

Logs: [<repro log>](logs/<file>), [<control log>](logs/<file>), [<patched log>](logs/<file>). Images, in
[fw/](fw/): control `<md5>`, patched `<md5>`. Adjacent cases run: <what else ran to catch a regression the fix introduces>. Verdict:
`<VERIFIED | VOID — reason | NOT REPRODUCED | PARTIAL>`.

## 7. Next steps

- Questions for the code owner: <...>
- Follow-up tickets: <sibling cases sharing the defect>
- Back-port range: first affected release <tag>; <n> releases; active lines hit: <...>; <whether carrying the defect
  means failing>
