#!/bin/bash
# Locate a Jenkins build by the value of one of its build parameters.
# Jenkins builds have no stable name, so matching on a parameter (for gerrit-triggered
# jobs: the change number) is the only reliable way to find "your" build.
#
# One request pulls numbers + status + parameters for the last N builds, instead of
# one request per build.
set -euo pipefail

JOB=""
PARAM=""
VALUE=""
COUNT=30
INSTANCE=internal
SAVE=""

usage() {
  cat <<'EOF'
Usage:
  find_jenkins_build.sh -j <job> -p <param> -v <value> [--blossom] [-n 30] [--save DIR]

Options:
  -j, --job JOB      Jenkins job name (e.g. utopx_ci, golan_fw_minireg)
  -p, --param NAME   build parameter to match (e.g. GERRIT_CHANGE_NUMBER)
  -v, --value VAL    value to match
  -n, --count N      how many recent builds to scan (default 30)
      --blossom      query $JENKINS_BLOSSOM_URL (anonymous) instead of $JENKINS_URL
      --save DIR     also download consoleText of every match into DIR
  -h, --help

Which instance hosts what:
  utopx_ci            -> blossom, readable anonymously   (--blossom)
  golan_fw_minireg    -> internal $JENKINS_URL, needs the token
  *_ci_rerun          -> internal $JENKINS_URL

A "Not Found" page (anonymous) or a 401 (wrong credentials) looks exactly like a
purged build and is NOT one. Try the other instance before concluding it is gone.
Jenkins purges builds in roughly 12 days -- save what you need immediately.

Windowing with -n is fine for LOCATING a build. It is never acceptable for
COUNTING running builds (long and short builds interleave).
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    -j|--job)   JOB="$2"; shift 2 ;;
    -p|--param) PARAM="$2"; shift 2 ;;
    -v|--value) VALUE="$2"; shift 2 ;;
    -n|--count) COUNT="$2"; shift 2 ;;
    --blossom)  INSTANCE=blossom; shift ;;
    --save)     SAVE="$2"; shift 2 ;;
    -h|--help)  usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

[ -n "$JOB" ] && [ -n "$PARAM" ] && [ -n "$VALUE" ] || { usage; exit 2; }

[ -r "$HOME/.jenkins_env" ] || { echo "missing ~/.jenkins_env" >&2; exit 1; }
# shellcheck disable=SC1091
source "$HOME/.jenkins_env"

if [ "$INSTANCE" = blossom ]; then
  BASE="${JENKINS_BLOSSOM_URL:?}"; AUTH=()
else
  BASE="${JENKINS_URL:?}"; AUTH=(-u "$JENKINS_USER:$JENKINS_API_TOKEN")
fi

TREE="builds%5Bnumber,building,result,actions%5Bparameters%5Bname,value%5D%5D%5D%7B0,$COUNT%7D"
RESP=$(curl -sf "${AUTH[@]}" "$BASE/job/$JOB/api/json?tree=$TREE") || {
  echo "request failed against $BASE/job/$JOB" >&2
  echo "if this was anonymous, try without --blossom (and vice versa) before assuming purged." >&2
  exit 1
}

MATCHES=$(printf '%s' "$RESP" | PARAM="$PARAM" VALUE="$VALUE" python3 -c '
import sys, json, os
param, value = os.environ["PARAM"], os.environ["VALUE"]
d = json.load(sys.stdin)
hits = []
for b in d.get("builds", []):
    ps = {p["name"]: p.get("value")
          for a in b.get("actions", []) or []
          for p in (a.get("parameters", []) or [])
          if isinstance(p, dict) and "name" in p}
    if str(ps.get(param)) == value:
        state = "BUILDING" if b.get("building") else (b.get("result") or "?")
        extra = ps.get("GERRIT_PATCHSET_NUMBER")
        hits.append((b["number"], state, f"patchset={extra}" if extra else ""))
for n, s, e in hits:
    print(n, s, e)
if not hits:
    sys.stderr.write(f"no build in the scanned window has {param}={value}\n")
')

if [ -z "$MATCHES" ]; then
  echo "(scanned the last $COUNT builds of $JOB on $INSTANCE -- widen with -n if the run is older)" >&2
  exit 1
fi

echo "$MATCHES" | while read -r N STATE EXTRA; do
  echo "$BASE/job/$JOB/$N/   $STATE $EXTRA"
done

if [ -n "$SAVE" ]; then
  mkdir -p "$SAVE"
  echo "$MATCHES" | while read -r N _ _; do
    OUT="$SAVE/${JOB}_${N}.log"
    curl -sf "${AUTH[@]}" "$BASE/job/$JOB/$N/consoleText" -o "$OUT" && echo "saved $OUT"
  done
  cat <<'EOF'

Now read it:
  grep -E 'Stage: ".*" Status:' <log> | grep -v 'Status: Success'
  grep -oE 'golan_fw_minireg #[0-9]+|nicx_minireg_doa/#[0-9]+' <log> | sort -u
  grep -oE 'session_id [0-9]+ .-device [a-z0-9]+ .-status [a-z]+' <log>
                                    ^ .-device, never --device (grep parses a leading -- as an option)
EOF
fi
