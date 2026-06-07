# Deploy `xiaomi_playback.py` **on the WRT32X** (always-on, on the NAS)

The companion plan **`deploy-xiaomi-playback.md`** runs the player on a Mac/PC over
CIFS. This plan instead runs it **on `wrt32x` itself**, so playback is available 24/7
without the Mac, and the heavy reads stay on the wired backbone instead of crossing
WiFi.

Companion script: **`./xiaomi_playback.py`** — pure stdlib, read-only. This
plan adds only *deployment glue* (a Python-on-disk install, a cifs mount script, a
procd service).

> **Canonical files live in `./`** — `python3-sda3`, `xiaomi-mounts.sh`,
> `xiaomi-playback.init`, `go2rtc.yaml`, and a `README.md` index. The inline scripts in
> §6/§7 below match those files; you can also just `scp`/pipe them straight from
> `assets/xiaomi/`. See `assets/xiaomi/README.md` for the full system map.
>
> **Live view** (single + 2×2 grid) is part of the player too and depends on **go2rtc**
> at 192.168.10.240 — see §13 below and `assets/xiaomi/go2rtc.yaml`.

> **As-built (2026-06-06).** Where the first draft was wrong, the verified value is
> used: SSH port **8822** (not 22) on `wrt32x` too; spare disk is **`/mnt/sda3`**;
> Python installs **onto `/mnt/sda3`** (flash had only ~70 MB free); cifs
> `iocharset=utf8` **dropped** (no UTF-8 NLS on this build); local disks **symlinked**
> to `c700_*` for pretty labels.

---

## 1. Why on `wrt32x` (the decision)

- **WiFi is the only weak link.** The Mac is on WiFi; both routers are wired. Hosting
  the server on the wired `wrt32x` keeps disk reads and the cross-box cifs fetch on
  wire — only the stream you watch crosses WiFi once (zero on a wired device). On the
  Mac, viewing from a phone crosses WiFi *twice*.
- **2 of the 4 cameras are local to `wrt32x`** (sda1, sda2), plus the empty spare
  (sda3); only the two on `wrt1200ac` come over a read-only cifs mount. Hosting on
  `wrt1200ac` would invert that and it's the slower box.
- **Capacity is a non-issue (measured).** Streams are **1.4–3.3 Mbps** each (134 MB
  chunks, **no transcoding** — the player serves bytes, the browser decodes). 4
  concurrent ≈ <20 Mbps through wrt32x (dual-core ARMv7 @ 1866 MHz, GbE, SMB
  encryption off, ~250 MB RAM free). Idle Python ≈ 15 MB / ~0 CPU. `ThreadingHTTPServer`
  handles concurrent Range requests.
- **Always-on, read-only.** `wrt32x` is up 24/7; the player never writes to any share,
  so it cannot conflict with camera uploads or `camera-rotate.sh`.

---

## 2. Target layout (source of truth, verified)

| Camera (MAC)     | Physical host | How `wrt32x` sees it            | Root passed to player |
|------------------|---------------|---------------------------------|-----------------------|
| `B88880974A38`   | `wrt32x`      | local `/mnt/sda1`               | `/mnt/c700_01` → sda1 |
| `B88880A0FD7C`   | `wrt32x`      | local `/mnt/sda2`               | `/mnt/c700_02` → sda2 |
| *(spare, empty)* | `wrt32x`      | local `/mnt/sda3`               | `/mnt/c700_05` → sda3 |
| `B88880976D02`   | `wrt1200ac`   | cifs `//192.168.10.100/c700_03` | `/mnt/c700_03`        |
| `B88880976D36`   | `wrt1200ac`   | cifs `//192.168.10.100/c700_04` | `/mnt/c700_04`        |

- Hosts: `wrt32x` = 192.168.10.200, `wrt1200ac` = 192.168.10.100. **Root SSH on port
  8822 on both.** ImmortalWrt 24.10.5, armv7l (Cortex-A9). SMB user `pi`, same password
  on both. `wrt1200ac`'s `sword` share is unrelated — not a camera.
- Local disks mount at `/mnt/sdaN`; the service **symlinks** them to `/mnt/c700_0X` so
  the dropdown shows `c700_01/02/05` (matching the share names; the cifs ones are
  already `c700_03/04`).
- `c700_05` (sda3) is the empty spare — shows as an empty entry until a 5th camera
  records there, then appears automatically. (Python lives in `/mnt/sda3/opt`, which the
  player ignores.)
- Chunk names `00_<start>_<end>.mp4`, ~128 MB; in-progress chunk has `start==end`
  (flagged amber/LIVE).

**Command the service runs** (5 roots + port; last all-digit arg = port):

```sh
/usr/local/bin/python3-sda3 /usr/local/bin/xiaomi_playback.py \
  /mnt/c700_01 /mnt/c700_02 /mnt/c700_03 /mnt/c700_04 /mnt/c700_05 8800
```

---

## 3. SSH in (ControlMaster, port 8822)

```sh
mkdir -p ~/.ssh/cm
SSH="ssh -p 8822 -o ControlMaster=auto -o ControlPath=~/.ssh/cm/wrt32x-%C \
        -o ControlPersist=10m -o StrictHostKeyChecking=accept-new -l root 192.168.10.200"
$SSH 'echo connected; . /etc/openwrt_release; echo $DISTRIB_DESCRIPTION'
```

> `scp` over busybox needs `scp -O`, or just pipe: `cat file | $SSH 'cat > /dest'`.
> `/usr/local/bin` is **not** in OpenWrt's default `PATH` — call scripts by full path.

---

## 4. Install Python 3 onto the spare disk `/mnt/sda3` (keep flash free)

Flash overlay has only ~70 MB free, so install Python to the roomy spare disk via an
opkg `dest`, with a tiny wrapper on flash (the disk-installed `libpython3` isn't on the
default linker path). Stdlib only: `os re sys time datetime threading json`,
`http.server`, `urllib.parse`, `socketserver`.

```sh
$SSH '
  mkdir -p /mnt/sda3/opt
  grep -q "^dest sda3 " /etc/opkg.conf || echo "dest sda3 /mnt/sda3/opt" >> /etc/opkg.conf
  opkg update
  opkg -d sda3 install python3-light python3-urllib python3-logging python3-codecs
  cat > /usr/local/bin/python3-sda3 <<EOF
#!/bin/sh
PFX=/mnt/sda3/opt/usr
export LD_LIBRARY_PATH="\$PFX/lib\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}"
exec "\$PFX/bin/python3" "\$@"
EOF
  chmod +x /usr/local/bin/python3-sda3
  /usr/local/bin/python3-sda3 -c "import http.server,urllib.parse,json,datetime,threading,re,socketserver,sys;print(\"py\",sys.version.split()[0],\"OK; prefix=\"+sys.prefix)"
'
```

- Footprint ≈ **15 MB on `/mnt/sda3`**, flash untouched. `sys.prefix` auto-resolves to
  `/mnt/sda3/opt/usr` (no `PYTHONHOME` needed).
- Deps (`python3-base`, `libpython3`, `libbz2`, `python3-email`, …) install to the
  `sda3` dest too; base libs already present are skipped.
- Runtime `ModuleNotFoundError: <name>` → `opkg -d sda3 install python3-<name>`.

---

## 5. Copy the player

```sh
cat assets/xiaomi/xiaomi_playback.py | $SSH '
  mkdir -p /usr/local/bin
  cat > /usr/local/bin/xiaomi_playback.py
  chmod +x /usr/local/bin/xiaomi_playback.py
  /usr/local/bin/python3-sda3 -m py_compile /usr/local/bin/xiaomi_playback.py && echo "syntax OK"
  md5sum /usr/local/bin/xiaomi_playback.py
'
md5 -r assets/xiaomi/xiaomi_playback.py     # checksums must match
```

---

## 6. cifs: kernel module (flash) + read-only mounts of `wrt1200ac`

```sh
$SSH '
  opkg install kmod-fs-cifs        # to flash — kernel modules live in /lib/modules; small
  mkdir -p /mnt/c700_03 /mnt/c700_04
  printf "SMBUSER=pi\nSMBPASS=CHANGE_ME\n" > /etc/xiaomi-playback.cred   # set the real pi password
  chmod 600 /etc/xiaomi-playback.cred
'
```

Install the idempotent mount script `/usr/local/bin/xiaomi-mounts.sh` — mounts both
shares **read-only** and recovers after a `wrt1200ac` reboot:

```sh
cat <<'EOF' | $SSH 'cat > /usr/local/bin/xiaomi-mounts.sh; chmod +x /usr/local/bin/xiaomi-mounts.sh'
#!/bin/sh
# Mount wrt1200ac's two camera shares read-only on wrt32x. Idempotent;
# recovers from a wrt1200ac reboot (stale mount -> umount -l + remount).
# Minimal opts on purpose: iocharset=utf8 needs kmod-nls-utf8 (absent on this build)
# and the filenames are pure ASCII, so it is not needed.
set -u
PEER=192.168.10.100
CRED=/etc/xiaomi-playback.cred
VERS=3.0                       # if mount fails, try 2.1 then 1.0
. "$CRED"                      # provides SMBUSER + SMBPASS
is_mounted() { grep -q " $1 cifs " /proc/mounts; }
mount_one() {
  share="$1"; mp="$2"
  mkdir -p "$mp"
  if is_mounted "$mp" && ls "$mp" >/dev/null 2>&1; then return 0; fi
  is_mounted "$mp" && umount -l "$mp" 2>/dev/null
  if mount -t cifs "//$PEER/$share" "$mp" -o "ro,user=$SMBUSER,pass=$SMBPASS,vers=$VERS"; then
    logger -t xiaomi-mounts "mounted $share -> $mp"
  else
    logger -t xiaomi-mounts "FAILED $share -> $mp (try VERS=2.1 or 1.0)"
  fi
}
mount_one c700_03 /mnt/c700_03
mount_one c700_04 /mnt/c700_04
EOF

$SSH '/usr/local/bin/xiaomi-mounts.sh; grep cifs /proc/mounts; ls -d /mnt/c700_03/XiaomiCamera_* /mnt/c700_04/XiaomiCamera_*'
```

> **Gotcha hit during deploy:** `mount` failed with "No error information" until
> `iocharset=utf8,noserverino` was removed — this build has no UTF-8 NLS charset. The
> minimal `ro,user=,pass=,vers=3.0` works. If `wrt1200ac` ever needs an older dialect,
> set `VERS=2.1` (or `1.0`). `ro` guarantees the player can never write to `wrt1200ac`.

---

## 7. Autostart with a procd init service

`/etc/init.d/xiaomi-playback` symlinks the local disks to `c700_*` names, brings the
cifs mounts up, then runs the server under procd with auto-respawn.

```sh
cat <<'EOF' | $SSH 'cat > /etc/init.d/xiaomi-playback; chmod +x /etc/init.d/xiaomi-playback'
#!/bin/sh /etc/rc.common
# Xiaomi timeline playback server (procd, always-on)
USE_PROCD=1
START=95
STOP=10
PYBIN=/usr/local/bin/python3-sda3          # wrapper -> python on /mnt/sda3
SCRIPT=/usr/local/bin/xiaomi_playback.py
PORT=8800
ROOTS="/mnt/c700_01 /mnt/c700_02 /mnt/c700_03 /mnt/c700_04 /mnt/c700_05"
start_service() {
    ln -sfn /mnt/sda1 /mnt/c700_01             # local c700_01
    ln -sfn /mnt/sda2 /mnt/c700_02             # local c700_02
    ln -sfn /mnt/sda3 /mnt/c700_05             # local spare c700_05
    /usr/local/bin/xiaomi-mounts.sh            # c700_03/04 read-only cifs up first
    procd_open_instance
    procd_set_param command "$PYBIN" "$SCRIPT" $ROOTS "$PORT"
    procd_set_param respawn 3600 5 5           # threshold timeout retries
    procd_set_param stdout 1
    procd_set_param stderr 1
    procd_set_param pidfile /var/run/xiaomi-playback.pid
    procd_close_instance
}
EOF

$SSH '
  /etc/init.d/xiaomi-playback enable
  /etc/init.d/xiaomi-playback start
  sleep 1
  ls /etc/rc.d/S*xiaomi-playback          # confirms boot-start
  logread -e xiaomi | tail -n 5
'
```

Manage with `/etc/init.d/xiaomi-playback {start|stop|restart|enable|disable}`.

---

## 8. Keep the cifs mounts alive (cron guard)

A `wrt1200ac` reboot leaves the mounts stale; re-run the mount script every 5 min
(no-op when healthy):

```sh
$SSH '
  grep -q xiaomi-mounts /etc/crontabs/root 2>/dev/null || \
    echo "*/5 * * * * /usr/local/bin/xiaomi-mounts.sh >/dev/null 2>&1" >> /etc/crontabs/root
  /etc/init.d/cron enable && /etc/init.d/cron restart
'
```

> The server keeps running across a remount; its scans re-read every `CACHE_TTL`
> (15 s), so the two cameras reappear within seconds of the mount returning.

---

## 9. Reach it

```
http://192.168.10.200:8800/      (or http://wrt32x.local:8800/)
```

No firewall change needed — the `lan` zone input is `ACCEPT` (verified). If a future
config blocks it, add a rule:

```sh
$SSH '
  uci add firewall rule
  uci set firewall.@rule[-1].name="Allow-xiaomi-playback"
  uci set firewall.@rule[-1].src="lan"; uci set firewall.@rule[-1].proto="tcp"
  uci set firewall.@rule[-1].dest_port="8800"; uci set firewall.@rule[-1].target="ACCEPT"
  uci commit firewall && /etc/init.d/firewall reload
'
```

---

## 10. Verification

```sh
# on wrt32x
$SSH 'logread -e xiaomi | tail; grep cifs /proc/mounts; curl -s localhost:8800/api/cameras'

# from the Mac — full round-trip incl. Range (proves seek + the cifs path)
curl -s http://192.168.10.200:8800/api/cameras           # -> c700_01..05
curl -s -D- -o /dev/null -r 0-1023 \
  'http://192.168.10.200:8800/video?cam=<id>&file=<a-real-chunk>.mp4'
#   expect: HTTP/1.0 206  +  Content-Length: 1024  +  Content-Range: bytes 0-1023/134217728
```

Confirmed 2026-06-06: 5 entries (`c700_01..05`); local **and** cifs cameras both return
`206`/`1024`. In a browser at `http://wrt32x.local:8800/`: dropdown lists all cameras,
latest day pre-selected, green blocks = footage (amber = LIVE), dragging the timeline
moves the playhead and seeks on release, finished chunks auto-advance, switching camera
keeps the time.

**Reboot test:** reboot wrt32x → procd auto-starts the service (`S95`) and the cifs
mounts come back (cron guard + `start_service`) with no manual step.

---

## 11. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `ModuleNotFoundError` on start | Missing stdlib pkg — `opkg -d sda3 install python3-<name>`. |
| `python3-sda3: not found` | `/usr/local/bin` not in `PATH` — call it by full path. |
| Only 3 cameras (no c700_03/04) | cifs mounts down — `grep cifs /proc/mounts`; run `/usr/local/bin/xiaomi-mounts.sh`; check `wrt1200ac` is up. |
| `mount -t cifs` "No error information" | Drop `iocharset=utf8` (no UTF-8 NLS here); or set `VERS=2.1`/`1.0`; verify the `pi` password in `/etc/xiaomi-playback.cred`. |
| Labels show `sda1/sda2` not `c700_*` | The `ln -sfn /mnt/sdaN /mnt/c700_0X` symlinks missing — `restart` the service (it recreates them). |
| Cameras vanish after `wrt1200ac` reboot | Stale mount — cron guard (§8) remounts within 5 min; or run the mount script. |
| Service flaps / respawns | `logread -e xiaomi`; usually a bad root path. |
| Can't reach `:8800` from the Mac | Same 192.168.10.x subnet? Add the firewall rule (§9). |

---

## 12. Relegate the Mac copy

The on-Mac server (`deploy-xiaomi-playback.md`) is no longer needed — stop it so two
servers don't compete for clients:

```sh
pkill -f xiaomi_playback.py            # on the Mac
```

The Mac's SMB mounts are no longer needed for playback (unmount or leave them).
`wrt32x` now serves everything at `http://wrt32x.local:8800/`.

---

## 13. Live view + playback grid (go2rtc)

The player has three live/multi modes besides single-camera timeline playback:
- **`看直播/看回放`** — single-camera live toggle.
- **`⊞ 四分屏`** (key `G`) — 2×2 **live** grid (all cameras).
- **`⊞ 回放分屏`** (key `P`) — 2×2 **recording** grid: all 4 cameras' recordings synced
  to one timeline (see "Playback grid" below). Pure-local, does not use go2rtc.

Live does **not** go through wrt32x — the browser connects **directly to go2rtc** at
`192.168.10.240:1984` over WebRTC. wrt32x only serves the page (and proxies go2rtc's
component JS same-origin at `/video-rtc.js`, `/video-stream.js`). Both single-live and the
live grid use the go2rtc **`<video-stream>` web component** (no iframe anymore — the iframe
was cross-origin and couldn't be instrumented; the component lets us add badges + a stall
watchdog, and fills the cell in Safari instead of letterboxing).

### Codec: native H265 over WebRTC (the 2025 change)

Modern browsers can now **receive H265/HEVC over WebRTC** (Chrome 136+, Safari). go2rtc
will send H265 if the browser offers it (verified: answer SDP carries `H265/90000`). So:

- The player feature-detects it (`webrtcCanH265()` via `RTCRtpReceiver.getCapabilities`).
- **Supported (Chrome136+/Safari):** `LIVE_SUFFIX='_sub'` → plays the camera's native
  **1080p H265 sub-stream directly, no transcode** → original quality, ~zero `.240` load.
- **Not supported (Firefox, Edge-default):** falls back to `LIVE_SUFFIX='_1080p'` → go2rtc's
  **H264 transcode**.
- `LIVE_MODE='webrtc'` either way. The top-right `● 实时 · RTC`/`· MSE` badge shows the
  actual negotiated protocol (read from the component: WebRTC→`srcObject`, MSE→`blob:`).

**Tradeoff to know (H265-direct can stutter):** WebRTC is lossy UDP and never retransmits;
H265 + a long camera GOP means one lost packet freezes the picture until the next keyframe,
which go2rtc cannot force the Xiaomi camera to emit on demand. On a not-perfect path this
shows as occasional freezes (and `cs2: pop buffer is full` in the go2rtc log — a slow
consumer made go2rtc drop a chunk). Xiaomi's own app avoids this because it uses a
**buffered + reliable + adaptive** path, not raw WebRTC. The smoother alternative is
**MSE** (go2rtc streams fMP4 over the WebSocket = **TCP, reliable + buffered**): it trades
~1–2 s latency for no packet-loss freezes, and still plays native H265 with no transcode.
Not enabled by default; switch `LIVE_MODE` to `'mse'` (and add a resume-reconnect to avoid
MSE's pause-falls-behind) if freezes bother you more than latency.

**Stall watchdog (self-heal):** a WebRTC stream can stay "connected" while frames stop
(source hiccup / lost GOP) — neither browser nor go2rtc reconnects, so it freezes
permanently. The player watches each live `<video>`'s `currentTime`; if it doesn't advance
for ~6 s (and isn't user-paused), it reconnects that cell.

### go2rtc box (Frigate, Windows, `.240`)

Config saved at `./go2rtc.yaml` (token/uid/did redacted). Per camera: `c700_0X_raw`
(4K H265 main, recording/Frigate), `c700_0X_sub` (1080p H265 sub — what live uses on
H265-capable browsers), `c700_0X_1080p` = `ffmpeg:..._sub#video=h264#audio=copy#hardware=cuda`
(the H264 fallback for non-H265 browsers).

- **Required:** `api: origin: "*"` — without it go2rtc returns **403** on the cross-origin
  WebSocket from the player page and live/grid stays black.
- Transcode (only used by Firefox/Edge now) is sourced from the **1080p sub**, not 4K
  (4K overflowed the buffer + the transcode died with `EOF`). `#audio=copy` (sub audio is
  already OPUS; `#audio=opus` re-encode reintroduced EOF). `#hardware=cuda` for NVDEC/NVENC.

### Playback grid (`⊞ 回放分屏` / key `P`)

2×2 of all 4 cameras' **recordings**, sharing the one timeline:
- **Drag the timeline / ±10s / prev-next-seg / speed / play-pause** act on all 4 together.
- **Master camera** = whatever is selected in the top `camSel` dropdown (defaults to
  `c700_01`); its cell gets an amber highlight + `· 基准` badge. The timeline coverage,
  the playhead, and the sync baseline all follow the master. Change the dropdown to move it.
- **Synchronized start:** on open/seek the 4 cells load paused and start together once all
  are buffered (≤2 s fallback) — so a fast-loading cell doesn't run ahead.
- **Periodic re-sync:** every 2 s, any cell drifting >1.5 s from the master is nudged back
  (same segment → set `currentTime`; crossed a segment → reload that cell). Tunables are
  the 2 s interval and 1.5 s threshold in `pbStartSync()`.

### Player consts (top of the inline JS)

`GO2RTC`, `webrtcCanH265()`→`LIVE_SUFFIX` (`_sub`|`_1080p`), `LIVE_MODE='webrtc'`,
`START_LIVE`. Plus a `GO2RTC` const on the Python side for the JS-proxy route. Change the
go2rtc IP in **both** spots if it moves.
