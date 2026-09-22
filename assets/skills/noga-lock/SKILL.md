---
name: noga-lock
description: Reserve, extend, release and monitor lab servers in the NOGA pool — both the `jmake --reg-malloc/--reg-extend/--reg-cancel` wrappers and raw noga_manage.py, the unattended wait-then-grab loop for a box held by mars_reg, and how to read the UTC lock_time_out. Use when asked to take/grab/lock a lab machine, malloc or extend an allocation, wait for a server to free up, check who holds a box, release a lock, or find machines by PSID.
---

# Monitoring and locking a lab server (NOGA)

Generic recipe for "watch server X until it frees up, take it, then set it up". Works for any
host in the NOGA pool; substitute `$HOST`.

⚠ **Except `l-fwminireg-*` — never take those.** NOGA reports them free while CI is running on
them. See skill `regression-repro`.

## Query, take, release

```bash
CLI=/.autodirect/sw_tools/Internal/Noga/RELEASE/latest/cli/noga_manage.py
HOST=l-fwreg-171                              # any pool host

python3 $CLI -ql -t host -n $HOST             # query -> Status.lock_owner / Status.lock_time_out
python3 $CLI -l  -t host -n $HOST -L 8        # take for 8 h; also renews when already ours
python3 $CLI -u  -t host -n $HOST             # release
```

`-l` on a host you already hold just extends the lease, so a monitor can call it blindly.
A refused grab is harmless — keep polling.

Find machines by PSID:

```bash
/mswg/projects/fw/fw_ver/hca_fw_tools/noga_allocation/get_setups_info.py \
    --team_name hca_fw --where "psid <PSID>"
```

## Reserve via the jmake wrappers — malloc / extend / cancel

These are jmake wrappers over the lab reservation aliases (`malloc`/`extend_my_alloc`/
`scancelme` in `/mswg/projects/fw/fw_ver/hca_fw_tools/.fwvalias`). Run from any dev box:

```bash
# Inventory / find state:
jmake --reg-info                     # full regression-server inventory (minfo)
jmake --reg-idle                     # idle servers (midle)
jmake --reg-mine                     # servers currently allocated to me (sqme)

# MALLOC — allocate the failing box (default 8h):
jmake --reg-malloc <machine>         # = malloc <machine> -t 8
#   If it prints "Resource locked by <holder> until <ts>": it's taken — wait for that
#   time or ping the holder; do NOT reproduce on a different host.
#   If it prints "Resource <machine> not in allocation pool (missing
#   HCA_FW_ALLOCATION_POOL_HOST label)": that box isn't in the malloc/sqme pool (some
#   dedicated BRONCO/BF reg boxes carry only the PARTITION_NOGA_ALLOC_reg label). malloc
#   and --reg-mine can't see it — lock it DIRECTLY via Noga instead (same lock the
#   regression/other users use; see the Noga fallback below). A direct Noga lock will NOT
#   show in `jmake --reg-mine`/sqme (sqme filters on HCA_FW_ALLOCATION_POOL_HOST) — confirm
#   you own it with `noga_manage.py -q -n <machine> -D | grep lock_owner` instead.

# EXTEND — add 3h to my current allocation (run before it expires mid-repro):
jmake --reg-extend                   # = extend_my_alloc
#   INTERACTIVE when you hold >1 box: it lists them and reads a number from stdin —
#   non-interactive shells get EOFError. Pipe the selection: `echo <n> | jmake --reg-extend`.
#   *** Run `jmake --reg-mine` FIRST and read <n> off that list. *** The order is not the order
#   you locked them in, and `echo 1` silently extends whichever box happens to be listed first —
#   which also RESETS that box's end time to NOW+3h, shortening it if it had longer to run.
#   Seen 2026-09-21: meant to extend l-fwreg-217 (40 min left), `echo 1` hit l-fwreg-146 instead.
#   Semantics: extend = NOW+3h (replaces the old end time; can even SHORTEN a fresh 8h lease).
#   Verify what you actually have with `jmake --reg-mine` (TIME LEFT column is unambiguous;
#   raw Noga lock_time_out timestamps are in the Noga DB timezone — trust TIME LEFT, not tz math).

# CANCEL — release my allocation(s) when done:
jmake --reg-cancel                   # = scancelme

# Confirm the lock + owner (Noga, authoritative):
python3 /.autodirect/sw_tools/Internal/Noga/RELEASE/latest/cli/noga_manage.py \
  -q -n <machine> -D 2>&1 | grep -E 'Status\.(status|lock_owner|lock_time_out)'
# want: Status.status = Lock, Status.lock_owner = <you>
```
> Raw fallback if `jmake --reg-*` is unavailable: `source /mswg/projects/fw/fw_ver/hca_fw_tools/.fwvalias`
> then `malloc <machine> -t <hours>` / `extend_my_alloc` / `scancelme` / `sqme` / `midle` / `minfo`.
> Or lock via Noga directly (REQUIRED for boxes lacking the malloc-pool label, above):
> `noga_manage.py -l -t server -n <machine> -L <hours> -N "repro #<ticket>"` — the `-t server`
> (type) is mandatory for `lock` ("required either id or type+name or expr"); `-L` is hours;
> verify with `-q -n <machine> -D | grep -E 'Status\.(status|lock_owner|lock_time_out)'`.
> Unlock with `noga_manage.py -u -t server -n <machine>`. Respect existing locks — see memory
> respect-reg-server-locks.

> **Noga REST outage (HTTP 504) — recognize it, don't misread it.** `malloc`, `minfo`, `sqme`
> AND `noga_manage.py -q` all go through the same REST backend
> (`https://noga.nvidia.com/app/server/php/rest_api/`). When every one of them hangs/504s,
> it's a backend outage — NOT a lock conflict; never read malloc's 504 traceback as "box
> taken". Cheap health probe (lightest api_cmd):
> ```bash
> curl -sS -m 20 -o /dev/null -w "%{http_code}\n" \
>   "https://noga.nvidia.com/app/server/php/rest_api/?api_cmd=get_teams"   # 504 = backend down
> ```
> The web UI `/app/view/` returning 200 proves nothing (static page; its data comes from the
> same dead REST). Outages self-heal (observed: hours) — poll the probe in the background and
> re-query owners on recovery. The only non-REST alternative is Noga's direct Oracle DB API
> (`/.autodirect/sw_tools/Internal/Noga/RELEASE/latest/import/lib/noga_api.py`, class
> `Noga_DB_API`: `set_cursor` → `res_type_by_name('server')` → `find_matching_ids(<box>)` →
> `get_resource_data_by_id`) — but it needs the Oracle client (`libclntsh.so`), which exists
> on STM/MARS hosts only (dev boxes lack `/opt/oraclient`); run it there with the
> `$MARS_PYVERSION` python.
>
> **`lock_time_out` is Israel time, and expiry LAGS.** Convert with
> `date -d 'TZ="Asia/Jerusalem" <ts>'`. A box can stay `Lock` well past its lock_time_out
> (lazy auto-release sweep, or the holder extended) — monitor the actual `Status.status`
> flip to `Release`, never schedule around the timestamp.

> Moved here from the repro procedure on 2026-09-16: this is lock machinery and belongs with the
> rest of it, not duplicated inside a reproduction runbook.

## Reading `lock_time_out`

It is **UTC**, formatted `DD-MON-YY HH.MM.SS.ffffff AM/PM` (local CST = UTC+8). Always convert
before reasoning about it; doing it in your head has caused a 23-minute error before.

```bash
~/myGit/crosslv/assets/skills/noga-lock/scripts/noga_expiry.py "13-AUG-26 09.05.12.123456 AM"
# prints seconds past expiry; >0 means the lease has lapsed
```

## When you may take a lock

1. `lock_owner` is empty — free, take it.
2. `lock_owner` is set **but** `lock_time_out` is more than a grace period (15 min works well)
   in the past. **NOGA does not clear `lock_owner` when a lease expires**, so a monitor that only
   waits for an empty owner can idle for hours beside a lock that already lapsed. This cost ~7 h
   of waiting once before the rule was understood.
3. Otherwise wait. Do not fight a live holder; in this pool `mars_reg` is the regression service
   and always wins by convention. Note its habit: it releases around **13:05–13:15 CST**,
   typically well before its nominal timeout.

## The monitor loop

```bash
~/myGit/crosslv/assets/skills/noga-lock/scripts/noga_wait.sh --help
~/myGit/crosslv/assets/skills/noga-lock/scripts/noga_wait.sh -n l-fwreg-171 -L 8 --hours 8 \
    --then 'bash <your env_rebuild script>'
```

**Read the current runtime adapter before starting a long watch:**
`references/hosts/claude.md` in Claude Code or `references/hosts/codex.md` in Codex. In either
runtime, chain setup into the same watcher with `--then`, avoid duplicate watchers, and retain a
way to observe liveness. The script emits a heartbeat every ~20 iterations with both owner and
seconds-to-expiry.

## Practical notes

- **A client restart or session transition can kill managed background tasks.** Re-check
  liveness with `ps` and the output-file mtime before assuming the watcher survived. A silent
  dead monitor looks exactly like a busy one.
- **Poll at 15 s — never longer.** The poll interval *is* the window in which somebody else can
  take the box out from under you. Two incidents, both lost boxes:
  - 2026-08-20: mars_reg's lock on m-fwreg-016 expired at 18:12:58 and a monitor polling every
    5 minutes found it already held by another user on its next check — who then kept it for the
    following 8 hours.
  - 2026-09-02: a monitor polling every **60 s** saw m-fwreg-017 go `Release` at 19:28:32 and
    fired `jmake --reg-malloc` in the *same second* — and still lost it to another user. The
    malloc round-trip through the Noga REST layer takes ~6 s, so on top of that you may be up to
    a full poll interval behind whoever else is watching. 60 s was not tight enough.
  15 s costs ~4x the queries and is still trivial load. Do not stretch it back out for
  log readability — log only state CHANGES plus a ~20 min heartbeat instead.
- **One agent per box — `noga_wait.sh` is already multi-instance safe.** Give each agent its
  own `-n <host>` and run it as a background task; the script writes progress to **stdout**, so
  every instance is isolated by its own task output. Do not fan out with a script that hardcodes
  a log path or a result file — two instances then append to the same log and the second grab
  overwrites the first one's result.
  ```bash
  # agent A                                        # agent B
  scripts/noga_wait.sh -n m-fwreg-017 -L 8 &       scripts/noga_wait.sh -n m-fwreg-018 -L 8 &
  ```
- **Never point two agents at the SAME box.** The success test is `lock_owner == $USER`, which
  cannot tell two of your own agents apart: the one that lost the malloc race still reads back
  its own username and also reports `LOCK_ACQUIRED`. Both then think they own it and will
  happily burn FW on top of each other.
- **Losing the race is normal; the script must survive it.** After malloc, always re-query and
  require `lock_owner == $USER` before declaring success, then keep looping for the next
  `Release`. A malloc that returns 0 is not proof you own the box.
- **A `Status.status` that parses as empty is not a Release.** Noga queries occasionally return
  a malformed record (observed once in a 4 h watch). Treat an unparseable status as "unknown,
  retry", never as an opportunity to grab — and never as a reason to stop watching.
- Reaching the box:
  ```bash
  sshpass -p <pw> ssh -o StrictHostKeyChecking=no -o ControlMaster=auto \
    -o ControlPath=/tmp/ssh_mux_<box> -o ControlPersist=28800 root@$HOST
  ```
  Give each box its **own** mux socket, otherwise concurrent work on two machines crosses wires.
- After any power cycle the mux socket is stale — close it (`ssh -O exit`) before reconnecting.
- **Verify the final state yourself instead of trusting the setup script's own summary.**
  Scripts have reported READY off a stale or partially-applied config more than once.
- **Release locks you are no longer using** — holding several boxes "just in case" blocks other
  teams.

## "Don't release it" means you must RENEW it

A NOGA lease is not a hold — it is a countdown. When it lapses, `mars_reg` takes the box
within minutes, and the outcome is identical to having called `unlock`. If Peter says
*don't release the machine*, honouring that requires **actively renewing before expiry**,
not merely refraining from `-u`.

Renew by re-issuing the lock; it resets the clock rather than failing:

```bash
python3 "$CLI" -l -t host -n "$HOST" -L 8 -N "<why>"      # resets to 8h from now
python3 "$CLI" -q -n "$HOST" -t server -D | grep lock_time_out   # always read back
```

`noga_wait.sh` only **acquires**. It does not keep the box. For a multi-hour hold, arm a
renewal watchdog right after acquiring — e.g. a `Monitor` (persistent) that re-locks well
before `lock_time_out`:

```bash
while true; do
  python3 "$CLI" -l -t host -n "$HOST" -L 8 -N "hold" >/dev/null 2>&1
  echo "renewed $(date -u '+%F %H:%M')"
  sleep 3600
done
```

Lost m-fwreg-017 this way on 2026-09-08→09: the lease ran out overnight, `mars_reg` picked
it up, and the work stalled — even though nothing ever called `unlock`.

### Holding a box across hours: the watchdog itself keeps dying

A `Monitor` (persistent) running a `while true; do ... sleep N; done` renewal loop is killed
by this harness after roughly one to two hours, always with **exit 144**. Observed twice on
2026-09-09 with different sleep intervals (3000 s and 300 s), so it is the harness, not the
script.

This is survivable, because each `-l` call resets the lease to the full 8 h and you get a
task notification the moment the watchdog dies — **re-arm it then**. What is not survivable
is a *silent* watchdog: the first one printed nothing for 50 min, died, and the box was gone
before anyone noticed. Make the loop:

- poll every ~5 min, not every 50
- **check `lock_owner` first**, re-lock immediately if it is not you, and say so loudly
- print a heartbeat every ~30 min so a dead watchdog is obvious

Also seen on 2026-09-09 and unexplained: a lock held by `pexiang` with 7 h left on the lease
**disappeared on its own** — no `unlock` was ever issued, and NOGA's CLI has no history or
audit subcommand to find out who cleared it. Assume a hold can evaporate and let the watchdog
re-take it; do not assume `lock_time_out` in the future means you still own the box.

## The two traps in `noga_wait.sh` (both cost a silent dead monitor)

`noga_expiry.py` uses its **exit code as the verdict** (0 = expired, 1 = still valid,
2 = unparseable) *and* prints the number. The consumer must take the value and discard
the status — getting either half wrong breaks the watch in a way that looks like nothing
happened:

```bash
exp=$(python3 "$EXPIRY" "$tout" 2>/dev/null | head -1) || true
#                                             ^^^^^^^     ^^^^^^^
#                                             value       status
```

- Drop `| head -1` (or use the old `|| echo 0`): `$exp` becomes two lines and every poll
  dies on `[: integer expression expected`. The `--grace` path is then dead, so an
  expired-but-owned lease is never grabbed — NOGA does not clear `lock_owner` on expiry,
  so that is the normal state of a free box. Cost: a 7-hour silent wait.
- Drop `|| true`: `set -euo pipefail` turns exit 1 into a **silent script death** — no
  `GAVE_UP`, no message, the monitor simply vanishes after the banner line. Cost: you
  believe a box is being watched when nothing is watching it.

Both were hit on 2026-09-07/08, the second while fixing the first.

**Do not model a multi-hour wait as one blocking tool call.** Follow the current runtime adapter
and verify the watcher with `ps` plus its heartbeat log. Do not assume that `nohup` or `setsid`
launched from a managed shell will outlive that shell.

Smoke-test any change to the script before trusting it:

```bash
timeout 40 bash noga_wait.sh -n <box> --hours 1 --poll 10; echo $?   # want 124
```

`124` means `timeout` killed a still-running script — i.e. it survived several polls.
Any other code means it died on its own.

## Related

- Firmware config on a BlueField box once you have it: skill `bluefield-fwconfig`.
- If a card stops enumerating: skill `nic-livefish-recovery`.
