# <task name> — task tracking

<One sentence on what this task is for.> Created <YYYY-MM-DD>; **kept current** (updated in place, never start a new file).
Assumes a reader with zero context on the task; <kind of detail> is in `<sub-document>.md` in the same directory.

**Last updated: <YYYY-MM-DD>**

---

<!-- N objects x M channels only (commits x branches and the like): the per-channel ledger,
     templates/parts.md part L, goes here, above the status board. Otherwise delete this comment. -->

## Status board

> Index of the whole file. **Must fit on one screen** — details go into the body below, never into this table.
> Update it at the close of every session; that is the session's last action.

| # | Milestone | Status | Time | Key artifact / current blocker |
|---|---|---|---|---|
| S0 | Create this document | ✅ | <MM-DD HH:MM> | this file |
| S1 | <first milestone> | 🔵 in progress | <MM-DD> | <artifact path / what it is waiting for> |
| S2 | <...> | 🔵 not started | — | — |

**Currently in flight**: <one line: where it is stuck right now and what the next step is. When interrupted, this line matters more than a complete narrative.>

---

## Definition of done

<Under what conditions this task counts as done. Write decidable sentences, not "do it well".>

**Key decisions locked**

1. <decision + who made the call + date>
2. <...>

---

## Constants

| Item | Value |
|---|---|
| repo | `<ssh://... or local path>` |
| <code review> web prefix | `<https://.../+/>` (always write a change as its bare full URL: prefix + change number) |
| CI job | `<https://.../job/<job>/>` |
| worktree / working directory | `<path>` |
| machine | `<hostname>` (<model / purpose>) |
| log archive | `<task dir>/logs/` |

---

## ⚠ Update discipline — do not wait to be reminded

**Updating this file is the last step of every action, not a later catch-up.** An action = execute + record;
**an unrecorded action counts as not done** — do not move to the next one.

For the events below, **update the moment they happen, in the same batch as the action** — do not save them up, do not wait to be asked:

| Event | Minimum to record |
|---|---|
| a long command / build finishes | SUCCESS/FAILED, elapsed time, `error:` count, archived log path |
| push completed | change number, new patchset number, the server's `new:`/`updated:` echo |
| CI verdict | build number, the stage it failed in, downstream job numbers, **session id** |
| merge / delivery landed | time, **the real SHA after landing** (merges are often rebased, so it differs from what was pushed) |
| review comment received / cleared | who raised it, which file and line, how it was fixed |
| experiment result | config / seed / **control group** / VERDICT |
| **any judgement overturned** | write "⚠ Correction" in place, **do not delete the old conclusion** — keeping it is how you know why it went wrong |
| session interrupted | the in-flight item + one sentence on the next step |

If this file has a per-channel ledger at the top, push / CI verdict / merge also update that object's row there.

**Two companion rules**

- **Archive the log before stating a conclusion.** CI consoles (one to two weeks) and the failure DB (~8 days) expire, and once expired
  they are gone for good (MARS session archives are kept for months, but the MARS API forgets a session after about two weeks). Capture into `logs/` and copy the job numbers, session id and archive path into this file.
- **Write identifiers in full and say which kind they are.** The "local SHA before push" and the "SHA on the branch after merge" often differ;
  mixing them up ends in "no such commit".

---

## Writing conventions

**Ordering**: within each section **ACTIVE items come first**; voided ones go into a fold — kept on file, out of sight.

**Greying out**: `~~strikethrough~~` = **void but kept on file**, strictly distinct from deletion.
**Results are not greyed out** — merged / passed is an outcome, not a retraction; just mark it in the table.

**Status markers: three independent axes — do not mix them**

| Axis | Markers and meaning |
|---|---|
| Progress | `✅` done · `🟡` partly done · `🔵` in flight / waiting on others · `⬜` **not applicable** (≠ missed) |
| Risk and disproof | `⚠` warning / correction · `🔴` the single current blocker (at most one row) · `❌` negated / disproved |
| Importance | `★` × 1–7, more = more important |

**Numbering only grows, never renumbered**: insert as `1.5` / `4.16` / `7a` / `7b` (no latin ordinals),
so an old reference like `see §<n>.<m>` never breaks.

**Name the file when citing another document**: `see §<n>.<m>` reads as "§<n>.<m> of this file";
across documents always write `` see `<file>.md` §<n>.<m> ``.

**Links**: `http(s)` external resources (code review / CI / tickets / log systems) are **always bare full URLs, never behind a markdown label,
table cells included**; **local file paths go in bare backticks** — never wrapped in a markdown link (wrapped, they no longer open).

**Headings are conclusions**: `## <number> [<date>] <conclusion> — <attribution verdict> ★`; never contentless headings such as "Analysis" or "Investigation".

**Distrust this file itself**: patchset numbers and branch tips recorded here are **snapshots from the moment of writing** and go stale.
Re-query the live system before acting.

---

## Sibling documents

| Document | Content | When to read it |
|---|---|---|
| `<sub-document>.md` | <content> | <when it is needed> |

---

<!-- ↓↓↓ Body: assemble parts from the skill's templates/parts.md as needed ↓↓↓ -->

## 1. <first body section>
