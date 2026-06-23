# Deploy `camera-rotate.sh` to an OpenWrt/ImmortalWrt NAS

A reusable plan to install an auto-rotation cron job that prunes the oldest SMB
camera recordings before either partition fills up.

Companion script: **`../template/camera-rotate.sh`** — the script the steps
below install. (Adjust the path if you move/rename either file.)

---

## 1. Goal

Keep one or more partitions hosting SMB camera recordings between a low and high
water mark by deleting the oldest `.mp4` chunks when usage crosses the high
mark, down to the low mark. Runs every hour via cron.

Without this, the partition fills, `smbd` returns `STATUS_DISK_FULL`, the
in-progress chunk is truncated, and the camera stops uploading until storage is
freed.

---

## 2. Assumptions about the target system

- OpenWrt or ImmortalWrt (verified on ImmortalWrt 24.10.5, busybox 1.36.1).
- BusyBox `head` supports `-n -N` (drop last N lines) — true since ~1.30.
- BusyBox `logger`, `df`, `awk`, `sort`, `ls`, `rm` available (all default).
- Root SSH access (key-based recommended).
- The recording layout is **one camera per directory**, with filenames whose
  lexicographic order = chronological order. Default expected pattern
  `00_YYYYMMDDhhmmss_*.mp4` (Xiaomi/C700 firmware). Other patterns require
  editing the `ls -1 "$dir"/00_*_*.mp4` glob in the script.
- `cron` service exists (`/etc/init.d/cron`). On stock OpenWrt the crontab
  `/etc/crontabs/root` is usually present but empty.

---

## 3. Connection setup (recommended)

Use SSH `ControlMaster` to avoid re-handshaking on every command:

```sh
mkdir -p ~/.ssh/cm
ssh -o ControlMaster=auto \
    -o ControlPath=~/.ssh/cm/nas-%C \
    -o ControlPersist=10m \
    -o BatchMode=yes -o StrictHostKeyChecking=no \
    -l root -p <SSH_PORT> <NAS_IP> 'echo connected'
```

All later `ssh` calls reuse `~/.ssh/cm/nas-%C`. Adapt the socket path per host
if managing multiple boxes.

> Gotcha: standard `scp` on modern OpenSSH defaults to SFTP, which busybox
> doesn't ship by default. Either use `scp -O` (legacy SCP protocol) **or** pipe
> via `cat | ssh ... 'cat >'` — the plan uses the latter to avoid scp issues.

---

## 4. Pre-flight checks (run before deploying)

```sh
ssh ... '
  echo "--- target dir ---"
  ls -ld /usr/local /usr/local/bin 2>&1 || true   # likely absent — we create it

  echo "--- busybox head -n -2 supported? (must print 1,2,3) ---"
  seq 1 5 | head -n -2

  echo "--- disk state ---"
  df -h /mnt/sda1 /mnt/sda2 /mnt/sda3 | awk "NR==1 || /sda/"

  echo "--- camera dirs and oldest chunk ---"
  for d in /mnt/sda1/XiaomiCamera_* /mnt/sda2/XiaomiCamera_* /mnt/sda3/XiaomiCamera_*; do
    echo "  $d"
    ls "$d" 2>/dev/null | sort | head -1
  done
'
```

If `head -n -2` does NOT print `1,2,3`, stop — the script's "skip newest 2"
guard will be broken; you must rework the tail-skip logic before deploying.

---

## 5. Customize the script for the target system

Edit `camera-rotate.sh` (companion file) only at the **`PAIRS=`** block:

```sh
PAIRS="
/mnt/sda1 /mnt/sda1/XiaomiCamera_00_B88880974A38
/mnt/sda2 /mnt/sda2/XiaomiCamera_00_B88880A0FD7C
/mnt/sda3 /mnt/sda3/XiaomiCamera_00_B88880948BA0
"
```

Each line is `<mount-point> <recording-dir>`. Add one line per camera/share.
Camera directory names typically embed the camera's MAC; find them with:

```sh
ssh ... 'ls -d /mnt/sda*/XiaomiCamera_* 2>/dev/null'
```

Optional tunables at the top of the script:

| var    | default | meaning |
|--------|---------|---------|
| `HIGH` | 90      | start rotating when `Use%` ≥ this |
| `LOW`  | 85      | stop rotating once `Use%` < this |
| `TAG`  | `camera-rotate` | syslog tag (use `logread \| grep $TAG`) |

Wider gap = fewer cron-tick rotations but more data deleted per cycle.

---

## 6. Deployment commands

Pipe-via-ssh (works without scp/sftp on target):

```sh
SCRIPT=/path/to/camera-rotate.sh   # the companion file, customized

# 6.1 — install
cat "$SCRIPT" | ssh ... '
  mkdir -p /usr/local/bin
  cat > /usr/local/bin/camera-rotate.sh
  chmod +x /usr/local/bin/camera-rotate.sh
'

# 6.2 — verify install
ssh ... '
  ls -la /usr/local/bin/camera-rotate.sh
  sh -n /usr/local/bin/camera-rotate.sh && echo "syntax OK"
  md5sum /usr/local/bin/camera-rotate.sh
'
md5sum "$SCRIPT"   # checksums should match
```

---

## 7. First run (verification — destructive if disk already > HIGH%)

```sh
ssh ... '
  echo "=== BEFORE ==="
  df -h /mnt/sda1 /mnt/sda2 /mnt/sda3 | awk "NR==1 || /sda/"

  echo "=== RUN ==="
  time /usr/local/bin/camera-rotate.sh

  echo "=== AFTER ==="
  df -h /mnt/sda1 /mnt/sda2 /mnt/sda3 | awk "NR==1 || /sda/"

  echo "=== SYSLOG ==="
  logread | grep camera-rotate | tail
'
```

Expected: each over-HIGH partition shows two `camera-rotate` log lines (start
+ end) and `Use%` drops to ≤ LOW. If everything is already under HIGH, the
script exits silently — that's normal.

> Reference timing: deleting ~750 chunks (≈ 96 GB of 128 MB MP4s) takes ~30 s
> on Armada-385 over USB 3.0 HDD.

---

## 8. Install cron entry

```sh
ssh ... '
  # avoid duplicates if rerun
  grep -q camera-rotate.sh /etc/crontabs/root 2>/dev/null \
    || echo "17 * * * * /usr/local/bin/camera-rotate.sh" >> /etc/crontabs/root
  cat /etc/crontabs/root

  /etc/init.d/cron enable
  /etc/init.d/cron restart

  ps w | grep -E "crond" | grep -v grep
  ls /etc/rc.d/S*cron   # confirms persistence on reboot
'
```

Minute-17 is arbitrary; pick any offset to avoid the top-of-hour rush from
other scheduled jobs.

---

## 9. Ongoing verification

After ≥ 1 hour has passed:

```sh
ssh ... 'logread | grep camera-rotate | tail -20'
```

Each hour where rotation actually fires logs exactly **2 lines per over-HIGH
partition**:

```
<ts> user.notice camera-rotate: /mnt/sdaN at NN% - rotating <dir> down to <LOW%
<ts> user.notice camera-rotate: /mnt/sdaN now at NN% after rotation
```

Hours where no partition crosses HIGH produce **no log lines** (the script is
intentionally quiet in the steady state).

---

## 10. Rollback / uninstall

```sh
ssh ... '
  sed -i "\\#camera-rotate.sh#d" /etc/crontabs/root
  /etc/init.d/cron restart
  rm -f /usr/local/bin/camera-rotate.sh
'
```

(`sed`'s `\#…#d` form is used because the path itself contains `/`.)

---

## 11. Scaling notes

- Adding more cameras to the same NAS: append one `<mount> <dir>` line to
  `PAIRS=` in `camera-rotate.sh` and redeploy (steps 6–7). No cron change.
- Adding a second NAS box (e.g., split cameras 2+2 across two routers): repeat
  this whole plan on the second box with the appropriate `PAIRS=` entries.
- The script handles arbitrary numbers of pairs — the inner loop just runs
  sequentially per partition.

---

## 12. Why these design choices

- **Hysteresis (HIGH/LOW gap)** — prevents thrashing one delete per cron tick.
- **Filename-sort, not mtime** — the camera firmware writes chunks with
  embedded timestamps in the filename; filename order is the true recording
  chronology and is stable across `cp`/restores. mtime can be misleading if
  files are ever touched/copied.
- **`head -n -2` keeps the 2 newest** — the most recent chunk is being written
  *right now* (don't yank it from under `smbd`); the second-newest may still
  have an open handle for finalization metadata. Two-file buffer is cheap
  insurance.
- **Glob `00_*_*.mp4`** — restricts deletion to chunk files, never directories
  or anything else a user might have placed in the share.
- **Per-partition `df`** — each pass re-reads `Use%` after each delete, so
  rotation stops exactly at LOW with no overshoot beyond one chunk.
- **`logger` to syslog** — survives reboots (via persistent log if enabled)
  and integrates with the standard `logread` workflow; no separate log file
  to rotate.

---

## 13. Quick reference / one-liner debug

```sh
ssh ... '
  echo --- DISKS ---;   df -h /mnt/sda1 /mnt/sda2 /mnt/sda3
  echo --- CRON ---;    cat /etc/crontabs/root; ps w | grep crond | grep -v grep
  echo --- LATEST ---;  logread | grep camera-rotate | tail -5
  echo --- SCRIPT ---;  ls -la /usr/local/bin/camera-rotate.sh
'
```
