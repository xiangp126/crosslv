---
name: noga-lock
description: Reserve, extend, release and monitor lab servers in the NOGA pool — both the `jmake --reg-malloc/--reg-extend/--reg-cancel` wrappers and raw noga_manage.py, the unattended wait-then-grab loop for a box held by mars_reg, and how to read the UTC lock_time_out. Use when asked to take/grab/lock a lab machine, malloc or extend an allocation, wait for a server to free up, check who holds a box, release a lock, or find machines by PSID.
---

# NOGA lab-server locks

Query, take, extend and release any host in the NOGA pool (substitute `$HOST`); watch a busy one
until it frees up, take it, then set it up.

- **Never take `l-fwminireg-*`** — dedicated CI machines; NOGA reports them free while CI is
  running on them. See skill `regression-repro`.
- **Respect existing locks.** A Noga lock is advisory — SSH still works — so never SSH into or run
  anything (flint, mlxconfig, utopx, burn, reset) on a box whose `lock_owner` is another user; work
  only on a box you hold or one that is free, and to get a held box, wait for it to free up and take
  it first. Do not fight a live holder.

## Commands

### Raw Noga — `noga_manage.py`

```bash
CLI=/.autodirect/sw_tools/Internal/Noga/RELEASE/latest/cli/noga_manage.py
HOST=l-fwreg-171                              # any pool host

# Authoritative lock + owner check. Want: Status.status = Lock, Status.lock_owner = <you>
python3 $CLI -q -t server -n $HOST | grep -E 'Status\.(status|lock_owner|lock_time_out)'
python3 $CLI -l -t server -n $HOST -L 8 -N "<why>"   # take for 8 h (-L is hours); renews to 8 h from now when yours
python3 $CLI -u -t server -n $HOST                   # release
```

- **`-t server`, always.** Pool boxes are NOGA type `Server` (every query prints
  `Resource Type = Server`). `-t` is required for `-l`/`-u` by name (without it:
  `[FATAL:] For action 'lock' required either id or type+name or expr`). `-t host` is a different
  type, not an alias: Noga resolves `-n` by name alone, so a lock or a `Status.*` read still hits the
  right box, but a `-t host` query renders the Host attribute set and drops `Common.labels`.
- `-l` on a box you already hold renews instead of failing. Never `-l` a box another user holds
  with a live lease: unlike `jmake --reg-malloc`, `noga_manage.py` does no owner check of its own,
  and Noga treats the call as a lock break, which takes the box from its holder wherever
  permissions allow. A refused grab is harmless — keep polling.
- Find machines by PSID:
  ```bash
  /mswg/projects/fw/fw_ver/hca_fw_tools/noga_allocation/get_setups_info.py \
      --team_name hca_fw --where "psid <PSID>"
  ```

### jmake wrappers — the allocation pool

Wrappers over the reservation aliases in `/mswg/projects/fw/fw_ver/hca_fw_tools/.fwvalias`; run
from any dev box. If `jmake --reg-*` is unavailable, `source` that file and call the alias.

| jmake | alias | does |
|---|---|---|
| `jmake --reg-info` | `minfo` | full regression-server inventory |
| `jmake --reg-idle` | `midle` | idle servers |
| `jmake --reg-mine` | `sqme` | servers currently allocated to me, with the **TIME LEFT** column |
| `jmake --reg-malloc <machine>` | `malloc <machine> -t 8` | allocate, default 8h (alias: `malloc <machine> -t <hours>`) |
| `jmake --reg-extend` | `extend_my_alloc` | end time := NOW+3h — see Extend |
| `jmake --reg-cancel` | `scancelme` (`noga_alloc.py --cancel_me`) | release — see Release |

`jmake --reg-malloc` outcomes:

- `Resource locked by <holder> until <ts>` — taken. Wait for that time (`noga_wait.sh`, below) or
  ping the holder; do NOT reproduce on a different host.
- `Resource <machine> not in allocation pool (missing HCA_FW_ALLOCATION_POOL_HOST label)` — the
  box is not in the malloc/sqme pool (some dedicated BRONCO/BF reg boxes carry only the
  `PARTITION_NOGA_ALLOC_reg` label), so malloc and `--reg-mine` cannot see it. Lock it DIRECTLY
  via Noga (`-l -t server` form above — the same lock the regression and other users take). That
  lock will NOT show in `jmake --reg-mine`/sqme (sqme filters on `HCA_FW_ALLOCATION_POOL_HOST`);
  confirm ownership with `noga_manage.py -q -t server -n <machine> | grep lock_owner`.
- Hangs, or an HTTP 504 traceback — never read it as "box taken"; check for a Noga REST outage
  (below).

### Extend — `jmake --reg-extend`

Sets the end time to **NOW+3h**. It *replaces*, it does not add — it can SHORTEN a fresh 8h lease.

| TIME LEFT (`jmake --reg-mine`) | do |
|---|---|
| **> 3h** | **do NOT extend** — it would SHORTEN the lease |
| < 3h | extend; the only window where it is a net gain |
| < 1h | extend now, and verify the read-back before starting anything long |

- **Always INTERACTIVE**: it prints a numbered menu of your boxes (`0` = All resources) and reads
  the entry from stdin, even when you hold a single box; a non-interactive shell gets `EOFError`.
  Always pipe the entry: `echo <n> | jmake --reg-extend`. Never `0` — it resets EVERY box you hold
  to NOW+3h.
- Read `<n>` off that menu FIRST: `jmake --reg-extend </dev/null` prints it, then stops at the
  prompt with `EOFError`, extending nothing. The menu is sorted by partition, then host name — NOT
  in `jmake --reg-mine` order (sorted by end time) — so a number taken from `--reg-mine`, or a blind
  `echo 1`, can extend the wrong box and reset *its* end time to NOW+3h, shortening it if it had
  longer to run.
- Verify the result with `jmake --reg-mine` (TIME LEFT — see Reading `lock_time_out`).

### Release — one box by name

`jmake --reg-cancel` is interactive like extend, and riskier: menu entry 0 is "All resources",
which releases EVERY box under your name — including boxes another session or agent is working
on. When you hold more than one, release the one box by name:

```bash
bash -c 'source /mswg/projects/fw/fw_ver/hca_fw_tools/.fwvalias >/dev/null 2>&1;
  ensure_min_python_for_noga_alloc &&
  /mswg/projects/fw/fw_ver/hca_fw_tools/noga_allocation/noga_alloc.py --team_name hca_fw \
    --resource_name <machine> --action release' </dev/null
# -> "-INFO-release request was successful"
```

Read back: `noga_manage.py -q -t server -n <machine>` shows `Status.status = Release`, and
`jmake --reg-mine` still lists your other boxes.

Release locks you are no longer using — holding several boxes "just in case" blocks other teams.

### Noga REST outage (HTTP 504)

`malloc`, `minfo`, `sqme` and `noga_manage.py -q` all go through one REST backend
(`https://noga.nvidia.com/app/server/php/rest_api/`). When every one of them hangs or 504s, the
backend is down — it is NOT a lock conflict; never read malloc's 504 traceback as "box taken".

```bash
curl -sS -m 20 -o /dev/null -w "%{http_code}\n" \
  "https://noga.nvidia.com/app/server/php/rest_api/?api_cmd=get_teams"   # lightest api_cmd; 504 = backend down
```

- The web UI `/app/view/` returning 200 proves nothing — a static page fed by the same REST.
- Outages self-heal (hours observed): poll the probe in the background, re-query owners on recovery.
- The only non-REST path is Noga's direct Oracle DB API:
  `/.autodirect/sw_tools/Internal/Noga/RELEASE/latest/import/lib/noga_api.py`, class `Noga_DB_API`:
  `set_cursor` → `res_type_by_name('server')` → `find_matching_ids(<box>)` → `get_resource_data_by_id`.
  It needs the Oracle client (`libclntsh.so`), present on STM/MARS hosts only (dev boxes lack
  `/opt/oraclient`); run it there with the `$MARS_PYVERSION` python.

## Reading `lock_time_out`

Format: `DD-MON-YY HH.MM.SS.ffffff AM/PM`. Convert with a tool and check the clock with `date` —
never in your head; mental arithmetic on lease deadlines has produced a 23-minute error.

It is **UTC** (local CST = UTC+8), not Israel time: a `lock_time_out` of `10.07.57 AM` matched
an 18:07 CST end time in `jmake --reg-mine`. Convert with:

```bash
~/myGit/crosslv/assets/skills/noga-lock/scripts/noga_expiry.py "13-AUG-26 09.05.12.123456 AM"
# prints seconds past expiry; >0 means the lease has lapsed
```

For a malloc'd box, read TIME LEFT from `jmake --reg-mine` instead; it needs no conversion
(its "Lock ENDTIME (IST)" column actually shows local CST). Expiry also LAGS: a box can stay `Lock` well past
its `lock_time_out` (lazy auto-release sweep, or the holder extended). Watch for the actual
`Status.status` flip to `Release`; never schedule around the timestamp.

## When you may take a lock

1. `lock_owner` is empty — free, take it.
2. `lock_owner` is set **but** `lock_time_out` is more than a grace period (15 min works well) in
   the past. **NOGA does not clear `lock_owner` when a lease expires** — expired-but-owned is the
   normal state of a free box, so a monitor that waits only for an empty owner can idle for hours
   beside a lapsed lock.
3. Otherwise wait. In this pool `mars_reg` is the regression service and always wins by
   convention; it releases around **13:05–13:15 CST**, typically well before its nominal timeout.

### `mars_reg` takes boxes back for its nightly session

It does so **even when your lock has hours left** (seen on a fresh 8h `jmake --reg-malloc` lease:
owner `mars_reg` by ~01:50 CST, box rebooted at 02:00 CST, then the regression installed its tools).

- Plan long flows (burn, cold boots, several cases) to finish before **~01:30 CST**, or start them
  after the ~13:00 CST release. The ARGAMAN CSP 0.8 nightly sessions start around 01:40–01:45 CST;
  check the session times for your setup.
- Takeback signature mid-flow: "MARS python not found" (python/NFS gone), flint unable to open the
  device, Fwreset failing — it looks like a broken environment. When these suddenly fail, query
  `lock_owner` before debugging the environment. Once the box has been taken, stop touching it and
  let `noga_wait.sh` take it back after the release.

## Waiting for a busy box — `noga_wait.sh`

```bash
~/myGit/crosslv/assets/skills/noga-lock/scripts/noga_wait.sh --help
~/myGit/crosslv/assets/skills/noga-lock/scripts/noga_wait.sh -n l-fwreg-171 -L 8 --hours 8 \
    --then 'bash <your env_rebuild script>'
```

The script polls every 15 s by default (never pass a larger `--poll`) and prints a heartbeat every
20 polls — about every 5 min at 15 s — with the owner and the seconds past expiry (negative = time
left). It grabs only when `Status.status` is `Release` or the lease expired more than `--grace`
seconds ago; a status that is neither `Lock` nor `Release` is retried (`status unknown …`), never
grabbed. Between heartbeats it stays silent unless a query fails (`query failed, retrying`) or the
wait ends (`ALREADY_OURS`, `LOCK_ACQUIRED` or `GAVE_UP`).

Running it:

- **Read the current runtime adapter first**: `references/hosts/claude.md` in Claude Code,
  `references/hosts/codex.md` in Codex. In either runtime: chain setup into the same watcher with
  `--then`, avoid duplicate watchers, and retain a way to observe liveness.
- Do not model a multi-hour wait as one blocking tool call. Do not assume `nohup` or `setsid`
  launched from a managed shell will outlive that shell.
- **Verify liveness** with `ps` plus the output/heartbeat-log mtime (a live `noga_wait.sh` writes
  at least every ~5 min), and re-check after any client restart or session transition — those can
  kill managed background tasks. A silent dead monitor looks exactly like a busy one.

Rules for the watch:

- **Poll at 15 s — never longer.** The poll interval is the window in which somebody else takes
  the box: the malloc round-trip through the Noga REST layer alone takes ~6 s, and on top of that
  you may be up to a full poll interval behind whoever else is watching; 60 s loses the race even
  when malloc fires in the same second the box goes `Release`. 15 s is still trivial load. Do not stretch it for log readability —
  log only state CHANGES plus a periodic heartbeat (`noga_wait.sh`: every 20 polls, ~5 min).
- **One agent per box — `noga_wait.sh` is already multi-instance safe.** Give each agent its own
  `-n <host>` and run it as a background task; the script writes progress to **stdout**, so each
  instance is isolated by its own task output. Do not fan out with a script that hardcodes a log
  path or a result file — two instances then append to the same log and the second grab
  overwrites the first one's result.
  ```bash
  # agent A                                        # agent B
  scripts/noga_wait.sh -n <box-A> -L 8 &           scripts/noga_wait.sh -n <box-B> -L 8 &
  ```
- **Never point two agents at the SAME box.** The success test is `lock_owner == $USER`, which
  cannot tell two of your own agents apart: the one that lost the malloc race still reads back
  your username and also reports `LOCK_ACQUIRED`. Both then burn FW on top of each other.
- **Losing the race is normal; survive it.** After malloc, always re-query and require
  `lock_owner == $USER` before declaring success; otherwise keep looping for the next `Release`.
  A malloc that returns 0 is not proof you own the box.
- **A `Status.status` that parses as empty is not a Release.** Noga occasionally returns a
  malformed record. Treat an unparseable status as "unknown, retry" — never as a chance to grab,
  never as a reason to stop watching (`noga_wait.sh` does this).

### The two traps in `noga_wait.sh` — each one silently kills the monitor

`noga_expiry.py` prints the number *and* uses its **exit code as the verdict** (0 = expired,
1 = still valid, 2 = unparseable). The consumer must take the value and discard the status:

```bash
exp=$(python3 "$EXPIRY" "$tout" 2>/dev/null | head -1) || true
#                                             ^^^^^^^     ^^^^^^^
#                                             value       status
```

- Without `| head -1` (or with the old `|| echo 0`): `$exp` becomes two lines and every poll dies
  on `[: integer expression expected`. The `--grace` path is then dead, so an expired-but-owned
  lease — the normal state of a free box — is never grabbed.
- Without `|| true`: `set -euo pipefail` turns exit 1 into a **silent script death** — no
  `GAVE_UP`, no message; the monitor vanishes after the banner line while you believe the box is
  being watched.

Smoke-test any change to the script before trusting it:

```bash
timeout 40 bash noga_wait.sh -n <box> --hours 1 --poll 10; echo $?   # want 124
```

`124` means `timeout` killed a still-running script — it survived several polls. Any other code
means it died on its own.

## Keeping a box: extend, do not ask

**When a lease is running out, extend it — do not stop to ask.** Only an explicit instruction to
release that machine overrides this. Extending is cheap and reversible; losing a box is neither.
A NOGA lease is a countdown, not a hold: when it lapses, `mars_reg` takes the box within minutes —
exactly as if you had called `unlock` — and **re-provisions it**, so the burned FW, the installed
udriver and the driver bindings are gone (~15 min to rebuild, plus however long the next free
window is).

- **"Don't release the machine" (Peter) means RENEW it** before expiry — not merely refrain
  from `-u`.
- **Reactive, not scheduled.** TIME LEFT passes your eyes on its own — every `jmake --reg-mine`,
  every allocation banner. When you notice it running low, extend instead of mentioning it. Do not
  arm a daemon, compute when to come back, or report a number and wait. (An unattended multi-hour
  hold with nobody at the keyboard is the watchdog case below.)

Renew by the path you took the box with — never cross them:

| box taken with | renew with | when | effect |
|---|---|---|---|
| `jmake --reg-malloc` | `jmake --reg-extend`, menu entry `<n>` piped in (see Extend) | only when TIME LEFT < 3h | end time := **NOW+3h** |
| a direct Noga lock (`noga_manage.py -l`, `noga_wait.sh`) | `python3 "$CLI" -l -t server -n "$HOST" -L 8 -N "<why>"` | any time | lease := **NOW+8h** |

Do not renew a malloc'd box through Noga just because 8 h is more than 3 h. Read back after either
path:

```bash
python3 "$CLI" -q -t server -n "$HOST" | grep -E 'Status\.(lock_owner|lock_time_out)'
```

### Unattended multi-hour hold: a renewal watchdog

`noga_wait.sh` only **acquires**; it does not keep the box. For a multi-hour hold, arm a renewal
watchdog right after acquiring, as a background task that notifies you when it exits. The loop
must:

- poll about every **5 min**;
- **check `lock_owner` first**; if the box is not held by you, say so loudly and re-lock at once
  through `noga_wait.sh`, which grabs immediately when the box is takeable and otherwise waits for
  the release — never `-l` over another user's live lease;
- renew by the path you took the box with (`VIA`): `malloc` → `jmake --reg-extend`, only when TIME
  LEFT < 3h (once below 3h it extends on every poll, holding the lease near 3h); `noga` →
  `noga_manage.py -l` on every poll (lease := NOW+8h). A box `noga_wait.sh` re-took is `noga`;
- print a heartbeat about every **30 min** so a dead watchdog is obvious.

```bash
CLI=/.autodirect/sw_tools/Internal/Noga/RELEASE/latest/cli/noga_manage.py
S=~/myGit/crosslv/assets/skills/noga-lock/scripts
HOST=<box>
VIA=noga      # how you took it: noga = noga_manage.py -l or noga_wait.sh; malloc = jmake --reg-malloc
i=0
while true; do
  Q=$(python3 "$CLI" -q -t server -n "$HOST" 2>/dev/null)
  st=$(echo "$Q"    | awk -F'= ' '/^Status\.status/        {print $2}' | tr -d ' ')
  owner=$(echo "$Q" | awk -F'= ' '/^Status\.lock_owner/    {print $2}' | tr -d ' ')
  tout=$(echo "$Q"  | awk -F'= ' '/^Status\.lock_time_out/ {print $2}')
  if [ -z "$st" ]; then
    echo "query failed $(date '+%F %T') -- state unknown, retrying"   # never a reason to grab
  elif [ "$st" != Lock ] || [ "$owner" != "$USER" ]; then
    echo "!!!!! $HOST NOT HELD: status=$st owner=${owner:-<none>} $(date '+%F %T') -- re-locking"
    "$S/noga_wait.sh" -n "$HOST" -L 8 --hours 12 || exit 1   # grabs at once if takeable, else waits
    VIA=noga                                                 # noga_wait.sh locks directly via Noga
  elif [ "$VIA" = noga ]; then
    python3 "$CLI" -l -t server -n "$HOST" -L 8 -N "hold" >/dev/null 2>&1   # lease := NOW+8h
  else                                                       # malloc: extend only when TIME LEFT < 3h
    past=$(python3 "$S/noga_expiry.py" "$tout" 2>/dev/null | head -1) || true   # negative = s left
    if [ -n "$past" ] && [ "$past" -gt -10800 ]; then
      n=$(jmake --reg-extend </dev/null 2>/dev/null | awk -v h="$HOST" '$4 == h {print $2}')
      if [ -n "$n" ]; then
        echo "$n" | jmake --reg-extend >/dev/null 2>&1       # end time := NOW+3h
        echo "extended $HOST (menu entry $n) $(date '+%F %T')"
      else
        echo "!!!!! $HOST is not in the --reg-extend menu $(date '+%F %T')"
      fi
    fi
  fi
  [ $((i % 6)) -eq 0 ] && echo "heartbeat $HOST status=$st owner=${owner:-<none>} until=$tout $(date '+%F %T')"
  i=$((i + 1))
  sleep 300
done
```

The watchdog itself dies: in Claude Code a persistent `Monitor` running such a loop is killed after
roughly 1–2 hours, always with **exit 144**, whatever the sleep — the harness, not the script. That
is survivable because the lease still has time left and the exit notification arrives at once —
**re-arm it then**. A *silent* watchdog is not survivable: it dies unnoticed and the box is gone.

A hold can also vanish with hours left and no `unlock` ever issued, and NOGA's CLI has no history
or audit subcommand to find out who cleared it. Only `lock_owner` shows that you still own the box
— a `lock_time_out` in the future does not.

## On the box

```bash
sshpass -p <pw> ssh -o StrictHostKeyChecking=no -o ControlMaster=auto \
  -o ControlPath=/tmp/ssh_mux_<box> -o ControlPersist=28800 root@$HOST
```

- Give each box its **own** mux socket, otherwise concurrent work on two machines crosses wires.
- After any power cycle the mux socket is stale — close it (`ssh -O exit`) before reconnecting.
- **Verify the final state yourself** instead of trusting the setup script's own summary — scripts
  have reported READY off a stale or partially-applied config.

## Related

- Firmware config on a BlueField box once you have it: skill `bluefield-fwconfig`.
- If a card stops enumerating: skill `nic-livefish-recovery`.
