#!/bin/bash
# Assemble the MARS view_log.php URL that goes in the ticket description.
#
# The URL uses /auto/sw_regression/... while the archive you actually read is mounted at
# /.autodirect/sw_regression/... -- both are correct in their own context, don't normalise one
# to the other.
#
# key_id is the archive node path: the directory with `result: 1` AND a sibling log.txt.
# Getting from a session id to that node is skill ci-forensics.
set -u

usage() {
  cat <<'EOF'
usage: mars_link.sh <setup_id> <session_id> <key_id> [test_name]

  setup_id    MARS setup dir name, e.g. BRONCO_FW-m-fwreg-018_SD_DPU_MODE_P1
  session_id  e.g. 11476316
  key_id      archive node path, e.g. 0.15.1.1.1.8.1.6.101.6.1
  test_name   the case name WITHOUT the utopx_NN_ prefix, e.g. scenario_steering_rules
              (omitted -> derived from the node's log.txt if the archive is reachable)

example:
  mars_link.sh BRONCO_FW-m-fwreg-018_SD_DPU_MODE_P1 11476316 0.15.1.1.1.8.1.6.101.6.1 scenario_steering_rules
EOF
  exit 1
}

[ $# -ge 3 ] || usage
SETUP=$1; SES=$2; KEY=$3; NAME=${4:-}

RESULTS=/auto/sw_regression/host_fw/HCA_CORE_FWV/MARS/conf/results
ARCHIVE=/.autodirect/sw_regression/host_fw/HCA_CORE_FWV/MARS/conf/results

if [ -z "$NAME" ]; then
  T="$ARCHIVE/$SETUP/$SES/$SES.tgz"
  if [ -f "$T" ]; then
    echo "== deriving test name from $T (streaming, no unpack)" >&2
    NAME=$(timeout 600 tar -xzOf "$T" 2>/dev/null \
           | grep -oE 'utopx_[0-9]+_[a-z0-9_]+' | sort -u | head -1 | sed 's/^utopx_[0-9]*_//')
  fi
  [ -n "$NAME" ] || { echo "could not derive test_name; pass it explicitly" >&2; exit 2; }
  echo "== test_name = $NAME" >&2
fi

printf 'https://mars.mellanox.com/web/server/php/view_log.php?results_dir=%s&name=%s&setup_id=%s&session_id=%s&key_id=%s&status=Failed\n' \
  "$RESULTS" "$NAME" "$SETUP" "$SES" "$KEY"
