# Xiaomi camera playback + live — file index & architecture

Self-hosted review/monitoring for 4 Xiaomi C700 cameras: a single-file, zero-dependency
Python web app gives a **timeline playback** of the SMB recordings **and** a **live view**
(single + 2×2 grid) sourced from go2rtc. Runs always-on **on the WRT32X NAS itself**.

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

- Multi-root timeline playback; per-camera day strip; drag-to-seek with a live timestamp bubble;
  prev/next-segment; cross-camera time alignment; "录制中" badge on the in-progress chunk.
- **View modes — a 4-way segmented switch in the header** (current mode amber-highlighted, unified
  `setMode()`): **`回放` · `直播` · `⊞ 直播分屏` · `⊞ 回放分屏`**. Default opens to single **直播**.
  Camera names show as **uppercase `C700_0X`** (mount/share names stay lowercase).
- **Live (go2rtc):** single 直播 + 直播分屏 use the go2rtc `<video-stream>` component (its
  `video-rtc.js`/`video-stream.js` proxied same-origin) — no iframe. Native H265 over WebRTC when
  supported, else H264 transcode. A `● 实时 · RTC`/`· MSE` badge (top-right, offset left of the native
  volume button) shows the protocol. **Stall watchdog:** a cell frozen ~3 s auto-reconnects.
- **Playback grid (`⊞ 回放分屏`):** 2×2 of the cameras' **recordings** synced to one timeline —
  drag/±10s/seg/speed act on all. Per cell: native controls, a `⤢` page-fill zoom (not OS fullscreen).
  Bottom transport: `▶︎ 全部播放 / ⏸ 全部暂停 / ⇄ 同步`. The top dropdown picks the **master (基准)**;
  timeline/playhead/sync follow it. **⇄ 同步** pauses all (freezing the instant), aligns every cell to
  the master, then leaves them paused for you to hit 全部播放. **Periodic re-sync:** every 2 s a playing
  cell drifting >1.5 s from master is nudged back (a cell you manually dragged stays independent until
  同步 / 全部播放 / timeline-drag).
- Keys: `空格` play · `←/→` ±10s · `,`/`.` prev/next seg · `R` refresh · `L` 直播 · `G` 直播分屏 ·
  `P` 回放分屏 (each toggles back to 回放).
- Consts at the top of the JS: `GO2RTC`, `RTC_H265 = webrtcCanH265()`, and the **`QUALS`** quality
  menu (原画1080P → `_sub1080`/webrtc · 转码1080P → `_1080p`/webrtc), `START_LIVE`. Plus a `GO2RTC`
  const on the Python side for the JS proxy. Change the go2rtc IP in **both** spots if it moves.

## go2rtc requirement for live

`go2rtc.yaml` must have `api: origin: "*"` — otherwise go2rtc returns **403** on the cross-origin
WebSocket from the player page and the live/grid goes black. Live (H265-capable browsers) pulls
`c700_0X_sub1080` directly; only Firefox/Edge trigger the `c700_0X_1080p` H264 transcode. See the
runbook §13 for the codec/stutter/MSE tradeoffs.
