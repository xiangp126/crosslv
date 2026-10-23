# <Feature name> — defects and fixes

> Last updated: <YYYY-MM-DD HH:MM CST>
> One section per defect, in the order a run from the starting baseline hits them (the reproduction ladder in §0). The current status of each defect is in [Tracking.md §3](Tracking.md#<id of its §3 heading>), not here.

## 0. Reproduction ladder

| Step | Code under test | Run parameters | Hits | Where it stops |
|---|---|---|---|---|
| <k> | <change + local commits, SHA> | <seed, -e args> | #<n> | [<file>:<line>](<path>?v=<commit>#L<line>) / <command> |

## 1. Defects in ladder order

### #<n> <one line: what goes wrong, in plain words>

**Side**: <test-tool change / FW change / udriver / existing code> · **Fix**: [<num>](<change URL>), or local commit `<sha>` ([Local-Only]), or none yet

**How to hit it**: ladder step <k> (<seed, parameters>).

**What happens** (verbatim):

```text
<FATAL / syndrome / kernel lines exactly as logged>
```

**Root cause**: <plain explanation, starting with what the thing is>; [<file>:<line>](<path>?v=<commit>#L<line>).

**Fix**:

```diff
<final diff>
```

Why it works: <...>. Deliberately not covered: <...>.

**Rejected alternatives**:

| Alternative | Change | Why rejected |
|---|---|---|
| <...> | <diff, or one line> | <...> |

**Evidence**: <runs before and after, the control run; log paths>.

**Open questions**: <question — for whom>.

## 2. Defects no longer seen

<Same layout. The Fix line says what removed it: an upstream patchset, another fix, a new FW.>

## 3. FW-side issues

<Same layout, or a short entry with a link when the issue is only a question for the FW owner.>

## 4. Pre-existing issues

Met during the runs, not caused by this feature.

| Where it stopped | Verbatim failure | Same failure in the regression DB | Handling |
|---|---|---|---|
| <...> | `<FATAL line>` | <setup, FW, date> | <seed excluded> |

## Appendix A. Concepts needed to read this document

<Short explanations of the mechanisms the sections above rely on.>
