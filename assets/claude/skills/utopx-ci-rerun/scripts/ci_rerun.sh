#!/bin/bash
# Trigger a CI re-run on a gerrit change via the *_ci_rerun Jenkins job.
#
# Guards built in, because each of these has cost a wasted queue slot before:
#   - REASON is validated against the LIVE choice list (the list gets edited over time)
#   - concurrency is checked before triggering (utopx_ci caps at 15 and HARD-ABORTS the
#     excess ~1 min in, at the CI Execution Checkpoint stage -- it does not queue)
#
# Reminder the script cannot check for you: Code-Review+2 must already be in place, or
# the pipeline aborts at "Pre Gerrit Validation" with "Code-Review vote is insufficient".
set -euo pipefail

PROJECT=utopx
CHANGE=""
REASON=""
THRESHOLD=11          # trigger only at or below this many running builds
FORCE=0
ACTION=trigger

usage() {
  cat <<'EOF'
Usage:
  ci_rerun.sh --reasons [-p utopx|golan_fw]
  ci_rerun.sh --concurrency
  ci_rerun.sh -c <change-number> -r "<reason verbatim>" [-p utopx|golan_fw] [--force]

Options:
  -c, --change N     gerrit change number
  -r, --reason STR   REASON parameter, must match a live choice verbatim
  -p, --project P    utopx (default) | golan_fw
      --reasons      list the current REASON choices and exit
      --concurrency  print the number of running utopx_ci builds and exit
      --force        skip the concurrency gate (you had better have a reason)
  -h, --help

Credentials come from ~/.jenkins_env (JENKINS_URL, JENKINS_BLOSSOM_URL,
JENKINS_USER, JENKINS_API_TOKEN). Never put the token anywhere else.

After triggering, follow through to the real utopx_ci build -- this job going
SUCCESS only means the trigger was accepted, not that any test ran.
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    -c|--change)   CHANGE="$2"; shift 2 ;;
    -r|--reason)   REASON="$2"; shift 2 ;;
    -p|--project)  PROJECT="$2"; shift 2 ;;
    --reasons)     ACTION=reasons; shift ;;
    --concurrency) ACTION=concurrency; shift ;;
    --force)       FORCE=1; shift ;;
    -h|--help)     usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

case "$PROJECT" in
  utopx)    RERUN_JOB=utopx_ci_rerun;    GERRIT_PATH=fw_ver/utopx ;;
  golan_fw) RERUN_JOB=golan_fw_ci_rerun; GERRIT_PATH=fw_ver/golan_fw ;;
  *) echo "unknown project: $PROJECT (use utopx or golan_fw)" >&2; exit 2 ;;
esac

[ -r "$HOME/.jenkins_env" ] || { echo "missing ~/.jenkins_env" >&2; exit 1; }
# shellcheck disable=SC1091
source "$HOME/.jenkins_env"
: "${JENKINS_URL:?}" "${JENKINS_USER:?}" "${JENKINS_API_TOKEN:?}"

list_reasons() {
  curl -sf -u "$JENKINS_USER:$JENKINS_API_TOKEN" \
       "$JENKINS_URL/job/$RERUN_JOB/api/json" \
  | python3 -c '
import sys, json
d = json.load(sys.stdin)
for a in d.get("actions", []):
    for p in a.get("parameterDefinitions", []):
        for c in p.get("choices", []):
            print(c)
'
}

count_running() {
  # NEVER window this query ({0,40}): long builds and quickly-aborted ones interleave,
  # so a windowed view under-counts badly (measured 8 when the real figure was 26).
  curl -sf "${JENKINS_BLOSSOM_URL:?}/job/utopx_ci/api/json?tree=builds%5Bnumber,building%5D" \
  | python3 -c '
import sys, json
print(sum(1 for b in json.load(sys.stdin)["builds"] if b.get("building")))
'
}

case "$ACTION" in
  reasons)     list_reasons; exit 0 ;;
  concurrency) echo "utopx_ci running builds: $(count_running)"; exit 0 ;;
esac

[ -n "$CHANGE" ] || { echo "-c/--change is required" >&2; usage; exit 2; }
[ -n "$REASON" ] || { echo "-r/--reason is required (see --reasons)" >&2; exit 2; }

echo "== validating REASON against the live choice list"
CHOICES=$(list_reasons)
if ! printf '%s\n' "$CHOICES" | grep -qxF -- "$REASON"; then
  echo "REASON does not match any live choice verbatim:" >&2
  printf '%s\n' "$CHOICES" | sed 's/^/  /' >&2
  exit 3
fi

if [ "$PROJECT" = utopx ] && [ "$FORCE" -eq 0 ]; then
  N=$(count_running)
  echo "== utopx_ci running builds: $N (threshold $THRESHOLD)"
  if [ "$N" -gt "$THRESHOLD" ]; then
    echo "refusing to trigger: over the concurrency threshold." >&2
    echo "the scheduler hard-aborts the excess ~1 min in and each attempt spawns a new patchset." >&2
    exit 4
  fi
  echo "== re-measuring in 20 s to rule out a transient dip"
  sleep 20
  N=$(count_running)
  echo "== utopx_ci running builds: $N"
  [ "$N" -le "$THRESHOLD" ] || { echo "refusing to trigger (second measurement)." >&2; exit 4; }
elif [ "$PROJECT" != utopx ]; then
  echo "== note: no concurrency gate implemented for $PROJECT (cap is documented for utopx_ci only)"
fi

CHANGE_URL="https://git-nbu.nvidia.com/r/c/$GERRIT_PATH/+/$CHANGE"
echo "== triggering $RERUN_JOB for $CHANGE_URL"

CRUMB=$(curl -sf -u "$JENKINS_USER:$JENKINS_API_TOKEN" "$JENKINS_URL/crumbIssuer/api/json" \
        | python3 -c 'import sys,json;print(json.load(sys.stdin)["crumb"])')

CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST \
  -u "$JENKINS_USER:$JENKINS_API_TOKEN" -H "Jenkins-Crumb: $CRUMB" \
  --data-urlencode "CHANGE_URL=$CHANGE_URL" \
  --data-urlencode "REASON=$REASON" \
  "$JENKINS_URL/job/$RERUN_JOB/buildWithParameters")

echo "HTTP $CODE (201 = accepted)"
[ "$CODE" = "201" ] || exit 5

cat <<EOF

Next, do NOT stop here:
  1. $RERUN_JOB going SUCCESS only means the trigger was accepted.
  2. Find the real build:
       find_jenkins_build.sh -j utopx_ci -p GERRIT_CHANGE_NUMBER -v $CHANGE --blossom
  3. Confirm it survived the CI Execution Checkpoint (~90 s in) -- that gate is
     where over-concurrency kills a run.
  4. A console of only ~30 lines means the pipeline script itself failed to
     compile; re-running is pointless until fw_automations is fixed.
EOF
