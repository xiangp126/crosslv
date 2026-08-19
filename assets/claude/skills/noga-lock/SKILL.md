---
name: noga-lock
description: Query, lock, release and monitor lab servers in the NOGA pool with noga_manage.py — including the unattended wait-then-grab loop for a box held by mars_reg, and how to read the UTC lock_time_out. Use when asked to take/grab/lock a lab machine, wait for a server to free up, check who holds a box, release a lock, or find machines by PSID.
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

## Reading `lock_time_out`

It is **UTC**, formatted `DD-MON-YY HH.MM.SS.ffffff AM/PM` (local CST = UTC+8). Always convert
before reasoning about it; doing it in your head has caused a 23-minute error before.

```bash
~/.claude/skills/noga-lock/scripts/noga_expiry.py "13-AUG-26 09.05.12.123456 AM"
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
~/.claude/skills/noga-lock/scripts/noga_wait.sh --help
~/.claude/skills/noga-lock/scripts/noga_wait.sh -n l-fwreg-171 -L 8 --hours 8 \
    --then 'bash /auto/fwgwork1/pexiang/bugZilla/OCI_EMU/tools/env_rebuild_171.sh'
```

Run it as a `run_in_background` Bash task and **chain the setup work into the same task**
(`--then`), so the whole grab-and-provision sequence is unattended and reports once at the end.
It emits a heartbeat every ~20 iterations carrying **both** the owner and seconds-to-expiry —
that one line answers "is the task alive" and "how much longer" at a glance.

## Practical notes

- **Session commands such as `/model` can kill background tasks.** If the user switches models
  mid-wait, re-check liveness (output-file mtime, plus `ps`) and restart the monitor. A silent
  dead monitor looks exactly like a busy one.
- Poll at 60 s. Anything faster only adds load; the interesting transition happens once a day.
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

## Related

- What to do with the box once you have it: skill `satpf-171` (sat-PF / l-fwreg-171).
- If a card stops enumerating: skill `nic-livefish-recovery`.
