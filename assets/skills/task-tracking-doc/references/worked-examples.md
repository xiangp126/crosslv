# Worked examples — patterns from the source documents

The format was distilled from these documents (written in Chinese). Every reusable fragment is
given in English below or in `templates/parts.md`; there is no need to open the originals.

| Document | Shape | Its patterns live in |
|---|---|---|
| `OCI_EMU/TRACKING.md` (formerly `branch_propagation_ledger.md`) | N commits × M branches propagation ledger | the skeleton; parts A, B, J1; §1 below |
| `OCI_EMU/bf4_bringup_log.md` | environment bring-up, problems keep surfacing | part H |
| `OCI_EMU/mars_regression_delegation_gap.md` | analysis document turned long-lived | §2, §3 below |
| `5257991_dbcq_cap/ROOTCAUSE_AND_FIX.md` | root-cause write-up whose conclusions were overturned | §4 below |

A linear task with milestones needs no example: `templates/TRACKING.md` is that shape — the
`S0..Sn` status board as the index of the whole file, plus a decidable definition of done.

## 1. Multi-object ledger layout

`# ★ Ledger (by branch)` with one section per branch, ACTIVE rows first, voided ones folded →
`## 1.x` procedures and hard rules (inserted as `1.5` / `1.6`) → `## 3 – 4.27` one section per
event, each heading a conclusion:
`## 4.14 <job number> fails at the same spot again — attribution: **not ours**, but blocks the branch (0805)`.

Its `## 7 / 7bis / 7ter / 7quater / 7quinquies / 7sexies / 7septies / 7octies` sections predate
the no-latin-ordinals rule — not an example; write `7a` / `7b`.

## 2. Four-element header for an analysis document

```markdown
**Date**: … **Trigger**: … **Conclusion**: … **Method**: …
```

## 3. Correction chain in the numbering

Strike the overturned section's title and point forward; the correction and the final verdict
take the next letters:

`## 16.4b ~~<original title>~~ ← overturned, see §16.4c` → `## 16.4c [Corrected] …` → `## 16.4d [Final] …`

## 4. Errata first

When conclusions in a long document have been overturned, make the first section

`## 0. ⚠ Read this first: three conclusions in this document were overturned by later investigation`

— errata up front, not scattered through the sections for readers to stumble on. The longer the
document, the more this pays.
