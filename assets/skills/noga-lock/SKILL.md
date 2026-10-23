---
name: noga-lock
description: Lock, renew, release and monitor lab servers in the NOGA pool — locking and renewing with noga_manage.py, one script (noga_watchdog.sh) that waits for a box, takes it and keeps it, releasing with jmake --reg-free, and how to read the UTC lock_time_out. Use when asked to take/grab/lock/malloc a lab machine, extend or keep a lock, wait for a server to free up, check who holds a box, release a lock, or find machines by PSID.
---

# NOGA lab-server locks

Query, take, extend and release any host in the NOGA pool (substitute `$HOST`); watch a busy one
until it frees up, take it, then set it up.

- **Lock with NOGA**: `noga_manage.py -l` or `scripts/noga_watchdog.sh`, and renew the same way.
  `jmake --reg-malloc` and `--reg-extend` are Peter's own shortcuts — do not use them, also when
  Peter says "malloc". A box he took with `jmake --reg-malloc` is a NOGA lock like any other and is
  renewed through NOGA.
- **Never take `l-fwminireg-*`** — dedicated CI machines; NOGA reports them free while CI is
  running on them. See skill `regression-repro`.
- **Lock only `fwreg` servers — `*-fwreg-*` hosts, the regression servers.** Never use an `fwdev`
  server (`l-fwdev-*`, NOGA partition `dev` or `userdev`): do not lock it, ssh into it or set it
  up, even when NOGA shows it `Release` — developers work on those boxes without taking a lock, so
  `Release` there does not mean idle. The listings also carry other non-`fwreg` hosts
  (`l-fwperf-*`, `l-fwvrt-*`, `icpe-*`); skip them too. A busy box is waited for; a substitute,
  when one is allowed at all, is another `*-fwreg-*` box.
- **Respect existing locks.** A Noga lock is advisory — SSH still works. On a box whose
  `lock_owner` is another user, read-only inspection is fine: log in and look (`who`, `last`, `ps`,
  `lspci`, `flint q`, logs), which is how you tell whether the holder is using it. Never change
  its state there (burn, `mlxconfig set`, reset, reboot, utopx, driver binding): work only on a box
  you hold or one that is free, and to get a held box, wait for it to free up and take it first.
  Do not fight a live holder: take over another user's live lock only on Peter's explicit order,
  and tell him whose lock it was.
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
  with a live lease unless Peter ordered the takeover: `noga_manage.py` does no owner check of its
  own, and Noga treats the call as a lock break, which takes the box from its holder wherever
  permissions allow. A refused grab is harmless — keep polling.
- Only `Status.status = Lock` with your user in `Status.lock_owner` proves you hold a box. A box
  without the `HCA_FW_ALLOCATION_POOL_HOST` label (some dedicated BRONCO/BF reg boxes carry only
  `PARTITION_NOGA_ALLOC_reg`) is missing from `jmake --reg-mine` even while you hold it; read its
  owner with the query above.
- A hang or an HTTP 504 traceback is never "box taken"; check for a Noga REST outage (below).
- Find machines by PSID. `--where "partition reg"` keeps the list to regression servers; without
  it the `l-fwdev-*` boxes with that card are listed too:
  ```bash
  /mswg/projects/fw/fw_ver/hca_fw_tools/noga_allocation/get_setups_info.py \
      --team_name hca_fw --where "psid <PSID>" --where "partition reg"
  ```

### jmake wrappers — listings and release

Wrappers over the aliases in `/mswg/projects/fw/fw_ver/hca_fw_tools/.fwvalias`; run from any dev
box. If `jmake --reg-*` is unavailable, `source` that file and call the alias.

| jmake | alias | does |
|---|---|---|
| `jmake --reg-info` | `minfo` | allocation-pool inventory, every partition but `userdev` — `fwdev` and `fwperf` boxes included |
| `jmake --reg-idle` | `midle` | idle boxes of that pool — take only the `*-fwreg-*` rows |
| `jmake --reg-mine` | `sqme` | servers locked by me, with the **TIME LEFT** column (pool boxes only) |
| `jmake --reg-free <server>[,<server>...]` | `noga_alloc.py --resource_name <server> --action release`, per box | release each named box you hold; others skipped and summarised — see Release |
| `jmake --reg-cancel` | `scancelme` (`noga_alloc.py --cancel_me`) | interactive menu; entry 0 releases ALL your boxes — do not use |

A box someone else holds is waited for (`noga_watchdog.sh --until-locked`, below) or its holder
pinged; never reproduce on a different host instead.

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

**Stop your own watchers for that box first.** A `noga_watchdog.sh` for the box (also when started
by its old name `noga_wait.sh`) re-locks it within one check after the release. Stop them, confirm
none is left with `ps -eo cmd | grep -cE '[n]oga_(watchdog|wait)\.sh.* <box>'` (the `[n]` keeps
grep from counting itself; a plain `pgrep -f` also counts the shell that runs it), then release.

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

`noga_manage.py`, `minfo`, `sqme` and `jmake --reg-free` all go through one REST backend
(`https://noga.nvidia.com/app/server/php/rest_api/`). When every one of them hangs or 504s, the
backend is down — it is NOT a lock conflict; never read a 504 traceback as "box taken".

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

For a box in the allocation pool, `jmake --reg-mine` shows the same end time with no conversion
needed (its "Lock ENDTIME (IST)" column actually shows local CST). Expiry also LAGS: a box can stay `Lock` well past
its `lock_time_out` (lazy auto-release sweep, or the holder extended). Watch for the actual
`Status.status` flip to `Release`; never schedule around the timestamp.

## When you may take a lock

1. `lock_owner` is empty — free, take it.
2. `lock_owner` is set **but** `lock_time_out` is more than 60 s in the past (the default `--grace`
   of `noga_watchdog.sh`; the 60 s only absorbs clock skew and a holder's last-second renewal).
   **NOGA does not clear `lock_owner` when a lease expires** — expired-but-owned is the normal state
   of a free box, so a monitor that waits only for an empty owner can idle for hours beside a lapsed
   lock.
3. Otherwise wait. In this pool `mars_reg` is the regression service and always wins by
   convention; it releases around **13:05–13:15 CST**, typically well before its nominal timeout.

**Lock first, then check.** Once a lease has expired, take the lock at once instead of waiting for
proof that the box is idle — holding the lock is what keeps the box from going to someone else.
Whether you may *touch* the box is decided afterwards, by the pre-touch check below.

### `mars_reg` takes boxes back for its nightly session

It does so **even when your lock has hours left**: owner `mars_reg` by ~01:50 CST, the box rebooted
at 02:00 CST, then the regression installs its tools.

- Plan long flows (burn, cold boots, several cases) to finish before **~01:30 CST**, or start them
  after the ~13:00 CST release. The ARGAMAN CSP 0.8 nightly sessions start around 01:40–01:45 CST;
  check the session times for your setup.
- Takeback signature mid-flow: "MARS python not found" (python/NFS gone), flint unable to open the
  device, Fwreset failing — it looks like a broken environment. When these suddenly fail, query
  `lock_owner` before debugging the environment. Once the box has been taken, stop touching it.
  The watchdog ends the watch on this takeover (see The renewal watchdog); take the box back —
  a new `noga_watchdog.sh --until-locked`, which waits for the release, then a watchdog — only
  when Peter asks again.

### Before touching any box you locked: confirm the MARS session is done with it

The check exists to establish one fact before the first burn, reset or mlxconfig: the regression
session that held the box has finished with it. Establish it once — it takes seconds; do not add
waiting windows on top.

1. **How did the box free up?**
   - **`mars_reg` released it before its `lock_time_out`** (`Status.status` flipped to `Release`
     while its lease still had time left): MARS releases the NOGA lock in its own teardown step
     `Done step (2:Release The Setup)`, so the session is done with the box.
   - **A `Release` at `mars_reg`'s `lock_time_out`, a lease that expired without a release, or you
     cannot tell**: NOGA drops an expired lease by itself while the session can still be running and
     starting new cases. Confirm the session reached that step. Newest session directory
     `/auto/sw_regression/host_fw/HCA_CORE_FWV/MARS/conf/results/<setup>/<sid>/` — once `<sid>.tgz`
     exists (written a few minutes after the release), read `session.log` out of it:
     ```bash
     tar -xzOf <dir>/<sid>.tgz --wildcards '*session.log' | grep -a 'Done step (2:Release The Setup)'
     ```
     (MARS log times are Israel time; `Teardown event: session_end` can be missing from the
     archived copy.) No `.tgz` and no release step means the session is still running or archiving:
     keep the lock, do not touch the box, look again in a few minutes.
2. **No regression process left on the box** — run it after every grab, whatever item 1 found;
   must print 0. Run it as its own `ssh` command: any
   other text in the same command line (e.g. a path under `/tmp/mars_tests`) matches the pattern
   and counts the command itself.
   ```bash
   ssh -o BatchMode=yes <box> 'ps -eo cmd | grep -cE "[u]topx\.exe|[R]egTools|[m]ars_tests|[F]wreset|[m]lxburn"'
   ```

Both hold → start. If a process is still there, keep the lock, do not touch the box, and wait for it
with a check that ends by itself — the busy count at 0 on three checks two minutes apart, or the lock
no longer yours — then report to Peter at once. Report also if it stays busy well past the expected
end of the session.

`/tmp/mars_tests` file times (`find /tmp/mars_tests -newermt "-30 min"`) are a fallback only, for
when the session record cannot be found (unknown setup name). Once the release is established they
add nothing but a 30-minute wait after the session's last test.

## Waiting for a busy box — `noga_watchdog.sh --until-locked`

One script waits for a box, takes it and keeps it: `scripts/noga_watchdog.sh`. With
`--until-locked` it ends as soon as the box is yours; without it, it keeps the box (The renewal
watchdog, below). `noga_wait.sh` is the old name for `noga_watchdog.sh --until-locked` and takes the
same options; it stays for command lines in older documents.

```bash
~/myGit/crosslv/assets/skills/noga-lock/scripts/noga_watchdog.sh --help
~/myGit/crosslv/assets/skills/noga-lock/scripts/noga_watchdog.sh l-fwreg-171 --until-locked -L 8 --hours 8
```

The script checks every 15 s by default (never pass a larger `--poll`), counted from the start of
one check to the start of the next: a NOGA query itself takes 2–5 s, so `query; sleep 15` would
check only about every 18 s. While it waits it prints a heartbeat every 5 min with the status, the
owner and the seconds past expiry (negative = time left). It grabs only when `Status.status` is
`Release` or the lease expired more than `--grace` seconds ago (default 60); a status that is
neither `Lock` nor `Release` is retried (`query failed or record unparsable …`), never grabbed.
Between heartbeats it stays silent unless a query fails or the wait ends (`ALREADY_OURS`,
`LOCK_ACQUIRED` or `GAVE_UP`).

Running it:

- **Report the grab the moment it happens** — which box, when, until when — in Claude Code and in
  Codex alike. Wait with `--until-locked`: the run ends on `LOCK_ACQUIRED`, `ALREADY_OURS` or
  `GAVE_UP`, and that end is the signal to report. Then run the pre-touch check, then start the
  watchdog. Never wait without `--until-locked`: once that run takes the box it keeps holding and
  never ends, so the grab goes unreported.
- **Read the current runtime adapter first**: `references/hosts/claude.md` in Claude Code,
  `references/hosts/codex.md` in Codex. It says how the end of the wait reaches you. In either
  runtime avoid duplicate watchers and keep a way to observe liveness.
- **No `--then` when someone is waiting for the box**: the chain runs before the wait ends, so the
  report comes only after setup. Report, then start setup. In an unattended wait, whatever `--then`
  runs must start with the pre-touch check and must not burn, reset or mlxconfig the box until it
  passes — the grab does not wait for the box to be idle.
- Do not model a multi-hour wait as one blocking tool call. Do not assume `nohup` or `setsid`
  launched from a managed shell will outlive that shell.
- **Verify liveness** with `ps` plus the output/heartbeat-log mtime (a live run writes at least
  every 5 min while it waits, every 30 min while it holds), and re-check after any client restart or
  session transition — those can kill managed background tasks. A silent dead monitor looks exactly
  like a busy one.

Rules for the watch:

- **Poll at 15 s — never longer.** The poll interval is the window in which somebody else takes
  the box: a lock call through the Noga REST layer alone takes seconds, and on top of that you may
  be up to a full poll interval behind whoever else is watching; 60 s loses the race even when the
  lock call fires in the same second the box goes `Release`. 15 s is still trivial load. Do not
  stretch it for log readability — log only state CHANGES plus a periodic heartbeat (every 5 min
  while waiting).
- **One agent per box — the script is already multi-instance safe.** Give each agent its own
  host and run it as a background task; the script writes progress to **stdout**, so each
  instance is isolated by its own task output. Do not fan out with a script that hardcodes a log
  path or a result file — two instances then append to the same log and the second grab
  overwrites the first one's result.
  ```bash
  # agent A                                                  # agent B
  scripts/noga_watchdog.sh <box-A> --until-locked &          scripts/noga_watchdog.sh <box-B> --until-locked &
  ```
- **Never point two agents at the SAME box.** The success test is `lock_owner == $USER`, which
  cannot tell two of your own agents apart: the one that lost the race still reads back your
  username and also reports `LOCK_ACQUIRED`. Both then burn FW on top of each other.
- **Losing the race is normal; survive it.** After a lock call, always re-query and require
  `lock_owner == $USER` before declaring success; otherwise keep looping for the next `Release`.
  A lock call that returns 0 is not proof you own the box.
- **A `Status.status` that parses as empty is not a Release.** Noga occasionally returns a
  malformed record. Treat an unparseable status as "unknown, retry" — never as a chance to grab,
  never as a reason to stop watching (the script does this).

### The parsing traps in `noga_watchdog.sh`

A watch runs for hours, so a bad reply must never end it: the script runs without `set -e`, and
two guards stay in place.

**A field the record does not carry.** Each field is read with an `awk` anchored on its name, so a
reply without a `Status.status =` line (a malformed one) reads as an empty status — "unknown,
retry" — never as `Release`.

**The exit code of `noga_expiry.py`.** It prints the number *and* uses its **exit code as the verdict** (0 = expired,
1 = still valid, 2 = unparseable). The consumer must take the value and discard the status:

```bash
e=$(python3 "$S/noga_expiry.py" "$tout" 2>/dev/null | head -1) || true
#                                                   ^^^^^^^     ^^^^^^^
#                                                   value       status
```

- Without `| head -1` (or with the old `|| echo 0`): the value becomes two lines and every check
  fails on `[: integer expression expected`. The `--grace` path is then dead, so an
  expired-but-owned lease — the normal state of a free box — is never grabbed.
- Without `|| true`, a script under `set -e` would die silently on exit 1 — no `GAVE_UP`, no
  message; the monitor vanishes after the banner line while you believe the box is being watched.

Smoke-test any change to the script before trusting it, against a name NOGA does not know — the
query fails every check, so nothing can be grabbed:

```bash
timeout 40 bash noga_watchdog.sh nonexistent-box --until-locked; echo $?   # want 124
```

`124` means `timeout` killed a still-running script — it survived several checks. Any other code
means it died on its own. The checks behind the `query failed or record unparsable` lines must
start 15 s apart.

To test the grab and hold logic end to end without NOGA, point `NOGA_CLI` at a stub that answers
`-q` with `Status.status` / `Status.lock_owner` / `Status.lock_time_out` lines from a state file,
locks on `-l`, and logs every call (a lock over someone else's live lease is a failure). With
`--poll 1`, drive the state file through:
foreign live lease → `Release` → own lease near expiry → another user's live lease → `Release` →
`mars_reg` live lease (exit 2). Also: a lease expired by more and by less than `--grace`, a malformed
reply, `--until-locked` with `--then`, and `--hours 0` (`GAVE_UP`).

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

Renew through NOGA when TIME LEFT is 1 h or less, whatever took the box — also one Peter took with
`jmake --reg-malloc`. On a box you hold, `-l` sets the lease to NOW+8h; then read it back:

```bash
python3 "$CLI" -l -t server -n "$HOST" -L 8 -N "<why>"
python3 "$CLI" -q -t server -n "$HOST" | grep -E 'Status\.(lock_owner|lock_time_out)'
```

### The renewal watchdog (arm it for every box you hold)

`noga_watchdog.sh` without `--until-locked` keeps the box. Start it right after you acquire a box and
have reported it — never on a box someone else holds: it would take the box itself without ending,
so nobody hears of the grab (see Waiting for a busy box). Run it as a background task that notifies
you when it exits:

```bash
mkdir -p <ticket dir>/logs/lock
~/myGit/crosslv/assets/skills/noga-lock/scripts/noga_watchdog.sh <box> \
    2>&1 | tee -a <ticket dir>/logs/lock/watchdog_<box>.log
```

It renews through NOGA whatever took the box (older command lines that add `noga` or `malloc`
after the box still work; the word is ignored). It checks every **15 s** (`--poll`), held or not:
a held lock can vanish at any time — a MARS session's teardown step `Release The Setup` releases
locks it does not own — and the box then goes to whoever checks first. What it does:

| state | action |
|---|---|
| not held: the start of the watch, a `Release`, or lost to anyone but `mars_reg` | grab as soon as the box is takeable — never `-l` over a live lease — then hold |
| held | renew when TIME LEFT <= **1h**, at most once every 5 min |
| held, then `Status.status = Lock` with `lock_owner = mars_reg` | the nightly takeover (~01:45–02:30 CST): report and **exit 2**. Do not re-grab; a new watch starts only when Peter asks again |
| not held for `--hours` in a row (default 14) | `GAVE_UP`, exit 1 |
| query fails or the record does not parse | retry at the next check — never read as a loss, never a grab |

A grab back does not end the watchdog, so it is silent too: read the `lost:` and `LOCK_ACQUIRED`
lines in its log whenever you report on the box. It checks first and sleeps after. It prints a
heartbeat every **30 min** while it holds the box and every 5 min while it waits, so a dead watchdog
is obvious. Never point two watchers at the same box; stop the old one before starting a new one.
Never edit a script a running watcher is executing — bash reads it as it goes; install a new
version with `mv`, which leaves running copies on the old file.

The watchdog itself dies: in Claude Code a persistent `Monitor` running such a loop is killed after
roughly 1–2 hours, always with **exit 144**, whatever the sleep — the harness, not the script. That
is survivable because the lease still has time left and the exit notification arrives at once —
**re-arm it then**. A *silent* watchdog is not survivable: it dies unnoticed and the box is gone.

A hold can also vanish with hours left and no `unlock` ever issued, and NOGA's CLI has no history
or audit subcommand to find out who cleared it. Only `lock_owner` shows that you still own the box
— a `lock_time_out` in the future does not.

## Related

- Logging in to a box you hold — ssh rules, root, a home that is not mounted: skill `lab-box-login`.
- Firmware config on a BlueField box once you have it: skill `bluefield-fwconfig`.
- If a card stops enumerating: skill `nic-livefish-recovery`.
