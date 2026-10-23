# Redmine #<ticket#> — ledger

> Every run and the step-by-step record of the work on [<ticket#>](https://redmine.nvidia.com/issues/<ticket#>). Status: [Tracking.md](Tracking.md).
> Rows and entries are only appended: a row at the end of the Run log, an entry at the end of the file. A conclusion
> that turns out wrong is struck through in place, followed by the correction, its date and the criterion to use next time.

## Run log

| # | Date | Box | FW / tool pin (patch when uncommitted) | Seed | Signature | Ended how | Log |
|---|---|---|---|---|---|---|---|
| <a id="run-1"></a>1 | <MM-DD HH:MM> | <box> | <version / sha> + [<log stamp>.diff](patches/<log stamp>.diff) | <seed> | <same / diverged / none> | <TEST FAILED / PASSED / VOID> | [<log file>](<relative path>) |

## 1. <short title: what happened, a few words>

<YYYY-MM-DD HH:MM CST> — <what was asked or found, stated as a conclusion>

<Peter's instruction verbatim, in quotes, when the entry starts from one>

- **Did**: <source read ([<file>:<line>](<path>?v=<commit>#L<line>)); commands; build (rc, `error:` count,
  image md5, log path); runs as `[Run log #<n>](#run-<n>)`>
- **Result**: <the finding and its evidence — `git blame` / `git log --author` attribution, the
  verbatim signature, log paths; verdict: confirmed / refuted / open>
- **Next**: <one line>
