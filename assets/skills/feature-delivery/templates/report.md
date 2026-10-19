# <Feature name> — test report <MMDD>, <box>, `<test-tool tree sha>`

> <date and time range>. Written once and not edited afterwards; later corrections go into `Tracking.md` or a new
> report.

## 1. Conclusion

- <n of m runs PASS>; the <k> failures: <attribution of each — a pre-existing issue with its regression-DB hit, or a
  new defect #n>.
- What the new path did in every passing run: <the feature's fingerprints, e.g. range sizes, order of FLRs, kernel
  IOMMU errors>.
- What this campaign proves, and what it does not.

## 2. Setup

| Item | Value |
|---|---|
| Box | <name, model, kernel, IOMMU> |
| Card | <part number, PSID, device> |
| FW | <version; base + changes; image md5> |
| INI and NV | <INI path; NV recipe> |
| Test tool | <worktree, tree SHA, binary and library md5> |
| Driver | <udriver version> |
| Run parameters | <conf, iterations, operations, -e args> |

## 3. Runs

| # | Seed | Result | <fingerprint 1> | <fingerprint 2> | Kernel errors | Log |
|---|---|---|---|---|---|---|
| R1 | <seed> | <PASS / FAIL> | <...> | <...> | <0> | `<log base>` |

## 4. Failures

| # | Where it stopped | Verbatim failure | Attribution |
|---|---|---|---|
| R<k> | <operation, function, file:line> | `<FATAL line>` | <pre-existing: setup and date of the same failure in the regression DB / new defect #n> |

## 5. Not covered

- <paths the campaign did not reach, and why>

## 6. Environment problems met

- <problem, how it showed, how it was handled>
