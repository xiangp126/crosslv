# <Feature name> — ledger

> Every device run and the step-by-step record of the work. Status and progress are in [Tracking.md](Tracking.md).
> Rows and entries are only appended: a row at the end of the Run log, an entry at the end of the file. A conclusion that
> turns out wrong is struck through in place, followed by the correction, its date and the criterion to use next time.

## Run log

| # | Date | Box | FW | Test-tool tree (patch when uncommitted), binary md5 | Seed, arguments | Verdict | Log |
|---|---|---|---|---|---|---|---|
| <a id="run-1"></a>1 | <MM-DD HH:MM> | <box> | <version; image md5> | `<sha>` + [<log stamp>.diff](patches/<log stamp>.diff), `<md5>` | <seed; -e args> | <NEW PATH EXERCISED / OLD PATH ONLY / RUN VOID / ...; rc> | [<log file>](<relative path>) |

## <N>. <short title: what happened, a few words>

<YYYY-MM-DD HH:MM CST> — <what was asked or what happened, stated as a conclusion>

<Peter's instruction verbatim, in quotes, when the entry starts from one>

- **Did**: <commands; SHAs with their kind (local / patchset revision / landed); build result (rc, `error:` count,
  elapsed, the log as a link); push (the change as `[<num>](<URL>)`, new patchset, what the server echoed); CI (`[<job> #<build>](<URL>)`, failed stage, MARS
  session id and archive path); runs as `[Run log #<n>](#run-<n>)`>
- **Result**: <outcome and evidence paths; the control it was compared with>
- **Next**: <one line>
