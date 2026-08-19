---
name: utopx-ci-rerun
description: Re-trigger CI on a gerrit change for fw_ver/utopx or fw_ver/golan_fw via the *_ci_rerun Jenkins jobs, and follow through to the real utopx_ci / golan_fw_minireg build it spawns. Use when asked to re-run CI, retrigger a build, kick a change through CI again, check whether a CI run actually started, or when a CI build failed and it is unclear whether the failure was environmental.
---

# Re-running utopx / golan_fw CI on a gerrit change

Credentials live in `~/.jenkins_env` (mode 600, NFS home, survives reboots). `source` it to get
`JENKINS_URL` (internal, l-jenkins-005), `JENKINS_BLOSSOM_URL` (blossom, where `utopx_ci` runs),
`JENKINS_USER`, `JENKINS_API_TOKEN`.

**Keep the token in that file only** — never in docs, memory, or commit messages. Regenerate at
`$JENKINS_URL/user/<user>/configure`.

## Use the script

```bash
~/.claude/skills/utopx-ci-rerun/scripts/ci_rerun.sh --help
~/.claude/skills/utopx-ci-rerun/scripts/ci_rerun.sh --reasons                 # list valid REASON values
~/.claude/skills/utopx-ci-rerun/scripts/ci_rerun.sh --concurrency             # check before triggering
~/.claude/skills/utopx-ci-rerun/scripts/ci_rerun.sh -c 1467618 -r "<reason>"  # trigger
```

It refuses to trigger above the concurrency ceiling and validates the REASON against the live
choice list. Re-runs go through a dedicated `*_ci_rerun` job — **do not re-trigger the CI job
directly.** Both rerun jobs live on the internal Jenkins:

| project | rerun job |
|---|---|
| `fw_ver/utopx` | `$JENKINS_URL/job/utopx_ci_rerun/` |
| `fw_ver/golan_fw` | `$JENKINS_URL/job/golan_fw_ci_rerun/` |

## Preconditions — check these before spending a queue slot

- **Get Code-Review+2 in place FIRST.** The job will happily start, but the pipeline's own
  `Pre Gerrit Validation` stage hard-checks the vote and aborts with
  `Code-Review vote is insufficient` / `Strongest Vote: 0` — it never reaches Compile or DoA.
  Pushing a new patchset outdates existing votes, so after any re-push you must re-collect CR+2.
  "Run it green, then get the vote" does not work.
- **A re-run cannot fix a deterministic failure.** DoA uses fixed seeds, so a real code defect
  reproduces identically every time. Confirm the failure is environmental first (see skill
  `ci-forensics` for attribution discipline); otherwise each re-run only burns a queue slot and
  copies stale `Verified-1` votes onto a new patchset.
- **`utopx_ci` caps at 15 concurrent and the scheduler HARD-ABORTS the excess** ~1 min in, at the
  `CI Execution Checkpoint` stage — it does not queue. Wasted runs also spawn a new patchset each
  time. Trigger only at ≤ 11 running, and re-measure 20 s later to avoid a transient dip.
- **Never window the build list** (`{0,40}`) when counting: long builds and quickly-aborted ones
  interleave, so a windowed query under-counts badly — measured 8 when the real figure was 26.

## Reading REASON

**Always read the current choices first.** The list is edited over time (dated entries get added
and removed) and the value must match verbatim. `ci_rerun.sh --reasons` does this.

## ⚠ `utopx_ci_rerun` reporting SUCCESS means nothing about the test run

That job's only work is handing the trigger to gerrit/Jenkins; it goes green as soon as the
request is accepted. **Always follow through to the `utopx_ci` build it spawned.**

A build whose console is only ~30 lines never entered a stage at all — check the head of the log
for a pipeline-level failure, e.g.

```
Obtained ci/utopx/jenkinsfile from git ssh://…/hca_fw/fw_automations
org.codehaus.groovy.control.MultipleCompilationErrorsException: startup failed:
WorkflowScript: 230: expecting '}', found '' @ line 230, column 1.
```

That is a broken pipeline script in `fw_automations`, hitting every change in the project at
once. Re-running is pointless until it is fixed (observed 2026-08-13: six consecutive builds
died this way).

## Where the builds live (this trips people up)

- **`utopx_ci` is on blossom** (`$JENKINS_BLOSSOM_URL`), readable **anonymously** — no auth
  needed for `consoleText` or `api/json`. Match builds on parameter `GERRIT_CHANGE_NUMBER`
  (and `GERRIT_PATCHSET_NUMBER`).
- The DoA it spawns is **`golan_fw_minireg #N`** (plus `nicx_minireg_doa/#N` on master-line
  branches, which runs the extra `NICX-DoA` stage). Grep the `utopx_ci` console for both.
- **`golan_fw_minireg` is NOT on blossom** — it is on the internal `$JENKINS_URL` and needs the
  token. Anonymous blossom answers `Not Found`, authenticated blossom answers `401`; **neither
  means the log was purged.** This cost a wrong "the log is gone" call on 2026-08-11.

```bash
source ~/.jenkins_env
curl -s -u "$JENKINS_USER:$JENKINS_API_TOKEN" \
  "$JENKINS_URL/job/golan_fw_minireg/<N>/consoleText" -o logs/minireg_<N>.log
grep -oE 'LAST_STABLE_FW="[^"]*"' logs/minireg_<N>.log | head -1   # the DoA baseline FW
```

- The `nvidia-jenkins` MCP **fails against blossom** (`not a member of SSA-allowed DLs:
  blossom-sre`) — use curl there.
- Anonymous has read-only rights on `utopx_ci_rerun`; the token is what allows triggering.
- `/auto/mswg/projects/fw/fw_ver/jenkins/svc-sw-hca-bot.auth` is readable but belongs to the CI
  service account — **do not** use it for manual re-runs, the audit trail would name the bot
  instead of you.

## Routinely-ignorable stages

`Pre FC Validation` and `Macros Guard` report `Failure_ignored` on healthy runs too.

## Related

- A red build → session_ids → raw failure log: skill `ci-forensics`.
- Reproducing the failure locally: skill `regression-repro`.
