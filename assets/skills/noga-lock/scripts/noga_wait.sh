#!/bin/bash
# Wait for a NOGA host to become takeable, grab it, then optionally run setup work
# in the same task so the whole grab-and-provision sequence is unattended.
#
# Run this as a run_in_background Bash task and pass --then, so it reports once at
# the end instead of needing to be babysat.
#
# Takeable means EITHER Status.status is Release OR the lease expired more than --grace
# seconds ago: NOGA does not clear lock_owner when a lease lapses, so waiting for an
# empty owner alone can idle for hours beside a dead lock. A status that does not parse
# as Lock or Release is "unknown, retry" -- never a reason to grab (a lock attempt on a
# box someone else holds is a Lock Break).
set -euo pipefail

CLI=/.autodirect/sw_tools/Internal/Noga/RELEASE/latest/cli/noga_manage.py
EXPIRY="$(dirname "$0")/noga_expiry.py"

HOST=""
LEASE=8         # hours to hold once taken
HOURS=8         # ceiling on how long to keep waiting
GRACE=900       # a lease this many seconds past expiry counts as free
POLL=15         # never raise it: grabs are first-come-first-served (see SKILL.md)
THEN=""

usage() {
  cat <<'EOF'
Usage: noga_wait.sh -n <host> [-L 8] [--hours 8] [--grace 900] [--poll 15] [--then 'cmd']

  -n, --name HOST    NOGA host to wait for and lock
  -L, --lease H      hold the lock for H hours once taken (default 8)
      --hours H      give up after H hours of waiting (default 8)
      --grace S      treat a lease expired by more than S seconds as free (default 900)
      --poll S       seconds between polls (default 15). Do NOT raise it: the poll
                     interval is the window in which somebody else takes the box, and
                     the malloc round-trip alone is ~6 s; 60 s loses the race.
      --then CMD     shell command to run once the lock is held
  -h, --help

mars_reg is the regression service and wins by convention -- do not fight a live
holder. It usually releases around 13:05-13:15 CST, well before its nominal timeout.

Refuses outright on l-fwminireg-* : those are dedicated CI machines, and NOGA
reports them Release/no-owner while a live CI session is running on them.
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    -n|--name)  HOST="$2"; shift 2 ;;
    -L|--lease) LEASE="$2"; shift 2 ;;
    --hours)    HOURS="$2"; shift 2 ;;
    --grace)    GRACE="$2"; shift 2 ;;
    --poll)     POLL="$2"; shift 2 ;;
    --then)     THEN="$2"; shift 2 ;;
    -h|--help)  usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

[ -n "$HOST" ] || { usage; exit 2; }

case "$HOST" in
  *l-fwminireg*)
    echo "REFUSED: $HOST is a dedicated CI/DoA machine." >&2
    echo "NOGA reports these free while CI is running on them, and a NOGA lock does not" >&2
    echo "stop the MARS scheduler from dispatching to them. Let CI run the experiment, or" >&2
    echo "ask the minireg pool owner to take a box out of rotation." >&2
    exit 3 ;;
esac

query() { python3 "$CLI" -q -t server -n "$HOST" 2>/dev/null; }
field() { echo "$1" | grep -i "$2" | awk -F'= ' '{print $2}'; }

ITERS=$(( HOURS * 3600 / POLL ))
echo "== waiting for $HOST (ceiling ${HOURS}h, poll ${POLL}s, grace ${GRACE}s) $(date '+%F %T')"

ACQUIRED=0
for i in $(seq 1 "$ITERS"); do
  Q=$(query) || { echo "query failed, retrying"; sleep "$POLL"; continue; }
  status=$(field "$Q" 'Status\.status =' | tr -d ' ')
  case "$status" in
    Lock|Release) ;;
    *) echo "status unknown (${status:-<empty>}), retrying $(date '+%H:%M:%S')"; sleep "$POLL"; continue ;;
  esac
  owner=$(field "$Q" lock_owner | tr -d ' ')
  tout=$(field "$Q" lock_time_out)

  if [ "$owner" = "$USER" ]; then
    echo "ALREADY_OURS $(date '+%F %T')"
    python3 "$CLI" -l -t server -n "$HOST" -L "$LEASE" >/dev/null 2>&1 || true   # renew
    ACQUIRED=1
    break
  fi

  # noga_expiry.py prints the value and uses its EXIT CODE as the verdict
  # (0 = expired, 1 = still valid, 2 = unparseable). Keep BOTH guards:
  #   `| head -1`  takes the value only; anything that appends a second line makes $exp
  #                multi-line and every poll dies on "[: integer expression expected";
  #   `|| true`    exit 1 means "not expired yet", and under `set -euo pipefail` that
  #                status would kill the script silently (no GAVE_UP, no message).
  exp=$(python3 "$EXPIRY" "$tout" 2>/dev/null | head -1) || true
  case "$exp" in ''|*[!0-9-]*) exp=0 ;; esac

  if [ "$status" = Release ] || [ "$exp" -gt "$GRACE" ]; then
    python3 "$CLI" -l -t server -n "$HOST" -L "$LEASE" >/dev/null 2>&1 || true
    owner=$(field "$(query)" lock_owner | tr -d ' ')
    if [ "$owner" = "$USER" ]; then
      echo "LOCK_ACQUIRED $(date '+%F %T')"
      ACQUIRED=1
      break
    fi
    # a refused grab is harmless -- keep polling
  fi

  if [ $((i % 20)) -eq 0 ]; then
    echo "heartbeat t=+$((i * POLL / 60))min owner=${owner:-<none>} expired=${exp}s $(date '+%H:%M')"
  fi
  sleep "$POLL"
done

if [ "$ACQUIRED" -ne 1 ]; then
  echo "GAVE_UP after ${HOURS}h without acquiring $HOST $(date '+%F %T')" >&2
  exit 1
fi

if [ -n "$THEN" ]; then
  echo "== running setup: $THEN"
  set +e
  eval "$THEN"
  RC=$?
  set -e
  echo "== setup exited $RC"
  echo "Verify the final state yourself -- setup scripts have reported READY off a stale"
  echo "or partially-applied config more than once."
  exit $RC
fi

echo "Keep it until Peter says to release it; then:  jmake --reg-free $HOST"
