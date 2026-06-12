# Xiaomi camera playback + live — file index & architecture

Self-hosted review/monitoring for 4 Xiaomi C700 cameras: a single-file, zero-dependency
Python web app gives a **timeline playback** of the SMB recordings **and** a **live view**
(single, or a 2/4/6-cell split grid) sourced from go2rtc. Runs always-on **on the WRT32X NAS itself**.

## Where everything runs

| Host | IP | Role |
|------|----|------|
| `wrt32x` (Linksys WRT32X, ImmortalWrt) | 192.168.10.200 | NAS for cams 1–2 (sda1/sda2) + spare (sda3); **runs the player** on :8800. SSH **:8822**. |
| `wrt1200ac` (Linksys WRT1200AC, OpenWrt) | 192.168.10.100 | NAS for cams 3–4 (sdb1/sdb2). SSH **:8822**. |
| Frigate box (Windows + go2rtc) | 192.168.10.240 | **go2rtc :1984** — live H264 transcode/WebRTC for all 4 cams. |
| Cameras (chuangmi.camera.81ac1) | .221/.222/.223/.224 | record to SMB; go2rtc pulls live. |

SMB user `pi` (same password on both NAS). 4 cams: `B88880974A38`(c700_01), `B88880A0FD7C`(c700_02),
`B88880976D02`(c700_03), `B88880976D36`(c700_04). c700_05 = empty spare disk.

## Data paths

- **Recordings:** cameras → SMB → `/mnt/sdaN` (wrt32x) & `/mnt/sdbN` (wrt1200ac). The player
  reads filenames to build a per-day timeline and streams chunks via HTTP Range. wrt32x reaches
  wrt1200ac's two shares via read-only **cifs** mounts (`/mnt/c700_03`, `/mnt/c700_04`).
- **Live:** browser ⇄ **go2rtc (.240)** directly over WebRTC (the player only embeds it; nothing
  streams through wrt32x). Browsers that support **WebRTC-H265** (Chrome 136+/Safari) play the
  camera's **native H265 sub-stream `c700_0X_sub1080` directly — no transcode** (original quality,
  ~zero `.240` load); others fall back to the **H264** transcode `c700_0X_1080p`. The player
  feature-detects and picks per browser. (H265 in a plain `<video>` MP4 also plays natively on
  macOS, which is why recordings always played.)

## Files

| File | Deploys to | Purpose |
|------|-----------|---------|
| `./xiaomi_playback.py` | wrt32x `/usr/local/bin/xiaomi_playback.py` | The whole app (HTTP server + inline HTML/CSS/JS). Pure stdlib, read-only. |
| `python3-sda3` | wrt32x `/usr/local/bin/python3-sda3` | Wrapper that runs Python from the data disk `/mnt/sda3` (flash too small). |
| `xiaomi-mounts.sh` | wrt32x `/usr/local/bin/xiaomi-mounts.sh` | Idempotent read-only cifs mount of wrt1200ac's c700_03/04 (cron + service call it). |
| `xiaomi-playback.init` | wrt32x `/etc/init.d/xiaomi-playback` | procd service: symlinks local disks → c700_*, mounts cifs, runs the player on :8800. |
| `go2rtc.yaml` | Frigate box (.240) `E:\Docker\frigate\go2rtc\go2rtc.yaml` | go2rtc live config (token redacted). |

Plans / runbooks:
- `./deploy-xiaomi-playback-on-wrt32x.md` — **production**: install on wrt32x (Python on
  /mnt/sda3, cifs, procd). The canonical scripts above are what it installs.
- `./deploy-xiaomi-playback.md` — alt/fallback: run the player on a Mac/PC over CIFS.
- `../../plans/deploy-camera-rotate.md` + `../../template/camera-rotate.sh` — disk auto-rotation
  (prunes oldest chunks) on each NAS.

## Player features (xiaomi_playback.py)

UI is all English; the page opens to a **4-cell live split** by default (`START_LIVE=true`,
`START_SPLIT=4`, both near the top of the JS).

- **Mode = time × split.** Two sliding segmented toggles in the **fixed bottom nav bar** drive
  everything: **Live / Playback**, and the cell count **1 / 2 / 4 / 6**. Their product is the
  current mode (`currentMode()` → `live` | `livegrid` | `play` | `pbgrid`), applied by
  `applyMode(time, n)`. 1 = single view; 2/4/6 = split grid (cameras 05/06 are reserved cells).
- **Camera names are decoupled from go2rtc.** Internal stream/disk names stay lowercase
  `c700_0X`; the UI shows display names from `CAM_NAMES` (`CAM 1`…`CAM 6`, via `dispCam()`).
  Edit `CAM_NAMES` to rename without touching stream wiring.
- **Timeline playback:** multi-root per-day strip; drag-to-seek with a timestamp bubble (snaps to
  the nearest recording if you land in a gap); prev/next **clip**; ±10s; speed; cross-camera time
  alignment. Recorded spans render as **solid green**; real recording gaps stay **dark** (a dark band
  = a genuine gap, not a segment seam). The in-progress chunk shows a **`● REC`** badge (single
  playback) and an amber edge on the timeline. A collapsible **date + hour/min/sec wheel picker** ("Go
  to time") jumps to an exact moment (hour/min/sec loop). On touch, a timeline drag commits to where
  the finger was just before release (skips finger-lift jitter).
- **Live (go2rtc):** single live + live split use the go2rtc `<video-stream>` component (its
  `video-rtc.js`/`video-stream.js` proxied same-origin) — no iframe. Native H265 over WebRTC when
  supported, else H264 transcode. A top-right **`● RTC`** / **`● MSE`** badge shows the negotiated
  protocol. **Stall watchdog:** a cell with no advancing frames ~6 s auto-reconnects.
- **Playback split:** the cameras' **recordings** synced to one timeline — drag / ±10s / seg / speed
  act on all. Bottom transport **Play all / Pause all / Sync**. One cell is the **master**, marked
  **`REF`** (amber); timeline/playhead/sync follow it. In playback split the top camera selector picks
  the master; **Sync** pauses all (freezing the instant), aligns every cell to the master, then leaves
  them paused for you to hit Play all. **Periodic re-sync:** every 2 s a playing cell drifting >1.5 s
  from the master is nudged back (a cell you manually dragged stays independent until Sync / Play all /
  timeline-drag).
- **Per-cell controls in a grid** (camera picker top-left, refresh `↻` left, zoom `⤢` right) plus a
  `⛶` **fill-screen** button (CSS viewport fill, not OS fullscreen) reveal on **hover** (desktop) or on
  **tap then auto-fade ~3 s** (touch). In **live split** the global camera selector is hidden — each
  cell's own top-left picker assigns its camera.
- Consts at the top of the JS: `GO2RTC`, `RTC_H265 = webrtcCanH265()`, `START_LIVE`, `START_SPLIT`,
  and the **`QUALS`** quality menu (**Direct** → `_sub1080`/webrtc · **Transcode** → `_1080p`/webrtc).
  Plus a `GO2RTC` const on the Python side for the JS proxy — change the go2rtc IP in **both** spots if
  it moves.

## go2rtc requirement for live

`go2rtc.yaml` must have `api: origin: "*"` — otherwise go2rtc returns **403** on the cross-origin
WebSocket from the player page and the live/grid goes black. Live (H265-capable browsers) pulls
`c700_0X_sub1080` directly; only Firefox/Edge trigger the `c700_0X_1080p` H264 transcode. See the
runbook §13 for the codec/stutter/MSE tradeoffs.
