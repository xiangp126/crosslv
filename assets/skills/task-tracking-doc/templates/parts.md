# Parts library — assembled into the body of TRACKING.md

The skeleton (`TRACKING.md`) is mandatory; the body is built from these parts. **Parts can be
fitted mid-task**: when the shape of the work changes, fit a new part — never start a new file.
Each part gives: when to fit it · its skeleton · a filled real sample where one exists. Copy
skeletons and samples as they are.

## A Main ledger table

**Fit when**: N independently advancing objects (commits / tickets / experiments); one row each.

The status column is a **micro-narrative**: chain dozens of facts with `·` (ticket numbers, PS,
SHA, CI numbers, session id, caveats) — it may run to thousands of characters. Do not split it
into more columns or tables; split, it must be read across columns.

```markdown
| Object | Content | Landed on | Status |
|---|---|---|---|
| <bare full URL of the change / ticket> | **<ID>** `<type>` <one sentence> | <branch/SHA> | <status narrative> |
```

Sample (status cell, excerpt):

> 🔵 **Pushed, waiting for review + CI** · Change-Id `Ib53f8d9…` shared by all four tracks · `src/hca/HcaCaps.cpp` **+6 −3** ·
> landed: **ES** https://git-nbu.nvidia.com/r/c/fw_ver/utopx/+/1505386 `bc3932816a` PS7 ✅ **MERGED 09-16 13:44 UTC** ·
> **master** https://git-nbu.nvidia.com/r/c/fw_ver/utopx/+/1506075 `e0f1638f17` PS6 ✅ **MERGED 09-17 00:52 UTC** ·
> **review**: Yan gave +2 on PS5, then immediately **retracted it with CR-2**; on PS6 gave **CR-1** with an inline comment asking for a rename; +2 as soon as PS7 fixed it

## B Alignment matrix

**Fit when**: N objects × M channels, and a missing cell must show at a glance.

**The heading must declare "measured, not copied from the table above", and the criterion must be
written down.** A matrix copied from the main table goes wrong together with it; a fixed criterion
forces a re-check every time.

```markdown
### ★ <N>-track alignment matrix (<date>, measured — not copied from the table above)

Criterion: <Change-Id hit / exact subject match / code content>, cross-checked and consistent.

| | <channel 1> | <channel 2> | <channel 3> | <identifier> |
|---|---|---|---|---|
| **<object>** | `<SHA>` | `<SHA>` | ⬜ not needed | `<Change-Id>` |
```

Sample row: `| **BF3** hotplug host-awareness | \`aec0f69672\` | ⬜ not needed | ⬜ not needed | \`I368c2063b52dd…\` |`

The table's value is the ⬜ / ❌ distinction: **⬜ = not needed (with a reason)**, ❌ = missing
(must be fixed).

## C Evidence table / criteria table ★

**Fit when**: arguing an attribution, a root cause, or that something does not exist. **A control
row is mandatory**: a zero without a control is a false negative, not evidence
(`references/update-discipline.md` §1).

```markdown
**<N>-criterion evidence (<date>), conclusions agree:**

| Criterion | <object 1> | <object 2> | <object 3> |
|---|---|---|---|
| <criterion 1> | <value> | — | — |
| <criterion 2: code content> | 1 hit | **0** | **0** |
| **Control: <something known to exist> (proves the query works)** | 10 hits | 8 hits | 8 hits |

The control row is mandatory: <explain why the zero is real and not a false negative from a wrong path>.
```

Two companion tables:

```markdown
| Allegation | Ruling |          ← answer external challenges point by point
| Hypothesis | Conclusion |     ← hypotheses you raised and eliminated, each with a measurement
```

## D Timeline table

**Fit when**: the order of events must be proven (who came first decides attribution), or the
work spans time zones.

```markdown
| Event | <their local time> | <our local time> | Source |
|---|---|---|---|
```

Across time zones, **write both columns side by side** and note the conversion direction under
the table — never convert in your head.

Mail / message timelines: `| Time | Sender | Key points |`; in Key points **quote the original
and bold the key sentence**, never paraphrase.

## E CI / test-run round table

**Fit when**: the same thing runs repeatedly and you must see which round passed and where each
one died.

```markdown
| Round | build / job number | Where it died | Verdict |
|---|---|---|---|
| 1 | https://<jenkins>/job/<job>/24368/ | <stage> | **not ours** (<reason>) |
```

The Verdict column takes exactly three values: **ours** / **not ours** / **undecided**. Undecided
is written as undecided, never fudged.

## F Experiment / seed matrix

**Fit when**: parameter sweep, seed re-verification, A/B. One row per config; the columns are the
successive gates; **the last column `VERDICT` closes the row**.

```markdown
| seed | Ruling | Iterations | <gate 1> | <gate 2> | VERDICT |
|---|---|---|---|---|---|
```

A/B: `| Seed | A (as is) | B (with change) | Divergence point |` — **A/B must change exactly one
variable**; with more than one difference it is not an A/B.

## G Status board row

**Part of the skeleton** (mandatory); only the row format is given here:

```markdown
| S3 | <milestone> | 🔵 in progress | 09-17 14:30 | waiting for CI #24950; next: push CSP 0.8 once green |
```

Status values: `✅` / `🟡` / `🔵` / `⬜` / `❌` only. The "Key artifact / current blocker" column
holds a path or a one-line blocker, never mood.

## H Numbered problem entries

**Fit when**: environment setup / bring-up / porting — problems keep surfacing. Open the log with
its recording convention:

```markdown
**Recording convention**: append an entry the moment a problem appears; once it is solved, update that entry in place (no new file, no deleted conclusions).
Every entry has: Symptom / Location / Action / Result. Script-level fixes always go into the script itself, never worked around with manual commands.
```

```markdown
## #<N> <one-line symptom> <✅ solved | 🟡 pending disposition | ⚠ my earlier conclusion was wrong>

**Symptom**: <paste the error verbatim, do not paraphrase>

**Location**: <code/config location file:line, and how it was found>

**Action**: <what was done>

**Result**: <how it was verified + conclusion>
```

Sample heading: `## #1 Chip mislabelled as ARGAMAN, actually BRONCO ✅ solved`

- The four sections are fixed; one missing means the problem is not run down. Paste the symptom
  verbatim, never paraphrase.
- When solved, **update the entry in place**; do not open a new one.
- When a later finding overturns an entry, the new entry states "overturns #N" and the old one
  stays; numbers are never reused.

## I Archive fold

**Fit when**: voided items start taking up the view.

```markdown
<details>
<summary>Voided / abandoned (<N> items, kept for reference)</summary>

| ~~Object~~ | ~~Content~~ | Voided at | Why it could be voided |
|---|---|---|---|

</details>
```

Write "voided" here only in the same batch as the abandon in the live system (`SKILL.md` §6).

## J Retraction / correction patterns ★★

The most distinctive part of the format. **Never delete the old conclusion.**

### J1 Retraction block — the whole conclusion is overturned and was already stated externally

```markdown
#### <original title> — ⚠️ **<date> conclusion retracted, reopened**

> ## ⚠️ Retraction (<date>, self-audit after <who> challenged it)
>
> **This section's earlier "<old conclusion>" is void.** <challenger>'s words:
> *"<verbatim quote>"* — the challenge stands.
>
> **My earlier review was incomplete**: <what was not checked>. In fact:
>
> | <dimension> | <scope> | Did I review it then? |
> |---|---|---|
> | `<file>` | +25 −2 | ✅ reviewed |
> | `<file>` | **40 lines** | ❌ **not a single line read** |
>
> **<what the re-check found>**, see "<new section>" below. **Until further evidence is in,
> do not use "<old conclusion>" in any external reply.**
```

Three required elements: **quote the challenger verbatim** · **self-audit table** (list honestly
what was missed) · **freeze external use of the conclusion**. Follow it immediately with
`##### Facts that still hold (unaffected by the retraction)`, separating what is retracted from
what still holds, and state that **they are different propositions**.

### J2 Whole section voided (kept on file)

```markdown
##### ~~<original title>~~ (<date>, overturned by §<X>)

> ⚠⚠ **This section's conclusion is void; it is kept only to remember why it went wrong.** <what was wrong + what the truth is>.
> The tracing of <some part> below still holds; only the final attribution step was wrong.
>
> **Lesson**: <one sentence> Criterion: <how to check next time>.
```

All four must be answered: **which part still holds** / **why it went wrong** / **lesson** /
**criterion for next time**.

### J3 Numbered self-correction (several at once)

```markdown
#### ⚠ <N> self-corrections this round (all false negatives / over-reading)

1. **<wrong claim>.** <evidence> — I once said "<original words>"; **withdrawn**.
2. **<wrong claim>.** <mechanism> The zero hits were a false negative.
```

### J4 In-table correction + lesson promoted to a general criterion

```markdown
> ⚠ **<date> Correction: <which table>, <which version> was wrong.**
> The cause was **<a method flaw>**: <specifics>. Switching to <correct criterion> made it match; <third criterion> cross-confirmed it.
>
> **Lesson: <this lesson written as a general criterion that applies directly next time>.**
```

The most valuable form: it turns a one-off mistake into a reusable criterion.

### J5 Repeat-offence record

```markdown
### <N> Lesson (time no. <N>)

§<X> was <the first form>; this section is <this form>.
**Whenever <trigger>, first <the check to run>, only then <conclusion>.**
```

Create it the second time the same trap is hit — repetition made visible beats hidden.

## K Proposed disposition (not executed)

**Fit when**: the diagnosis is done but the disposition is not yours to decide. What needs an
order first: `SKILL.md` §6.

```markdown
#### Proposed disposition (not executed, awaiting instruction)

| Option | Cost | Risk |
|---|---|---|

**Recommended**: <which one + one-line reason>
```
