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
  camera's **native H265 sub-stream `c700_0X_sub` directly — no transcode** (original quality,
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
- **Live (go2rtc):** `看直播/看回放` toggle (single cam) + **`⊞ 四分屏`** 2×2 live grid; default
  opens to live. Both use the go2rtc `<video-stream>` component (its `video-rtc.js`/`video-stream.js`
  proxied same-origin by the player) — no iframe. Native H265 over WebRTC when supported, else H264
  transcode. A `● 实时 · RTC`/`· MSE` badge shows the actual protocol. **Stall watchdog:** a live
  cell frozen >6 s (connected but no frames) auto-reconnects.
- **Playback grid (`⊞ 回放分屏`, key `P`):** 2×2 of all 4 cameras' **recordings** synced to one
  timeline — drag/±10s/seg/speed/play act on all 4. The top dropdown picks the **master camera**
  (amber-highlighted, `· 基准`): timeline coverage, playhead, and sync baseline follow it.
  Synchronized start (waits for all to buffer) + periodic re-sync (drift >1.5 s nudged every 2 s).
- Keys: `空格` play · `←/→` ±10s · `,`/`.` prev/next seg · `R` refresh · `L` live/playback ·
  `G` live grid · `P` playback grid.
- `GO2RTC` / `LIVE_SUFFIX` (=`webrtcCanH265()?'_sub':'_1080p'`) / `LIVE_MODE` / `START_LIVE` consts
  at the top of the JS; `GO2RTC` (Python) for the JS proxy. Change the go2rtc IP in **both** spots.

## go2rtc requirement for live

`go2rtc.yaml` must have `api: origin: "*"` — otherwise go2rtc returns **403** on the cross-origin
WebSocket from the player page and the live/grid goes black. Live (H265-capable browsers) pulls
`c700_0X_sub` directly; only Firefox/Edge trigger the `c700_0X_1080p` H264 transcode. See the
runbook §13 for the codec/stutter/MSE tradeoffs.
