---
name: fsearch-failures
description: >-
  Query the regression failure database (MARS analytics / fsearch) - how often a failure happens,
  on which machines, under which FW and utopx commit; the main tool for attributing a regression to
  a commit (new path and Python 3.8 since 2026-09). Run it FIRST when a repro or root-cause
  investigation starts, before allocating a box; also to tell whether a failure is new, how often
  it occurs, whether our commit caused it, or for an A/B attribution over regression history.
---

# fsearch — the regression failure database

Failure triage is a three-skill chain. Go 1 → 2 → 3: leg 2 often ends the investigation, and one
log from leg 3 alone cannot tell a one-off from a month-old epidemic.

| Leg | Question it answers | Skill |
|---|---|---|
| 1 | Did anything fail last night, and where? | `regression-report-mail` (Outlook) |
| 2 | Is this failure new? How many setups? Which commit introduced it? | `fsearch-failures` (failure DB) |
| 3 | What exactly happened in that one run? | `ci-forensics` (Jenkins → MARS log) |

fsearch is a CLI over the MARS analytics DB: one row per **failure occurrence**, with the setup, FW
version, **utopx commit**, failure text and timestamp. Use it for attribution ("is this ours? since
when? how often?"); to read one run's log use skill `ci-forensics`.

## Call it

```bash
python3.8 /auto/sw/work/hca_fw/projects/mars_analytics/search.py --errlike "0xac5816"
```

First time on a machine, install the deps **without touching system python**:

```bash
python3.8 -m pip install --user \
    -r /auto/sw/work/hca_fw/projects/mars_analytics/requirements.txt
```

(The team's official command is `sudo python3.8 -m pip install -r …`; `--user` works and is the
right choice from an AI session.)

The interactive `fsearch` alias points at the same script but **does not exist in Bash tool
calls** — always write the full path. To repair a human's broken alias:
`source /mswg/projects/fw/fw_ver/hca_fw_tools/.fwvalias && refreshalias`; then `type fsearch` must
print `sudo python3.8 /auto/sw/work/hca_fw/projects/mars_analytics/search.py`.

## Three traps — each one silently flips the conclusion

### 1. The old path is dead and answers every query with "No records found"

| | path | |
|---|---|---|
| **use this** | `/auto/sw/work/hca_fw/projects/mars_analytics/search.py` | live |
| ~~never~~ | ~~`/mswg/projects/fw/fw_ver/mars_analytics/search.py`~~ | frozen 2026-05-31, **always empty** |

The dead path does not error — it returns `No records found.` in ~1.8 s for anything, which reads
as "that failure does not exist in regression history". **Always run a control query with a term
you know exists**; if the control is also empty, the tool is broken, not the data.

### 2. The DB only holds the last ~8 days

The window is DB-wide, the same for every setup (MUSTANG, BRONCO, TAMAR, cx9).

- **"First seen on <date>" is meaningless unless that date is well inside the window** — usually
  it is just the retention edge.
- A commit that landed three weeks ago cannot be A/B'd with fsearch at all — the "before" side
  does not exist. The MARS session archives
  (`/auto/sw_regression/host_fw/HCA_CORE_FWV/MARS/conf/results/<setup>/<sid>/<sid>.tgz`) go back
  months — check the oldest `<sid>` with `ls` — so scan them for the before side (skill
  `ci-forensics`). For a controlled before/after, run the two builds on a local device.

### 3. `--datefrom` / `--dateto` are accepted and ignored

`--datefrom 2026-08-01 --dateto 2026-08-31` and `--datefrom 2026-09-16` return the *same* rows, with
no error and no warning. **Filter on the timestamp column of the output yourself.**

Judge a result by the control query, never by elapsed time: the old rule "a real query takes
70–90 s, an instant return is a false negative" is **obsolete** — Fsearch2 is far faster (32 rows
in 5.8 s).

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

- **A failure confined to one setup is a machine/config signal, not a code signal** — check that
  before blaming a commit. A failure across many setups and branches that starts at a known landing
  date is the strong form of attribution — but apply trap 2 before believing any "starts at".
- **"It starts at FW X" — check whether the burned INI changed at the same time.** fsearch rows
  carry FW and utopx commit but not the INI, and MARS burns a per-session INI that the regression
  infrastructure regenerates per branch (extra lines injected on top of the release INI). Every
  session's INI is kept:

  ```bash
  ls /auto/sw/work/hca_fw/data/burn_fw/ini_files/ | grep "_session_<sid>_"
  #   <n>_session_<sid>_version_<fw>_psid_<psid>.ini
  diff <ini of last good session> <ini of first bad session>
  ```

  An INI change can make a failure look like a FW regression when the FW is innocent. If FW and INI
  changed together, history cannot separate them: swap one of them on the box (skill
  `regression-repro`).

## What it does and does not record

- **Records**: failures during the regression run, case-level; since Fsearch2 also preparation /
  pre / post steps, cloud sessions (PXE, NICX), MNG, and minireg/DoA/SF (those only from
  2026-07-02 onward).
- **Does not record**: CI build / packaging failures. Anything dying in setup/init before a case
  starts may never reach it. **Nor any coverage data** — an empty fsearch result says nothing about
  whether a feature ran. Functional coverage lives in a separate SQLite DB; see skill
  `regression-report-mail`.
- Fsearch2 renamed `UTOPX_TAG` → `TEST_TAG` and **removed the `FATAL` column**. TMV is native now —
  the old `--tmv` flag is gone.

## Related

- Functional coverage counters (a different DB entirely): skill `regression-report-mail`.
- One specific red build → its raw log: skill `ci-forensics`.
- Reproducing the failure locally: skill `regression-repro`.
- Filing it: skill `utopx-regression-ticket`.
