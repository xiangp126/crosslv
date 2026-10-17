---
name: lab-box-login
description: >-
  Get a working shell on a lab or regression box (l-fwreg-*, m-fwreg-*, a BlueField ARM) from an
  agent: the ssh rules for tool calls and scripts (BatchMode, DISPLAY, ControlMaster, waiting for a
  rebooted box), logging in as root and where the shared lab passwords are, and repairing a box
  whose NFS home is not mounted (autofs, an empty /etc/auto.master, nfs-server). Use when ssh to a
  lab box fails with Permission denied (publickey) or hangs, a password popup appears, the home
  directory is missing on the box, or root is needed on a reg box or a DPU ARM.
---

# Logging in to a lab box

Which box you may touch at all is skill `noga-lock` (hold its lock; never `l-fwminireg-*`). This
skill is how to get a shell once you may.

## 1. Every ssh from a tool call or a script

- **`-o BatchMode=yes` on every ssh and scp, and `unset DISPLAY` at the top of a script.** A tool
  call has no TTY but inherits the user's X `DISPLAY`: when publickey auth fails, ssh falls back to
  a password, opens `ssh-askpass` on the user's desktop and blocks until someone answers.
  `SSH_ASKPASS_REQUIRE=never` would also stop it but needs OpenSSH 8.4; the dev box runs 8.2.
- A password popup appeared anyway → `ps -eo pid,ppid,etime,cmd | grep '[s]sh-askpass'` and walk
  the ppid chain up to the ssh and the script that started it.
- **One command per ssh.** In a bundled remote script a buffered `tail` hides an early failure
  until the run ends, and a bundled failure aborts opaquely.
- **One ControlMaster connection per box, on its own socket**:
  `-o ControlMaster=auto -o ControlPath=/tmp/ssh_mux_<box> -o ControlPersist=28800
  -o ServerAliveInterval=5 -o ServerAliveCountMax=3`. A master whose TCP connection died then exits
  within ~15 s; a socket shared by two boxes crosses wires.
- **Close the master before a power cycle** (`ssh -o ControlPath=<mux> -O exit <host>`). A master
  left behind is dead after the reboot, and an ssh that attaches to it hangs: `ConnectTimeout` does
  not cover a multiplexed session.
- **After a power cycle, wait for a new boot id over a fresh connection**:
  `cat /proc/sys/kernel/random/boot_id` with `-o ControlMaster=no -o ControlPath=none`, BatchMode,
  under `timeout`, until it differs from the id read before. `jmake --power-cycle` can return while
  the old boot still answers ssh. For a minute or two after boot publickey auth fails because the
  NFS home is not mounted yet — the same `Permission denied` as §3, but it clears by itself.

## 2. Root

```bash
unset DISPLAY SSH_ASKPASS
PW=...    # read from references/lab-credentials.md in this same command; never print it
sshpass -p "$PW" ssh -o StrictHostKeyChecking=no -o BatchMode=no -o PreferredAuthentications=password \
  -o ControlMaster=auto -o ControlPath=/tmp/ssh_mux_root_<box> -o ControlPersist=28800 root@$HOST '<cmd>'
```

- The passwords are in `references/lab-credentials.md` — local only, gitignored; create it from
  `lab-credentials.md.example` next to it. The x86 reg boxes' root password is its "root — x86 reg
  boxes" row. Never echo it, and never write it into a document, a log or a commit message.
- `sshpass` is the one ssh that runs without BatchMode: it answers the prompt on its own pty, so no
  askpass is involved. Exit 5 = wrong password — stop; do not try other values.
- Root is for repairing the box (§3) and what needs it outright. Test runs stay under your own user;
  the lab-box scripts refuse to run as root.

## 3. Your own login fails: the home is not mounted

`Permission denied (publickey,password)` for your user, while `ping` answers and the denial
outlasts the first minutes after a boot (a power cycle does not help), means the box cannot read
`~/.ssh/authorized_keys`: `/labhome` is mounted by autofs from an NIS map, and it is not mounted.
Seen on reg boxes right after a MARS session. Log in as root (§2), then in this order:

1. `systemctl restart autofs; systemctl status autofs`, then `ls /labhome/$USER`.
2. Still missing: `automount -m | grep -ci labhome` prints 0 and `/etc/auto.master` is empty →
   write the stock master map back and restart autofs:
   ```bash
   chattr -i /etc/auto.master 2>/dev/null
   printf '%s\n' '/misc   /etc/auto.misc' '+dir:/etc/auto.master.d' '+auto.master' > /etc/auto.master
   grep '^automount:' /etc/nsswitch.conf     # must read: automount:  files nis
   systemctl restart autofs; ls /labhome/$USER/.ssh
   ```
   `+auto.master` pulls the NIS master map, which holds `/labhome` and `/auto`.
3. Still missing: `systemctl restart nfs-server.service; systemctl status nfs-server.service`.

- Checks: `ypwhich` must name an NIS server; `ypwhich -m | grep -i labhome` lists the map;
  `ypcat -k auto.labhome.mtl | grep $USER` shows the filer path. Mounting that path by hand on
  `/mnt/test` proves the filer and the export are fine, but does not replace `/labhome`: dotfiles in
  the home link to paths under `/labhome/$USER`.
- `nfs.service not found` on Ubuntu is expected (no such unit there) — not the fault.
- If `/etc/auto.master` is empty again after the next reboot or MARS session, something overwrites
  it: tell Peter, for a Unix ticket (l-fwreg-171's was RITM01839996), instead of fixing it again
  silently.

## 4. BlueField ARM

- `ssh root@<arm-ip>`; `uname -m` must print `aarch64` (skill `bluefield-fwconfig`).
- utopx logs in to the ARM as the user `GetArmUserName()` returns, with `GetArmPassword()`
  (`utopx: src/arm_agent_api/ArmAgentApiOS.cpp`; Bronco and non-Bronco differ) — the values are in
  `references/lab-credentials.md`. If that password was changed on the box (ArmAgent scp fails 60
  attempts), `root` usually still works: `echo '<user>:<password>' | chpasswd` restores what utopx
  expects. Other BF4 traps: skill `regression-repro`, `references/key-learnings.md`.
