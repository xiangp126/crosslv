# Update discipline — evidence rules

The update contract (events, companions, backstop) is `SKILL.md` §4; the writing and meta rules
are `SKILL.md` §6. This file holds the bar a conclusion must clear: **a record is not a proof.**

## 1. Every conclusion points at a control

Zero hits are not evidence unless a control **known to exist** was queried the same way and found.
A broken query returns zero for everything — e.g. a stale failure-DB tool path (DB held no data)
returned no rows for `--errlike "0xac5816"` and none for a control keyword known to have many
records.

Put the control in the table:

```markdown
| **Control: <something known to exist> (proves the query works)** | 10 hits | 8 hits | 8 hits |
```

## 2. Run at least two criteria; when they disagree, the lowest-level one wins

"Is change X on branch Y" — three criteria, weakest first:

1. identifier (Change-Id and the like) — **weakest**, may be replaced during propagation
2. title / subject — medium, may be reworded
3. **code content** — strongest, content does not lie

Never conclude absence from the identifier alone: propagated copies can carry a different
Change-Id, so a Change-Id-only search reports "only on master" for a change that the subject
criterion finds on every branch.

`git merge-base --is-ancestor <hash> <branch>` never works across cherry-picked branches —
propagation changes the hash.

## 3. Not disproved ≠ established

Finding no counter-example only means none was found. Until there is positive evidence, mark the
conclusion `🟡 unproven` and **do not use it in any external reply**.

## 4. Attribution needs content evidence and timeline evidence

- Content: does the code path actually pass through our change?
- Timeline: when did the failure first appear vs when did the change land?

Trap: **the failure DB's retention window fakes a "first appearance"**. Before trusting "appears
since day X", confirm X lies inside the retention window; otherwise X is only the window edge.

## 5. Elimination: write down every hypothesis with a measurement

```markdown
| Hypothesis | Conclusion |
|---|---|
| <hypothesis 1> | ❌ **disproved** — <measured evidence> |
```

Disproved hypotheses **stay in the table** — the next reader (or your next session) will think of
the same hypothesis, and the row saves re-testing it.
