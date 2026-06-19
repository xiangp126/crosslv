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
| *(OCR engine, not in repo)* | wrt32x `/mnt/sda3/opt/ocr/` | onnxruntime-web runtime + **`rec_v4_server.onnx`** (PP-OCRv4-server) + `ppocr_keys.txt` + tesseract.js fallback. Served same-origin at `/ocr/`. Re-host per `ocr-precise-sync.md`. |

Plans / runbooks:
- `./deploy-xiaomi-playback-on-wrt32x.md` — **production**: install on wrt32x (Python on
  /mnt/sda3, cifs, procd). The canonical scripts above are what it installs.
- `./deploy-xiaomi-playback.md` — alt/fallback: run the player on a Mac/PC over CIFS.
- `./ocr-precise-sync.md` — **Precise-sync OCR**: design, model choice (why PP-OCRv4-server), and the
  full local-deploy + verification process for the in-browser OCR engine.
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
- **Timeline playback:** pick the **day** from the **date dropdown in the bottom nav bar** (shows
  `MM-DD weekday · clip-count`, e.g. `06-18 Thu · 141`); pick the **time** by dragging the timeline
  (timestamp bubble; snaps to the nearest recording if you land in a gap) or via the collapsible
  **hour/min/sec wheel** (`📅` "Go to time" — time-only, same day; hour/min/sec loop). **Prev/Next clip**
  and **±10s** live on the **transport row** (playback only); plus speed + cross-camera time alignment.
  Recorded spans render as **solid green**; real recording gaps stay **dark** (a dark band = a genuine
  gap, not a segment seam). The in-progress chunk shows a **`● REC`** badge (single playback) and an
  amber edge on the timeline. The current moment is shown once in the **`📅` clock** (no duplicate
  readout); on touch, a timeline drag commits to where the finger was just before release (skips
  finger-lift jitter). The bottom nav bar **wraps to fit on phones** (no off-screen controls).
- **Live (go2rtc):** single live + live split use the go2rtc `<video-stream>` component (its
  `video-rtc.js`/`video-stream.js` proxied same-origin) — no iframe. Native H265 over WebRTC when
  supported, else H264 transcode. A top-right **`● RTC`** / **`● MSE`** badge shows the negotiated
  protocol. **Stall watchdog:** a cell with no advancing frames auto-reconnects — a few fast retries,
  then a slow ~12 s backoff that **never permanently gives up**, so a flaky WebRTC source (e.g. a camera
  whose go2rtc transcode hiccups) recovers on its own once the stream settles.
- **Playback split:** the cameras' **recordings** synced to one timeline — drag / ±10s / seg / speed
  act on all. Bottom transport **Play all / Pause all**, plus a **`⇄ Coarse | ◎ Precise`** sync-mode
  toggle. One cell is the **master**, marked **`REF`** (amber); timeline/playhead follow it; the top
  camera selector picks the master. **Coarse** aligns every cell by assumed (filename) time. **Precise**
  OCR-reads each cell's burned-in clock and aligns to the master's real time (±1 s) — see *Precise sync*
  below. A 500 ms **offset-aware maintenance loop** keeps non-master cells locked to the master (rate-nudge
  for small drift, hard-seek for large, cross-clip when the master moves past a clip). **Non-master cells
  are ALWAYS pulled back** — dragging one is undone on purpose (workflow: pause the others, scrub the
  master to the key moment, then **Play all** to resync everyone). Real time is the simple
  `s0 + currentTime (+ OCR offset)` and every cell plays at the selected speed. (Each camera's media clock
  actually ticks ~1 % off real time and differs per camera, so cells drift apart slowly over a clip and snap
  back at each crossing/recal; a per-clip "slope" correction was tried to remove that but it made non-master
  cells stutter, so it was reverted — a smooth view with slow drift beats a stuttering one.) **Background-tab recovery:** browsers
  throttle the 500 ms loop to a crawl when the tab is hidden, so a cell left at a >1× catch-up rate keeps
  playing and **runs away** (e.g. "came back later and CAM3 is ~70 s ahead"). A `visibilitychange` handler
  freezes all rates to base on hide and **re-aligns every playing cell to the master on return**, so leaving
  and coming back finds it synced (paused cells stay paused — pause workflow preserved). A **watchdog** rolls a cell that
  reaches/stalls at a clip end over to the next clip, and reloads a genuinely black/frozen cell — but
  **never interrupts a cell that's still downloading**, which used to leave cells stuck black. Two things
  count as "still loading, don't touch": the buffered range is growing, **and** the cell is in its **initial
  cold load** — a 4K-H265 clip reports `buffered.end = 0` from `loadstart` until `canplay` (~7 s+, longer for
  the slow remote cams under 4-way contention), so a `~15 s` grace (`PB_COLD_MS`) holds off any reload until
  it has buffered something. Reloading inside that window restarts the load from scratch so it **never
  finishes** — this was the real cause of "playback loads so slowly / a cell never loads" (proven: killing
  the watchdog let stuck cells load immediately; the sync/maintenance loop was **not** the cause, it never
  touches a cell at `readyState < 1`). A cell **loading a new clip** (tail roll-over or relocate) shows
  **`Loading…`** and is skipped until frames flow. **Decoder-queue wait:** a cell that has never produced a
  frame (no error, buffered still 0) is queued for a decoder — Safari caps concurrent 4K-H265 decodes, so the
  4th cell in a 4-split waits. The watchdog keeps its load **open** and just shows `Loading…`; it does **not**
  reload it (reloading discards the download and drops the src, so it misses the decoder another cell frees on
  a crossing — that churn was the "cells stuck loading forever" bug). It loads on its own once a decoder frees
  (verified: a 4-split reached **4/4 with 0 reloads**). Reloads (backoff, never a dead `No video`) fire only
  on a real error or a post-data mid-play stall. If a Mac can't fit all four 4K decodes, 2-split always works.
  Because these fMP4 (`moov duration=0`) report no duration until warmed, a seek **poll-retries
  until it actually lands** — a cold first click no longer snaps to the clip edge.
- **Precise sync (OCR, local):** reads the white burned-in timestamp (top-left of each SOURCE frame, a
  resolution-based crop so it's screen/layout independent) and aligns cells to the master's true time.
  All-or-nothing: only if **every** cell's clock is verified does it move them; otherwise it stays in
  Precise and retries on each segment change. Each cell's offset is the **average of several frame reads**
  (~8, outlier-rejected) — the burned clock is whole-seconds, so averaging frames spread over >1 s drives
  the unknown sub-second fraction to a **common ~0.5 s bias on every cell**, which cancels in the *relative*
  alignment → cells land together in one click (two-sample agreement used to leave them >2 s apart, "needs
  two clicks"). After a cell crosses into a new clip its offset is re-calibrated **once** (the per-crossing
  `recal`, shown in the debug window). OCR runs **fully in-browser** — **PaddleOCR PP-OCRv4-server** (ONNX) via **onnxruntime-web**,
  frames never leave the LAN; **tesseract.js is the fallback**. Engine files are hosted on the router under
  `/ocr/` (see Files). A combined debug window (double-click or **30 s** auto-hide after the last update)
  shows each cell's crop + read. Heavy enough that **iPad can't run it** (use Mac/iPhone); see
  `ocr-precise-sync.md` for the model choice + deployment.
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
