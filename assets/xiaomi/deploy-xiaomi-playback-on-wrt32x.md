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
> **Live view** (single, or a 2/4/6-cell split grid) is part of the player too and depends on **go2rtc**
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

The **fixed bottom nav bar** holds two sliding segmented toggles (their product is the current
mode, `currentMode()`, applied by `applyMode(time, n)`), plus the **date dropdown** (`#dates` — the
day picker, shows `MM-DD weekday · clip-count`), the **camera** select, the **quality** select
(Direct/Transcode), and **refresh**:
- **Live / Playback** — the time axis.
- **1 / 2 / 4 / 6** — the cell count. `1` = single view; `2/4/6` = split grid.

On phones the nav bar **wraps** (`@media max-width:760px` → `.nav-mid{flex:1 1 100%;flex-wrap:wrap}`)
so every control stays on-screen and tappable (it's ~720px wide — without wrapping the right-hand
controls overflowed off-screen with no scroll).

So the four modes are **`live`** (single live), **`livegrid`** (live split), **`play`** (single
timeline playback), **`pbgrid`** (recording split synced to one timeline — pure-local, no go2rtc).
The page opens to **`livegrid` at 4 cells** by default (`START_LIVE=true`, `START_SPLIT=4`). There
are **no keyboard shortcuts**.

Camera names are decoupled from go2rtc: internal stream/disk names stay lowercase `c700_0X`, while
the UI shows display names from **`CAM_NAMES`** (`CAM 1`…`CAM 6`, via `dispCam()`). Cells `05/06`
are reserved (no live source / no disk yet).

Live does **not** go through wrt32x — the browser connects **directly to go2rtc** at
`192.168.10.240:1984` over WebRTC. wrt32x only serves the page (and proxies go2rtc's
component JS same-origin at `/video-rtc.js`, `/video-stream.js`). Both single-live and the
live grid use the go2rtc **`<video-stream>` web component** (no iframe anymore — the iframe
was cross-origin and couldn't be instrumented; the component lets us add badges + a stall
watchdog, and fills the cell in Safari instead of letterboxing).

### Codec: native H265 over WebRTC (the 2025 change)

Modern browsers can now **receive H265/HEVC over WebRTC** (Chrome 136+, Safari). go2rtc
will send H265 if the browser offers it (verified: answer SDP carries `H265/90000`). So:

- The player feature-detects it (`webrtcCanH265()` via `RTCRtpReceiver.getCapabilities` → `RTC_H265`).
- **Supported (Chrome136+/Safari):** plays the camera's native **1080p H265 `c700_0X_sub1080`
  directly, no transcode** → original quality, ~zero `.240` load.
- **Not supported (Firefox, Edge-default):** falls back to the **H264 transcode `c700_0X_1080p`**.
- Always WebRTC (the quality menu `QUALS` maps **Direct**→`_sub1080`, **Transcode**→`_1080p`).
  The top-right `● RTC`/`● MSE` badge shows the
  actual negotiated protocol (read from the component: WebRTC→`srcObject`, MSE→`blob:`).

**Tradeoff to know (H265-direct can stutter):** WebRTC is lossy UDP and never retransmits;
H265 + a long camera GOP means one lost packet freezes the picture until the next keyframe,
which go2rtc cannot force the Xiaomi camera to emit on demand. On a not-perfect path this
shows as occasional freezes (and `cs2: pop buffer is full` in the go2rtc log — a slow
consumer made go2rtc drop a chunk). Xiaomi's own app avoids this because it uses a
**buffered + reliable + adaptive** path, not raw WebRTC. A smoother alternative is **MSE**
(go2rtc streams fMP4 over the WebSocket = **TCP, reliable + buffered**): trades ~1–2 s latency
for no packet-loss freezes, still native H265 no transcode. It was tried and **removed** (the
user preferred WebRTC's low latency + pause-jumps-to-live); the quality menu is WebRTC-only now.
To revisit, re-add a `QUALS` entry with `mode:'mse'` plus a resume-reconnect for MSE's
pause-falls-behind. The everyday smoothness backstop is the stall watchdog below.

**Stall watchdog (self-heal):** a WebRTC stream can stay "connected" while frames stop
(source hiccup / lost GOP) — neither browser nor go2rtc reconnects, so it freezes
permanently. The player watches each live `<video>`'s `currentTime`; a cell with no advancing
frames (and not user-paused) is reconnected — a few **fast retries**, then a **slow ~12 s backoff
that never permanently gives up** (it still shows `No signal` after the fast tries, but keeps
trying), so a flaky source like a camera whose go2rtc transcode hiccups recovers on its own
once the stream settles.

### go2rtc box (Frigate, Windows, `.240`)

Config saved at `./go2rtc.yaml` (uid/did/token redacted as placeholders). Per camera, **3 streams**:
`c700_0X_raw` (4K H265 main, recording/Frigate, subtype=3), `c700_0X_sub1080` (1080p H265 sub,
subtype=2&stream=0 — what live uses on H265-capable browsers), `c700_0X_1080p` =
`ffmpeg:..._sub1080#video=h264#audio=copy#hardware=cuda` (the H264 fallback for non-H265 browsers).

- **Required:** `api: origin: "*"` — without it go2rtc returns **403** on the cross-origin
  WebSocket from the player page and live/grid stays black.
- Transcode (only used by Firefox/Edge now) is sourced from the **1080p sub**, not 4K
  (4K overflowed the buffer + the transcode died with `EOF`). `#audio=copy` (sub audio is
  already OPUS; `#audio=opus` re-encode reintroduced EOF). `#hardware=cuda` for NVDEC/NVENC.

### Playback split (`pbgrid`)

A 2/4/6-cell grid of the cameras' **recordings**, sharing the one timeline:
- **Drag the timeline / ±10s / prev-next-seg / speed** act on all together (`seekTo`→`gridSeekAll`).
- **Per-cell controls** (reveal on hover, or tap-then-auto-fade on touch): a **camera picker**
  top-left (assigns that cell's camera), native `<video>` controls, and a `⤢` **page-fill zoom**
  (fills the grid area, not OS fullscreen — Safari's fullscreen-exit shifts the frame). A `⛶`
  **fill-screen** button makes the whole grid fill the viewport (CSS, not OS fullscreen).
- **Bottom transport row** (shown in playback only — `body.live-mode`/`body.grid-mode` hide `.transport`):
  `Play all` (realign all to the reference's moment, then play together) · `Pause all` · a
  **`⇄ Coarse | ◎ Precise`** sync-mode toggle · **±10s** · **Prev clip / Next clip** (`jumpSeg`) ·
  speed · `Jump to latest`. *(The duplicate timeline timestamp `#tlDate` was removed — the current
  moment shows once in the `📅` clock; the timeline's hover/drag bubble `.tip` gives the scrub time.
  The `📅` "Go to time" wheel is **time-only** now — hour/min/sec; the day is the nav-bar dropdown.)*
- **Master cell** = the cell showing the camera selected in the top camera dropdown (defaults to the
  current single-view camera); marked **`REF`** + amber border. Timeline coverage, playhead, and sync
  baseline follow it. Change the dropdown (or a cell's picker) to move it. *(In **live split** the top
  camera dropdown is hidden — there the per-cell pickers own the cameras and there is no master.)*
- **Sync modes:** **`⇄ Coarse`** aligns every cell by *assumed* (filename) time (`pbAlignCoarse`).
  **`◎ Precise`** OCR-reads each cell's burned-in clock and aligns to the master's *real* time,
  all-or-nothing — see `ocr-precise-sync.md`. Each cell's offset is the **average of ~8 frame reads**
  (the burned clock is whole-seconds; averaging spreads the sub-second error into a common bias that
  cancels relatively → cells sync in **one** click instead of needing two). Once it can't verify a cell it
  **stays** in Precise and retries on each segment change (no silent fall-back to Coarse); a cell that
  crosses into a new clip is re-calibrated **once** (the per-crossing `recal`, shown in the debug window).
- **Offset-aware maintenance (`pbStartSync`, every 500 ms):** the **master is forced to the selected Speed
  each tick** (else a cell nudged >1× to catch up, then promoted to REF, stays sped up forever since the loop
  skips the master — the "reference cell is playing fast" bug). Then it keeps each non-master cell locked to
  the master's real time `mw = master.s0 + master.currentTime + (_ocrOff||0)` — rate-nudge if drift ≤2.5 s,
  one hard-seek (with a ~1.5 s cooldown) if larger, cross to the right clip when `mw` leaves the current
  one. A locked non-master plays at the **master's rate** (`mRate`); the rate-nudge is clamped to **±5 %
  (0.95–1.05×, `PB_CAP=0.05`)** — imperceptible, and enough to absorb the ~1 % per-camera media-clock
  difference, but it can never slam a cell to half-speed (the old `PB_CAP=1.0` pinned a drifting non-master at
  ~0.5× = a visible slow-motion stutter). **Non-master cells are ALWAYS pulled back** — there is no "independent after drag"; dragging a
  non-master cell is undone (intended workflow: `Pause all` the others, scrub the master, then `Play all`).
  > **Per-clip "slope" — tried and REVERTED.** Each camera's media clock ticks ~0.8–1.7 % off real wall-time
  > and differs per camera, so `real = s0 + currentTime` drifts the cells apart slowly over a clip (they snap
  > back at each crossing/recal). A `real = s0 + currentTime*slope` correction (`slope = span/video.duration`,
  > plus a per-cell tracking playbackRate) removed the drift in headless tests but made the **non-master cells
  > stutter** in the real browser (and the matching rate logic was fragile). It was fully removed — a smooth
  > view with a small slow drift beats a stuttering one. The model is back to the simple 1:1.
- **Background-tab recovery (`visibilitychange`):** a hidden tab has its 500 ms loop throttled (≈1/min or
  paused) while the `<video>`s keep playing, so a cell left at a >1× catch-up rate **runs away** (the "left
  for a while, came back, CAM3 is ~70 s ahead" bug). On hide, all rates are frozen to base; on show,
  `pbResyncVisible()` resets rates + hard-seeks every playing non-master cell back to the master. Paused
  cells are left paused (pause workflow preserved).
- **Synchronized start / seeking:** on open/seek each cell is flagged `_settling` (the watchdog/maintenance
  leave it alone) and **poll-retries its seek until it actually lands** — these fMP4 (`moov duration=0`)
  clamp a cold seek to the clip start, so a single seek would "jump to the segment edge"; retrying as the
  file warms makes it land on the requested time. Cells play together once positioned. **`gridSeekAll`
  uses this same poll-retry landing whether or not it then plays** — `play` only gates the final
  `.play()`. So a **paused** jump (e.g. `±10s` while paused) lands just as reliably and stays paused;
  the old `play=false` shortcut used `pbLoadCell` with no poll-retry, which clamped and made a paused
  split jump to the wrong clip ("±10s did nothing / jumped backwards"). **`pbOcrSync` does the
  same:** after a Precise click it holds every cell PAUSED at the target time until *all* have positioned,
  then starts them together — playing each the instant it was ready let the master (no reload) run ahead for
  the seconds a crossing cell (the slow cifs CAM3/4) spent reloading, so the master ended up several seconds
  ahead and a 2nd Precise click was needed.
- **Watchdog (`pbWatchCell`):** rolls a cell that reaches/stalls at a clip *end* over to the next clip
  (covers a clean `ended`, an fMP4 tail error, and the silent buffer-stall); reloads a genuinely black/
  frozen cell — but treats a cell whose **buffered range is still growing**, OR that is in its **initial cold
  load** (`buffered.end = 0` from `loadstart`→`canplay`, a `~15 s` `PB_COLD_MS` grace), as still-loading and
  leaves it alone. Reloading inside that window restarts the download from scratch so it **never finishes** —
  this (not the sync loop) was the real cause of "playback loads so slowly / one cam never loads"; verified
  by killing the watchdog, after which stuck cells loaded immediately. A clip roll-over and a
  maintenance relocate both go through **`pbEnterSeg`**, which marks the cell `_settling` + shows
  **`Loading…`** and clears both only once frames flow (12 s safety) — so a slow **new-segment load** no
  longer churns through the reload cap into a false **`No video`**. **Decoder-queue wait:** a cell that has
  **never produced a frame** (`buffered.end = 0`, no error, `!_hadData`) is QUEUED for a decoder — Safari
  caps concurrent 4K-H265 decodes, so the 4th cell in a 4-split waits. The watchdog keeps its load **open**
  and just shows `Loading…`; it does **NOT** reload it (only a ~40 s silent-hang hedge). Reloading was
  counter-productive — `removeAttribute('src')` discards the buffered download and drops the src, so the cell
  misses the decoder another cell frees on a clip crossing → it churned `Loading…` forever (the "two cells
  stuck loading" report). Verified headless: with no churn a 4-split loaded **4/4 with 0 reloads in 70 s**.
  An actual reload (backoff, never a dead `No video`) fires only on a real `v.error` or a **post-data
  mid-play stall**. If a given Mac still can't fit all four 4K decodes, 2-split always works. A genuine
  recording *gap* is separate: the maintenance loop sets
  `_seg=null` + `No recording`, after which `pbWatchCell` isn't called for that cell, so there's no churn.
- A background single-`<video>` ending does **not** auto-advance while a grid mode is active (guard in the
  `ended` handler), and the single recording does not autoplay in the background while in a grid. The
  startup background timeline preload is protected by the `livePreload` flag so it can't tear the grid down.

### Player consts (top of the inline JS)

`GO2RTC`, `RTC_H265 = webrtcCanH265()`, the `QUALS` quality menu (**Direct**→`_sub1080` ·
**Transcode**→`_1080p`, both WebRTC), `START_LIVE`, and `START_SPLIT` (default cell count on load:
1/2/4/6). Plus a `GO2RTC` const on the Python side for the JS-proxy route. Change the
go2rtc IP in **both** spots if it moves.

---

## 14. Precise-sync OCR engine (separate hosting step on sda3)

Playback split's **`◎ Precise`** mode OCR-reads each cell's burned-in clock **in the browser** to align
to the reference's real time (±1 s). The OCR engine is **not** inside `xiaomi_playback.py` — it's static
files hosted on **`/mnt/sda3/opt/ocr/`**, served same-origin at `/ocr/`: the **onnxruntime-web** runtime
(`ort.min.js` + the `ort-wasm-simd-threaded.wasm/.mjs` loaders), the **PP-OCRv4-server** recognition model
(`rec_v4_server.onnx`, ~90 MB), the dict (`ppocr_keys.txt`), and a **tesseract.js** fallback. Frames never
leave the LAN.

These files survive a router OS reflash (sda3 is a data disk) but are **lost if sda3 is reformatted**, and
are **not in the repo** → re-host them after a fresh install.

→ See **`ocr-precise-sync.md`** for the pipeline, the model choice (why PP-OCRv4-server vs v3/mobile),
the content-type requirements (`.mjs`→`text/javascript` etc.), and the copy-paste re-host runbook.
