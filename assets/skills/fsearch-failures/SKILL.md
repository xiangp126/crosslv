---
name: fsearch-failures
description: Query the regression failure database (MARS analytics / fsearch) to answer "how often does this failure happen, on which machines, under which FW and utopx commit" — the main tool for attributing a regression to a commit. Covers the 2026-09 move to a new path + Python 3.8, and the three traps that silently produce the opposite conclusion. Run it FIRST when reproducing a regression or root-causing a CI/DoA/MARS failure, before allocating a box. Use when asked whether a failure is new, how many times it occurred, on how many setups, whether our commit caused it, when doing an A/B attribution over regression history, or when a regression repro or root-cause investigation starts.
---

# fsearch — the regression failure database

> **Failure triage is a three-skill chain — know which leg you are on.**
>
> | Leg | Question it answers | Skill |
> |---|---|---|
> | 1 | *Did anything fail last night, and where?* | `regression-report-mail` (Outlook) |
> | 2 | *Is this failure new? how many setups? which commit introduced it?* | `fsearch-failures` (failure DB) |
> | 3 | *What exactly happened in that one run?* | `ci-forensics` (Jenkins → MARS log) |
>
> Going 1→2→3 costs minutes and often ends the investigation at leg 2. Jumping straight to leg 3
> gets you one log with no idea whether it is a one-off or a month-old epidemic.

It is a CLI over the MARS analytics DB. One row per **failure occurrence**, with the
setup, FW version, **utopx commit**, failure text and timestamp. This is the tool for
*attribution* questions ("is this ours? since when? how often?"), not for reading one
run's log — that is skill `ci-forensics`.

## Call it

```bash
python3.8 /auto/sw/work/hca_fw/projects/mars_analytics/search.py --errlike "0xac5816"
```

First time on a machine, install deps **without touching system python**:

```bash
python3.8 -m pip install --user \
    -r /auto/sw/work/hca_fw/projects/mars_analytics/requirements.txt
```

(The team's official line is `sudo python3.8 -m pip install -r …`; `--user` works and is
the right choice from an AI session.)

The interactive `fsearch` alias points at the same script but **is not available in Bash
tool calls** — always write the full path. If a human's alias is broken:
`source /mswg/projects/fw/fw_ver/hca_fw_tools/.fwvalias && refreshalias`, then
`type fsearch` must print
`sudo python3.8 /auto/sw/work/hca_fw/projects/mars_analytics/search.py`.

## 🔴 Three traps — each one silently flips the conclusion

### 1. The old path is dead and answers every query with "No records found"

| | path | |
|---|---|---|
| **use this** | `/auto/sw/work/hca_fw/projects/mars_analytics/search.py` | live |
| ~~never~~ | ~~`/mswg/projects/fw/fw_ver/mars_analytics/search.py`~~ | frozen 2026-05-31, **always empty** |

It does not error. It returns `No records found.` in ~1.8 s for *anything*.
On 2026-09-17 this produced a confident "that failure does not exist in regression
history" — wrong. **Always run a control query with a term you know exists**; if the
control is also empty, the tool is broken, not the data.

### 2. The DB only holds the last ~8 days

Measured 2026-09-17: across **every** setup (MUSTANG, BRONCO, TAMAR, cx9) the earliest
row in the whole database was 2026-09-10.

⇒ **"First seen on <date>" is meaningless unless that date is well inside the window.**
It is usually just the retention edge. A commit that landed three weeks ago cannot be
A/B'd with fsearch at all — the "before" side does not exist. Same limit kills MARS
archives (~12 days). For a real before/after you need a local device run of the two
builds.

### 3. `--datefrom` / `--dateto` are accepted and ignored

`--datefrom 2026-08-01 --dateto 2026-08-31` and `--datefrom 2026-09-16` return the *same*
rows. No error, no warning. **Filter on the timestamp column of the output yourself.**

> ⚠ The old "a real query takes 70–90 s, an instant return is a false negative" rule is
> **obsolete** — Fsearch2 is far faster (32 rows in 5.8 s). Judge by the control query,
> never by elapsed time.

## Flags

```
--errlike --errexact --erregex        failure text (errlike is the workhorse)
--setuplike --setupnotlike            by machine / setup
--session                             by MARS session_id
--branchlike --branchexact --branchnotlike
--fwlike --fwexact --devices
--testlike --testexact
--fdlike --fdexact --fdregex          failure-details column
--callralike --callraexact --callraregex
--limit --sort --cols --count --countper --grep
--today --yesterday --regcycle --nodoa --nomr --db --sendto
```

`--limit` truncates by default — pass something large when you want the full set.

## The attribution workflow

```bash
S=/auto/sw/work/hca_fw/projects/mars_analytics/search.py

# 1. does it exist at all — plus a control
python3.8 $S --errlike "<signature>"
python3.8 $S --errlike "<something you know occurs>"       # control, MUST be non-empty

# 2. spread: one machine or many? one branch or all?
python3.8 $S --errlike "<signature>" --limit 100000 > /tmp/f.txt
grep -oE '[A-Z]+_FW-[a-z0-9-]+[a-zA-Z_]*' /tmp/f.txt | sort | uniq -c
grep -oE '2026-[0-9]{2}-[0-9]{2}'          /tmp/f.txt | sort | uniq -c

# 3. the useful column: the utopx commit — take it straight to git
git -C <worktree> merge-base --is-ancestor <our-commit> <commit-from-fsearch> \
    && echo "that run contained our change"
```

**A failure confined to one setup is a machine/config signal, not a code signal** —
check that before blaming a commit. Conversely a failure across many setups and branches
that starts at a known landing date is the strong form of attribution — but see trap 2
before believing any "starts at".

## What it does and does not record

- **Records**: failures during the regression run, case-level; since Fsearch2 also
  preparation / pre / post steps, cloud sessions (PXE, NICX), MNG, and minireg/DoA/SF
  (those only from 2026-07-02 onward).
- **Does not record**: CI build / packaging failures. Anything dying in setup/init before
  a case starts may never reach it.
- Fsearch2 renamed `UTOPX_TAG` → `TEST_TAG` and **removed the `FATAL` column**.
  TMV is native now — the old `--tmv` flag is gone.

## Related

- One specific red build → its raw log: skill `ci-forensics`.
- Reproducing the failure locally: skill `regression-repro`.
- Filing it: skill `utopx-regression-ticket`.
