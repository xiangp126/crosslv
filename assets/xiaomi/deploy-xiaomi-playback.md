# Deploy `xiaomi_playback.py` — timeline playback for Xiaomi SMB recordings

A lightweight, zero-dependency timeline player for the Xiaomi C700 recordings the
four cameras upload to two NAS boxes (`wrt32x`, `wrt1200ac`). It runs **on your
Mac/Windows machine** and reads the footage over CIFS mounts of the SMB shares —
the NAS only ever serves plain file reads.

Companion script: **`./xiaomi_playback.py`** — the server the steps below
run.

> **Production setup runs on the NAS, not the Mac.** The always-on deployment runs the
> player on `wrt32x` itself — see **`deploy-xiaomi-playback-on-wrt32x.md`**. This
> Mac/CIFS guide is the optional fallback for running it from your laptop.
>
> The player also has a **live view** (single, or a 2/4/6-cell split grid) via go2rtc — see
> `deploy-xiaomi-playback-on-wrt32x.md` §13 and `./`. All the deployment
> artifacts (server, wrapper, cifs/procd scripts, go2rtc.yaml) live in `./`.

---

## 1. Why this and not Jellyfin/Plex

Jellyfin/Plex/Emby are media *libraries*: they treat each 128 MB chunk as a movie,
scrape metadata, and burn themselves out generating thousands of thumbnails — with
no time axis, no scrubbing, no cross-chunk continuous play. For ~1 TB / ~8000 chunks
across four cameras that is exactly the wrong tool.

`xiaomi_playback.py` instead reads only **filenames** to build a per-day timeline
(`00_<start>_<end>.mp4` already encodes the times), and streams just the current
~128 MB chunk on demand via HTTP Range. So total footage size is irrelevant to RAM /
bandwidth; parsing a few thousand filenames takes under a second.

---

## 2. Recording layout (the source of truth)

Four cameras across **two** NAS boxes (same `pi` SMB credentials on both):

| Camera (MAC)   | NAS         | LAN IP         | SMB share | NAS disk    |
|----------------|-------------|----------------|-----------|-------------|
| `B88880974A38` | `wrt32x`    | 192.168.10.200 | `c700_01` | `/mnt/sda1` |
| `B88880A0FD7C` | `wrt32x`    | 192.168.10.200 | `c700_02` | `/mnt/sda2` |
| `B88880976D02` | `wrt1200ac` | 192.168.10.100 | `c700_03` | `/mnt/sdb1` |
| `B88880976D36` | `wrt1200ac` | 192.168.10.100 | `c700_04` | `/mnt/sdb2` |

- `wrt32x` = Linksys WRT32X / Armada-385 (ImmortalWrt); `wrt1200ac` = Linksys
  WRT1200AC (kernel 6.6, armv7l). Both resolve via mDNS as `<name>.local`. SMB
  user `pi` (same password on both). Root SSH: `wrt32x` per
  `../../plans/deploy-camera-rotate.md`; `wrt1200ac` on **port 8822**
  (`ssh -p 8822 -l root wrt1200ac.local`).
- `wrt32x` also exports a spare disk `c700_05` (empty for now — reserved for a
  future 5th camera). It **is** passed as a root, but contributes no entry in the
  dropdown until a camera actually records there, at which point it appears
  automatically (hit ↻ or reload). `wrt1200ac` also exports an unrelated `sword`
  share — that one is not a camera, don't pass it as a root.
- Chunk names: `00_YYYYMMDDHHMMSS_YYYYMMDDHHMMSS.mp4`, ~128 MB, lexical order =
  chronological. (Same layout `camera-rotate.sh` prunes — see
  `../../plans/deploy-camera-rotate.md`.) The in-progress chunk has `start == end`; the
  player flags it amber / LIVE.

The player takes **multiple root dirs**; each mount point contains one
`XiaomiCamera_*` folder, so all four cameras land in one dropdown.

---

## 3. macOS deploy (primary)

### 3.1 Mount all four shares

Finder → ⌘K → connect to each (same `pi` password on both boxes; tick
"Remember in my keychain" so it won't re-prompt next time):

```
smb://pi@wrt32x.local/c700_01
smb://pi@wrt32x.local/c700_02
smb://pi@wrt32x.local/c700_05      # spare/empty, optional — armed for a future camera
smb://pi@wrt1200ac.local/c700_03
smb://pi@wrt1200ac.local/c700_04
```

They appear at `/Volumes/c700_01` … `/Volumes/c700_05`. (If a name doesn't
resolve, use the IP from §2.) Scriptable alternative — auto-creates the
mountpoints, uses Keychain or pops one auth dialog per host:

```sh
for s in c700_01 c700_02 c700_05; do osascript -e "mount volume \"smb://pi@wrt32x.local/$s\""; done
for s in c700_03 c700_04;        do osascript -e "mount volume \"smb://pi@wrt1200ac.local/$s\""; done
```

Sanity-check the camera mounts hold one camera folder each (c700_05 is empty):

```sh
ls -d /Volumes/c700_0[1-4]/XiaomiCamera_*   # four dirs, one per mount
```

### 3.2 Run

```sh
python3 assets/xiaomi/xiaomi_playback.py /Volumes/c700_0{1,2,3,4,5} 8800
```

The banner lists the cameras it found. Open **http://localhost:8800/**. It
auto-selects the latest day with recordings.

> Last positional arg that is all digits is treated as the port (default `8800`);
> everything else is a root dir. With no args it defaults to all five mounts
> (`/Volumes/c700_01 … c700_05`, port 8800), so plain
> `python3 …/xiaomi_playback.py` works once the shares are mounted. `c700_05` is
> the empty spare — it's harmless to list and yields no camera until populated.

**Cross-camera time alignment:** pick a time on one camera (say 10:10), then switch
cameras — the new camera jumps to the **same day & time**, or to the nearest footage
if it has a gap there, preserving play/pause state. ↻ re-detects cameras (so a newly
added camera, e.g. on `c700_05`, shows up without restarting the server).

### 3.3 Leave it running (optional)

To keep it up after you close the terminal, start it detached:

```sh
nohup python3 assets/xiaomi/xiaomi_playback.py >/tmp/xiaomi-playback.log 2>&1 &
```

It survives the shell but **not** a reboot/logout — after a reboot you must remount
the shares (§3.1) and start it again.

### 3.4 Access from another machine on the LAN

`localhost` needs no firewall change. To reach it from another device, allow the
port through the macOS application firewall (System Settings → Network → Firewall →
Options → allow incoming for `python3`), then browse `http://<mac-ip>:8800/`.

---

## 4. Windows deploy (alt)

Map the shares to drive letters (File Explorer → Map network drive, e.g. `Z:` →
`\\wrt32x\c700_01`, `Y:` → `\\wrt32x\c700_02`, `X:` → `\\wrt1200ac\c700_03`,
`W:` → `\\wrt1200ac\c700_04`), then:

```bat
python xiaomi_playback.py Z:\ Y:\ X:\ W:\ 8800
```

Optional autostart via Task Scheduler ("At log on" → start `python.exe` with those
args). Allow the port in Windows Defender Firewall only if accessing from another
machine.

---

## 5. Does always-on pressure the router?

**No.** The server runs on your Mac/PC, not the WRT32X, and the cost to the NAS is
zero at rest:

- **Idle** — the web UI has no background polling (no `setInterval`); once a day is
  loaded it makes no further requests. An idle (even open-but-idle) browser, or a
  running server with no browser at all, generates **zero** SMB traffic.
- **Browsing** — clicking a day triggers one directory listing over SMB (sub-second
  for ~2000 files per camera), cached for 15 s, so repeated clicks don't re-list.
  Filenames only; video files are never opened to build the timeline. The two NAS
  boxes are independent — a given camera only ever touches its own box.
- **Playback** — streams the current 128 MB chunk in 256 KB Range reads. That's the
  same I/O profile the camera already sustains *writing* the chunk — trivial for a
  box `camera-rotate.sh` clears 96 GB from in ~30 s.

The NAS `deadtime = 30` drops idle SMB sessions; the client reconnects on demand.
The only standing cost of "always-on" is a tiny idle Python process on your Mac.

The player is **read-only** — it never writes to the shares, so it cannot conflict
with the cameras' uploads or with `camera-rotate.sh`.

---

## 6. Verification

```sh
# 6.1 syntax
python3 -m py_compile assets/xiaomi/xiaomi_playback.py && echo "syntax OK"

# 6.2 smoke test WITHOUT the NAS — dummy tree of correctly-named empty files
TMP=$(mktemp -d)
mkdir -p "$TMP/XiaomiCamera_00_TEST"
: > "$TMP/XiaomiCamera_00_TEST/00_20260603160000_20260603161000.mp4"
: > "$TMP/XiaomiCamera_00_TEST/00_20260603161000_20260603162000.mp4"
python3 assets/xiaomi/xiaomi_playback.py "$TMP" 8801 &   # serve the dummy tree
sleep 1
curl -s localhost:8801/api/cameras                                   # -> [{"id":"0:XiaomiCamera_00_TEST",...}]
curl -s 'localhost:8801/api/timeline?cam=0:XiaomiCamera_00_TEST'     # -> {"days":[{"date":"2026-06-03","count":2}]}
curl -s 'localhost:8801/api/segments?cam=0:XiaomiCamera_00_TEST&date=2026-06-03'
curl -s -D- -o /dev/null -r 0-1023 \
  'localhost:8801/video?cam=0:XiaomiCamera_00_TEST&file=00_20260603160000_20260603161000.mp4'
# (empty files -> 416/no body; with a real mp4 expect HTTP/1.0 206 + Content-Length: 1024)
kill %1; rm -rf "$TMP"
```

Live test (mounts up): dropdown lists **all four** cameras; latest day pre-selected;
green blocks line up with recorded spans (amber = in-progress LIVE chunk); dragging
the timeline moves the playhead live and seeks on release; a chunk ending
auto-advances to the next; a real chunk returns `206` with `Content-Length: 1024`
for `-r 0-1023`.

---

## 7. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Banner says "未发现任何 XiaomiCamera_* 目录" | Shares not mounted, or wrong root path. Check `ls /Volumes/c700_0*`. |
| Dropdown shows fewer than 4 cameras | A share isn't mounted, or fewer roots passed. Check `ls -d /Volumes/c700_0[1-4]/XiaomiCamera_*` (4 expected). |
| Video won't seek / scrub jumps to 0 | Browser couldn't get Range — confirm `curl -r` returns `206` (not `200`). |
| Day strip empty but files exist | Filenames don't match `00_<14>_<14>.mp4`. Check the camera firmware's naming. |
