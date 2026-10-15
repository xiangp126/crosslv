#!/bin/bash
# Keep a NOGA host you hold, and get it back when you lose it -- except to the nightly
# regression, which ends the watch.
#
# usage: noga_watchdog.sh <host> [noga|malloc]
#   noga    (default) the box is locked through NOGA (noga_manage.py -l or noga_wait.sh);
#           renew with noga_manage.py -l, lease := NOW+8h
#   malloc  the box was taken with jmake --reg-malloc; renew with jmake --reg-extend,
#           end := NOW+3h
#
# Flow:
#   not held at start, or lost to anyone but mars_reg, or released
#       -> noga_wait.sh polls every 15 s and grabs as soon as the box is takeable (never
#          over a live lease); then the hold loop resumes
#   held -> check every 5 min; renew when <= 1 h is left
#   held, then Status Lock with lock_owner mars_reg (the nightly takeover, ~01:45-02:30 CST)
#       -> report and exit 2; a new watch starts only when Peter asks again
#   noga_wait.sh ends without the lock (14 h ceiling, refusal) -> exit 1
#   a query that fails or does not parse is retried -- never read as a loss, never a grab
# Run it as a background task. It prints a heartbeat every 30 min while it holds the box;
# noga_wait.sh prints its own every ~5 min while it waits.
CLI=${NOGA_CLI:-/.autodirect/sw_tools/Internal/Noga/RELEASE/latest/cli/noga_manage.py}   # NOGA_CLI: test stub only
S=$(cd "$(dirname "$0")" && pwd)
HOST=${1:?usage: noga_watchdog.sh <host> [noga|malloc]}
VIA=${2:-noga}
PERIOD=${WATCHDOG_PERIOD:-300}   # hold-loop period in s; WATCHDOG_PERIOD is a test hook only
WAIT_HOURS=14                    # noga_wait.sh ceiling: outlasts a nightly session (~02:00-14:30 CST)
MARS=mars_reg

case "$VIA" in noga|malloc) ;; *) echo "usage: noga_watchdog.sh <host> [noga|malloc]" >&2; exit 3 ;; esac
case "$HOST" in
  *l-fwminireg*) echo "REFUSED: $HOST is a dedicated CI/DoA machine -- never lock it" >&2; exit 3 ;;
esac

query() {
  Q=$(python3 "$CLI" -q -t server -n "$HOST" 2>/dev/null)
  st=$(echo "$Q"    | awk -F'= ' '/^Status\.status/        {print $2}' | tr -d ' ')
  owner=$(echo "$Q" | awk -F'= ' '/^Status\.lock_owner/    {print $2}' | tr -d ' ')
  tout=$(echo "$Q"  | awk -F'= ' '/^Status\.lock_time_out/ {print $2}')
}

renew() {
  if [ "$VIA" = noga ]; then
    python3 "$CLI" -l -t server -n "$HOST" -L 8 -N "hold" >/dev/null 2>&1   # lease := NOW+8h
    query
    echo "renewed $HOST via noga $(date '+%F %T') -- owner=${owner:-<none>} until=$tout"
  else
    n=$(jmake --reg-extend </dev/null 2>/dev/null | awk -v h="$HOST" '$4 == h {print $2}')
    if [ -n "$n" ]; then
      echo "$n" | jmake --reg-extend >/dev/null 2>&1                        # end := NOW+3h
      echo "extended $HOST (menu entry $n) $(date '+%F %T')"
    else
      echo "!!!!! $HOST is not in the --reg-extend menu $(date '+%F %T')"
    fi
  fi
}

acquire() {
  echo "== $HOST not held (status=$st owner=${owner:-<none>}) $(date '+%F %T') -- noga_wait.sh, 15 s polls"
  NOGA_CLI=$CLI "$S/noga_wait.sh" -n "$HOST" -L 8 --hours "$WAIT_HOURS"
  rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "!!!!! noga_wait.sh exited $rc without the lock $(date '+%F %T') -- watchdog exits"
    exit 1
  fi
  VIA=noga   # noga_wait.sh locks directly through NOGA
}

echo "== watchdog $HOST via $VIA: hold check every ${PERIOD}s, grab polls every 15 s," \
     "exits if $MARS takes the box back $(date '+%F %T')"
HELD=0     # 1 once the box has been ours in this run
next_hb=0
while true; do
  query
  if [ "$st" != Lock ] && [ "$st" != Release ]; then
    echo "query failed or unparsable (status='$st') $(date '+%F %T') -- retrying"
  elif [ "$st" = Lock ] && [ "$owner" = "$USER" ]; then
    HELD=1
    past=$(python3 "$S/noga_expiry.py" "$tout" 2>/dev/null | head -1) || true   # negative = s left
    case "$past" in
      ''|*[!0-9-]*) echo "!!!!! cannot read lock_time_out '$tout' $(date '+%F %T') -- retrying" ;;
      *) if [ "$past" -gt -3600 ]; then renew; fi ;;
    esac
  elif [ "$HELD" = 1 ] && [ "$st" = Lock ] && [ "$owner" = "$MARS" ]; then
    echo "!!!!! $HOST taken back by $MARS at $(date '+%F %T') (its lease until $tout)" \
         "-- watchdog exits; ask again to monitor"
    exit 2
  else
    acquire
    continue   # re-read at once: confirm the hold and its lease
  fi
  now=$(date +%s)
  if [ "$now" -ge "$next_hb" ]; then
    echo "heartbeat $HOST status=$st owner=${owner:-<none>} until=$tout $(date '+%F %T')"
    next_hb=$((now + 1800))
  fi
  sleep "$PERIOD"
done
