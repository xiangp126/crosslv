---
name: utopx-ci-rerun
description: Re-trigger CI on a gerrit change for fw_ver/utopx or fw_ver/golan_fw via the *_ci_rerun Jenkins jobs, and follow through to the real utopx_ci / golan_fw_minireg build it spawns. Use when asked to re-run CI, retrigger a build, kick a change through CI again, check whether a CI run actually started, wait for a CI-locked branch to reopen, or when a CI build failed or was aborted and it is unclear whether the cause was environmental.
---

# Re-running utopx / golan_fw CI on a gerrit change

## Credentials

`source ~/.jenkins_env` (mode 600, NFS home, survives reboots) for `JENKINS_URL` (internal,
l-jenkins-005), `JENKINS_BLOSSOM_URL` (blossom, where `utopx_ci` runs), `JENKINS_USER`,
`JENKINS_API_TOKEN`. Keep the token in that file only — never in docs, memory, or commit messages.
Regenerate it at `$JENKINS_URL/user/<user>/configure`.

## Use the script

```bash
~/myGit/crosslv/assets/skills/utopx-ci-rerun/scripts/ci_rerun.sh --help
~/myGit/crosslv/assets/skills/utopx-ci-rerun/scripts/ci_rerun.sh --reasons                 # list valid REASON values
~/myGit/crosslv/assets/skills/utopx-ci-rerun/scripts/ci_rerun.sh --concurrency             # check before triggering
~/myGit/crosslv/assets/skills/utopx-ci-rerun/scripts/ci_rerun.sh --lock <branch>           # is the branch CI-locked?
~/myGit/crosslv/assets/skills/utopx-ci-rerun/scripts/ci_rerun.sh -c 1467618 -r "<reason>"  # trigger
```

The script refuses to trigger while the change's branch is locked or above the concurrency
ceiling, and validates REASON against the live choice list. Re-run through the dedicated
`*_ci_rerun` job only — **never re-trigger the CI job directly.** Both rerun jobs live on the
internal Jenkins:

| project | rerun job |
|---|---|
| `fw_ver/utopx` | `$JENKINS_URL/job/utopx_ci_rerun/` |
| `fw_ver/golan_fw` | `$JENKINS_URL/job/golan_fw_ci_rerun/` |

## Preconditions — check before spending a queue slot

- **Code-Review+2 must already be in place.** The job starts anyway, but the pipeline's own
  `Pre Gerrit Validation` stage hard-checks the vote and aborts with
  `Code-Review vote is insufficient` / `Strongest Vote: 0` — it never reaches Compile or DoA. A new
  patchset outdates existing votes, so re-collect CR+2 after every re-push. "Run it green, then get
  the vote" does not work.
- **The branch must not be CI-locked.** A branch owner can lock a branch in VDash (broken branch,
  code freeze); the `CI Execution Checkpoint` then aborts every run ~1 min in with
  `CI is DISABLED for project fw_ver/utopx, branch <branch>, because of ::: <project>/<branch> locked by <name> (<reason>) ::: Run aborted.`
  and the bot votes `Verified-1`. Nothing compiled or ran, so the abort is environmental; confirm
  with a control (other changes on that branch aborted the same way). The lock state is
  `https://vdash.nvidia.com/api/hca-fw-ci/locks/check?project=utopx&branch=<branch>` — the
  checkpoint's own query; `project=fw_ver/utopx` is rejected with `400 Unknown project`.
  `ci_rerun.sh --lock <branch>` prints it, and the trigger refuses while it is locked, reading the
  branch from the change's last `utopx_ci` build because VDash answers `"locked": false` for a
  branch name that does not exist. To wait for an unlock, poll from a bounded background loop and
  trigger only after two `UNLOCKED` readings a minute apart. A VDash outage counts as unlocked for
  the checkpoint but as `UNKNOWN` (blocking) for the script.
- **The failure must be environmental.** DoA uses fixed seeds, so a real code defect reproduces
  identically every time; a re-run only burns a queue slot and copies stale `Verified-1` votes onto
  a new patchset. Decide per skill `ci-forensics` (Attribution discipline).
- **Concurrency: trigger only at ≤ 11 running `utopx_ci` builds, and re-measure 20 s later** to rule
  out a transient dip. `utopx_ci` caps at 15 concurrent and the scheduler hard-aborts the excess
  ~1 min in, at the `CI Execution Checkpoint` stage — it does not queue — and every wasted run also
  spawns a new patchset.
- **Never window the build list** (`{0,40}`) when counting: long builds and quickly-aborted ones
  interleave, so a windowed query under-counts badly (8 counted vs 26 real).

## REASON

Read the current choices before every trigger (`ci_rerun.sh --reasons`): the list is edited over
time (dated entries get added and removed) and the value must match verbatim.

## `utopx_ci_rerun` SUCCESS says nothing about the test run

The rerun job only hands the trigger to gerrit/Jenkins and goes green as soon as the request is
accepted. **Always follow through to the `utopx_ci` build it spawned.**

A build whose console is only ~30 lines never entered a stage. Check the head of the log for a
pipeline-level failure, e.g.:

```
Obtained ci/utopx/jenkinsfile from git ssh://…/hca_fw/fw_automations
org.codehaus.groovy.control.MultipleCompilationErrorsException: startup failed:
WorkflowScript: 230: expecting '}', found '' @ line 230, column 1.
```

That is a broken pipeline script in `fw_automations`; it hits every change in the project at once
(consecutive builds all die the same way). Do not re-run until it is fixed.

## Where the builds live

- **`utopx_ci` is on blossom** (`$JENKINS_BLOSSOM_URL`), readable anonymously — no auth needed for
  `consoleText` or `api/json`. Match builds on parameter `GERRIT_CHANGE_NUMBER` (and
  `GERRIT_PATCHSET_NUMBER`).
- The DoA it spawns is **`golan_fw_minireg #N`** (plus `nicx_minireg_doa/#N` on master-line
  branches, which runs the extra `NICX-DoA` stage). Grep the `utopx_ci` console for both.
- **`golan_fw_minireg` is NOT on blossom** — it is on the internal `$JENKINS_URL` and needs the
  token. Anonymous blossom answers `Not Found`, authenticated blossom answers `401`; **neither
  means the log was purged.**

  ```bash
  source ~/.jenkins_env
  curl -s -u "$JENKINS_USER:$JENKINS_API_TOKEN" \
    "$JENKINS_URL/job/golan_fw_minireg/<N>/consoleText" -o logs/minireg_<N>.log
  grep -oE 'LAST_STABLE_FW="[^"]*"' logs/minireg_<N>.log | head -1   # the DoA baseline FW
  ```

- The `nvidia-jenkins` MCP fails against blossom
  (`not a member of SSA-allowed DLs: blossom-sre`) — use curl there.
- Anonymous has read-only rights on `utopx_ci_rerun`; the token is what allows triggering.
- `/auto/mswg/projects/fw/fw_ver/jenkins/svc-sw-hca-bot.auth` is readable but belongs to the CI
  service account — do not use it for manual re-runs; the audit trail would name the bot instead
  of you.

## Routinely-ignorable stages

`Pre FC Validation` and `Macros Guard` report `Failure_ignored` on healthy runs too.

## Related

- A red build → session_ids → raw failure log: skill `ci-forensics`.
- Reproducing the failure locally: skill `regression-repro`.
