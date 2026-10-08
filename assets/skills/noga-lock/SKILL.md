---
name: noga-lock
description: Reserve, extend, release and monitor lab servers in the NOGA pool — both the `jmake --reg-malloc/--reg-extend/--reg-free/--reg-cancel` wrappers and raw noga_manage.py, the unattended wait-then-grab loop for a box held by mars_reg, and how to read the UTC lock_time_out. Use when asked to take/grab/lock a lab machine, malloc or extend an allocation, wait for a server to free up, check who holds a box, release a lock, or find machines by PSID.
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
- **Never release a box you hold without Peter's explicit permission** — not when the experiment
  is done, not when the box looks idle, not to be polite to other teams. When the work on it is
  finished, report that and ask; release only after he says so, and only the box(es) he named:
  `jmake --reg-free <server>[,<server>...]`.
- **Never let a lease you hold expire.** An expired lease loses the box exactly like releasing it
  (`mars_reg` or another user takes it within minutes). Renew every held box when **1 hour** is
  left on it, and arm the renewal watchdog (below) the moment you take a box — not only for
  unattended holds. Keep it running while you build, push or write docs.

## Commands

### Raw Noga — `noga_manage.py`

```bash
CLI=/.autodirect/sw_tools/Internal/Noga/RELEASE/latest/cli/noga_manage.py
HOST=l-fwreg-171                              # any pool host

# Authoritative lock + owner check. Want: Status.status = Lock, Status.lock_owner = <you>
python3 $CLI -q -t server -n $HOST | grep -E 'Status\.(status|lock_owner|lock_time_out)'
python3 $CLI -l -t server -n $HOST -L 8 -N "<why>"   # take for 8 h (-L is hours); renews to 8 h from now when yours
python3 $CLI -u -t server -n $HOST                   # release (prefer jmake --reg-free, which checks the owner)
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
| `jmake --reg-free <server>[,<server>...]` | `noga_alloc.py --resource_name <server> --action release`, per box | release each named box you hold; others skipped and summarised — see Release |
| `jmake --reg-cancel` | `scancelme` (`noga_alloc.py --cancel_me`) | interactive menu; entry 0 releases ALL your boxes — do not use |

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
| **> 1h** | do nothing yet |
| **<= 1h** | extend now (end time := NOW+3h) and read back the new TIME LEFT |

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

### Release — named boxes only

Only on Peter's explicit instruction (see the rule at the top), and only the box(es) he named:

```bash
jmake --reg-free <machine> </dev/null
jmake --reg-free <machine-a>,<machine-b> </dev/null            # several: comma-separated...
jmake --reg-free <machine-a> --reg-free <machine-b> </dev/null  # ...or repeated
```

Best effort: it de-duplicates the names, then handles each one in order
(`noga_manage.py -q -t server -n <machine>`):

| box | result |
|---|---|
| `l-fwminireg-*` | `✗ … CI/DoA machine`, skipped (never sent to NOGA) |
| unknown to NOGA / query failed | `✗ NOGA has no server named …`, skipped |
| already `Release` | `✓ <machine> is already free`, skipped |
| held by someone else | `✗ <machine> is held by <owner>, not <you>`, skipped |
| held by you | released with `noga_alloc.py --team_name hca_fw --resource_name <machine> --action release` (stdin from `/dev/null`), then read back: `✓ Released <machine>` or `✗ <machine> still reads … after the release` |

- After the loop: one `jmake --reg-mine` listing if anything was released, then — only when two or
  more names were given — `Summary of N servers` with `released:`, `already free:` and
  `not released:` (one line per box with the reason).
- Exit code 0 only if every named box ended free (released or already free); 1 if any was not.
- Because every box you hold in the list IS released, put only the boxes Peter named in the list
  and re-read it before running — a stray name of yours gets released too.

Never use `jmake --reg-cancel`: it is an interactive menu whose entry 0 ("All resources") releases
every box under your name, including boxes other sessions are working on, and without a terminal
it dies on `EOFError`. If jmake is unavailable, release by hand after checking the owner:

```bash
bash -c 'source /mswg/projects/fw/fw_ver/hca_fw_tools/.fwvalias >/dev/null 2>&1;
  ensure_min_python_for_noga_alloc &&
  /mswg/projects/fw/fw_ver/hca_fw_tools/noga_allocation/noga_alloc.py --team_name hca_fw \
    --resource_name <machine> --action release' </dev/null
```

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

### Before touching any box you locked: confirm no regression is running on it

Every time, however you got the lock — taken from `mars_reg`, found free, first to lock it, or
re-locked after a release. A NOGA `Release` or your own lock is not proof: MARS can still be
running, or finishing, a session on the box. Run all three before the first burn, reset or
mlxconfig, and do not touch the box until they pass:

1. No regression process — must print 0. Run it as its own `ssh` command: any other text in the
   same command line (e.g. a path under `/tmp/mars_tests`) matches the pattern and counts the
   command itself.
   ```bash
   ssh <box> 'ps -eo cmd | grep -cE "[u]topx\.exe|[R]egTools|[m]ars_tests|[F]wreset|[m]lxburn"'
   ```
2. No fresh MARS activity on the box — must print 0:
   ```bash
   ssh <box> 'find /tmp/mars_tests -newermt "-30 min" 2>/dev/null | wc -l'
   ```
3. The newest MARS session for the setup ended:
   `/auto/sw_regression/host_fw/HCA_CORE_FWV/MARS/conf/results/<setup>/<newest sid>/` must hold
   `<sid>.tgz`, and its `session.log` must contain `Teardown event: session_end` and
   `Done step (2:Release The Setup)` (MARS log times are Israel time). A newest session directory
   without the `.tgz` means the session may still be running or archiving — wait. The `.tgz` is
   written about a minute after the release; right after a `mars_reg` release, re-check once it
   appears.

If any check fails, stop, report it to Peter, and keep the lock.

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
- **Scheduled, not reactive.** Arm the renewal watchdog as soon as you hold a box; it renews at
  1 hour left. Noticing TIME LEFT by chance is not enough — a box was lost while the session was
  busy pushing commits. Also check TIME LEFT whenever you report progress.

Renew by the path you took the box with — never cross them:

| box taken with | renew with | when | effect |
|---|---|---|---|
| `jmake --reg-malloc` | `jmake --reg-extend`, menu entry `<n>` piped in (see Extend) | when TIME LEFT <= 1h | end time := **NOW+3h** |
| a direct Noga lock (`noga_manage.py -l`, `noga_wait.sh`) | `python3 "$CLI" -l -t server -n "$HOST" -L 8 -N "<why>"` | when TIME LEFT <= 1h | lease := **NOW+8h** |

Do not renew a malloc'd box through Noga just because 8 h is more than 3 h. Read back after either
path:

```bash
python3 "$CLI" -q -t server -n "$HOST" | grep -E 'Status\.(lock_owner|lock_time_out)'
```

### The renewal watchdog (arm it for every box you hold)

`noga_wait.sh` only **acquires**; it does not keep the box. Arm a renewal watchdog right after
acquiring any box, as a background task that notifies you when it exits. The loop
must:

- poll about every **5 min**;
- **check `lock_owner` first**; if the box is not held by you, say so loudly and re-lock at once
  through `noga_wait.sh`, which grabs immediately when the box is takeable and otherwise waits for
  the release — never `-l` over another user's live lease;
- renew when TIME LEFT <= **1h**, by the path you took the box with (`VIA`): `malloc` →
  `jmake --reg-extend` (end := NOW+3h); `noga` → `noga_manage.py -l` (lease := NOW+8h). A box
  `noga_wait.sh` re-took is `noga`;
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
  else                                                       # renew when TIME LEFT <= 1h
    past=$(python3 "$S/noga_expiry.py" "$tout" 2>/dev/null | head -1) || true   # negative = s left
    if [ -n "$past" ] && [ "$past" -gt -3600 ] && [ "$VIA" = noga ]; then
      python3 "$CLI" -l -t server -n "$HOST" -L 8 -N "hold" >/dev/null 2>&1   # lease := NOW+8h
      echo "renewed $HOST via noga $(date '+%F %T')"
    elif [ -n "$past" ] && [ "$past" -gt -3600 ]; then
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
