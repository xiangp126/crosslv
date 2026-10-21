#!/bin/bash
# Wait for a NOGA host, take it, and keep it: one loop that checks every --poll seconds
# (default 15), whether the box is someone else's or ours. Every lock and renewal goes through
# NOGA (noga_manage.py -l), whatever took the box.
#
#   someone else's live lease       -> wait; never lock over a live lease (a lock break)
#   takeable: Status.status is Release, or the lease expired more than --grace s ago
#                                   -> lock it for -L hours, read the owner back
#   ours                            -> renew when <= 1 h is left (lease := NOW + -L hours)
#   ours earlier in this run, now Lock by mars_reg (the nightly takeover)
#                                   -> exit 2; a new watch starts only when Peter asks again
#   not ours for --hours in a row   -> GAVE_UP, exit 1
#   a query that fails, or a record that does not parse
#                                   -> retry; never read as a loss, never a grab
#
# --until-locked ends the run as soon as the box is ours (LOCK_ACQUIRED or ALREADY_OURS),
# after running --then if one is given. A background task wakes an agent only when it exits,
# so an agent waits for a busy box with --until-locked, reports the grab, then starts a second
# run without it to keep the box.
#
# Heartbeat: every 5 min while waiting, every 30 min while holding.
set -uo pipefail

CLI=${NOGA_CLI:-/.autodirect/sw_tools/Internal/Noga/RELEASE/latest/cli/noga_manage.py}   # NOGA_CLI: test stub only
S=$(cd "$(dirname "$0")" && pwd)
MARS=mars_reg

HOST=""
LEASE=8         # hours a lock or renewal runs for
POLL=15         # seconds from the start of one check to the start of the next
GRACE=60        # a lease this many seconds past expiry counts as free (lock first, check after)
HOURS=14        # give up after this many hours in a row without the box
UNTIL=0
THEN=""

usage() {
  cat <<'EOF'
Usage: noga_watchdog.sh <host> [options]
       noga_watchdog.sh -n <host> [options]

Waits for the host, takes it, and keeps it: renews the lease when 1 h is left and takes the box
back within one check when the lock is lost -- until mars_reg takes it back (exit 2). Locks and
renewals go through NOGA, whatever took the box.

  -n, --name HOST       the host, instead of the first argument
  -L, --lease H         hours a lock or renewal runs for (default 8)
      --poll S          seconds from the start of one check to the start of the next (default
                        15), waiting and holding alike. Do NOT raise it: the interval is the
                        window in which somebody else takes the box, and a held lock can vanish
                        at any time (a MARS session's teardown releases locks it does not own).
      --grace S         treat a lease expired by more than S seconds as free (default 60);
                        a grabbed box is not idle yet -- run the pre-touch check first
      --hours H         give up after H hours in a row without the box (default 14)
      --until-locked    end as soon as the box is ours: LOCK_ACQUIRED or ALREADY_OURS
      --then CMD        with --until-locked: run CMD once the box is ours, exit with its status
  -h, --help

Exit: 0 the box is ours (--until-locked); 1 GAVE_UP; 2 mars_reg took the box back;
3 usage or refusal; with --then, the command's status.

mars_reg is the regression service and wins by convention -- do not fight a live holder.
Refuses outright on l-fwminireg-* : those are dedicated CI machines, and NOGA reports them
Release/no-owner while a live CI session is running on them.
EOF
}

die() { echo "$*" >&2; echo "run with --help for the usage" >&2; exit 3; }
whole() { case "$2" in ''|*[!0-9]*) die "$1 needs a whole number, got '$2'" ;; esac; }

while [ $# -gt 0 ]; do
  case "$1" in
    -n|--name|-L|--lease|--poll|--grace|--hours|--then)
      [ $# -ge 2 ] || die "$1 needs a value"
      case "$1" in
        -n|--name)  HOST=$2 ;;
        -L|--lease) LEASE=$2 ;;
        --poll)     POLL=$2 ;;
        --grace)    GRACE=$2 ;;
        --hours)    HOURS=$2 ;;
        --then)     THEN=$2 ;;
      esac
      shift 2 ;;
    --until-locked) UNTIL=1; shift ;;
    -h|--help)      usage; exit 0 ;;
    noga|malloc)    shift ;;   # older command lines name how the box was taken; renewal is NOGA either way
    -*)             die "unknown option: $1" ;;
    *)              [ -z "$HOST" ] || die "unexpected argument: $1"; HOST=$1; shift ;;
  esac
done

[ -n "$HOST" ] || die "no host given"
whole -L "$LEASE"; whole --poll "$POLL"; whole --grace "$GRACE"; whole --hours "$HOURS"
[ "$LEASE" -ge 1 ] && [ "$POLL" -ge 1 ] || die "-L and --poll must be at least 1"
[ -z "$THEN" ] || [ "$UNTIL" = 1 ] || die "--then runs only with --until-locked"

case "$HOST" in
  *l-fwminireg*)
    echo "REFUSED: $HOST is a dedicated CI/DoA machine." >&2
    echo "NOGA reports these free while CI is running on them, and a NOGA lock does not" >&2
    echo "stop the MARS scheduler from dispatching to them. Let CI run the experiment, or" >&2
    echo "ask the minireg pool owner to take a box out of rotation." >&2
    exit 3 ;;
esac

# One NOGA read into st / owner / tout. A failed or malformed reply leaves st empty.
query() {
  local q
  q=$(timeout 60 python3 "$CLI" -q -t server -n "$HOST" 2>/dev/null) || q=""
  st=$(printf '%s\n' "$q"    | awk -F'= ' '/^Status\.status/        {print $2; exit}' | tr -d ' ')
  owner=$(printf '%s\n' "$q" | awk -F'= ' '/^Status\.lock_owner/    {print $2; exit}' | tr -d ' ')
  tout=$(printf '%s\n' "$q"  | awk -F'= ' '/^Status\.lock_time_out/ {print $2; exit}')
}

# Seconds past the lease end (negative = time left), or nothing when it does not parse.
# noga_expiry.py prints the value AND uses its exit code as the verdict (0 expired,
# 1 still valid, 2 unparseable): take the first line, never the status.
since_expiry() {
  local e
  e=$(python3 "$S/noga_expiry.py" "$tout" 2>/dev/null | head -1) || true
  if [[ "$e" =~ ^-?[0-9]+$ ]]; then echo "$e"; fi
}

grab() { timeout 60 python3 "$CLI" -l -t server -n "$HOST" -L "$LEASE" >/dev/null 2>&1; }

renew() {
  timeout 60 python3 "$CLI" -l -t server -n "$HOST" -L "$LEASE" -N "hold" >/dev/null 2>&1   # lease := NOW+L h
  query
  echo "renewed $HOST $(date '+%F %T') -- owner=${owner:-<none>} until=$tout"
}

# Sleep only what is left of this check's period, so checks start every $POLL seconds
# whatever the query took.
pace() { local d=$(( POLL - ($(date +%s) - t0) )); if [ "$d" -gt 0 ]; then sleep "$d"; fi; }

# --until-locked: the box is ours.
finish() {
  if [ -n "$THEN" ]; then
    echo "== running setup: $THEN"
    eval "$THEN"
    local rc=$?
    echo "== setup exited $rc"
    echo "Verify the final state yourself -- setup scripts have reported READY off a stale"
    echo "or partially-applied config more than once."
    exit "$rc"
  fi
  echo "Keep it until Peter says to release it; then:  jmake --reg-free $HOST"
  exit 0
}

if [ "$UNTIL" = 1 ]; then mode="ends once the box is ours"; else mode="keeps the box, exits if $MARS takes it back"; fi
echo "== $HOST: check every ${POLL}s, grace ${GRACE}s, lease ${LEASE}h," \
     "gives up after ${HOURS}h without it; $mode $(date '+%F %T')"

HELD=0                  # the box has been ours in this run
OURS=0                  # the box was ours at the last check
since=$(date +%s)       # start of the current stretch without the box
next_hb=0               # when the next heartbeat is due
next_renew=0            # earliest next renewal attempt
exp=""; past=""

while :; do
  t0=$(date +%s)
  query
  if [ "$st" != Lock ] && [ "$st" != Release ]; then
    echo "query failed or record unparsable (status='$st') $(date '+%F %T') -- retrying"
    pace
    continue
  fi

  if [ "$st" = Lock ] && [ "$owner" = "$USER" ]; then
    if [ "$OURS" = 0 ]; then
      echo "ALREADY_OURS $(date '+%F %T')"
      OURS=1; HELD=1; next_hb=0
    fi
    past=$(since_expiry)
    if [ -z "$past" ]; then
      echo "!!!!! cannot read lock_time_out '$tout' $(date '+%F %T') -- retrying"
    elif [ "$past" -gt -3600 ] && [ "$t0" -ge "$next_renew" ]; then
      renew
      next_renew=$(( $(date +%s) + 300 ))
    fi
    if [ "$UNTIL" = 1 ]; then finish; fi
  else
    if [ "$OURS" = 1 ]; then
      echo "!!!!! $HOST lost: status=$st owner=${owner:-<none>} until=$tout $(date '+%F %T')"
      OURS=0; since=$t0; next_hb=0
    fi
    if [ "$HELD" = 1 ] && [ "$st" = Lock ] && [ "$owner" = "$MARS" ]; then
      echo "!!!!! $HOST taken back by $MARS at $(date '+%F %T') (its lease until $tout)" \
           "-- exiting; ask again to monitor"
      exit 2
    fi
    exp=$(since_expiry)
    if [ "$st" = Release ] || { [ -n "$exp" ] && [ "$exp" -gt "$GRACE" ]; }; then
      grab
      query
      if [ "$st" = Lock ] && [ "$owner" = "$USER" ]; then
        echo "LOCK_ACQUIRED $(date '+%F %T')"
        OURS=1; HELD=1; next_hb=0; next_renew=0
        if [ "$UNTIL" = 1 ]; then finish; fi
      fi
      # a refused grab is harmless -- keep checking
    fi
    if [ "$OURS" = 0 ] && [ $(( $(date +%s) - since )) -ge $(( HOURS * 3600 )) ]; then
      echo "GAVE_UP after ${HOURS}h without acquiring $HOST $(date '+%F %T')"
      exit 1
    fi
  fi

  now=$(date +%s)
  if [ "$now" -ge "$next_hb" ]; then
    if [ "$OURS" = 1 ]; then
      echo "heartbeat $HOST held owner=$owner until=$tout $(date '+%F %T')"
      next_hb=$(( now + 1800 ))
    else
      echo "heartbeat $HOST waiting status=$st owner=${owner:-<none>} expired=${exp:-?}s $(date '+%F %T')"
      next_hb=$(( now + 300 ))
    fi
  fi
  pace
done
