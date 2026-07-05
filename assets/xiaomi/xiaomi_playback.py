#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
xiaomi_playback.py  --  Lightweight timeline playback service for Xiaomi camera SMB recordings

Xiaomi lays out each camera's recordings flat inside one folder, named like
    XiaomiCamera_00_B88880974A38/
with file names like
    00_20260603160305_20260603160947.mp4
i.e.  <channel>_<start YYYYMMDDHHMMSS>_<end YYYYMMDDHHMMSS>.mp4

This service reads only the "file names" to rebuild each day's timeline (it never opens
the video files to parse them), then streams a single segment on demand via HTTP Range, so:
  * parsing a few thousand files takes under a second;
  * playback only streams the current ~128MB segment, so how many GB are on disk is
    irrelevant to the browser/memory;
  * dragging the progress bar / clicking the timeline can seek normally.

Multiple root directories (multiple disks / multiple cameras) are supported. If a disk has
one or more XiaomiCamera_* subdirectories, they are all aggregated into the same dropdown.

Usage:
    python3 xiaomi_playback.py [ROOT ...] [PORT]

    ROOT  The "parent directory" containing the XiaomiCamera_* folders; multiple may be given
          (you can also point it directly at a single camera folder).
          If omitted, defaults to /Volumes/c700_01 /Volumes/c700_02 (macOS CIFS mount points).
    PORT  If the last argument is a plain number it is used as the port; default is 8800.

Examples:
    python3 xiaomi_playback.py /Volumes/c700_01 /Volumes/c700_02 8800
    python3 xiaomi_playback.py /mnt/sda1 /mnt/sda2

Then open in a browser  http://<local IP>:8800/   (or http://127.0.0.1:8800/)
"""

import os
import re
import sys
import time
import datetime
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import urllib.request
import json

# --------------------------------------------------------------------------- #
# Configuration / constants
# --------------------------------------------------------------------------- #
DEFAULT_ROOTS = [
    "/Volumes/c700_01",   # wrt32x    /mnt/sda1  XiaomiCamera_00_B88880974A38
    "/Volumes/c700_02",   # wrt32x    /mnt/sda2  XiaomiCamera_00_B88880A0FD7C
    "/Volumes/c700_03",   # wrt1200ac /mnt/sdb1  XiaomiCamera_00_B88880976D02
    "/Volumes/c700_04",   # wrt1200ac /mnt/sdb2  XiaomiCamera_00_B88880976D36
    "/Volumes/c700_05",   # wrt32x    /mnt/sda3  XiaomiCamera_00_B88880948BA0
]
DEFAULT_PORT = 8800

# go2rtc (Frigate machine): the player same-origin proxies its video-stream component JS,
# bypassing the CORS restriction on cross-origin ES modules.
GO2RTC = "http://192.168.10.240:1984"
_JS_CACHE = {}
_JS_LOCK = threading.Lock()

# Locally-hosted tesseract.js OCR engine (served same-origin at /ocr/<file>); computation runs in the browser, this server only serves the static files.
OCR_DIR = "/mnt/sda3/opt/ocr"
_OCR_CT = {".js": "text/javascript; charset=utf-8", ".mjs": "text/javascript; charset=utf-8",
           ".wasm": "application/wasm", ".onnx": "application/octet-stream",
           ".gz": "application/octet-stream", ".traineddata": "application/octet-stream", ".txt": "text/plain; charset=utf-8"}

# File name recognition: 00_<14-digit start>_<14-digit end>.mp4
FN_RE = re.compile(r"(\d{14})_(\d{14})\.mp4$", re.IGNORECASE)
# Camera folder recognition (Xiaomi default prefix)
CAM_RE = re.compile(r"xiaomicamera", re.IGNORECASE)

# Camera display name: defaults to the "share name" (mount point name, e.g. c700_01). For a more
# readable name, fill it in here keyed by MAC to override (leave "" to use the share name).
# The key is the 12-char MAC.
CAM_NAMES = {
    "B88880974A38": "",   # c700_01 · wrt32x    · sda1
    "B88880A0FD7C": "",   # c700_02 · wrt32x    · sda2
    "B88880976D02": "",   # c700_03 · wrt1200ac · sdb1
    "B88880976D36": "",   # c700_04 · wrt1200ac · sdb2
    "B88880948BA0": "",   # c700_05 · wrt32x    · sda3
}


def _cam_label(folder, share):
    """Dropdown display name: a friendly name filled into CAM_NAMES takes priority;
    otherwise use the share name `share` (e.g. c700_01).
    `folder` looks like XiaomiCamera_00_<MAC>."""
    m = re.search(r"([0-9A-Fa-f]{12})$", folder or "")
    if m:
        name = CAM_NAMES.get(m.group(1).upper())
        if name:
            return name
    return share   # internally always use the lowercase share name (c700_01); the page shows uppercase C700 via CSS text-transform

CACHE_TTL = 15.0  # seconds: how long scan results are cached; after that it auto-rescans to discover new files
LIVE_STALE_SEC = 300.0  # a start==end chunk not written for this long = abandoned (camera froze), not truly in-progress

ROOTS = list(DEFAULT_ROOTS)
PORT = DEFAULT_PORT

_seg_cache = {}            # cam_id -> (scan_time, segments)
_seg_lock = threading.Lock()
_reg_cache = {"t": 0.0, "reg": {}}   # camera registry cache
_reg_lock = threading.Lock()


# --------------------------------------------------------------------------- #
# Camera registry: maps (root, folder) to a safe cam_id, preventing path traversal
# --------------------------------------------------------------------------- #
def _build_registry():
    """Returns OrderedDict: cam_id -> {"id","label","dir"}.
    Each XiaomiCamera_* subdirectory under a root counts as one camera; if a root has no such
    subdirectory (it holds recording segments directly, or it is still an empty spare disk), the
    root itself is treated as one camera — so the empty disk c700_05 also appears in the dropdown
    by its share name (no recordings yet), and will be picked up automatically once a camera
    starts writing into it (at that point cid changes from "i:." to "i:XiaomiCamera_...", the
    label still being the share name)."""
    reg = {}
    for i, root in enumerate(ROOTS):
        if not root or not os.path.isdir(root):
            continue
        subs = []
        try:
            with os.scandir(root) as it:
                for ent in it:
                    try:
                        if ent.is_dir() and CAM_RE.search(ent.name):
                            subs.append(ent.name)
                    except OSError:
                        continue
        except OSError:
            continue
        subs.sort()
        share = os.path.basename(os.path.normpath(root)) or root
        if subs:
            multi = len(subs) > 1
            for name in subs:
                cid = "%d:%s" % (i, name)
                lbl = _cam_label(name, share)
                if multi and lbl == share:        # when one disk has multiple cameras, use the MAC tail to tell them apart
                    mac = re.search(r"([0-9A-Fa-f]{12})$", name)
                    if mac:
                        lbl = "%s·%s" % (share, mac.group(1)[-4:])
                reg[cid] = {"id": cid, "label": lbl, "dir": os.path.join(root, name)}
        else:
            cid = "%d:." % i
            reg[cid] = {"id": cid, "label": _cam_label(share, share), "dir": root}
    return reg


def registry():
    now = time.time()
    with _reg_lock:
        r = _reg_cache["reg"]
        if r and now - _reg_cache["t"] < CACHE_TTL:
            return r
    reg = _build_registry()
    with _reg_lock:
        _reg_cache["t"] = now
        _reg_cache["reg"] = reg
    return reg


def list_cameras():
    """Returns [{id,label}], across all root directories."""
    return [{"id": c["id"], "label": c["label"]} for c in registry().values()]


def cam_dir(cam_id):
    """Resolves cam_id to a disk directory; only via the registry, never concatenating untrusted input → no path traversal."""
    c = registry().get(cam_id)
    if c and os.path.isdir(c["dir"]):
        return c["dir"]
    return None


# --------------------------------------------------------------------------- #
# Index: read file names only
# --------------------------------------------------------------------------- #
def _parse_name(name):
    m = FN_RE.search(name)
    if not m:
        return None
    try:
        s = datetime.datetime.strptime(m.group(1), "%Y%m%d%H%M%S")
        e = datetime.datetime.strptime(m.group(2), "%Y%m%d%H%M%S")
    except ValueError:
        return None
    return s, e


def scan(cam_id):
    """Scans all recognizable segments under a camera directory (with a short cache)."""
    now = time.time()
    with _seg_lock:
        c = _seg_cache.get(cam_id)
        if c and now - c[0] < CACHE_TTL:
            return c[1]

    d = cam_dir(cam_id)
    segs = []
    if d and os.path.isdir(d):
        try:
            with os.scandir(d) as it:
                for ent in it:
                    try:
                        if not ent.is_file():
                            continue
                    except OSError:
                        continue
                    pr = _parse_name(ent.name)
                    if not pr:
                        continue
                    s, e = pr
                    live = e <= s  # equal/inverted start-end = the segment currently being recorded
                    if live:
                        try:
                            fresh = (now - ent.stat().st_mtime) < LIVE_STALE_SEC
                        except OSError:
                            fresh = True
                        if fresh:
                            e = datetime.datetime.now()
                            if e <= s:
                                e = s + datetime.timedelta(seconds=1)
                        else:
                            e = s + datetime.timedelta(seconds=1)
                            live = False
                    segs.append({"file": ent.name, "start": s, "end": e, "live": live})
        except OSError:
            pass
    segs.sort(key=lambda x: x["start"])

    with _seg_lock:
        _seg_cache[cam_id] = (now, segs)
    return segs


def days_for(segs):
    """List of dates that have recordings (with a rough per-day segment count), in ascending date order."""
    days = {}
    one = datetime.timedelta(days=1)
    for sg in segs:
        cur = sg["start"].date()
        last = sg["end"].date()
        while cur <= last:
            k = cur.isoformat()
            rec = days.setdefault(k, {"date": k, "count": 0})
            rec["count"] += 1
            cur += one
    return [days[k] for k in sorted(days)]


def segs_for_day(segs, date_str):
    """All segments overlapping a given day (00:00~24:00 local time), sorted."""
    try:
        d = datetime.date.fromisoformat(date_str)
    except ValueError:
        return []
    day0 = datetime.datetime.combine(d, datetime.time.min)
    day1 = day0 + datetime.timedelta(days=1)
    out = []
    for sg in segs:
        if sg["start"] < day1 and sg["end"] > day0:
            out.append({
                "file": sg["file"],
                "start": sg["start"].isoformat(),
                "end": sg["end"].isoformat(),
                "live": sg["live"],
            })
    return out


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
class Handler(BaseHTTPRequestHandler):
    server_version = "XiaomiPlayback/1.0"

    def log_message(self, *args):
        pass  # quiet

    # -- helpers ----------------------------------------------------------
    def _json(self, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _html(self):
        body = HTML_PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _jsproxy(self, path):
        # Same-origin proxy of go2rtc's video-rtc.js / video-stream.js (with a short cache), used by the split-view component
        with _JS_LOCK:
            body = _JS_CACHE.get(path)
        if body is None:
            try:
                body = urllib.request.urlopen(GO2RTC + path, timeout=8).read()
            except Exception:
                self.send_error(502, "go2rtc unreachable")
                return
            with _JS_LOCK:
                _JS_CACHE[path] = body
        self.send_response(200)
        self.send_header("Content-Type", "text/javascript; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "max-age=3600")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _ocr_file(self, path):
        # Serve a locally-hosted tesseract.js engine file from OCR_DIR (basename only → no path traversal)
        name = os.path.basename(path[len("/ocr/"):])
        if not name or ".." in name:
            self.send_error(404); return
        fp = os.path.join(OCR_DIR, name)
        if not os.path.isfile(fp):
            self.send_error(404); return
        try:
            with open(fp, "rb") as f:
                body = f.read()
        except OSError:
            self.send_error(404); return
        ct = _OCR_CT.get(os.path.splitext(name)[1], "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "max-age=86400")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    # -- routing ----------------------------------------------------------
    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        try:
            if u.path in ("/", "/index.html"):
                self._html()
            elif u.path == "/api/cameras":
                self._json(list_cameras())
            elif u.path == "/api/timeline":
                cam = q.get("cam", [""])[0]
                self._json({"days": days_for(scan(cam))})
            elif u.path == "/api/segments":
                cam = q.get("cam", [""])[0]
                date = q.get("date", [""])[0]
                self._json({"segments": segs_for_day(scan(cam), date)})
            elif u.path == "/video":
                self._video(q)
            elif u.path in ("/video-stream.js", "/video-rtc.js"):
                self._jsproxy(u.path)
            elif u.path.startswith("/ocr/"):
                self._ocr_file(u.path)
            else:
                self.send_error(404)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as ex:  # noqa: BLE001
            try:
                self.send_error(500, str(ex))
            except Exception:
                pass

    def do_HEAD(self):
        u = urlparse(self.path)
        if u.path == "/video":
            try:
                self._video(parse_qs(u.query))
            except (BrokenPipeError, ConnectionResetError):
                pass
        else:
            self.send_error(405)

    # -- video stream (supports Range, for seeking) ----------------------
    def _video(self, q):
        cam = q.get("cam", [""])[0]
        fn = q.get("file", [""])[0]
        d = cam_dir(cam)
        if not d or not FN_RE.search(fn or ""):
            self.send_error(404)
            return
        fpath = os.path.join(d, os.path.basename(fn))
        if not os.path.isfile(fpath):
            self.send_error(404)
            return

        size = os.path.getsize(fpath)
        start, end, partial = 0, size - 1, False
        rng = self.headers.get("Range")
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)", rng.strip())
            if m:
                gs, ge = m.group(1), m.group(2)
                if gs == "" and ge != "":          # last N bytes
                    start = max(0, size - int(ge))
                    end = size - 1
                else:
                    start = int(gs) if gs else 0
                    end = int(ge) if ge else size - 1
                end = min(end, size - 1)
                if start > end or start < 0:
                    start, end = 0, size - 1
                partial = True

        length = end - start + 1
        self.send_response(206 if partial else 200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if partial:
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

        if self.command == "HEAD":
            return

        chunk = 256 * 1024
        with open(fpath, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                buf = f.read(min(chunk, remaining))
                if not buf:
                    break
                try:
                    self.wfile.write(buf)
                except (BrokenPipeError, ConnectionResetError):
                    break
                remaining -= len(buf)


# --------------------------------------------------------------------------- #
# Frontend (control-room style single page)
# --------------------------------------------------------------------------- #
HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Xiaomi Recordings Playback</title>
<style>
  :root{
    --bg:#0a0c0f; --panel:#12161b; --panel2:#0e1216; --line:#1e252d;
    --text:#c9d3da; --dim:#97a2ab; --accent:#4e9fd6; --accent2:#d2694e;   /* one restrained accent (steel-blue) for selected/active; accent2 (muted coral) only for REC/in-progress */
    --cover:#38434e; --cover2:#454f5a; --grid:#161c22;   /* recording coverage = neutral slate gray ("has recording", not an alarm) */
    --mono:ui-monospace,"SF Mono","JetBrains Mono",Menlo,Consolas,monospace;
    --ui:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",sans-serif;
  }
  *{box-sizing:border-box}
  html,body{margin:0;height:100%}
  body{background:var(--bg);color:var(--text);font-family:var(--ui);
       display:flex;flex-direction:column;min-height:100vh}
  /* ===== Nav bar: fixed at the bottom of the screen (action buttons are all down here, easier to reach); three balanced groups, color uses amber only for "selected" ===== */
  header{background:#0e1216;border-top:1px solid #1b222a;position:fixed;left:0;right:0;bottom:0;z-index:60}
  .navin{display:flex;align-items:center;gap:12px;flex-wrap:wrap;
         max-width:1180px;width:100%;margin:0 auto;box-sizing:border-box;
         padding:9px 16px calc(9px + env(safe-area-inset-bottom, 0px))}   /* bottom safe-area: keep buttons above the iOS home-gesture zone so taps register */
  .nav-left{flex:1 1 auto;display:flex;align-items:center;gap:9px;min-width:0}
  .nav-mid{flex:0 0 auto;display:flex;align-items:center;gap:8px}
  .nav-right{flex:1 1 auto;display:flex;align-items:center;justify-content:flex-end;gap:8px}
  header .dot{width:6px;height:6px;border-radius:50%;background:var(--accent);box-shadow:0 0 8px rgba(78,159,214,.5);flex:0 0 auto}
  header h1{font-size:11px;letter-spacing:.08em;text-transform:uppercase;font-weight:600;margin:0;color:var(--dim);white-space:nowrap}   /* small, dimmed wordmark — a quiet logo, not a heading that competes with the controls */
  /* Mobile: hide brand + empty right spacer so the controls aren't pushed to the very bottom edge */
  /* Mobile: hide brand + spacer, and let the control group WRAP to fit (it's ~720px wide, far past a phone's width — without this it overflows off-screen with no way to reach the right-hand controls). Wrapping keeps everything visible/tappable; a couple of widths are trimmed to pack tidily. */
  @media (max-width:760px){
    .nav-left, .nav-right{display:none}
    .navin{justify-content:center;gap:8px;padding:8px 10px calc(8px + env(safe-area-inset-bottom, 0px))}
    .nav-mid{flex:1 1 100%;flex-wrap:wrap;justify-content:center;gap:8px}
    #modebar button{width:62px}
    #dates{max-width:150px}
  }
  /* Unified control look: same height 34, same radius 9, same base */
  .navin select,.navin #refreshBtn{height:34px;font-size:13px;color:#cdd5dc;
    background:#161b21;border:1px solid #232c34;border-radius:9px;padding:0 12px;cursor:pointer;line-height:1}
  .navin select:hover,.navin #refreshBtn:hover{border-color:#36434f;background:#1b2127}
  .navin select:disabled{opacity:.45;cursor:not-allowed}   /* quality is greyed out during playback */
  /* Mode segments: pill container + inner segments, selected = amber fill */
  .modebar{display:inline-flex;align-items:center;height:34px;padding:3px;gap:2px;
    background:#12161b;border:1px solid #232c34;border-radius:10px}
  .modebar button{height:28px;border:0;background:transparent;border-radius:7px;color:var(--dim);
    padding:0 16px;font-size:13px;cursor:pointer}
  .modebar button:hover:not(.on):not(:disabled){color:var(--text);background:#1b2127}
  .modebar button.on{background:var(--accent);color:#0a0c0f;font-weight:600}
  .modebar button:disabled{opacity:.4;cursor:not-allowed}
  /* Live/Playback: toggle style — the amber slider slides between the two (the split selector is still a plain segment) */
  #modebar{position:relative;overflow:hidden;gap:0}
  #modebar::before{content:'';position:absolute;top:3px;bottom:3px;left:3px;width:calc(50% - 3px);
    background:var(--accent);border-radius:7px;transition:transform .2s ease;z-index:0;pointer-events:none}
  #modebar.t-play::before{transform:translateX(100%)}
  #modebar button{position:relative;z-index:1;width:74px;padding:0;text-align:center}   /* equal width so the slider aligns and text stays centered */
  #modebar button.on{background:transparent}                 /* highlight comes from the slider, the button itself is transparent */
  #modebar button:hover:not(.on){background:transparent}
  /* 1/2/4/6: same toggle style (4-segment slider). Buttons are equal width so the slider aligns precisely */
  #splitbar{position:relative;overflow:hidden;gap:0}
  #splitbar button{position:relative;z-index:1;width:40px;padding:0;text-align:center}
  #splitbar::before{content:'';position:absolute;top:3px;bottom:3px;left:3px;width:calc((100% - 6px)/4);
    background:var(--accent);border-radius:7px;transition:transform .2s ease;z-index:0;pointer-events:none}
  #splitbar.s-2::before{transform:translateX(100%)}
  #splitbar.s-4::before{transform:translateX(200%)}
  #splitbar.s-6::before{transform:translateX(300%)}
  #splitbar button.on{background:transparent}
  #splitbar button:hover:not(.on){background:transparent}
  #splitBtn.on{background:var(--accent);border-color:var(--accent);color:#0a0c0f;font-weight:600}
  #refreshBtn{padding:0 11px;font-size:15px}
  #qualSel{max-width:170px}
  #camSel, #camSel option{text-transform:uppercase}   /* show only uppercase C700; internal value stays lowercase */
  select,button{font-family:var(--ui);font-size:13px;color:var(--text);
    background:#171c22;border:1px solid var(--line);border-radius:6px;
    padding:7px 10px;cursor:pointer}
  select:hover,button:hover{border-color:#33414d}
  button.ghost{background:transparent}
  .accent{color:var(--accent)}
  main{flex:1;display:flex;flex-direction:column;gap:14px;max-width:1180px;width:100%;margin:0 auto;
       padding:16px 16px calc(88px + env(safe-area-inset-bottom, 0px))}   /* reserve space for the fixed bottom nav (incl. safe area) */
  .stage{position:relative;background:#000;border:1px solid var(--line);
         border-radius:10px;overflow:hidden;aspect-ratio:16/9}
  video{width:100%;height:100%;display:block;background:#000;object-fit:contain}
  #live{position:absolute;inset:0;display:none;background:#000}
  #live video-stream{position:relative;display:block;width:100%;height:100%;background:#000;overflow:hidden}
  #live video-stream video{width:100%;height:100%;object-fit:contain;display:block}
  #live video-stream .info{display:none}   /* hide the component's built-in RTC badge */
  body.live-mode #vid,
  body.live-mode .transport,
  body.live-mode .liveTag{display:none !important}   /* option two: the timeline (.dates/.tlwrap) is also kept during live */
  .liveTag{position:absolute;top:10px;right:52px;font-family:var(--mono);
    font-size:11px;color:#0a0c0f;background:var(--accent2);padding:3px 8px;
    border-radius:5px;font-weight:700;display:none}
  .grid{position:absolute;inset:0;display:none;gap:2px;background:#000;z-index:4;
    grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr}              /* default 2×2 */
  .grid[data-n="2"]{grid-template-columns:1fr 1fr;grid-template-rows:1fr}  /* 2-split: vertical cut, two cells side by side */
  .grid[data-n="4"]{grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr}
  .grid[data-n="6"]{grid-template-columns:1fr 1fr 1fr;grid-template-rows:1fr 1fr}   /* 6-split: desktop 3×2 */
  @media (max-width:760px){ .grid[data-n="6"]{grid-template-columns:1fr 1fr;grid-template-rows:repeat(3,1fr)} }  /* narrow screen 6-split: 2×3 */
  .cellmsg{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
    color:#6b7884;font-family:var(--mono);font-size:13px;pointer-events:none}   /* No signal / No recording placeholder */
  /* Split view fills the whole viewport (like a monitor wall); fill via CSS viewport instead of system fullscreen (iPad does not support requestFullscreen on a div) */
  /* Fill the whole viewport: applied to the player frame .stage → single view (#vid/#live) and split view (#grid) both fill */
  .stage.full{position:fixed;inset:0;z-index:80;background:#000;max-width:none;aspect-ratio:auto;border:0}
  body.gridfull{overflow:hidden}
  .gridfullbtn{position:absolute;top:8px;right:8px;z-index:9;cursor:pointer;user-select:none;color:#fff;
    background:rgba(10,12,15,.66);border:1px solid var(--line);border-radius:7px;padding:5px 9px;font-size:15px;line-height:1}
  .gridfullbtn:hover{background:rgba(10,12,15,.92);border-color:#34424e}
  /* Maximize / exit button: appear when the frame is hovered (desktop) or the frame is tapped (touch — .tapped set by JS); both ⛶ and ✕ */
  .gridfullbtn{opacity:0;transition:opacity .15s}
  @media (hover:hover){ .stage:hover .gridfullbtn{opacity:1} }   /* hover only on real pointers — avoids iOS sticky-hover keeping it on after a tap */
  .stage.tapped .gridfullbtn{opacity:1}
  .grid video-stream{position:relative;display:block;width:100%;height:100%;background:#000;overflow:hidden;touch-action:manipulation}
  .grid video-stream video{width:100%;height:100%;object-fit:contain;display:block}
  .grid video-stream .info{display:none}   /* hide the component's built-in RTC badge */
  video-stream .cellbadge, .pbcell .cellbadge{position:absolute;top:8px;right:48px;z-index:6;pointer-events:none;
    font-family:var(--mono);font-size:11px;color:#e6edf3;background:rgba(10,12,15,.55);border:1px solid var(--line);
    padding:2px 7px;border-radius:5px;font-weight:600}
  .cellbadge.livebadge{display:inline-flex;align-items:center;gap:5px;color:#ff6b6b;letter-spacing:.05em}   /* mockup-style ● LIVE indicator (protocol moves to the tooltip) */
  .livedot{width:7px;height:7px;border-radius:50%;background:#ff4d4f;box-shadow:0 0 6px rgba(255,77,79,.85);animation:livepulse 1.6s ease-in-out infinite}
  @keyframes livepulse{0%,100%{opacity:1}50%{opacity:.35}}
  body.grid-mode .grid{display:grid}
  body.grid-mode #vid,
  body.grid-mode #live,
  body.grid-mode .liveTag,
  body.grid-mode .transport{display:none !important}   /* live split also keeps the bottom timeline (.dates/.tlwrap); all four modes share the same display */
  /* Live split: the global camera selector is meaningless (per-cell dropdowns own the cameras), so keep it invisible but STILL occupying its slot (visibility, not display:none) — otherwise toggling Live↔Playback changes the nav-mid width and the centered Live/Playback slider shifts. pointer-events:none also blocks the old no-recording-cam strand bug. */
  body.grid-mode #camSel{visibility:hidden;pointer-events:none}
  /* Quality dropdown: always visible (nav bar identical in both modes, never hidden or empty). Changing it during playback only presets the next live quality, no side effect */
  /* Playback split: reuse the .grid layout, but keep the timeline/controls; cells are <video> wrapped in .pbcell */
  .grid .pbcell{position:relative;background:#000;overflow:hidden;touch-action:manipulation}
  .grid .pbcell video{width:100%;height:100%;object-fit:contain;display:block}
  .pbcell .pbname{background:rgba(10,12,15,.72);color:#fff;box-shadow:none;text-transform:uppercase}   /* camera name badge (shows uppercase C700, value stays lowercase) */
  .grid .pbcell.master{outline:2px solid var(--accent);outline-offset:-2px}   /* reference camera: highlighted border */
  .pbcell.master .pbname{background:var(--accent);color:#0a0c0f}
  .grid .gzoom{position:absolute;top:50%;right:8px;transform:translateY(-50%);z-index:8;cursor:pointer;user-select:none;color:#fff;
    background:rgba(10,12,15,.66);border:1px solid var(--line);border-radius:7px;width:32px;height:32px;display:inline-flex;align-items:center;justify-content:center;padding:0;font-size:15px;line-height:1;box-sizing:border-box}
  .grid .gzoom:hover{background:rgba(10,12,15,.92);border-color:#34424e}
  .grid .gref{position:absolute;top:50%;left:8px;transform:translateY(-50%);z-index:8;cursor:pointer;user-select:none;color:#fff;
    background:rgba(10,12,15,.66);border:1px solid var(--line);border-radius:7px;width:32px;height:32px;display:inline-flex;align-items:center;justify-content:center;padding:0;font-size:15px;line-height:1;box-sizing:border-box}
  .grid .gref:hover{background:rgba(10,12,15,.92);border-color:#34424e}
  /* Per-cell controls (refresh / zoom / camera picker): appear when the cell is hovered (desktop) or tapped (touch — .tapped set by JS) */
  .grid .gref, .grid .gzoom, .grid .cellcam{opacity:0;transition:opacity .15s}
  @media (hover:hover){   /* hover only on real pointers — avoids iOS sticky-hover keeping controls on after a tap */
    .grid video-stream:hover .gref, .grid video-stream:hover .gzoom, .grid video-stream:hover .cellcam,
    .grid .pbcell:hover .gref, .grid .pbcell:hover .gzoom, .grid .pbcell:hover .cellcam{opacity:1}
  }
  .grid video-stream.tapped .gref, .grid video-stream.tapped .gzoom, .grid video-stream.tapped .cellcam,
  .grid .pbcell.tapped .gref, .grid .pbcell.tapped .gzoom, .grid .pbcell.tapped .cellcam{opacity:1}
  .grid .cellcam{position:absolute;top:8px;left:8px;z-index:9;font-family:var(--mono);font-size:11px;color:#fff;
    background:rgba(10,12,15,.7);border:1px solid var(--line);border-radius:6px;padding:3px 4px;text-transform:uppercase;cursor:pointer}
  .grid .cellcam:hover{border-color:#34424e}
  .grid.zoomed > :not(.zoom){display:none}            /* hide the other cells when zoomed */
  .grid > .zoom{grid-column:1 / -1;grid-row:1 / -1}    /* the zoomed cell fills the whole grid area */
  body.pbgrid-mode .grid{display:grid}
  body.pbgrid-mode #vid,
  body.pbgrid-mode #live,
  body.pbgrid-mode .liveTag{display:none}
  #pbPlayAll,#pbPauseAll,#pbSyncMode{display:none}                      /* Play all / Pause all / Sync-mode toggle: shown only in playback split */
  body.pbgrid-mode #playBtn{display:none}                               /* playback split uses "Play all/Pause all" instead of the single-stream play key */
  body.pbgrid-mode #pbPlayAll,body.pbgrid-mode #pbPauseAll{display:inline-block}
  body.pbgrid-mode #pbSyncMode{display:inline-flex}
  #pbSyncMode{border:1px solid var(--cover2);border-radius:7px;overflow:hidden;vertical-align:middle}   /* segmented Coarse|Precise sync-mode toggle */
  #pbSyncMode button{border:0;border-radius:0;margin:0;background:transparent;color:#9fb0bd;padding:5px 11px;font-size:13px}
  #pbSyncMode button.on{background:var(--accent);color:#0b0f13}
  .transport{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
  .transport .grow{flex:1}
  .pill{font-family:var(--mono);font-size:12px;color:var(--dim)}
  /* Date bar */
  /* Date picker: a single dropdown (day + weekday + segment count) now living in the bottom nav row; inherits .navin select styling, just cap its width. */
  #dates{max-width:180px;font-family:var(--mono)}
  /* Select date: always-on dial (date/hour/min/sec, 3D wheel) + a live clock on top + Go to / Back to live buttons.
     No card frame around it; flush to the edge, same width as the time bar / player frame (matching the time bar) */
  .dppanel{padding:4px 0 0}   /* no margin-bottom: main's flex gap (14px) already separates it from the timeline (the date strip that used to sit between them is gone) */
  .dprow{display:flex;align-items:center;gap:12px}   /* header row: just the 📅 time/wheel toggle now (Prev/Next clip moved to the transport row) */
  .dpbar{display:inline-flex;align-items:center;gap:10px;width:auto;background:none;border:0;
    padding:6px 2px;cursor:pointer;color:var(--text)}   /* shrink to content (📅 time ▾) and left-align; no longer a full-width row */
  .dpbarL{font-size:13px;color:var(--dim)}
  .dpclock{font-family:var(--mono);font-size:17px;color:var(--text);font-weight:600}
  .dpchev{color:var(--dim);font-size:12px;transition:transform .15s}   /* sits right after the clock now (bar is content-width, not full row) */
  .dpbody{display:none;margin-top:4px}
  .dppanel.open .dpbody{display:block}
  .dppanel.open .dpchev{transform:rotate(180deg)}
  /* Wheels: smaller + centered, with space on both sides (on phones the blank areas can scroll the page up/down); each column has ▲/▼ arrows on top/bottom (click with a Mac mouse to nudge one step); the buttons are on the same row as the wheels */
  .dpwheels{position:relative;display:flex;justify-content:center;align-items:center;gap:8px;overflow:hidden}
  .dpcol{display:flex;flex-direction:column;align-items:center}
  .dlbl{font-size:11px;color:var(--dim);margin-bottom:2px}
  .wharr{background:none;border:0;color:var(--dim);cursor:pointer;font-size:12px;line-height:1;padding:3px 6px}
  .wharr:hover{color:var(--accent)}
  .whcol{width:56px;height:160px;overflow-y:scroll;scroll-snap-type:y mandatory;
    scrollbar-width:none;padding:64px 0;box-sizing:border-box;border-radius:8px;
    background:linear-gradient(180deg,transparent 64px,rgba(230,237,243,.16) 64px,rgba(230,237,243,.16) 65px,transparent 65px,transparent 95px,rgba(230,237,243,.16) 95px,rgba(230,237,243,.16) 96px,transparent 96px)}   /* center slot = two thin frame lines (NOT a filled band): a filled band tints 2 items at once while scrolling → looked like "multiple highlights"; frame lines tint nothing, so only the centered .sel item is highlighted */
  .whcol::-webkit-scrollbar{display:none}
  .whitem{height:32px;line-height:32px;text-align:center;font-family:var(--mono);font-size:18px;
    color:var(--text);opacity:.32;scroll-snap-align:center;scroll-snap-stop:always}   /* no opacity/color transition: while scrolling the highlight jumps item-to-item; a fade transition left several items mid-fade at once → looked like "multiple highlights". Instant switch = only the centered item is ever bright. */
  .whitem.sel{opacity:1;color:var(--accent);font-weight:700}
  .whcol[data-k="date"] .whitem{font-size:15px}
  .dpacts{margin-left:8px}
  .dpacts .dlbl,.dpacts .wharr{visibility:hidden;pointer-events:none}   /* spacer: align the button with the centered highlight row of the wheels */
  .dpgowrap{height:160px;display:flex;align-items:center}
  #dpGo{background:var(--accent);color:#0a0c0f;border-color:var(--accent);font-weight:700;font-size:14px;padding:10px 14px;white-space:nowrap}
  /* Timeline */
  /* Remove the outer card (border/background/radius) and left/right padding, so the timeline track aligns to the same width as the date bar above and the player frame */
  .tlwrap{padding:0 0 10px}   /* no padding-top: rely on main's flex gap; the timeline sits right under the 📅 / Prev-Next row */
  .track{position:relative;height:46px;border-radius:6px;cursor:crosshair;touch-action:none;
    background:
      repeating-linear-gradient(90deg,var(--grid) 0,var(--grid) 1px,transparent 1px,transparent calc(100%/24));
    background-color:var(--panel2);border:1px solid var(--line);overflow:hidden}
  .cover{position:absolute;top:0;bottom:0;background:linear-gradient(var(--cover2),var(--cover))}
         /* solid (not translucent): recorded = solid green, so the faint hour-grid only shows through in genuine gaps → a dark band = a real recording gap, not a segment seam */
  .cover.live{background:var(--accent2)}   /* in-progress (REC) edge — the only warm accent, matches the ● REC badge */
  .playhead{position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--accent);
    box-shadow:0 0 8px var(--accent);pointer-events:none;display:none}
  .tip{position:fixed;transform:translateX(-50%);white-space:nowrap;
    font-family:var(--mono);font-size:11px;color:#0a0c0f;background:var(--accent);
    padding:3px 7px;border-radius:5px;pointer-events:none;display:none;z-index:50;
    box-shadow:0 2px 8px rgba(0,0,0,.5)}
  .tip::after{content:"";position:absolute;left:50%;top:100%;transform:translateX(-50%);
    border:4px solid transparent;border-top-color:var(--accent)}
  .ticks{display:flex;justify-content:space-between;font-family:var(--mono);
    font-size:10px;color:#aab4bd;margin-top:5px;padding:0 1px}
  .empty{font-family:var(--mono);font-size:12px;color:var(--dim);
    text-align:center;padding:14px 0}
  .hint{font-family:var(--mono);font-size:11px;color:#aab4bd}
  kbd{font-family:var(--mono);background:#171c22;border:1px solid var(--line);
    border-bottom-width:2px;border-radius:4px;padding:1px 5px;font-size:10px;color:var(--text)}
</style>
<script type="module" src="/video-stream.js"></script>
<script src="/ocr/tesseract.min.js" defer></script>   <!-- fallback OCR engine (same-origin), runs in the browser -->
<script src="/ocr/ort.min.js" defer></script>          <!-- onnxruntime-web: runs the PaddleOCR PP-OCRv3 recognition model (local/same-origin); primary OCR for precise sync -->

</head>
<body>
<header>
  <div class="navin">
    <div class="nav-left">
      <span class="dot"></span>
      <h1>Xiaomi</h1>
    </div>
    <div class="nav-mid">
      <div class="modebar" id="modebar">
        <button data-time="live" title="Live stream">Live</button>
        <button data-time="play" title="Recording playback">Playback</button>
      </div>
      <div class="modebar" id="splitbar" title="Split count (each cell can pick its own camera)">
        <button data-n="1" title="Single view">1</button>
        <button data-n="2" title="2-split (left/right)">2</button>
        <button data-n="4" title="4-split (2×2)">4</button>
        <button data-n="6" title="6-split (3×2)">6</button>
      </div>
      <select id="dates" title="Pick a day — then choose the time with the timeline or the 📅 wheel"></select>
      <select id="camSel" title="Camera"></select>
      <select id="qualSel" title="Live codec (Direct = H265 direct feed, Transcode = H264 compatible)"></select>
      <select id="resSel" title="Live resolution (1080P / 480P — 480P is light for multi-cam split)"></select>
      <button id="refreshBtn" title="Rescan recordings / reconnect live">↻</button>
    </div>
    <div class="nav-right"></div>
  </div>
</header>

<main>
  <div class="stage">
    <video id="vid" preload="metadata" playsinline controls></video>
    <div id="live"></div>
    <div class="liveTag" id="liveTag">● REC</div>
    <div class="grid" id="grid"></div>
    <button id="gridFull" class="gridfullbtn" title="Fill screen / exit">⛶</button>
  </div>

  <div class="transport">
    <button id="playBtn">▶︎ Play</button>
    <button id="pbPlayAll" title="Play all cells together (no reload; use «⇄ Sync» to align)">▶︎ Play all</button>
    <button id="pbPauseAll" title="Pause all cells at once">⏸ Pause all</button>
    <span id="pbSyncMode" title="Sync mode. Coarse: fast align by assumed time, held in sync continuously. Precise: OCR the burned-in clock for ±1s (all-or-nothing), then held by the lightweight maintenance. Click a mode to (re)sync now; re-click Precise after a segment change to re-OCR.">
      <button id="pbModeCoarse" class="on">⇄ Coarse</button>
      <button id="pbModePrecise">◎ Precise</button>
    </span>
    <button id="back10">⟲ 10s</button>
    <button id="fwd10">10s ⟳</button>
    <button id="prevSeg" title="Jump to the previous recording clip">⏮ Prev clip</button>
    <button id="nextSeg" title="Jump to the next recording clip">Next clip ⏭</button>
    <span class="grow"></span>
    <span class="pill">Speed</span>
    <select id="rateSel">
      <option value="0.5">0.5×</option>
      <option value="1" selected>1×</option>
      <option value="2">2×</option>
      <option value="4">4×</option>
      <option value="8">8×</option>
      <option value="16">16×</option>
    </select>
    <button id="latestBtn">Jump to latest</button>
  </div>

  <div class="dppanel" id="dppanel">
    <div class="dprow">
      <button class="dpbar" id="dpbar" title="Tap to pick a time to jump to (pick the day from the date dropdown in the bottom bar)">
        <span class="dpbarL">📅</span>
        <span class="dpclock" id="dpclock">—</span>
        <span class="dpchev" id="dpchev">▾</span>
      </button>
    </div>
    <div class="dpbody" id="dpbody">
      <div class="dpwheels">
        <div class="dpcol"><span class="dlbl">Hr</span><button class="wharr whup" data-k="h">▲</button><div class="whcol" data-k="h"></div><button class="wharr whdn" data-k="h">▼</button></div>
        <div class="dpcol"><span class="dlbl">Min</span><button class="wharr whup" data-k="m">▲</button><div class="whcol" data-k="m"></div><button class="wharr whdn" data-k="m">▼</button></div>
        <div class="dpcol"><span class="dlbl">Sec</span><button class="wharr whup" data-k="s">▲</button><div class="whcol" data-k="s"></div><button class="wharr whdn" data-k="s">▼</button></div>
        <div class="dpcol dpacts">
          <span class="dlbl">&nbsp;</span>
          <span class="wharr" aria-hidden="true">▲</span>
          <div class="dpgowrap"><button id="dpGo">Go to time</button></div>
          <span class="wharr" aria-hidden="true">▼</span>
        </div>
      </div>
    </div>
  </div>

  <div class="tlwrap">
    <div class="track" id="track">
      <div class="playhead" id="playhead"></div>
      <div class="tip" id="tip"></div>
    </div>
    <div class="ticks" id="ticks"></div>
    <div class="empty" id="empty" style="display:none">No recordings on this day</div>
  </div>
</main>

<script>
const DAY = 86400; // seconds
const $ = id => document.getElementById(id);
const vid = $('vid');

// Live picture (go2rtc / Frigate machine).
// If the browser natively supports HEVC (MSE) — Safari, Chrome on macOS — play the camera's H265 substream (_sub) directly:
// go2rtc just repackages without transcoding → original quality, almost zero load on .240. Otherwise (e.g. Firefox without HEVC)
// fall back to the H264 (_1080p) transcoded by go2rtc + WebRTC.
const GO2RTC = 'http://192.168.10.240:1984';
// WebRTC receiving H265: supported by desktop Chrome 136+/Safari; not by Firefox/Edge default/old Safari → only offer the transcode track.
function webrtcCanH265(){
  try{ return ((RTCRtpReceiver.getCapabilities('video') || {}).codecs || [])
              .some(c => /h265|hevc/i.test(c.mimeType)); }
  catch(_){ return false; }
}
const RTC_H265 = webrtcCanH265();
// Live quality = two independent axes: CODEC (Direct = H265 direct out, no transcode / Transcode = H264 via go2rtc) × RESOLUTION (1080 / 480).
// Maps to go2rtc stream names: Direct = _sub<RES>, Transcode = _<RES>p → _sub1080 / _sub480 / _1080p / _480p. 480P is the light track for multi-cam split.
const QUAL_CODECS = [];
if(RTC_H265) QUAL_CODECS.push({label:'Direct', kind:'sub'});   // H265 direct out (no transcode, original codec); default when WebRTC-H265 is supported
QUAL_CODECS.push({label:'Transcode', kind:'p'});               // H264 transcode (the only option for browsers without WebRTC-H265)
const QUAL_RES = ['1080', '480'];
let qualIdx = 0;   // index into QUAL_CODECS: Direct when supported, otherwise Transcode
let resIdx = 0;    // index into QUAL_RES: default 1080 (full quality)
function liveSuffix(){ const c = QUAL_CODECS[qualIdx] || QUAL_CODECS[0], r = QUAL_RES[resIdx] || '1080'; return c.kind === 'sub' ? ('_sub' + r) : ('_' + r + c.kind); }
function liveModeNow(){ return 'webrtc'; }
const START_LIVE = true;      // opening the page defaults to live (set false = default to the latest recording)
const START_SPLIT = 4;        // default split count on load: 1 = single stream, 2/4/6 = grid
let liveMode = false;
let gridMode = false;   // live split (splitN>1 and live)
let pbGrid = false;     // playback split (splitN>1 and playback, sharing the timeline)
// Split: choose 1/2/4/6 cells, each cell assigned one camera. cellCams[i] = the camera label (c700_0X) for cell i
const ALL_CAMS = ['c700_01','c700_02','c700_03','c700_04','c700_05','c700_06'];   // internal names (used to pull streams / find recordings, do not change)
// UI display names (display only, unrelated to go2rtc). Change here to use different names:
const CAM_NAMES = { c700_01:'CAM 1', c700_02:'CAM 2', c700_03:'CAM 3', c700_04:'CAM 4', c700_05:'CAM 5', c700_06:'CAM 6' };
function dispCam(lbl){ return CAM_NAMES[lbl] || lbl; }
let splitN = 1;                                   // current split count (1 = single stream)
const CELL_ORDER = ['c700_01','c700_02','c700_03','c700_05','c700_04','c700_06'];   // order cells are FILLED by default: 4-split shows 1,2,3,5 (cam4 moves to the 5th slot). Separate from ALL_CAMS so the per-cell picker stays in natural 1..6 order.
let cellCams = CELL_ORDER.slice(0, 4);            // cameras per cell, default fill from CELL_ORDER; truncated/padded by N when changing split count

let cam = null;
let dateStr = null;
let segs = [];          // segments of the current day [{file,start(Date),end(Date),live, s0(seconds relative to start of day), s1}]
let curIdx = -1;
let dayStart = null;    // the Date for 00:00 of the current day
let firstLoad = true;   // only the first load auto-jumps to the latest; afterwards switching date/camera keeps the current position
let livePreload = false;   // true while the startup timeline load runs in the background under a live/grid view — loadSegment must NOT tear that view down or autoplay (it only preloads the latest clip into the hidden #vid)

const pad = n => String(n).padStart(2, '0');
function hms(sec){
  sec = Math.max(0, Math.floor(sec));
  return pad(Math.floor(sec/3600)) + ':' + pad(Math.floor(sec/60)%60) + ':' + pad(sec%60);
}

async function api(p){ const r = await fetch(p); return r.json(); }

// ---- Initialize cameras ----
// ---- Fetch/refresh the camera list (keep the current selection where possible; newly connected cameras appear automatically) ----
async function reloadCameras(){
  const cams = await api('/api/cameras');
  const sel = $('camSel'); const prev = cam;
  sel.innerHTML = '';
  cams.forEach(c => {
    const o = document.createElement('option');
    o.value = c.id; o.dataset.lbl = c.label; o.textContent = dispCam(c.label);   // internal name stored in dataset.lbl, display via dispCam
    sel.appendChild(o);
  });
  if(cams.length){
    cam = cams.some(c => c.id === prev) ? prev : cams[0].id;
    sel.value = cam;
  }
  updateLiveBtn();
  return cams.length;
}

async function init(){
  const n = await reloadCameras();
  if(!n){
    $('empty').style.display = '';
    $('empty').textContent = 'No XiaomiCamera_* directory found under the root (check the mount points / startup arguments)';
    return;
  }
  if(START_LIVE && liveAvailable()){
    applyMode('live', START_SPLIT);   // open straight into the default live view (single or split)
    livePreload = true;   // protect the live/grid view from the background preload's loadSegment (teardown + autoplay)
    loadTimeline();    // load the timeline in the background (no await); its loadSegment goes to the hidden #vid, does not autoplay, does not affect live
  } else {
    await loadTimeline();   // playback default: locate to the latest and play
  }
  setInterval(refreshDates, 3600000);
}

function fillDateOptions(box, days){
  box.innerHTML = '';
  days.forEach(d => {
    const o = document.createElement('option');
    o.value = d.date;
    const wd = WD[new Date(d.date + 'T00:00:00').getDay()];     // weekday for that date
    o.textContent = d.date.slice(5) + ' ' + wd + '  ·  ' + d.count;   // e.g. "06-18 Wed  ·  109" (segment count, no unit word)
    box.appendChild(o);
  });
}
async function refreshDates(){
  if(!cam) return;
  let t;
  try{ t = await api('/api/timeline?cam=' + encodeURIComponent(cam)); }catch(_){ return; }
  const box = $('dates'); if(!box) return;
  const days = t.days || [];
  const cur = box.value;
  fillDateOptions(box, days);
  if(days.some(d => d.date === cur)) box.value = cur;
}
// ---- Load the available dates of a camera ----
async function loadTimeline(want){
  const t = await api('/api/timeline?cam=' + encodeURIComponent(cam));
  const days = t.days || [];
  const keys = days.map(d => d.date);
  const box = $('dates'); fillDateOptions(box, days);
  // selecting a day keeps the current timeline position (same moment, jump to the nearest)
  box.onchange = () => { const w = currentWall(), d = box.value;
    if(gridMode){ setPbGrid(true).then(() => selectDay(d, w.sec, w.play)); return; }   // live split → playback split at the chosen day (keep the split, don't drop to single)
    if(liveMode) setLive(false);
    selectDay(d, w.sec, w.play);
  };
  if(days.length){
    let target, sec, play;
    if(want && want.date && keys.includes(want.date)){
      target = want.date; sec = want.sec; play = !!want.play;     // switching camera/refresh: keep the same day, same moment
    } else {
      target = days[days.length - 1].date;                       // default the latest day
      if(firstLoad){ sec = 'latest'; play = true; }              // first load: locate to the latest moment
      else { sec = want ? want.sec : null; play = !!(want && want.play); }
    }
    firstLoad = false;
    selectDay(target, sec, play);
    if($('dppanel').classList.contains('open')) buildDials();   // rebuild dials only when the collapsible bar is already expanded (collapsed has no layout, rebuild when expanded)
    $('empty').style.display = 'none';
  } else {
    segs = []; renderTrack(); $('empty').style.display = '';
    $('empty').textContent = 'No recordings on this day';
  }
}

// ---- Select a day ----
async function selectDay(d, targetSec, play){
  dateStr = d;
  dayStart = new Date(d + 'T00:00:00');
  const dsel = $('dates'); if(dsel && dsel.value !== d) dsel.value = d;   // reflect the current day in the dropdown (e.g. on Back-to-latest / camera switch)
  if(pbGrid){                          // playback split: changing day → re-pull all streams, whole screen jumps to the target moment
    await pbFetchDay(d);
    segs = pbSegs[pbMaster] || []; curIdx = -1; renderTrack();
    $('empty').style.display = segs.length ? 'none' : '';
    const t = (targetSec === 'latest' || targetSec == null || !isFinite(targetSec))
              ? (segs.length ? segs[segs.length-1].s1 - 2 : 0) : targetSec;
    gridSeekAll(t, !!play);
    return;
  }
  const r = await api('/api/segments?cam=' + encodeURIComponent(cam) + '&date=' + d);
  segs = (r.segments || []).map(s => {
    const st = new Date(s.start), en = new Date(s.end);
    return { file:s.file, live:s.live, start:st, end:en,
             s0:(st - dayStart)/1000, s1:(en - dayStart)/1000 };
  });
  curIdx = -1;
  renderTrack();
  $('empty').style.display = segs.length ? 'none' : '';
  if(!segs.length) $('empty').textContent = 'No recordings on this day';   // selected a date with no recordings
  if(segs.length){
    if(targetSec === 'latest'){              // first load: locate to the end of the latest segment
      const i = segs.length - 1;
      loadSegment(i, Math.max(0, segs[i].s1 - segs[i].s0 - 2), !!play);
    } else if(targetSec != null && isFinite(targetSec)){
      const b = bestSegForSec(targetSec);    // align to the closest point to the target moment
      loadSegment(b.idx, b.offset, !!play);
    } else {
      loadSegment(0, 0, false);
    }
  }
  livePreload = false;   // chokepoint: the protected startup/grid preload is at most one loadSegment per selectDay — clear here so the flag can never get stuck (e.g. a day with no recordings never calls loadSegment)
}

// ---- Draw the timeline ----
function renderTrack(){
  const track = $('track');
  [...track.querySelectorAll('.cover')].forEach(e => e.remove());
  segs.forEach((s, i) => {
    const l = Math.max(0, s.s0)/DAY, r = Math.min(DAY, s.s1)/DAY;
    if(r <= l) return;
    const el = document.createElement('div');
    el.className = 'cover' + (s.live ? ' live' : '');
    el.style.left = (l*100) + '%'; el.style.width = ((r-l)*100) + '%';
    el.title = hms(Math.max(0, s.s0)) + ' → ' + hms(Math.min(DAY, s.s1));
    track.insertBefore(el, $('playhead'));
  });
  const ticks = $('ticks'); ticks.innerHTML = '';
  for(let h=0; h<=24; h+=2){
    const sp = document.createElement('span'); sp.textContent = pad(h) + ':00';
    ticks.appendChild(sp);
  }
}

// ---- Find the segment covering a given "seconds of the day" ----
function segIndexAt(sec){
  for(let i=0; i<segs.length; i++){ if(sec >= segs[i].s0 && sec < segs[i].s1) return i; }
  return -1;
}
function nextSegAfter(sec){
  for(let i=0; i<segs.length; i++){ if(segs[i].s0 >= sec) return i; }
  return -1;
}
// Find the segment closest to a given "seconds of the day" (used to align cross-camera to the same moment)
function bestSegForSec(sec){
  const cover = segIndexAt(sec);
  if(cover >= 0) return { idx: cover, offset: sec - segs[cover].s0 };
  let best = 0, bestDist = Infinity, bestOff = 0;
  for(let i=0; i<segs.length; i++){
    const s = segs[i];
    let dist, off;
    if(sec < s.s0){ dist = s.s0 - sec; off = 0; }                    // before this segment → segment start
    else { dist = sec - s.s1; off = Math.max(0, s.s1 - s.s0 - 1); }  // after this segment → segment end
    if(dist < bestDist){ bestDist = dist; best = i; bestOff = off; }
  }
  return { idx: best, offset: bestOff };
}

// ---- Load and locate a segment ----
function loadSegment(idx, offsetSec, autoplay){
  if(idx < 0 || idx >= segs.length) return;
  if(gridMode && !livePreload) setGrid(false);   // any playback action exits the live split (but the startup background preload must leave the grid intact)
  curIdx = idx; const s = segs[idx];
  $('liveTag').style.display = s.live ? 'block' : 'none';
  vid.src = '/video?cam=' + encodeURIComponent(cam) + '&file=' + encodeURIComponent(s.file);
  const onMeta = () => {
    vid.removeEventListener('loadedmetadata', onMeta);
    try{ vid.currentTime = Math.max(0, offsetSec); }catch(e){}
    if(autoplay && !liveMode && !gridMode && !pbGrid){ vid.play().catch(()=>{}); }   // under live/split, do not let the background hidden single-stream recording autoplay
    updateHead();
  };
  vid.addEventListener('loadedmetadata', onMeta);
  vid.load();
  livePreload = false;   // one-shot: only the very first startup preload is protected; later timeline clicks tear down the grid as usual
}

// ---- Track: drag/click; the playhead follows the cursor and shows the precise time bubble at that position ----
let dragging = false;
let cancelDrag = false;   // moving cursor/finger above or below the track while dragging = cancel this drag (no jump on release)
let dragHist = [];        // recent {t, sec} samples while dragging — fallback commit (skips lift jitter) when the user lifts without dwelling
const SETTLE_MS = 70;     // how far before release to look back for the intended position (touch, non-dwell case)
// Dwell-to-lock: holding the finger ~still for DWELL_MS "locks" the selection — the playhead/time freeze there and later small moves (the finger-lift jitter) are ignored, so the shown time doesn't twitch. A move > STILL_PX unlocks and follows again.
let dwellTimer = null, dragLocked = false, dragLockedSec = null, dragShownSec = null, dragLastX = null;
const DWELL_MS = 130, STILL_PX = 8;
const track = $('track');

function moveHead(sec){            // sec = seconds relative to 00:00 of the day
  const cs = Math.min(DAY, Math.max(0, sec));
  const ph = $('playhead');
  ph.style.display = 'block';
  ph.style.left = (cs/DAY*100) + '%';
  // (the playhead time used to also print into #tlDate; that duplicated #dpclock — removed. Drag-time feedback is the .tip bubble.)
}
function trackSec(e){
  // Use the content box (clientLeft/clientWidth, excluding the 1px border) to compute pixels→seconds, same reference frame as the left% of .cover/.playhead;
  // otherwise the offset caused by the border grows with position (more off the further right), making the visual drag position not match the seeked second
  const rect = track.getBoundingClientRect();
  const cw = track.clientWidth || rect.width;
  const frac = Math.min(1, Math.max(0, (e.clientX - rect.left - track.clientLeft) / cw));
  return frac * DAY;
}
function showTip(e){              // a time bubble that follows the cursor; fixed positioning, to avoid being clipped by the track's overflow:hidden
  const sec = trackSec(e);
  const rect = track.getBoundingClientRect();
  const tip = $('tip');
  tip.style.left = e.clientX + 'px';
  tip.style.top  = (rect.top - 30) + 'px';
  tip.textContent = (dateStr ? dateStr + ' ' : '') + hms(sec);
  tip.style.display = 'block';
}
function hideTip(){ $('tip').style.display = 'none'; }
function dragShow(sec, e){ moveHead(sec); showTip(e); dragShownSec = sec; }   // move the playhead/time and remember where it is (so a dwell-lock can freeze on it)
function armDwell(){ clearTimeout(dwellTimer); dragLocked = false; dwellTimer = setTimeout(() => { dragLocked = true; dragLockedSec = dragShownSec; }, DWELL_MS); }   // (re)start the hold timer; firing it = the finger held still → lock the selection
function seekTo(sec){
  if(pbGrid){ gridSeekAll(sec, true); return; }   // playback split: whole screen jumps to the same moment
  if(gridMode){ setPbGrid(true).then(() => gridSeekAll(sec, true)); return; }   // dragging the timeline in live split → enter [split playback] and jump to that moment
  if(liveMode) setLive(false);   // clicking/dragging the timeline → switch to recordings
  if(!segs.length) return;
  const b = bestSegForSec(sec);  // locate to the segment covering that moment; if it lands in a gap, snap to the nearest recording (otherwise the click/Go-to would be silently dropped)
  loadSegment(b.idx, b.offset, true);
}

track.addEventListener('pointerdown', e => {
  if(!segs.length || !dayStart) return;
  dragging = true; cancelDrag = false; dragLocked = false; dragLockedSec = null; dragLastX = e.clientX;
  try{ track.setPointerCapture(e.pointerId); }catch(_){}
  const sec = trackSec(e); dragShow(sec, e);     // move the line immediately + show the time
  dragHist = [{t: Date.now(), sec}];
  armDwell();
});
track.addEventListener('pointermove', e => {
  if(!segs.length) return;
  const rect = track.getBoundingClientRect();
  const off = e.clientY < rect.top - 48 || e.clientY > rect.bottom + 48;   // moved 48px above/below the track = cancel zone
  if(dragging && off){                       // cancel zone: show "Release to cancel", the playhead snaps back to the current position to indicate no jump
    cancelDrag = true;
    const w = currentWall(); if(w && w.sec != null && isFinite(w.sec)) moveHead(w.sec);
    const tip = $('tip'); tip.style.left = e.clientX + 'px'; tip.style.top = (rect.top - 30) + 'px';
    tip.textContent = 'Release to cancel'; tip.style.display = 'block';
    return;
  }
  cancelDrag = false;
  const sec = trackSec(e);
  if(dragging){
    const dx = Math.abs(e.clientX - (dragLastX == null ? e.clientX : dragLastX));
    if(dx > STILL_PX){               // deliberate movement → follow the finger, record history, restart the hold timer
      dragLastX = e.clientX;
      dragShow(sec, e);
      dragHist.push({t: Date.now(), sec}); if(dragHist.length > 40) dragHist.shift();
      armDwell();
    } else if(!dragLocked){          // small drift, not yet locked → keep following (responsive); don't reset the timer so it still locks on hold
      dragShow(sec, e);
    }
    // dragLocked && small move → frozen: the finger-lift jitter is ignored, playhead/time stay put
  } else {
    showTip(e);                      // hover (mouse): just the time bubble
  }
});
track.addEventListener('pointerleave', () => { if(!dragging) hideTip(); });
function endDrag(e){
  if(!dragging) return;
  dragging = false; clearTimeout(dwellTimer);
  try{ track.releasePointerCapture(e.pointerId); }catch(_){}
  hideTip();
  if(cancelDrag){ cancelDrag = false; updateHead(); return; }   // cancel: no jump, the playhead returns to the actual position
  let sec;
  if(dragLocked && dragLockedSec != null){
    sec = dragLockedSec;             // dwelled → use the locked position; the finger-lift jitter was already ignored
  } else if(e.pointerType === 'touch' && dragHist.length){
    const upT = Date.now();          // lifted without dwelling → still skip the trailing jitter via the short history
    sec = dragHist[dragHist.length - 1].sec;
    for(let i = dragHist.length - 1; i >= 0; i--){ if(upT - dragHist[i].t >= SETTLE_MS){ sec = dragHist[i].sec; break; } }
  } else {
    sec = trackSec(e);               // mouse/pen lifts cleanly → exact position
  }
  seekTo(sec);                       // only jump/load on release
}
track.addEventListener('pointerup', endDrag);
track.addEventListener('pointercancel', () => { dragging = false; cancelDrag = false; dragLocked = false; clearTimeout(dwellTimer); hideTip(); updateHead(); });
// Press Esc while dragging to cancel (desktop)
document.addEventListener('keydown', e => { if(e.key === 'Escape' && dragging){ dragging = false; cancelDrag = false; dragLocked = false; clearTimeout(dwellTimer); hideTip(); updateHead(); } });

// ---- During playback let the playhead follow progress (do not steal it while dragging) ----
function updateHead(){
  if(dragging) return;
  if(pbGrid){ const v = pbVids[pbMaster]; if(v && v._seg) moveHead(v._seg.s0 + v.currentTime); return; }
  if(curIdx < 0) return;
  const s = segs[curIdx];
  moveHead(s.s0 + vid.currentTime);
}
vid.addEventListener('timeupdate', updateHead);

// ---- When one segment finishes, automatically continue to the next (continuous playback) ----
vid.addEventListener('ended', () => {
  if(gridMode || pbGrid) return;   // in split mode, do not continue after the background single-stream recording ends (otherwise it would exit the split via loadSegment)
  if(curIdx >= 0 && curIdx + 1 < segs.length){
    loadSegment(curIdx + 1, 0, true);
  }
});

// ---- Controls ----
// Current playback position (date + seconds of the day + whether playing), used to align cross-camera to the same moment
function currentWall(){
  if(pbGrid){
    const v = pbVids[pbMaster];
    return { date: dateStr, sec: (v && v._seg) ? (v._seg.s0 + v.currentTime) : null, play: pbPlaying() };
  }
  return {
    date: dateStr,
    sec: (curIdx >= 0) ? (segs[curIdx].s0 + vid.currentTime) : null,
    play: !vid.paused,
  };
}
$('camSel').onchange = e => {
  const w = currentWall(); cam = e.target.value;
  updateLiveBtn();
  if(pbGrid){   // playback split: switch the reference (master clock) to the cell showing the selected camera (key by index, match by label)
    const lbl = liveLabel();
    const c = pbCams().find(c => c.label === lbl);
    if(c){ pbMaster = c.key; segs = pbSegs[c.key] || []; curIdx = -1; pbMarkMaster(); renderTrack(); updateHead(); }
    return;
  }
  if(gridMode){ livePreload = true; loadTimeline(w); return; }   // live split: per-cell dropdowns own the cameras — only refresh the background timeline, do NOT let loadSegment tear the grid down
  loadTimeline(w);                                            // the timeline always updates to the new camera
  if(liveMode){ liveAvailable() ? setLive(true) : setLive(false); }   // live follows the switch; if the new camera has no live, exit
};
$('refreshBtn').onclick = async () => {
  if(gridMode){ setGrid(true); return; }   // live split: rebuild (reload) all live streams
  if(liveMode){ setLive(true); return; }   // live: rebuild the component (reconnect to the live end)
  if(pbGrid){ const w = currentWall(); await reloadCameras(); await pbFetchDay(dateStr); segs = pbSegs[pbMaster] || []; renderTrack(); gridSeekAll(w.sec != null ? w.sec : 0, w.play); return; }  // playback split: rescan + whole screen back to the current moment
  const w = currentWall(); await reloadCameras(); loadTimeline(w);   // playback: rescan recordings, keep the current position
};

// ---- Live picture (go2rtc): toggle with «● Live» in the title bar; the browser connects directly to go2rtc, not through wrt32x ----
function liveLabel(){ const o = $('camSel').selectedOptions[0]; return o ? (o.dataset.lbl || o.textContent) : ''; }   // returns the internal name c700_0X
function liveAvailable(){ return /^c700_0[1-5]$/.test(liveLabel()); }   // c700_01–05 have a go2rtc live source; c700_06 is the spare slot with no live source yet
// ===== View modes: Playback / Live / Live split / Playback split (toggled uniformly by the segmented switches) =====
function currentMode(){ return pbGrid ? 'pbgrid' : gridMode ? 'livegrid' : liveMode ? 'live' : 'play'; }
function curTime(){ const m = currentMode(); return (m==='live' || m==='livegrid') ? 'live' : 'play'; }
function curSplit(){ return splitN > 1; }
function ensureCellCams(){   // keep the existing per-cell cameras, pad/truncate to the current splitN (pad with the default first few streams)
  const n = Math.max(1, splitN);
  while(cellCams.length < n) cellCams.push(CELL_ORDER[cellCams.length] || ALL_CAMS[0]);
  cellCams = cellCams.slice(0, n);
}
function applyMode(time, n){   // time: live/play; n: split count 1/2/4/6
  n = n || 1;
  const m = (n > 1) ? (time === 'live' ? 'livegrid' : 'pbgrid') : (time === 'live' ? 'live' : 'play');
  const sameGrid = (m === currentMode()) && n > 1;   // same kind of grid but split count/cameras changed → needs rebuild (setMode's same-mode dedup would skip it)
  splitN = n; ensureCellCams();
  if(sameGrid){ if(m === 'livegrid') setGrid(true); else setPbGrid(true); updateModeBar(); return; }
  setMode(m);
}
function updateModeBar(){
  document.querySelectorAll('#modebar button').forEach(b => b.classList.toggle('on', b.dataset.time === curTime()));
  $('modebar').classList.toggle('t-play', curTime() === 'play');   // toggle slider: slides to the right during playback
  document.querySelectorAll('#splitbar button').forEach(b => b.classList.toggle('on', +b.dataset.n === splitN));
  const sb = $('splitbar');   // split toggle slider: slides to the matching slot by splitN (1 = leftmost, no class)
  sb.classList.toggle('s-2', splitN === 2);
  sb.classList.toggle('s-4', splitN === 4);
  sb.classList.toggle('s-6', splitN === 6);
  $('qualSel').disabled = (curTime() !== 'live');   // quality only applies to live → greyed out/disabled during playback (single/split)
  $('resSel').disabled = (curTime() !== 'live');
}
function setMode(m){
  const cur = currentMode();
  if(m === cur) return;
  // Sync the split count to keep the nav bar consistent with the actual mode (the L/G/P shortcuts call setMode directly, not applyMode, otherwise you would get "nav shows split, content is single stream" mismatch)
  if(m === 'live' || m === 'play') splitN = 1;          // single view
  else if(splitN < 2) splitN = 4;                        // entering grid: at least 2, default 4
  ensureCellCams();
  resIdx = (splitN > 1) ? 1 : 0; if($('resSel')) $('resSel').value = resIdx;   // resolution default follows the layout: split → 480P (light for multi-cam decode), single → 1080P. The user can still override via the dropdown; a grid→grid split-count change (applyMode sameGrid path) keeps the override.
  // Exit the current mode back to baseline
  if(cur === 'pbgrid'){
    if(m === 'play') setPbGrid(false);   // to single-stream playback: needs selectDay to restore the single view
    else pbTeardown();                    // to live/live-split: just tear down, do not trigger async selectDay (otherwise its loadSegment would kick the newly entered split back to single playback)
  }
  else if(cur === 'livegrid') setGrid(false);
  else if(cur === 'live') setLive(false);
  // Enter the target mode
  if(m === 'live') setLive(true);
  else if(m === 'livegrid') setGrid(true);
  else if(m === 'pbgrid') setPbGrid(true);
  updateModeBar();
}
function updateLiveBtn(){ updateModeBar(); }   // compatibility for old call sites (camSel.onchange / reloadCameras)
function killStreams(root){   // disconnect the WebRTC of old live components (using the component's own disconnectedCallback, best-effort)
  root.querySelectorAll('video-stream').forEach(el => { try{ el.background = false; el.disconnectedCallback && el.disconnectedCallback(); }catch(_){} });
}
function setLive(on){
  if(gridMode) setGrid(false);   // exit the live split when switching to single stream
  if(pbGrid) pbTeardown();        // exit the playback split
  clearLiveTimers();
  on = on && liveAvailable();
  liveMode = on;
  document.body.classList.toggle('live-mode', on);
  updateModeBar();
  document.title = on ? 'Xiaomi Recordings · Live' : 'Xiaomi Recordings · Timeline Playback';
  const box = $('live');
  killStreams(box);                 // first disconnect the old component's WebRTC (avoid zombie consumers)
  box.innerHTML = '';               // then clear
  if(on){
    vid.pause();
    box.style.display = 'block';    // show first
    // Same as the split: wait one tick (until the container layout/visibility is ready) before connecting. Otherwise desktop Safari, receiving the stream before layout is ready, will not render → black screen (yet the consumer has already connected)
    setTimeout(() => {
      if(!liveMode) return;         // if we already switched away in the meantime, do not connect
      const v = document.createElement('video-stream');
      v.mode = liveModeNow();       // by quality track: webrtc or mse
      v.media = 'video,audio';      // with audio
      v.background = true;          // do not stop the stream just because it is invisible
      box.appendChild(v);           // add to DOM (the component creates the inner <video>)
      if(v.video){ v.video.controls = true; v.video.muted = true; v.video.playsInline = true; }   // set muted/inline before src to guarantee autoplay
      const url = GO2RTC + '/api/ws?src=' + encodeURIComponent(liveLabel() + liveSuffix());
      v.src = url;                  // trigger connection
      attachResume(v, url);         // play after pause → reconnect to the live end
      attachLiveBadge(v);  // top-right: ● Live + actual protocol (RTC/MSE)
      watchStall(v, url);  // stall self-heal: auto-reconnect when frozen past the threshold
    }, 0);
  } else {
    box.style.display = 'none';     // removing the component = stop pulling the stream
  }
}
document.querySelectorAll('#modebar button').forEach(b => b.onclick = () => applyMode(b.dataset.time, splitN));
document.querySelectorAll('#splitbar button').forEach(b => b.onclick = () => applyMode(curTime(), +b.dataset.n));
// Split fills the whole viewport (like a monitor wall): CSS viewport fill, not system fullscreen (iPad does not support it on a div)
const stageEl = document.querySelector('.stage');
function setGridFull(on){
  stageEl.classList.toggle('full', on);
  document.body.classList.toggle('gridfull', on);
  $('gridFull').textContent = on ? '✕' : '⛶';
}
$('gridFull').onclick = () => setGridFull(!stageEl.classList.contains('full'));
document.addEventListener('keydown', e => { if(e.key === 'Escape' && stageEl.classList.contains('full')) setGridFull(false); });
// Touch (no hover): tap to reveal the controls + maximize button, then auto-fade after a few seconds — like a native video player. Tapping a control resets the timer.
if(matchMedia('(hover:none)').matches){
  let tapTimer = null;
  const hideTapped = () => {
    stageEl.querySelectorAll('.tapped').forEach(c => c.classList.remove('tapped'));
    stageEl.classList.remove('tapped');
  };
  const armHide = () => { clearTimeout(tapTimer); tapTimer = setTimeout(hideTapped, 3000); };
  stageEl.addEventListener('click', e => {
    if(e.target.closest('.gref,.gzoom,.cellcam,.gridfullbtn')){ armHide(); return; }   // using a control: keep visible, restart the timer
    const cell = e.target.closest('.grid video-stream, .grid .pbcell');
    stageEl.querySelectorAll('.grid .tapped').forEach(c => c.classList.remove('tapped'));
    stageEl.classList.add('tapped');
    if(cell) cell.classList.add('tapped');
    armHide();
  });
}
// Select date: always-on dial (date/hour/min/sec, 3D wheel). Only clicking «Go to time» reloads, scrolling itself does not jump
// → live is not interrupted. The date column only lists days that have recordings → days without recordings are not in the wheel = cannot be selected.
const WH_ITEM = 32;   // height of each item, matches the CSS
const WD = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
function wh3d(col){    // flat, crisply aligned: highlight only the [centered item] (amber bold), the rest dimmed by CSS. Only change two items when the centered item changes
  const items = col.children;
  let idx = Math.round(col.scrollTop / WH_ITEM);
  idx = Math.max(0, Math.min(items.length - 1, idx));   // clamp to the valid range (on overscroll/bounce of a short list idx can go out of range → old highlight not removed → multiple amber rows)
  if(col._sel === idx) return;
  if(col._sel != null && items[col._sel]) items[col._sel].classList.remove('sel');
  if(items[idx]) items[idx].classList.add('sel');
  col._sel = idx;
}
function whCol(k){ return document.querySelector('.whcol[data-k="' + k + '"]'); }
function whIdx(k){ const col = whCol(k); const n = col.children.length;
  return Math.max(0, Math.min(n - 1, Math.round(col.scrollTop / WH_ITEM))); }
function whVal(k){ const c = whCol(k); const it = c.children[whIdx(k)]; return it ? it.dataset.val : null; }   // take the real value of the centered item (correct whichever copy you land on when looping)
function whFill(k, items, idx, loop){
  const col = whCol(k);
  let list = items, base = 0;
  if(loop){                                  // looping column (min/sec): lay out several copies of 0–59, start in the middle copy
    const COPIES = 7; list = [];
    for(let c = 0; c < COPIES; c++) list = list.concat(items);
    base = ((COPIES - 1) >> 1) * items.length;   // offset of the middle copy
    col._loop = items.length; col._base = base;
  } else { col._loop = 0; }
  col.innerHTML = list.map(it => '<div class="whitem" data-val="' + it.val + '">' + it.txt + '</div>').join('');
  col._sel = null;
  col.scrollTop = (base + idx) * WH_ITEM;
  wh3d(col);
  if(!col._wired){ col._wired = true; col.addEventListener('scroll', () => {   // only update the highlight, do not jump
    if(!col._raf) col._raf = requestAnimationFrame(() => { col._raf = 0; wh3d(col); });
    if(col._loop){ clearTimeout(col._loopT); col._loopT = setTimeout(() => whRecenter(col), 140); }   // looping: after settling, quietly return to the middle copy (seamless)
  }); }
}
function whRecenter(col){    // looping column: map the current value back to the same-value position in the middle copy (same-value copies look identical → user does not notice), achieving infinite looping
  const n = col._loop; if(!n) return;
  const idx = Math.round(col.scrollTop / WH_ITEM);
  const val = ((idx % n) + n) % n;
  const target = col._base + val;
  if(target !== idx){ col.scrollTop = target * WH_ITEM; wh3d(col); }   // do not set _sel=null (otherwise the old highlight is not removed → double highlight); wh3d uses _sel to remove the old and add the new
}
function buildDials(){   // called after loadTimeline has rendered the dates; the dial rests at the current time (does not trigger a jump). The DAY is picked on the date strip, so the wheel is time-only (no Date column).
  const w = currentWall(); const cs = (w && isFinite(w.sec)) ? Math.floor(w.sec) : 0;
  const r = n => Array.from({length:n}, (_, i) => ({val:i, txt:String(i).padStart(2,'0')}));
  whFill('h', r(24), Math.floor(cs/3600) % 24, true);   // hour: looping (0↔23)
  whFill('m', r(60), Math.floor(cs/60) % 60, true);     // min: looping (0↔59)
  whFill('s', r(60), cs % 60, true);                    // sec: looping (0↔59)
  requestAnimationFrame(() => document.querySelectorAll('.whcol').forEach(wh3d));   // recalibrate the highlight after layout is ready (do not set _sel=null, to avoid double highlight)
}
// Collapsible bar: tap to expand/collapse in place. Only after expanding (now visible) does buildDials run, so scrollTop can take effect
$('dpbar').onclick = () => {
  const p = $('dppanel'), willOpen = !p.classList.contains('open');
  p.classList.toggle('open', willOpen);
  if(willOpen) buildDials();
};
// ▲/▼ arrows: mouse-click nudges that column up/down one step (for use on a Mac without a touchscreen)
document.querySelectorAll('.wharr').forEach(b => {
  b.onclick = () => { const col = whCol(b.dataset.k); if(col) col.scrollBy({top: b.classList.contains('whup') ? -WH_ITEM : WH_ITEM, behavior:'smooth'}); };
});
// Go to time: jump to the selected time ON THE CURRENT DAY (the day is chosen on the date strip; the wheel is time-only). Stops precisely at that moment (if it's a gap, stops there). Collapses the bar after jumping.
$('dpGo').onclick = async () => {
  if(!dateStr) return;
  const sec = Number(whVal('h'))*3600 + Number(whVal('m'))*60 + Number(whVal('s'));   // use the real values (correct whichever copy you land on in a looping column)
  $('dppanel').classList.remove('open');
  if(gridMode || pbGrid){                                 // live split / playback split → enter [playback split] and whole screen jumps to that moment
    if(!pbGrid) await setPbGrid(true);                    // live split → switch to playback split (current day)
    gridSeekAll(sec, true);                               // whole screen jumps to sec on the current day
    return;
  }
  if(liveMode) setLive(false);                            // single stream
  seekTo(sec);                                            // locate precisely to the selected moment on the current day
};
// Reading on the collapsible bar: during playback show the real moment of [the current playback position] (not a live clock, to avoid misleading); during live show "● Live"
function dpClockText(){
  if(liveMode || gridMode) return '● Live';
  const w = currentWall();
  if(dateStr && w && isFinite(w.sec)) return dateStr + ' ' + hms(Math.max(0, w.sec));
  return dateStr || '—';
}
$('dpclock').textContent = dpClockText();
setInterval(() => { const el = $('dpclock'); if(el) el.textContent = dpClockText(); }, 1000);
// ---- Split view: watch all cameras' live pictures at once ----
function liveGridLabels(){ return cellCams.slice(0, splitN); }   // cameras per cell (determined by cellCams)
// Stick "● Live · protocol" in the top-right corner of the live component, the protocol read from the component's actual state:
// for WebRTC the <video> uses srcObject (MediaStream); for MSE the src is blob:.
// Custom "zoom/restore" (shared by live split + playback split): tap a cell to fill the grid area, tap again to restore. In-page zoom, not system fullscreen (avoids the Safari bug where the picture shifts up after exiting fullscreen).
function addZoom(cellEl){
  const g = $('grid');
  const z = document.createElement('span'); z.className = 'gzoom'; z.textContent = '⤢'; z.title = 'Zoom / restore (double-tap the picture also works)';
  const toggle = () => {
    const on = !cellEl.classList.contains('zoom');
    g.querySelectorAll('.zoom').forEach(x => x.classList.remove('zoom'));
    g.querySelectorAll('.gzoom').forEach(x => x.textContent = '⤢');
    cellEl.classList.toggle('zoom', on); g.classList.toggle('zoomed', on);
    if(on) z.textContent = '⤡';
  };
  z.onclick = (e) => { e.stopPropagation(); toggle(); };
  // Double-click/double-tap the picture = in-page zoom/restore: detected by "two clicks within 300ms" (click fires on both mouse and touch; dblclick is often unreliable on phones)
  let lastTap = 0;
  cellEl.addEventListener('click', () => { const now = Date.now(); if(now - lastTap < 300){ lastTap = 0; toggle(); } else lastTap = now; });
  // Block the browser's default "native fullscreen" on double-click of <video> (keep only our in-page zoom, to avoid double-click maximizing)
  cellEl.addEventListener('dblclick', (e) => { e.preventDefault(); e.stopPropagation(); });
  cellEl.appendChild(z);
}

function attachLiveBadge(v){
  const b = document.createElement('span'); b.className = 'cellbadge livebadge';
  const dot = document.createElement('span'); dot.className = 'livedot';
  b.appendChild(dot); b.appendChild(document.createTextNode('LIVE')); v.appendChild(b);
  const upd = () => {
    const el = v.video; if(!el) return;
    const proto = el.srcObject ? 'WebRTC' : ((el.src || '').startsWith('blob:') ? 'MSE' : 'connecting');
    b.title = 'Live · ' + proto;   // negotiated protocol kept in the tooltip (badge shows the clean ● LIVE)
  };
  if(v.video){ v.video.addEventListener('loadeddata', upd); v.video.addEventListener('playing', upd); }
  setTimeout(upd, 800);   // fallback: refresh once more after connecting
  return b;
}

// ---- Single-cell lifecycle: create/wire/self-heal (touches only this cell, others unaffected) ----
function gridUrl(lbl){ return GO2RTC + '/api/ws?src=' + encodeURIComponent(lbl + liveSuffix()); }
function showCellMsg(el, text){   // show/clear placeholder text in a cell (No signal / No recording). el = cell container (live: video-stream; playback: .pbcell)
  if(!el) return;
  let m = el.querySelector(':scope > .cellmsg');
  if(text){ if(!m){ m = document.createElement('div'); m.className = 'cellmsg'; el.appendChild(m); } m.textContent = text; }
  else if(m) m.remove();
}
function addCellCam(cellEl, idx, onChange){   // top-left camera dropdown per cell (c700_01..06), changing it triggers onChange(idx, label)
  const sel = document.createElement('select'); sel.className = 'cellcam'; sel.title = 'Camera for this cell';
  ALL_CAMS.forEach(lbl => { const o = document.createElement('option'); o.value = lbl; o.textContent = dispCam(lbl); if(lbl === cellCams[idx]) o.selected = true; sel.appendChild(o); });
  sel.onclick = e => e.stopPropagation();           // do not trigger double-click zoom
  sel.onchange = () => onChange(idx, sel.value);
  cellEl.appendChild(sel);
}
function makeGridCell(lbl){    // create the component (not yet in DOM; the caller inserts it into the grid first, then wireCell)
  const v = document.createElement('video-stream');
  v.mode = liveModeNow(); v.media = 'video,audio'; v.background = true; v._lbl = lbl;
  return v;
}
function wireCell(v){          // v is already in DOM: set src to trigger connection + camera dropdown/badge/zoom/refresh/self-heal
  const url = gridUrl(v._lbl);
  v.src = url;
  if(v.video){ v.video.controls = true; v.video.muted = true; }
  attachResume(v, url);
  attachLiveBadge(v);
  addZoom(v);
  addCellRefresh(v);
  addCellCam(v, v._idx, gridReassign);   // camera dropdown per cell
  cellWatch(v);
}
function gridReconnect(v){     // rebuild the whole cell in place (only reconnect this stream, other cells untouched)
  if(!gridMode || !document.contains(v)) return;
  const wasZoom = v.classList.contains('zoom');
  try{
    v.background = false;
    if(v.disconnectTID){ clearTimeout(v.disconnectTID); v.disconnectTID = 0; }
    if(v.reconnectTID){ clearTimeout(v.reconnectTID); v.reconnectTID = 0; }
    if(typeof v.ondisconnect === 'function') v.ondisconnect();
    else if(v.disconnectedCallback) v.disconnectedCallback();
  }catch(_){}
  const nv = makeGridCell(v._lbl); nv._idx = v._idx; nv._tries = v._tries || 0; nv._lastStall = v._lastStall || 0;   // carry over the index/retry count
  if(wasZoom) nv.classList.add('zoom');
  $('grid').replaceChild(nv, v);   // replace in place, keeping the grid position
  wireCell(nv);
}
function gridReassign(idx, newLabel){   // change a cell's camera (live): after swapping the label, reconnect only this cell
  cellCams[idx] = newLabel;
  const v = $('grid').children[idx]; if(!v) return;
  v._lbl = newLabel; v._tries = 0; showCellMsg(v, '');
  gridReconnect(v);
}
function addCellRefresh(v){    // single-cell refresh key: refresh only this stream (replaces the global refresh)
  const r = document.createElement('span'); r.className = 'gref'; r.textContent = '↻'; r.title = 'Refresh only this stream';
  r.onclick = (e) => { e.stopPropagation(); v._tries = 0; showCellMsg(v, ''); gridReconnect(v); };
  v.appendChild(r);
}
// Single-cell self-heal: black screen (no frames for a while) or freeze reconnects only this cell; repeated reconnects still with no frames (e.g. unconnected 05/06) → mark "No signal" and stop; the timer auto-stops once this cell is replaced/the split is exited
const FRAME_STALL_MS = 10000;
const STALL_RECONNECT_MIN_MS = 20000;
function cellWatch(v){
  let last = -1, frozen = 0, grace = 6, started = false, armed = false;
  const arm = (el) => { armed = true; v._frameTs = Date.now(); const cb = () => { v._frameTs = Date.now(); if(v.video === el) el.requestVideoFrameCallback(cb); }; el.requestVideoFrameCallback(cb); };
  const id = setInterval(() => {
    if(!gridMode || !document.contains(v)){ clearInterval(id); return; }   // already replaced/exited the split: stop the timer
    const el = v.video; if(!el) return;
    if(el.requestVideoFrameCallback && !armed) arm(el);
    if(el.currentTime > 0.1){ started = true; v._tries = 0; showCellMsg(v, ''); }   // frames flowing → healthy, reset the retry counter
    if(grace > 0){ grace--; return; }                    // connection grace period (~6s)
    if(!started){                                         // never produced a frame
      const t = (v._tries || 0);
      if(t >= 3) showCellMsg(v, 'No signal');             // after 3 quick tries, show the placeholder — but DO NOT stop
      const fast = t < 3, slowDue = (Date.now() - (v._lastTry || 0) > 12000);
      if(fast || slowDue){ v._tries = t + 1; v._lastTry = Date.now(); gridReconnect(v); }   // keep retrying: fast at first, then a slow ~12s backoff. Never give up permanently → a flaky WebRTC source (e.g. CAM2) auto-recovers once go2rtc/the camera settles.
      return;
    }
    if(el.paused){ last = -1; frozen = 0; v._frameTs = Date.now(); return; }       // already played, user paused: not a stall
    if(document.hidden){ last = el.currentTime; frozen = 0; v._frameTs = Date.now(); return; }
    if(el.requestVideoFrameCallback){
      if(Date.now() - (v._frameTs || 0) > FRAME_STALL_MS){
        if(Date.now() - (v._lastStall || 0) > STALL_RECONNECT_MIN_MS){ v._lastStall = Date.now(); gridReconnect(v); }
        else showCellMsg(v, 'No signal');
      }
      return;
    }
    if(el.currentTime === last){ if(++frozen >= 3){ frozen = 0; gridReconnect(v); } }   // frozen 3s → reconnect this cell (reset so we don't reconnect every tick)
    else { last = el.currentTime; frozen = 0; }
  }, 1000);
  liveTimers.push(id);
}

function setGrid(on){
  if(pbGrid) pbTeardown();          // exit the playback split
  clearLiveTimers();
  gridMode = on;
  document.body.classList.toggle('grid-mode', on);
  updateModeBar();
  document.title = on ? 'Xiaomi Recordings · Live Split' : (liveMode ? 'Xiaomi Recordings · Live' : 'Xiaomi Recordings · Timeline Playback');
  const g = $('grid');
  killStreams(g);                   // first disconnect the old component's WebRTC (avoid zombie consumers)
  g.innerHTML = '';                 // then clear
  if(on){
    vid.pause();
    g.dataset.n = splitN;           // grid layout (2/4/6)
    // Build ALL cells immediately so the full grid (e.g. 2×2) shows at once on load — no "single then jump to N-split" flash.
    const labels = liveGridLabels();
    labels.forEach((lbl, i) => { const v = makeGridCell(lbl); v._idx = i; g.appendChild(v); });
    // Only the WebRTC connection is staggered (400ms apart) to avoid simultaneous handshakes fighting; the layout is already complete, video just fills in cell by cell.
    labels.forEach((lbl, i) => {
      setTimeout(() => {
        if(!gridMode) return;        // exited the split in the meantime → don't connect
        const v = g.children[i];     // the cell built above (kept in order)
        if(v) wireCell(v);           // set src to connect + camera dropdown/badge/zoom/single-cell refresh/self-heal
      }, i * 400);
    });
  }
}
// ===== Live stall self-heal =====
// WebRTC/MSE occasionally "stays connected but stops delivering frames": the picture freezes, the connection is not dropped so the component does not auto-reconnect.
// Watch <video>.currentTime; if it does not advance for about 6 seconds (and it is not a user-initiated pause) reconnect that stream.
let liveTimers = [];
function clearLiveTimers(){ liveTimers.forEach(t => clearInterval(t)); liveTimers = []; }
// Check playback progress every 1s; reconnect after a full 3s freeze; give 4s grace after reconnecting (let it connect, do not misjudge a stall again).
// The polling itself just reads currentTime, negligible cost; the real cost is the "reconnect", so the threshold should not be too small (otherwise it reconnects on transient little stalls that would self-heal, making it jitter more).
function watchStall(v, url){
  let last = -1, frozen = 0, grace = 0;
  liveTimers.push(setInterval(() => {
    const el = v.video;
    if(!el || el.paused){ last = -1; frozen = 0; return; }               // user pause is not a stall
    if(grace > 0){ grace--; last = el.currentTime; frozen = 0; return; } // just reconnected, let it connect first
    if(el.currentTime === last){ frozen++; if(frozen >= 3){ frozen = 0; grace = 4; v.src = url; } }  // frozen 3s → reconnect
    else { last = el.currentTime; frozen = 0; }
  }, 1000));
}
// Play after pause → reconnect to the live end (the MSE track falls behind when paused; reconnecting WebRTC is also harmless)
function attachResume(v, url){
  if(!v.video) return;
  let wasPaused = false;
  v.video.addEventListener('pause', () => { wasPaused = true; });
  v.video.addEventListener('play',  () => { if(wasPaused){ wasPaused = false; v.src = url; } });
}

// ===== Playback split: multiple recording streams share one timeline, with drag/play/speed linked =====
let pbSegs = {};      // { camId: [seg...] } each camera's segments for the day
let pbVids = {};      // { camId: <video> }
let pbMaster = null;  // master-clock camera (drives the playhead/timeline display)
let pbSyncTimer = null;  // periodic resync timer
let pbRefetchTimer = null;  // periodic segment rescan (picks up freshly-finalized clips so cells parked on an in-progress recording auto-resume)
let pbGridGen = 0;       // rebuild generation: bumped on every enter/teardown so a slow async setPbGrid(true) continuation (after its await) bails if the mode changed under it (rapid split-count clicks)
let pbSyncMode = 'coarse';   // 'coarse' (align by assumed time) | 'precise' (OCR-verified offsets, held by offset-aware maintenance; re-click Precise to re-OCR after a segment change)
let pbSelfHeal = true;       // watchdog black/stall AUTO-RELOAD: ON. (Verified NOT the cause of "cells stuck Loading" — headless does 4/4 with 0 reloads; the real cause is the Mac's concurrent-4K-HEVC decode cap.) Clip-end roll-over (advancing to the next segment) is independent and ALWAYS on regardless of this flag. Set pbSelfHeal=false (console) to disable mid-play black/stall recovery for debugging.

function pbCamId(lbl){ const o = [...$('camSel').options].find(o => o.dataset.lbl === lbl); return o ? o.value : null; }   // internal name → disk id (unconnected 05/06 return null)
// One {key=cell index, label, id} per cell. Keyed by index → supports any per-cell camera, duplicates, reserved (no id)
function pbCams(){ return cellCams.slice(0, splitN).map((lbl, i) => ({ key: String(i), label: lbl, id: pbCamId(lbl) })); }

async function pbFetchDay(date){      // concurrently pull each cell's segments for the day (cells without an id = empty). Build into a temp then swap atomically so the 500ms maintenance loop never reads a half-empty pbSegs (matters for the periodic refetch below).
  const cams = pbCams(), next = {};
  await Promise.all(cams.map(async c => {
    if(!c.id){ next[c.key] = []; return; }
    try{ const r = await api('/api/segments?cam=' + encodeURIComponent(c.id) + '&date=' + date);
      next[c.key] = (r.segments || []).map(s => { const st = new Date(s.start), en = new Date(s.end);
        return { file:s.file, live:s.live, start:st, end:en, s0:(st-dayStart)/1000, s1:(en-dayStart)/1000 }; });
    }catch(_){ next[c.key] = pbSegs[c.key] || []; }
  }));
  pbSegs = next;
}
async function pbRefetchSegs(){       // periodic rescan while in playback split: picks up a freshly-FINALIZED clip (live → completed) so cells PARKED on an in-progress recording auto-resume.
  if(!pbGrid) return;
  if(!pbCams().some(c => { const v = pbVids[c.key]; return v && (v._gapHold || !v._seg); })) return;   // ONLY rescan when a cell is actually waiting on a clip to finalize. Otherwise skip: each rescan = 5 camera-dir scans (2 over remote CIFS) on the weak router, which competes with the 4K /video streaming and stalls cold-loads (playback "stuck loading"). No one waiting → nothing to pick up → don't hammer the server.
  const gen = pbGridGen;
  await pbFetchDay(dateStr);
  if(gen !== pbGridGen || !pbGrid) return;
  const w = currentWall();
  if(w && w.sec != null && isFinite(w.sec)) pbCams().forEach(c => { const v = pbVids[c.key]; if(v && !v._seg && pbCovers(c.key, w.sec)) pbLoadCell(c.key, w.sec, pbPlaying()); });   // a cell parked with no usable clip (all-live edge) can now play a freshly-finalized completed clip
  segs = pbSegs[pbMaster] || []; renderTrack();
}

function pbSeek(v, t){ v._progT = Date.now(); try{ v.currentTime = Math.max(0, t); }catch(_){} }   // programmatic positioning: record the timestamp; distinguish user drags from seeking via a time window (one seek may fire seeking multiple times)

function pbBest(key, sec){            // the COMPLETED segment of this cell closest to sec (seconds of the day). Live (in-progress) clips are skipped: their fMP4 has no finalized moov/index → can't seek to a target moment → endless "Loading…". They become seekable once the camera finalizes the clip (the periodic refetch picks it up).
  const arr = pbSegs[key] || [];
  for(let i=0;i<arr.length;i++) if(!arr[i].live && sec>=arr[i].s0 && sec<arr[i].s1) return {idx:i, offset:sec-arr[i].s0};
  let best=-1, bd=Infinity, bo=0;
  for(let i=0;i<arr.length;i++){ const s=arr[i]; if(s.live) continue; let d,o;
    if(sec<s.s0){d=s.s0-sec;o=0;} else {d=sec-s.s1;o=Math.max(0,s.s1-s.s0-1);}
    if(d<bd){bd=d;best=i;bo=o;} }
  return best<0 ? null : {idx:best, offset:bo};
}
function pbCovers(key, sec){          // does this cell have a COMPLETED (seekable) recording covering `sec`? (live/in-progress clips don't count — see pbBest)
  const arr = pbSegs[key] || [];
  for(const s of arr) if(!s.live && sec >= s.s0 && sec < s.s1) return true;
  return false;
}
function pbLiveCovers(key, sec){      // is `sec` inside this cell's currently-RECORDING clip? (used only to label the hold as "录制中" vs a plain gap)
  const arr = pbSegs[key] || [];
  for(const s of arr) if(s.live && sec >= s.s0 && sec < s.s1) return true;
  return false;
}
function pbNextDone(key, i){          // index of the next COMPLETED clip after i (skips live/in-progress clips), or -1
  const arr = pbSegs[key] || [];
  for(let j=(i|0)+1;j<arr.length;j++) if(!arr[j].live) return j;
  return -1;
}
function pbHoldMsg(key, sec){ return pbLiveCovers(key, sec) ? '录制中…' : 'No recording'; }

function pbLoadCell(key, sec, autoplay){
  const v = pbVids[key]; if(!v) return;
  const arr = pbSegs[key] || [];
  const b = pbBest(key, sec);
  if(!b){ v.removeAttribute('src'); v.load(); v._seg=null; v._idx=-1; v._gapHold=true; showCellMsg(v.parentElement, pbHoldMsg(key, sec)); return; }   // no COMPLETED clip at this moment (real gap, or only an in-progress recording) → park + hold (the refetch resumes it once a clip finalizes)
  showCellMsg(v.parentElement, '');
  v._idx = b.idx; v._seg = arr[b.idx];
  v.src = '/video?cam=' + encodeURIComponent(v._id) + '&file=' + encodeURIComponent(arr[b.idx].file);
  const onMeta = () => { v.removeEventListener('loadedmetadata', onMeta);
    pbSeek(v, b.offset);
    if(autoplay) v.play().catch(()=>{}); };
  v.addEventListener('loadedmetadata', onMeta);
  let tries = 0;
  const onSeeked = () => {   // fMP4's first seek can land off-target → re-assert until it's near the requested offset
    if(v._seg && Math.abs(v.currentTime - b.offset) > 2 && tries < 3){ tries++; pbSeek(v, b.offset); return; }
    v.removeEventListener('seeked', onSeeked);
  };
  v.addEventListener('seeked', onSeeked);
  v.load();
}

function gridSeekAll(sec, play){
  const cams = pbCams();
  const _rate = parseFloat($('rateSel').value) || 1;
  cams.forEach(c => { const v = pbVids[c.key]; if(v){ v._manual = false; v._miss = 0; v._ocrOff = null; v._gapHold = false; v.playbackRate = _rate; } });   // a whole-screen jump = clear per-cell independent flag + give-up counter + stale OCR offset (new positions) + gap-hold + reset nudge rate to the selected speed
  // Reliable LANDING for BOTH play states: every stream seeks to its target with the poll-retry below; once all land they play together — but ONLY if play=true. A PAUSED jump (e.g. ±10s while paused) must land just as reliably and then STAY paused. (The old !play shortcut used pbLoadCell with no poll-retry → a cold fMP4 seek clamped and the paused split jumped to the wrong clip/spot — the "±10s doesn't work" bug.) While positioning, the cell is flagged _settling so the watchdog/maintenance DON'T touch it.
  let pending = 0, started = false;
  const startAll = () => { if(started) return; started = true; if(play) cams.forEach(c => { const v = pbVids[c.key]; if(v && v._seg) v.play().catch(()=>{}); }); updateHead(); };
  cams.forEach(c => {
    const v = pbVids[c.key]; if(!v) return;
    const arr = pbSegs[c.key] || [];
    const b = pbBest(c.key, sec);
    if(!b){ v.removeAttribute('src'); v.load(); v._seg = null; v._idx = -1; v._settling = false; v._gapHold = true; showCellMsg(v.parentElement, pbHoldMsg(c.key, sec)); return; }   // no COMPLETED clip at this moment (real gap, or only an in-progress recording) → park + hold; the maintenance resumes it once a completed clip covers the master moment
    showCellMsg(v.parentElement, '');
    const sameLoaded = (b.idx === v._idx && v.readyState >= 1);   // already on this clip and loaded → cheap in-file seek (no reload), e.g. ±10s within the same clip
    v._idx = b.idx; v._seg = arr[b.idx]; v._settling = true;
    pending++; let tries = 0, done = false;
    const finish = () => { if(done) return; done = true; v.removeEventListener('loadedmetadata', onMeta); v._settling = false; if(--pending <= 0) startAll(); };
    const seekNow = () => { if(v.readyState >= 1) pbSeek(v, b.offset); };   // a seek only takes effect once metadata is parsed (duration known); before that currentTime won't move at all
    const onMeta = () => seekNow();   // metadata arrived → seek AT ONCE (don't wait for the next 600ms tick)
    // POLL-RETRY until the seek actually LANDS. A cold fMP4 (moov duration=0) ignores/clamps a seek until the file's metadata is parsed; re-seek until it sticks. The cap is GENEROUS (~36s): a 4K clip's metadata can take 10s+ to parse (4-way decode contention / slow remote cifs), and the OLD 12s cap expired EXACTLY as metadata arrived — releasing the cell at the clip START, so "picked 13:38" played from the clip head 13:36 (the reported regression). Now we wait for it to truly land before playing.
    const trySeek = () => {
      if(done) return;
      if(pbVids[c.key] !== v || v._seg !== arr[b.idx]){ finish(); return; }                   // reassigned / torn down
      if(v.readyState >= 1 && Math.abs(v.currentTime - b.offset) <= 1.5){ finish(); return; }  // LANDED on target
      if(tries++ >= 100){ seekNow(); finish(); return; }                                       // ~60s last resort: one final seek, then release (never hang forever on a broken clip). This is only an UPPER BOUND — a normal clip lands within a second of loadedmetadata and finishes immediately; the cap just has to exceed the worst-case metadata-parse time so a slow 4K clip isn't released at the clip head before its seek can land.
      seekNow();
      setTimeout(trySeek, 600);
    };
    if(!sameLoaded){ v.src = '/video?cam=' + encodeURIComponent(v._id) + '&file=' + encodeURIComponent(arr[b.idx].file); v.addEventListener('loadedmetadata', onMeta); v.load(); }
    trySeek();
  });
  if(pending === 0) updateHead();      // nothing playable
  else setTimeout(startAll, 65000);    // hard fallback (matches the ~60s per-cell cap) so the screen never hangs — but it no longer fires BEFORE cells have had time to land (the old 15s fallback played from the wrong spot)
}
function pbPlaying(){ const v = pbVids[pbMaster]; return v ? !v.paused : false; }
function pbToggle(){ const playing = pbPlaying();
  pbCams().forEach(c => { const v = pbVids[c.key]; if(!v) return; playing ? v.pause() : v.play().catch(()=>{}); });
  $('playBtn').textContent = playing ? '▶︎ Play' : '⏸ Pause';
}
// ===== OCR-precise sync: read each cell's burned-in timestamp (top-left of the SOURCE frame) and align to the reference's real time (±1s, the burn-in is whole-seconds). tesseract.js runs in the browser; engine hosted same-origin under /ocr/. =====
let _ocrWorker = null, _ocrInit = null;
function ocrReady(){ return typeof Tesseract !== 'undefined' || typeof ort !== 'undefined'; }   // either engine loaded is enough to run precise sync
async function getOcrWorker(){
  if(_ocrWorker) return _ocrWorker;
  if(!_ocrInit){
    _ocrInit = Tesseract.createWorker('engbest', 1, { workerPath:'/ocr/worker.min.js', corePath:'/ocr/tesseract-core-simd-lstm.wasm.js', langPath:'/ocr/' })   // 'engbest' = tessdata_BEST eng model (most accurate LSTM; /ocr/engbest.traineddata.gz on sda3). New lang name → bypasses the browser's IndexedDB cache of the old 'eng' (fast) model. oem 1 = LSTM only.
      .then(async w => { await w.setParameters({ tessedit_char_whitelist:'0123456789:/ ', tessedit_pageseg_mode:'7' }); _ocrWorker = w; return w; });
  }
  return _ocrInit;
}
function parseClock(text){   // → seconds of day from the OCR'd timestamp
  const str = String(text || '');
  const m = str.match(/(\d{1,2})\s*:\s*(\d{2})\s*:\s*(\d{2})/);   // primary: explicit HH:MM:SS
  if(m){ const h = +m[1], mi = +m[2], s = +m[3]; if(h < 24 && mi < 60 && s < 60) return h*3600 + mi*60 + s; }
  const d = str.replace(/\D/g, '');   // fallback: burn-in is YYYYMMDDHHMMSS → last 6 digits = HHMMSS (robust to dropped ":" / "/")
  if(d.length >= 6){ const t = d.slice(-6); const h = +t.slice(0,2), mi = +t.slice(2,4), s = +t.slice(4,6); if(h < 24 && mi < 60 && s < 60) return h*3600 + mi*60 + s; }
  return null;
}
const _ocrCanvas = document.createElement('canvas');
let _ocrLast = {};   // latest read line per cell-tag → shown one-per-line in the debug window
async function ocrCellTimeTess(v, tag, isMaster){   // FALLBACK engine (tesseract): crop the top-left timestamp from the SOURCE frame, binarize, OCR → seconds of day.
  if(!v || !v.videoWidth) return null;
  tag = tag || '?';
  const cw = Math.round(v.videoWidth * 0.40), ch = Math.round(v.videoHeight * 0.08), SC = 2;   // SC: upscale for crisper OCR
  _ocrCanvas.width = cw*SC; _ocrCanvas.height = ch*SC;
  const ctx = _ocrCanvas.getContext('2d');
  try{ ctx.drawImage(v, 0, 0, cw, ch, 0, 0, cw*SC, ch*SC); }catch(_){ return null; }
  try{   // binarize by NEAR-WHITE only: the timestamp is pure-white text (R≈G≈B≈255); scene bright areas are usually warm/colored (not pure white), so keep only near-white pixels as text → black-on-white. Avoids bright/coloured scene turning into black blobs that drown the digits.
    const img = ctx.getImageData(0, 0, _ocrCanvas.width, _ocrCanvas.height), px = img.data;
    for(let i = 0; i < px.length; i += 4){ const isWhite = px[i] > 235 && px[i+1] > 235 && px[i+2] > 235; const val = isWhite ? 0 : 255; px[i] = px[i+1] = px[i+2] = val; }
    ctx.putImageData(img, 0, 0);
  }catch(_){}
  try{ const w = await getOcrWorker(); const { data } = await w.recognize(_ocrCanvas);
    const parsed = parseClock(data.text);
    console.log('[OCR ' + tag + '] vw=' + v.videoWidth + ' crop=' + cw + 'x' + ch + ' raw=' + JSON.stringify((data.text||'').trim()) + ' parsed=' + parsed);
    try{ ocrDbgShow(_ocrCanvas, tag, (data.text||'').trim(), parsed, isMaster); }catch(_){}   // DEBUG: show the exact image fed to OCR + per-cell read lines
    return parsed;
  }catch(e){ console.log('[OCR] error: ' + (e && e.message || e)); return null; }
}
// ===== PRIMARY OCR: PaddleOCR PP-OCRv3 recognition via onnxruntime-web (local, same-origin). Far more robust to cluttered backgrounds than tesseract. tesseract stays as a fallback. REVERT: set OCR_ENGINE='tesseract'. =====
const OCR_ENGINE = 'paddle';   // 'paddle' | 'tesseract'
let _ortSess = null, _ortDict = null, _ortInit = null;
async function getPaddle(){
  if(_ortSess && _ortDict) return _ortSess;
  if(!_ortInit){
    ort.env.wasm.wasmPaths = '/ocr/'; ort.env.wasm.numThreads = 1;   // single-thread wasm → no SharedArrayBuffer / COOP-COEP headers needed
    _ortInit = Promise.all([
      ort.InferenceSession.create('/ocr/rec_v4_server.onnx', { executionProviders:['wasm'] }),   // PP-OCRv4 SERVER rec (90MB, HTTP-cached after first load). Verified offline: it reads the cluttered-background timestamps (e.g. CAM4) that v3 and v4-mobile mangled. Heavier inference but precise sync is on-demand. (Same dict as v3 → ppocr_keys.txt unchanged.)
      fetch('/ocr/ppocr_keys.txt').then(r => r.text())
    ]).then(([sess, txt]) => {
      _ortSess = sess;
      const keys = txt.replace(/\n+$/, '').split('\n');           // 6623 dict chars (no trailing blank)
      _ortDict = ['blank'].concat(keys).concat([' ']);            // CTC classes: 0=blank, then dict, then space → 6625, matches the model
      if(_ortDict.length !== 6625) console.warn('[paddle] dict size ' + _ortDict.length + ' != 6625 (decode may misalign)');
      return sess;
    });
  }
  await _ortInit; return _ortSess;
}
const _pCanvas = document.createElement('canvas');
async function paddleCellTime(v, tag, isMaster){   // crop the timestamp band (RAW colour — the neural model wants natural pixels, no binarization), PP-OCRv3 → CTC decode → seconds of day
  if(!v || !v.videoWidth) return null;
  tag = tag || '?';
  const sess = await getPaddle();
  const cw = Math.round(v.videoWidth * 0.40), ch = Math.round(v.videoHeight * 0.08);   // crop band (reverted: tighter 0.045 clipped/squashed the text and OCR got worse — 0.08 reads better in practice)
  const H = 48, W = Math.max(32, Math.round(H * cw / ch));        // model input height = 48; width keeps the crop aspect
  _pCanvas.width = W; _pCanvas.height = H;
  const ctx = _pCanvas.getContext('2d', { willReadFrequently: true });
  try{ ctx.drawImage(v, 0, 0, cw, ch, 0, 0, W, H); }catch(_){ return null; }
  const img = ctx.getImageData(0, 0, W, H).data, N = W*H, t = new Float32Array(3*N);
  for(let i=0;i<N;i++){ const p=i*4; t[i] = img[p+2]/127.5 - 1; t[N+i] = img[p+1]/127.5 - 1; t[2*N+i] = img[p]/127.5 - 1; }   // NCHW, BGR order, normalized to [-1,1]
  const feeds = {}; feeds[sess.inputNames[0]] = new ort.Tensor('float32', t, [1, 3, H, W]);
  const res = await sess.run(feeds);
  const o = res[sess.outputNames[0]], d = o.data, T = o.dims[1], C = o.dims[2];
  let prev = -1, str = '';
  for(let ti=0; ti<T; ti++){ let best=0, bv=-Infinity; const base=ti*C; for(let c=0;c<C;c++){ const val=d[base+c]; if(val>bv){ bv=val; best=c; } } if(best!==0 && best!==prev && best<_ortDict.length) str += _ortDict[best]; prev=best; }   // CTC greedy decode (collapse repeats, drop blank)
  const parsed = parseClock(str);
  console.log('[paddle ' + tag + '] raw=' + JSON.stringify(str) + ' parsed=' + parsed);
  try{ ocrDbgShow(_pCanvas, tag, str, parsed, isMaster); }catch(_){}
  return parsed;
}
async function ocrCellTime(v, tag, isMaster){   // dispatcher: PaddleOCR primary, tesseract fallback on engine error
  if(OCR_ENGINE === 'paddle' && typeof ort !== 'undefined'){
    try{ return await paddleCellTime(v, tag, isMaster); }
    catch(e){ console.log('[paddle] error → tesseract fallback: ' + (e && e.message || e)); }
  }
  return ocrCellTimeTess(v, tag, isMaster);
}
function ocrDbgShow(cnv, tag, raw, parsed, isMaster){   // update the combined window: the crop OCR was given + each cell's latest read, one line per cell — recal reads show here too (the user wants to SEE the per-crossing re-calibration)
  ocrBox();
  const c = document.getElementById('ocrdbgc'); c.width = cnv.width; c.height = cnv.height; c.getContext('2d').drawImage(cnv, 0, 0);
  _ocrLast[tag] = tag + '  raw="' + raw + '" → ' + (parsed != null ? hms(parsed) : 'null') + (isMaster ? '   ◄ REF' : '');   // parsed time as HH:MM:SS; REF marker at the END of the line
  document.getElementById('ocrdbgt').textContent = Object.keys(_ocrLast).map(k => _ocrLast[k]).join('\n');
}
// Single combined OCR window (bottom-right, above the nav): the binarized crop + the current frame's read line + the run summary. Text is selectable for copying; DOUBLE-CLICK to dismiss (single click / drag-select does NOT close it, so you can highlight and copy).
function ocrBox(){
  let box = document.getElementById('ocrdbg');
  if(!box){
    box = document.createElement('div'); box.id = 'ocrdbg';
    box.style.cssText = 'position:fixed;bottom:110px;right:6px;z-index:99999;background:#000;border:1px solid var(--accent);padding:4px;color:#7f8c98;font:11px/1.35 monospace;max-width:46vw;user-select:text;-webkit-user-select:text;cursor:text';
    const c = document.createElement('canvas'); c.id = 'ocrdbgc'; c.style.cssText = 'display:block;max-width:44vw;height:auto;image-rendering:pixelated';
    const t = document.createElement('div'); t.id = 'ocrdbgt'; t.style.cssText = 'white-space:pre-wrap;line-height:1.5;color:#8b97a3';
    const s = document.createElement('div'); s.id = 'ocrdbgs'; s.style.cssText = 'margin-top:4px;padding-top:5px;border-top:1px solid #2a3a48;color:#8fa0ad;white-space:pre-wrap;line-height:1.5;font-size:12px';
    box.appendChild(c); box.appendChild(t); box.appendChild(s);
    box.title = 'Double-click to dismiss (auto-hides 30s after the last update)'; box.ondblclick = () => { clearTimeout(box._t); box.remove(); };
    document.body.appendChild(box);
  }
  clearTimeout(box._t); box._t = setTimeout(() => box.remove(), 30000);   // auto-dismiss 30s after the latest update (every OCR read/summary refresh — manual Precise AND per-crossing recal — calls ocrBox → resets this); double-click dismisses it sooner. Crossings are minutes apart, so between them the 30s elapses and the window closes.
  return box;
}
function pbToast(msg){ ocrBox(); document.getElementById('ocrdbgs').textContent = msg; }   // write the run summary into the combined window's summary line
// Calibrate a cell's currentTime↔real-time offset by OCR'ing the burned-in clock WHILE PLAYING (a moving scene → some frame's timestamp reads cleanly even if others are drowned by bright scene). The offset is constant within a segment, so one clean read calibrates the whole segment — robust to which scene happens to sit behind the clock. Returns the offset (seconds) or null if nothing readable before the deadline.
async function calibrateOffset(v, deadline, tag, isMaster){
  const reads = [];
  // Gather MANY reads (not just two), then average. The burned clock is whole-seconds, so each read's
  // offset = trueOffset − f (f = the unknown sub-second fraction, 0–1 s, different per frame). Two samples
  // average f poorly (±1 s noise → cells land >2 s apart, "needs two clicks"). Averaging ~8 reads that span
  // >1 s drives f to a COMMON ~0.5 s bias on every cell → the residual is shared → **exact relative sync**.
  while(Date.now() < deadline && reads.length < 8){
    if(!v._seg || !v.videoWidth){ await new Promise(r => setTimeout(r, 120)); continue; }
    const ct = v.currentTime;                       // currentTime at the captured frame (drawImage in ocrCellTime is synchronous → pairs with this frame)
    const tReal = await ocrCellTime(v, tag, isMaster);
    if(tReal != null && v._seg){
      const off = tReal - (v._seg.s0 + ct);   // realtime = s0 + currentTime + off
      if(Math.abs(off) <= 120) reads.push(off);      // plausible currentTime↔realtime offset; reject gross misreads (wrong hour/minute → huge off)
    }
    await new Promise(r => setTimeout(r, 110));       // let the frame advance so the next read samples a different sub-second phase (and a possibly cleaner scene)
  }
  if(reads.length < 3) return null;                  // too few to trust (precise mode demands accuracy; no single-read guessing)
  const sorted = [...reads].sort((a, b) => a - b), med = sorted[sorted.length >> 1];
  const good = reads.filter(o => Math.abs(o - med) <= 1.5);   // drop misread outliers (a wrong digit gives a wildly different offset)
  if(good.length < 3) return null;
  return good.reduce((a, b) => a + b, 0) / good.length;       // average of the consistent reads → sub-second quantization cancels relatively
}
// ◎ OCR Sync: high-precision alignment, ALL-OR-NOTHING. Play all cells; OCR each (retried across rounds as the scene advances) until its burned-in clock is VERIFIED (two frames agree on the same offset). Only if EVERY cell verifies do we align them to the reference's real time (±1s). If any cell can't be verified within OCR_MAX_MS, the whole sync is ABORTED — nothing is moved (accuracy or nothing; no coarse faking). Always reports the outcome.
const OCR_MAX_MS = 25000, OCR_ROUND_MS = 2500;   // generous total budget / per-cell budget within one round — verified cells return early, so a stubborn cell gets many retry rounds before giving up
async function pbOcrSync(){   // returns true if all cells were verified & aligned, false otherwise
  const btn = $('pbModePrecise'), lbl = btn ? btn.textContent : '';
  if(!ocrReady()){ pbToast('OCR engine not loaded — cannot run precise sync'); return false; }
  const cams = pbCams().filter(c => { const v = pbVids[c.key]; return v && v._seg; });
  if(!cams.length){ pbToast('No playable cells to align'); return false; }
  if(!cams.some(c => c.key === pbMaster)){ pbToast('Reference (REF) cell has no recording here — pick another REF cell, or use ⇄ Coarse'); return false; }   // need the master as the time target
  const wasPaused = {}; cams.forEach(c => { wasPaused[c.key] = pbVids[c.key].paused; });   // remember prior play/pause so an aborted run can restore it (no cell is repositioned on abort)
  _ocrLast = {};   // fresh read-line panel for this run
  if(btn) btn.disabled = true; { const cb = $('pbModeCoarse'); if(cb) cb.disabled = true; }   // lock BOTH mode buttons during calibration so a mid-run Coarse click can't seek cells while OCR is reading them
  pbStopSync();                                                    // suspend periodic resync during calibration so it can't nudge/seek the cells mid-read
  cams.forEach(c => { try{ pbVids[c.key].play(); }catch(_){} });   // OCR reads each cell at its current (already-decoded) frame — no pre-reload, so the crop/read shows up promptly and isn't a black loading frame. place() below crosses any far-apart cell to T via targetCT.
  const gDeadline = Date.now() + OCR_MAX_MS;
  const off = {};
  let round = 0;
  while(Date.now() < gDeadline){
    const pending = cams.filter(c => off[c.key] == null);
    if(!pending.length) break;                       // every cell read → done early
    round++;
    for(const c of pending){
      if(Date.now() >= gDeadline) break;
      if(btn) btn.textContent = '⏳ OCR ' + Object.keys(off).length + '/' + cams.length + (round > 1 ? ' r' + round : '');
      const tag = 'cell' + (Number(c.key) + 1) + ' ' + dispCam(c.label);   // 1-based label in the debug window (cell1..cell4)
      const o = await calibrateOffset(pbVids[c.key], Math.min(gDeadline, Date.now() + OCR_ROUND_MS), tag, c.key === pbMaster);   // cell keeps PLAYING between rounds → next retry sees a later (maybe cleaner) frame
      if(o != null){ off[c.key] = o; console.log('[OCR ' + tag + '] → offset=' + o.toFixed(2) + 's (round ' + round + ')'); }
      else console.log('[OCR ' + tag + '] → unreadable (round ' + round + '), will retry if time remains');
    }
  }
  if(btn){ btn.disabled = false; btn.textContent = lbl; } { const cb = $('pbModeCoarse'); if(cb) cb.disabled = false; }   // calibration done → unlock both mode buttons
  const failed = cams.filter(c => off[c.key] == null);
  if(failed.length){                                                // mode B: ANY unverified cell → abort, move NOTHING
    cams.forEach(c => { if(wasPaused[c.key]){ try{ pbVids[c.key].pause(); }catch(_){} } });   // restore prior pause state (no cell was repositioned during calibration)
    pbStartSync();
    pbToast('⚠ OCR couldn\'t verify ' + failed.length + '/' + cams.length + ' cell(s): ' + failed.map(c => dispCam(c.label)).join(', ') + '.\nStaying in Precise — it retries on each segment change; or click ◎ Precise again.');
    return false;
  }
  // every cell verified → align all PRECISELY to the reference's real time
  cams.forEach(c => { try{ pbVids[c.key].pause(); }catch(_){} });   // freeze, then position everyone to the reference real time
  $('playBtn').textContent = '⏸ Pause';
  const trueNow = {}; cams.forEach(c => { const v = pbVids[c.key]; trueNow[c.key] = v._seg.s0 + v.currentTime + off[c.key]; });
  const T = trueNow[pbMaster];   // master is verified → its real time is the alignment target
  console.log('[OCR] target real time T = ' + hms(T) + ' (' + T.toFixed(1) + 's of day, from REF cell' + pbMaster + ')');
  // SYNCHRONIZED start: position every cell (master included) at real time T, each with the SAME reliable poll-retry landing as gridSeekAll. Only once EVERY cell has actually LANDED do they play together. The OLD code released after a 4s timeout, so the master (already warm + in-clip → instantly positioned) ran ahead for the ~12s a cross-clip non-master spent reloading+warming → "the reference is several seconds fast while the others agree with each other" (exactly the reported bug). Now nobody plays until all have landed.
  let pending = 0, started = false;
  const startAll = () => { if(started) return; started = true; cams.forEach(c => { const v = pbVids[c.key]; if(v && v._seg && v.paused) v.play().catch(() => {}); }); updateHead(); };
  // position a cell at real burned-time T. targetCT = T − s0 − off (real = s0 + currentTime + off). If T is inside the current file → seek there and KEEP the offset; else cross to the file holding T (coarse there). Landing is async + poll-retried (a cold fMP4 clamps the first seek; a cross-clip cell must reload+warm, 10s+). Returns whether the offset stayed applicable (stayed in its measured clip).
  const place = (key, T, offv) => {
    const v = pbVids[key], arr = pbSegs[key] || []; if(!v || !v._seg) return false;
    const inCT = T - v._seg.s0 - offv, sameClip = (inCT >= -1 && inCT <= (v._seg.s1 - v._seg.s0) + 1);
    let targetCT, reload = false;
    if(sameClip){ targetCT = Math.max(0, Math.min(v._seg.s1 - v._seg.s0, inCT)); }
    else { const b = pbBest(key, T); if(!b) return false; v._idx = b.idx; v._seg = arr[b.idx]; targetCT = b.offset; reload = true; }   // cross to T's file (its own OCR offset unknown → coarse for that clip)
    v._manual = false; v._miss = 0; v.playbackRate = parseFloat($('rateSel').value) || 1;
    v._settling = true; pending++; let tries = 0, done = false;
    const fin = () => { if(done) return; done = true; v.removeEventListener('loadedmetadata', onMeta); v._settling = false; if(--pending <= 0) startAll(); };
    const seekNow = () => { if(v.readyState >= 1) pbSeek(v, targetCT); };
    const onMeta = () => seekNow();
    const poll = () => {
      if(done) return;
      if(v.readyState >= 1 && Math.abs(v.currentTime - targetCT) <= 1.5){ fin(); return; }   // LANDED on target
      if(tries++ >= 100){ seekNow(); fin(); return; }                                        // ~60s last resort (cross-clip 4K metadata can be slow); never hang forever
      seekNow();
      setTimeout(poll, 600);
    };
    if(reload){ v.src = '/video?cam=' + encodeURIComponent(v._id) + '&file=' + encodeURIComponent(arr[v._idx].file); v.addEventListener('loadedmetadata', onMeta); v.load(); }
    poll();
    return sameClip;
  };
  const nmW = Math.max(5, ...cams.map(c => dispCam(c.label).length));   // pad camera names to a column so times line up (monospace)
  const _ov = cams.map(c => off[c.key]).filter(v => v != null).sort((a, b) => a - b);   // for flagging (not rejecting) a cell whose offset is far from the others
  const offMed = _ov.length ? _ov[Math.floor(_ov.length / 2)] : 0, OFF_OUTLIER = 15;
  let aligned = 0, gaps = 0, big = 0; const body = [];
  for(const c of cams){
    const o = off[c.key];
    if(!pbCovers(c.key, T)){                                            // no recording at T → can't align (footage doesn't exist); flag it
      const b = pbBest(c.key, T), arr = pbSegs[c.key] || [];
      body.push(' ✗ ' + dispCam(c.label).padEnd(nmW) + ' no recording at ' + hms(T) + (b && arr[b.idx] ? ' (nearest ' + hms(arr[b.idx].s0) + ')' : ''));
      pbVids[c.key]._ocrOff = null; gaps++; continue;
    }
    // A far-from-the-others offset is NO LONGER treated as a "misread → coarse": calibrateOffset already averaged ~8 frames + median-filtered, so a value that came back means the burned clock tracked currentTime CONSISTENTLY across the clip — a REAL offset (e.g. a cam genuinely running ~60 s behind because its clip's filename doesn't match its content), not a random digit error. The old rejection left that cam PERMANENTLY out of sync (coarse can't correct a real content lag). APPLY it — correcting exactly this is the whole point of Precise — and just flag a large one so it's visible.
    const far = c.key !== pbMaster && Math.abs(o - offMed) > OFF_OUTLIER;
    const applied = place(c.key, T, o); pbVids[c.key]._ocrOff = applied ? o : null; aligned++;   // keep the offset only if we stayed in the segment it was measured in
    body.push(' • ' + dispCam(c.label).padEnd(nmW) + ' ' + hms(trueNow[c.key]) + ' off ' + (o >= 0 ? '+' : '') + o.toFixed(1) + 's' + (c.key === pbMaster ? ' (REF)' : '') + (far ? ' (large → corrected)' : ''));
    if(far) big++;
  }
  const lines = ['✓ OCR aligned to ' + hms(T), ...body, aligned + '/' + cams.length + ' precise' + (big ? ' · ' + big + ' large offset corrected' : '') + (gaps ? ' · ' + gaps + ' no footage' : '') + ' — playing all ▶︎'];
  if(pending === 0) startAll(); else setTimeout(startAll, 65000);   // all in-clip & instant → play now; otherwise play once every cell has LANDED (hard cap matches the per-cell ~60s so a broken cell can't hang the grid)
  $('playBtn').textContent = '⏸ Pause';
  updateHead();
  pbStartSync();                                                   // offset-aware maintenance keeps the alignment as they play
  pbToast(lines.join('\n'));
  return true;
}
function pbAlignCoarse(){      // fallback: align by assumed time (master._seg.s0 + currentTime); stays paused
  const m = pbVids[pbMaster]; if(!m || !m._seg) return;
  m._ocrOff = null;                                       // coarse path → drop the reference's OCR offset too, so the whole sync stays on the assumed-time basis (consistent)
  const T = m._seg.s0 + m.currentTime;                 // freeze the reference moment at this instant
  const cams = pbCams();
  cams.forEach(c => { const v = pbVids[c.key]; if(v) v.pause(); });   // pause all (including the reference), time no longer advances
  cams.forEach(c => {                                  // align each stream to T (the reference is just a reference, its position not moved; stays paused throughout)
    if(c.key === pbMaster) return;
    const v = pbVids[c.key]; if(!v) return;
    v._manual = false; v._miss = 0; v._ocrOff = null; v.playbackRate = parseFloat($('rateSel').value) || 1;   // coarse Sync = align by assumed time → clear any OCR offset so the periodic sync stays coarse too (consistent), + reset nudge rate
    const arr = pbSegs[c.key] || [];
    const b = pbBest(c.key, T); if(!b) return;
    if(b.idx === v._idx && v.readyState >= 1){
      pbSeek(v, b.offset);                                          // same segment loaded: cheap seek (pbSeek records _progT so the 'seeking' event isn't misread as a user drag → _manual would wrongly flip and disable maintenance)
    } else {
      v._idx = b.idx; v._seg = arr[b.idx];                          // cross-segment/not loaded: reload into place (no play)
      v.src = '/video?cam=' + encodeURIComponent(v._id) + '&file=' + encodeURIComponent(arr[b.idx].file);
      const om = () => { v.removeEventListener('loadedmetadata', om); pbSeek(v, b.offset); };
      v.addEventListener('loadedmetadata', om); v.load();
    }
  });
  $('playBtn').textContent = '▶︎ Play';                // stay paused after syncing
  updateHead();
}
function pbTeardown(){ pbGridGen++; pbStopSync(); pbGrid=false; document.body.classList.remove('pbgrid-mode'); $('grid').innerHTML=''; pbVids={}; updateModeBar(); }

function pbStopSync(){ if(pbSyncTimer){ clearInterval(pbSyncTimer); pbSyncTimer = null; } if(pbRefetchTimer){ clearInterval(pbRefetchTimer); pbRefetchTimer = null; } }
// Keep the non-master cells aligned to the master by QUICK (hard-seek) positioning, not smooth rate-nudging:
// once a cell is out of the lock band, seek it straight to the aligned position (browsers do accurate seeks, so it snaps right there). A small lock band absorbs the ~0.2s the master advances during the seek; a per-cell give-up stops a slow source from thrashing.
const PB_LOCK = 0.5;     // |drift| within this (s) = in sync → just match the master's rate
const PB_NUDGE_MAX = 2.5;// |drift| within this = close it with a GENTLE playback-rate nudge (a hard seek alone can't: the master keeps advancing during the seek's landing latency)
const PB_GAIN = 0.04;    // rate delta per second of drift — DELIBERATELY SMALL. Each camera's media clock differs from the master's by ~1%, so a non-master needs a steady ~0.99× to hold; the nudge settles there. (Old PB_GAIN=0.5/PB_CAP=1.0 slammed it down to ~0.5× — visible SLOW-MOTION stutter on the non-master cells.)
const PB_CAP = 0.05;     // max ± rate delta from the master rate = ±5% (0.95–1.05×) — imperceptible, but enough to absorb the ~1.6% per-camera clock difference + slowly converge residual drift. Never a half-speed lurch.
const PB_COLD_MS = 15000;// grace for a COLD load before the watchdog may reload it: a 4K-H265 clip reports buffered.end=0 from loadstart→canplay (~7s+, longer for the slow remote cams under 4-way contention). Reloading inside that window restarts the load from scratch so it never finishes — verified by killing the watchdog, after which stuck cells loaded. So leave the first load alone until it has buffered something OR this grace elapses (a real 404/decode error still trips the reload immediately via v.error).
// real time = s0 + currentTime (1:1). A per-clip "slope" correction (real = s0 + currentTime*media-rate) was tried to remove the small ~1% per-camera drift, but it made the non-master cells stutter (constant lock↔nudge) and was reverted — a smooth view with a slow drift that recal/crossings reset beats a stuttering one.
function pbReloadCell(key){   // hard-reset + reload one cell at the current sync moment (shared by the manual ↻ button and the auto watchdog)
  const v = pbVids[key]; if(!v) return;
  v._miss = 0; v._manual = false;
  const w = currentWall();
  try{ v.pause(); v.removeAttribute('src'); v.load(); }catch(_){}
  if(v.parentElement) showCellMsg(v.parentElement, '');
  pbLoadCell(key, (w && w.sec != null && isFinite(w.sec)) ? w.sec : 0, pbPlaying());   // load the clip at the sync moment, seek + play (pbLoadCell handles the seek-on-loadedmetadata)
}
function pbEnterSeg(v, file, seekTo, play, rate){   // load a freshly-crossed clip (tail roll-over / maintenance relocate). Marks _settling + shows "Loading…" so the watchdog SKIPS the cell and never churns a slow new-segment load into "No video"; seeks once metadata arrives; clears settling+message once frames actually flow (or a safety timeout, so a broken source isn't stranded).
  v._settling = true; if(v.parentElement) showCellMsg(v.parentElement, 'Loading…');
  const clear = () => { v.removeEventListener('loadedmetadata', om); v.removeEventListener('playing', pl); clearTimeout(st); v._settling = false; if(v.parentElement) showCellMsg(v.parentElement, ''); };
  const om = () => { pbSeek(v, seekTo); if(rate != null) v.playbackRate = rate; if(play){ v.play().catch(() => {}); } else { clear(); } };   // paused grid fires no 'playing' → clear right after the seek lands
  const pl = () => clear();
  v.addEventListener('loadedmetadata', om); v.addEventListener('playing', pl);
  const st = setTimeout(() => { v._settling = false; }, 12000);   // safety: never strand the cell if 'playing' never fires (broken source) — hand back to the watchdog
  v.src = '/video?cam=' + encodeURIComponent(v._id) + '&file=' + encodeURIComponent(file);
  v.load();
}
function pbWatchCell(v, key){   // black/stall self-heal: a cell that errored or has no advancing frame for ~3s is auto-reloaded (capped, so a genuinely missing file isn't reloaded forever)
  if(!v._wHook){ v._wHook = 1; v._loadT = Date.now(); v._hadData = false; v.addEventListener('loadstart', () => { v._loadT = Date.now(); v._hadData = false; }); }   // stamp every (re)load start + reset the "ever decoded a frame" flag → feed the cold-load grace + the decoder-queue wait below
  if(v.seeking || v._settling){ v._wMiss = 0; v._tMiss = 0; v._wT = v.currentTime; return; }       // mid-seek, or being positioned by gridSeekAll (_settling) → don't touch it
  const arr = pbSegs[key] || [], nextI = pbNextDone(key, v._idx), hasNext = v._seg && nextI >= 0;   // next COMPLETED clip (skips a live/in-progress clip — can't roll into something not yet seekable)
  const nextGap = hasNext ? (arr[nextI].s0 - v._seg.s1) : Infinity;    // seconds of recording gap between this clip's end and the next clip's start
  const mayRoll = hasNext && (key === pbMaster || nextGap <= 5);       // the master skips gaps (it drives the timeline); a NON-master must NOT roll across a gap — it would run ahead of the master. The maintenance parks it ("No recording") and resumes it once the master re-enters its coverage.
  const prog = v.currentTime - (v._wT == null ? v.currentTime : v._wT);   // forward progress since the last 500ms tick
  const stalled = !v.paused && prog < 0.05;                            // playing but barely advancing — catches BUFFER stalls that micro-advance, not just an exact freeze
  const dur = v._seg ? (v._seg.s1 - v._seg.s0) : 0, atTail = v._seg && v.currentTime >= dur - 5;
  // TAIL ROLL-OVER — a cell at/past its clip end that HAS a CONTIGUOUS next clip MUST advance. Covers a clean end (v.ended), the fMP4 tail ERROR, AND the silent buffer-stall at the unindexed tail (fires no event). Always rolls to the next clip from 0 → forward, never an in-place reload that would just re-stall.
  if(mayRoll && (v.ended || (atTail && !!v.error) || (atTail && stalled))){
    v._wT = v.currentTime; v._sMiss = 0;
    if((v._tMiss = (v._tMiss || 0) + 1) >= ((v.ended || v.error) ? 1 : 3)){   // real end/error → roll next tick; silent stall → confirm ~1.5s first
      v._tMiss = 0; v._wMiss = 0; v._wReloads = 0;
      const ni = nextI; v._idx = ni; v._seg = arr[ni]; v._ocrOff = null; if(pbSyncMode === 'precise') v._recalPending = true;
      pbEnterSeg(v, arr[ni].file, 0, true, null);   // load next clip from 0 + play; "Loading…" + watchdog-skip until frames flow (no churn into "No video")
      console.log('[pb watchdog] cell' + key + ' end-of-clip → advance to next clip');
    }
    return;
  }
  v._tMiss = 0;
  if(!pbSelfHeal){ if(v.readyState >= 2 && v.videoWidth > 0 && v.parentElement) showCellMsg(v.parentElement, ''); return; }   // self-heal disabled (user opt-out): ONLY clip-end roll-over (above) runs; never auto-reload. Just clear a stale message once a cell is actually playing.
  const bufEnd = v.buffered.length ? v.buffered.end(v.buffered.length - 1) : 0;
  if(bufEnd > 0) v._hadData = true;                    // has produced at least one decodable frame on this clip
  const loading = bufEnd > (v._bufLast || 0) + 0.05;   // the buffered range is still GROWING → actively decoding; never reload a cell that's making progress
  v._bufLast = bufEnd;
  const coldLoad = bufEnd === 0 && !v.error && (Date.now() - (v._loadT || 0)) < PB_COLD_MS;   // still in the initial load (buffered.end=0 is NORMAL until canplay)
  // DECODER QUEUE: a cell that has never produced a frame (bufEnd always 0, no error, not currently growing) is
  // WAITING for a decoder — Safari caps concurrent 4K-H265 decodes, so the 4th cell in a 4-split queues. Reloading
  // it is COUNTER-productive: removeAttribute('src') discards its buffered download AND drops its src, so it MISSES
  // the decoder another cell frees when it crosses a clip → it churns "Loading…" forever (the reported stuck cells).
  // Keep its load OPEN and just wait — it grabs a decoder on its own the moment one frees. Only a very slow ~40 s
  // hedge-reload covers a genuinely silent-hung load (network errors fire 'error' → handled as bad below).
  const queued = bufEnd === 0 && !v.error && !v._hadData && !loading && !coldLoad;
  const frozen = stalled && v.readyState >= 2;         // had data then stopped advancing → a real mid-play stall (reload helps)
  const bad = !!v.error || frozen;                     // reload ONLY for a real error or a post-data stall — NOT for a cell still cold-loading / queued for a decoder
  v._wT = v.currentTime;
  if(coldLoad || queued){
    if(v.parentElement) showCellMsg(v.parentElement, 'Loading…');
    if(queued){ if((v._wMiss = (v._wMiss || 0) + 1) >= 80){ v._wMiss = 0; pbReloadCell(key); } }   // ~40 s silent-hang hedge only; otherwise WAIT (don't churn) so it can grab a freed decoder
    else v._wMiss = 0;
    return;
  }
  if(!bad){ v._wMiss = 0; v._wReloads = 0; if(v.parentElement) showCellMsg(v.parentElement, ''); return; }   // healthy → reset + clear any stale message
  const reloads = v._wReloads || 0;
  if((v._wMiss = (v._wMiss || 0) + 1) < (reloads < 3 ? 10 : 24)) return;   // first 3 attempts ~5 s apart, then back off to ~12 s — never permanently give up
  v._wMiss = 0;
  v._wReloads = reloads + 1;
  if(v.parentElement) showCellMsg(v.parentElement, 'Loading…');
  console.log('[pb watchdog] cell' + key + ' error/stall → auto-reload (#' + v._wReloads + ')');
  pbReloadCell(key);
}
function pbResyncVisible(){   // tab is BACK in the foreground. While it was hidden the browser throttled the 500ms maintenance interval to a crawl (often 1/min or paused), so any non-master cell left at a catch-up playbackRate (>1) kept playing in the background and RAN AWAY — the "came back later and CAM3 is ~70s ahead" bug. Reset every cell to the base rate, clear seek cooldowns, and snap the playing non-master cells straight back to the master NOW (don't wait for the throttled-then-resumed loop to slowly notice).
  if(!pbGrid) return;
  const m = pbVids[pbMaster]; if(!m || !m._seg) return;
  const base = parseFloat($('rateSel').value) || 1;
  const mw = m._seg.s0 + m.currentTime + (m._ocrOff || 0);
  pbCams().forEach(c => {
    const v = pbVids[c.key]; if(!v) return;
    v.playbackRate = base; v._reseekT = 0;                                         // kill any background runaway rate + clear the re-seek cooldown
    if(c.key === pbMaster || v.paused || !v._seg || v._settling) return;           // leave the master / paused cells (honor the pause workflow) / mid-load cells alone
    const off = (v._ocrOff || 0), dur = v._seg.s1 - v._seg.s0, targetCT = mw - v._seg.s0 - off;
    if(targetCT >= -1 && targetCT <= dur + 1) pbSeek(v, Math.max(0, Math.min(dur, targetCT)));   // within the current clip → snap back immediately; a cross-clip runaway is relocated by the next (now unthrottled) maintenance tick
  });
}
function pbVisChange(){
  if(!pbGrid) return;
  if(document.hidden){ const base = parseFloat($('rateSel').value) || 1; pbCams().forEach(c => { const v = pbVids[c.key]; if(v) v.playbackRate = base; }); }   // going to background: freeze every rate to base so a throttled maintenance can't leave a cell racing ahead at up to 2x
  else pbResyncVisible();                                                          // back to foreground: reset + re-align everyone to the master
}
function pbStartSync(){
  pbStopSync();
  pbRefetchTimer = setInterval(pbRefetchSegs, 15000);   // rescan every ~15s (matches the server scan cache) so a clip that just finalized (live → completed) lets its parked cell resume
  if(!window.__pbVisHooked){ window.__pbVisHooked = 1; document.addEventListener('visibilitychange', pbVisChange); }   // recover from background-tab timer throttling (registered once; the handler no-ops outside grid mode)
  pbSyncTimer = setInterval(() => {
    pbCams().forEach(c => { const v = pbVids[c.key]; if(v && v._seg) pbWatchCell(v, c.key); });   // black/stall self-heal for every cell, independent of the sync state below
    const m = pbVids[pbMaster];
    if(!m || !m._seg || m.paused) return;                            // master not playing → nothing to track
    if(m.seeking){ pbCams().forEach(cc => { const vv = pbVids[cc.key]; if(vv) vv._miss = 0; }); return; }   // master is mid-drag (currentTime still moving) → don't chase a moving target; reset give-up counters so cells realign cleanly once it settles
    const mRate = parseFloat($('rateSel').value) || 1;   // the master ALWAYS plays at the SELECTED speed — force it. A cell nudged >1× (to catch up while it was a non-master) and then promoted to REF would otherwise keep racing forever, because this loop skips the master and nothing else resets its rate (the "reference cell is sped up" bug).
    if(m.playbackRate !== mRate) m.playbackRate = mRate;
    const mw = m._seg.s0 + m.currentTime + (m._ocrOff || 0);   // master's real time (||0 offset → plain assumed time = coarse baseline)
    pbCams().forEach(c => {
      if(c.key === pbMaster) return;
      const v = pbVids[c.key]; if(!v || !v._seg || v._settling) return;   // skip a cell still being positioned by gridSeekAll (_settling)
      const arr = pbSegs[c.key] || [], off = (v._ocrOff || 0);
      // GAP-HOLD — a non-master parked during a recording gap: either flagged in the relocate branch below, or it played to a clip end whose next clip is across a gap (v.ended, since the contiguity-gated roll-over left it). DISTINCT from a USER pause (honored, never auto-resumed — "Play all" resyncs). Resume only when the master re-enters this cell's coverage in a DIFFERENT clip, so the clip boundary can't reload-loop.
      if(v._gapHold || (v.paused && v.ended)){
        v._gapHold = true;
        const bg = pbCovers(c.key, mw) ? pbBest(c.key, mw) : null;
        if(!bg || bg.idx === v._idx){ showCellMsg(v.parentElement, bg ? '' : pbHoldMsg(c.key, mw)); return; }
        v._gapHold = false; showCellMsg(v.parentElement, '');
        v._reseekT = Date.now(); v._idx = bg.idx; v._seg = arr[bg.idx]; v._ocrOff = null; if(pbSyncMode === 'precise') v._recalPending = true;
        pbEnterSeg(v, arr[bg.idx].file, Math.max(0, mw - arr[bg.idx].s0), true, mRate);
        return;
      }
      if(v.paused) return;                                           // user-paused (mid-clip) → honor the pause workflow
      if(v.seeking || v.readyState < 1) return;                      // a seek is still landing, or the cell is mid-(re)load → don't judge drift / count misses yet
      const dur = v._seg.s1 - v._seg.s0, targetCT = mw - v._seg.s0 - off;   // where real-time mw sits in the cell's CURRENT file (real = s0 + currentTime + off). Content-based, so it's correct for any offset sign near a file boundary — a wall-clock pbBest(mw) mis-judges cross-segment when |off| is large (the cause of a large-offset cell never re-aligning).
      if(targetCT >= -1 && targetCT <= dur + 1){                       // mw is within the current file → align INSIDE it
        const drift = targetCT - v.currentTime, ad = Math.abs(drift);  // + = this cell is BEHIND the master
        if(ad <= PB_LOCK){ if(v.playbackRate !== mRate) v.playbackRate = mRate; v._miss = 0; return; }   // in sync → just match the master's rate
        if(ad <= PB_NUDGE_MAX){                                        // small residual → gentle rate-nudge converges it (a hard seek can't close this last bit because of landing latency); always converges, so no give-up needed
          v.playbackRate = Math.max(0.25, mRate + Math.max(-PB_CAP, Math.min(PB_CAP, drift * PB_GAIN))); v._miss = 0; return;
        }
        if(Date.now() - (v._reseekT || 0) < 1500) return;   // cooldown: the previous seek may still be landing (fMP4's first seek can miss and take ~1s to settle). Re-seeking every 500ms tick is exactly what makes a cell "jump repeatedly" after a master drag → seek ONCE, wait, then re-judge.
        v._reseekT = Date.now();
        pbSeek(v, Math.max(0, Math.min(dur, targetCT))); v.playbackRate = mRate; return;   // big gap → ONE hard seek; the next ticks' nudge finishes the residual
      }
      // mw's real time is outside the current clip's CONTENT → relocate to the clip that holds it.
      if(Date.now() - (v._reseekT || 0) < 1500) return;               // cooldown so a relocate and its landing seek don't thrash
      if(!pbCovers(c.key, mw)){ v._gapHold = true; try{ v.pause(); }catch(_){} showCellMsg(v.parentElement, pbHoldMsg(c.key, mw)); return; }   // no COMPLETED footage at mw (a real gap, or the moment is inside an in-progress recording) → park (pause + hold) so the cell can't run ahead / spin on an unseekable live clip; the gap-hold block above resumes it once a completed clip covers mw (after the periodic refetch finalizes it).
      const b = pbBest(c.key, mw);
      if(!b || b.idx === v._idx) return;   // pbBest still points at THIS clip → mw is inside its filename window, content only JUST past it (a small precise offset). Do NOT step by index here — that oscillates idx↔idx+1 at the boundary. Let the clip play to its natural end → 'ended' advances cleanly. (Coarse mode never lands here: with offset 0, mw past the content means mw is past the filename range too, so pbBest returns a DIFFERENT clip — e.g. CAM1 stuck at a tail still crosses, now that the give-up is gone.)
      const ni = b.idx;
      if(ni < 0 || ni >= arr.length) return;                          // edge of the day's recordings
      v._reseekT = Date.now();
      v._idx = ni; v._seg = arr[ni]; v._ocrOff = null; if(pbSyncMode === 'precise') v._recalPending = true;   // new file → offset invalid; mark for a one-shot OCR re-calibration (precise mode only)
      const land = Math.max(0, mw - arr[ni].s0);                      // coarse position of mw in the new clip (its own offset unknown until re-OCR)
      pbEnterSeg(v, arr[ni].file, land, true, mRate);   // load + seek to mw's coarse position + play at master rate; "Loading…" + watchdog/maintenance-skip (via _settling) until frames flow → the next cooldown'd seek refines it
      // play → the fresh clip loads forward → its index resolves → the next (cooldown'd) maintenance seek lands correctly even if this first one misses (fMP4 moov duration=0). No give-up: a real gap is handled above, so relocation always makes progress and can't loop forever.
    });
    if(pbSyncMode === 'precise'){   // one-shot OCR re-calibration per segment crossing: a cell that just rolled into a new file (offset invalidated) is re-OCR'd ONCE to restore ±1s precision; fires only on the cross (the _recalPending flag), so it can't spin continuously like the old always-on auto-recal
      pbCams().forEach(c => {
        const v = pbVids[c.key];
        if(!v || !v._recalPending || v._recal || v.paused || !v._seg || !v.videoWidth) return;
        v._recalPending = false; v._recal = true;
        calibrateOffset(v, Date.now() + OCR_ROUND_MS, 'recal cell' + (Number(c.key) + 1) + ' ' + dispCam(c.label), c.key === pbMaster).then(o => {
          v._recal = false;
          if(o != null && v._seg){ v._ocrOff = o; console.log('[OCR recal] cell' + c.key + ' re-verified offset=' + o.toFixed(2) + 's after segment change'); }   // next tick's targetCT uses it → snaps back to precise
        }).catch(() => { v._recal = false; });
      });
    }
  }, 500);
}

function pbMarkMaster(){      // highlight the reference cell, append " · Ref" to its badge
  pbCams().forEach(c => {
    const v = pbVids[c.key]; if(!v || !v.parentElement) return;
    const isM = (c.key === pbMaster);
    v.parentElement.classList.toggle('master', isM);
    const badge = v.parentElement.querySelector('.pbname');
    if(badge){ badge.textContent = isM ? 'REF' : ''; badge.style.display = isM ? '' : 'none'; }   // camera name lives in the top-left picker now; top-right badge only marks the reference cell
  });
}
function pbReassign(idx, newLabel){   // change a cell's camera (playback): re-pull that cell's segments for the day and position to the current master moment, other cells untouched
  cellCams[idx] = newLabel;
  const key = String(idx), v = pbVids[key]; if(!v) return;
  v._id = pbCamId(newLabel); v._lbl = newLabel; v._manual = false; v._ocrOff = null;   // different stream → old OCR offset invalid
  const badge = v.parentElement && v.parentElement.querySelector('.pbname');
  if(badge){ const isM = (key === pbMaster); badge.textContent = isM ? 'REF' : ''; badge.style.display = isM ? '' : 'none'; }   // camera name is in the top-left picker; top-right badge only marks the reference cell
  (async () => {
    if(v._id){ const r = await api('/api/segments?cam=' + encodeURIComponent(v._id) + '&date=' + dateStr);
      pbSegs[key] = (r.segments || []).map(s => { const st = new Date(s.start), en = new Date(s.end);
        return { file:s.file, live:s.live, start:st, end:en, s0:(st-dayStart)/1000, s1:(en-dayStart)/1000 }; }); }
    else pbSegs[key] = [];
    const w = currentWall(); pbLoadCell(key, (w && w.sec != null && isFinite(w.sec)) ? w.sec : 0, pbPlaying());
    if(key === pbMaster){ segs = pbSegs[key] || []; curIdx = -1; renderTrack(); }   // reference cell changed camera → the timeline changes with it
  })();
}

async function setPbGrid(on){
  if(on){
    const gen = ++pbGridGen;          // claim this rebuild; a newer enter/teardown bumps pbGridGen → this run bails after its await
    const w = currentWall();          // the current moment before entering
    if(liveMode) setLive(false);
    if(gridMode) setGrid(false);
    pbGrid = true;
    document.body.classList.add('pbgrid-mode');
    updateModeBar();
    document.title = 'Xiaomi Recordings · Playback Split';
    vid.pause(); try{ vid.removeAttribute('src'); vid.load(); }catch(_){}   // FULLY unload the single-stream video (not just pause) → frees its H265 hardware decoder + its server connection for the split cells. Leaving it loaded steals a decoder, and 4K H265 decoders are scarce — that starved 1-2 split cells (black/spinning).
    const g = $('grid'); killStreams(g); g.innerHTML = ''; pbVids = {};
    g.dataset.n = splitN;             // grid layout (2/4/6)
    const cams = pbCams();
    // Reference = the cell showing the same camera as the current single stream, otherwise the first cell with an id, otherwise the first cell
    pbMaster = ((cams.find(c => c.id && c.id === cam) || cams.find(c => c.id) || cams[0] || {}).key) || null;
    cams.forEach(c => {
      const cell = document.createElement('div'); cell.className = 'pbcell';
      const v = document.createElement('video'); v.muted = true; v.playsInline = true; v.preload = 'metadata'; v.controls = true;  // native controls: play/progress/volume/fullscreen
      v._id = c.id; v._lbl = c.label;
      const b = document.createElement('span'); b.className = 'cellbadge pbname'; b.textContent = ''; b.style.display = 'none';   // top-right badge: only the reference cell shows REF (set by pbMarkMaster); camera name is in the top-left picker
      cell.appendChild(v); cell.appendChild(b); g.appendChild(cell);
      addZoom(cell);   // zoom key (in-page zoom, not system fullscreen)
      addCellCam(cell, +c.key, pbReassign);   // camera dropdown per cell (playback)
      // Per-cell refresh: a cell that failed to load (black) can be reloaded alone, re-positioned to the current sync moment, without disturbing the others
      (function(key, cellEl){
        const r = document.createElement('span'); r.className = 'gref'; r.textContent = '↻'; r.title = 'Reload this camera';
        r.onclick = (e) => { e.preventDefault(); e.stopPropagation(); const vv = pbVids[key]; if(vv){ vv._wReloads = 0; } pbReloadCell(key); };   // manual ↻: reset the auto-reload cap + hard reload this cell
        cellEl.appendChild(r);
      })(c.key, cell);
      // No 'seeking' handler is needed. Dragging the REFERENCE within its current clip does NOT invalidate any OCR offset (the currentTime↔real-time mapping is constant within a file), so the maintenance keeps every non-master cell PRECISELY aligned to the reference's new moment using their intact offsets. (Clearing offsets here used to dump Precise back to coarse on every reference drag = the cells "going out of alignment".) A genuine clip change is handled where it actually happens: gridSeekAll (timeline jump) and the maintenance cross both reset/re-OCR the offset.
      pbVids[c.key] = v;
      v.addEventListener('timeupdate', updateHead);          // the reference cell drives the playhead (decided inside updateHead)
      const advance = () => {                                // continue to this cell's next COMPLETED segment (skip a live/in-progress clip — not yet seekable)
        const arr = pbSegs[c.key] || []; const ni = pbNextDone(c.key, v._idx);
        if(ni < 0) return false;
        v._idx = ni; v._seg = arr[ni]; v._ocrOff = null; if(pbSyncMode === 'precise') v._recalPending = true;   // new file → offset invalid; in precise mode mark for a one-shot OCR re-calibration so ±1s is restored automatically
        v.src = '/video?cam=' + encodeURIComponent(v._id) + '&file=' + encodeURIComponent(arr[ni].file);
        const om = () => { v.removeEventListener('loadedmetadata', om); v.play().catch(()=>{}); };
        v.addEventListener('loadedmetadata', om); v.load(); return true;
      };
      v.addEventListener('ended', advance);                  // clean end of clip → next clip (the watchdog is the backstop for stalls that fire no event)
      v.addEventListener('error', () => { if(v._seg && v.currentTime >= (v._seg.s1 - v._seg.s0) - 10) advance(); });   // fMP4 tail error → advance; a mid-clip error is left to the watchdog reload
    });
    pbMarkMaster();                   // mark the reference camera (highlighted border)
    await pbFetchDay(dateStr);
    if(gen !== pbGridGen) return;     // a newer mode change happened during the fetch → abandon this stale rebuild (don't resurrect torn-down grid state / start a zombie sync loop)
    segs = pbSegs[pbMaster] || [];    // the timeline shows the master camera's coverage
    curIdx = -1; renderTrack();
    $('empty').style.display = segs.length ? 'none' : '';
    const fresh = !(w && w.sec != null && isFinite(w.sec));   // entered playback with no prior position (from Live) → default to the latest reliably-playable moment, not midnight 00:00
    let startSec = w ? w.sec : 0;
    if(fresh){ const comp = segs.filter(s => !s.live), last = comp.length ? comp[comp.length - 1] : segs[segs.length - 1];   // skip the in-progress (still-recording) clip: seeking its growing LIVE edge spins / lands minutes off. Use the last COMPLETED clip's end — solid, seekable, and covered by every camera.
      startSec = last ? Math.max(0, last.s1 - 2) : 0; }
    gridSeekAll(startSec, fresh ? true : !!(w && w.play));   // entering playback → PLAY (same path as a timeline click): these fMP4 (moov duration=0) only seek accurately once playing loads the file forward — a paused first-load lands at the segment end (cells misaligned). Play to lock the positions, then you can Pause all.
    pbStartSync();                    // start periodic resync
  } else {
    const w = currentWall();          // pbGrid is still true → take the master camera's current moment
    const mv = pbVids[pbMaster];      // collapse to the SINGLE view of the REF (master) cell's camera (read before pbTeardown clears pbVids)
    if(mv && mv._id){ cam = mv._id; const cs = $('camSel'); if(cs) cs.value = cam; }
    pbTeardown();
    document.title = 'Xiaomi Recordings · Timeline Playback';
    selectDay(dateStr, (w && w.sec != null) ? w.sec : null, !!(w && w.play));   // back to the single view at the same moment (now showing the REF camera)
  }
}
// Playback split: Play all (realign to the current moment then play together) / Pause all
$('pbPlayAll').onclick  = () => { const w = currentWall(); if(w && w.sec != null && isFinite(w.sec)) gridSeekAll(w.sec, true); else pbCams().forEach(c => { const v = pbVids[c.key]; if(v && v._seg) v.play().catch(()=>{}); }); $('playBtn').textContent = '⏸ Pause'; };   // realign every cell to the reference's CURRENT moment, then play together — matches the "pause the others → scrub the reference to the key moment → Play all" workflow (the paused cells jump to the reference and resume in sync)
$('pbPauseAll').onclick = () => { pbCams().forEach(c => { const v = pbVids[c.key]; if(v) v.pause(); }); $('playBtn').textContent = '▶︎ Play'; };
function pbSetSyncMode(mode){ pbSyncMode = mode; $('pbModeCoarse').classList.toggle('on', mode === 'coarse'); $('pbModePrecise').classList.toggle('on', mode === 'precise'); }
$('pbModeCoarse').onclick = () => { pbSetSyncMode('coarse'); pbAlignCoarse(); };   // Coarse mode: align by assumed time now; background maintains coarse
$('pbModePrecise').onclick = async () => {   // Precise mode: OCR-align now; STAY in Precise even if it can't verify every cell this round — it keeps re-trying on each segment crossing, and you can click Precise again. (No auto fall-back to Coarse.)
  pbSetSyncMode('precise');
  await pbOcrSync();
};

// Quality dropdown: fill options + rebuild the current live on change (applies to both single view and split)
QUAL_CODECS.forEach((q, i) => { const o = document.createElement('option'); o.value = i; o.textContent = q.label; $('qualSel').appendChild(o); });
QUAL_RES.forEach((r, i) => { const o = document.createElement('option'); o.value = i; o.textContent = r + 'P'; $('resSel').appendChild(o); });
$('qualSel').value = qualIdx; $('resSel').value = resIdx;
const onQualChange = () => { qualIdx = +$('qualSel').value; resIdx = +$('resSel').value; if(gridMode) setGrid(true); else if(liveMode) setLive(true); };   // rebuild the live stream(s) at the new codec×resolution
$('qualSel').onchange = onQualChange;
$('resSel').onchange = onQualChange;
$('playBtn').onclick = () => { if(pbGrid){ pbToggle(); return; } if(vid.paused) vid.play().catch(()=>{}); else vid.pause(); };
vid.addEventListener('play',  () => $('playBtn').textContent = '⏸ Pause');
vid.addEventListener('pause', () => $('playBtn').textContent = '▶︎ Play');
$('back10').onclick = () => { if(pbGrid){ const w = currentWall(); gridSeekAll(Math.max(0,(w.sec||0)-10), pbPlaying()); return; } vid.currentTime = Math.max(0, vid.currentTime - 10); };
$('fwd10').onclick  = () => { if(pbGrid){ const w = currentWall(); gridSeekAll((w.sec||0)+10, pbPlaying()); return; } vid.currentTime = vid.currentTime + 10; };
// Prev/Next recording clip: step the whole screen to the start of the previous/next segment (split → gridSeekAll, single → loadSegment).
function jumpSeg(delta){
  if(pbGrid){
    if(!segs.length) return;
    const cur = pbVids[pbMaster] ? (pbVids[pbMaster]._idx | 0) : -1;
    let i = (cur < 0) ? 0 : cur + delta;
    i = Math.max(0, Math.min(segs.length - 1, i));
    gridSeekAll(segs[i].s0, true);
    return;
  }
  if(!segs.length) return;
  if(liveMode) setLive(false);   // Prev/Next → switch to recordings
  let i = (curIdx < 0) ? 0 : curIdx + delta;
  i = Math.max(0, Math.min(segs.length - 1, i));
  loadSegment(i, 0, true);
}
$('prevSeg').onclick = () => jumpSeg(-1);
$('nextSeg').onclick = () => jumpSeg(1);
$('rateSel').onchange = e => { const r = parseFloat(e.target.value); vid.playbackRate = r; pbCams().forEach(c => { const v = pbVids[c.key]; if(v) v.playbackRate = r; }); };
$('latestBtn').onclick = async () => {
  await reloadCameras();                          // rescan: surface a possibly new latest day (e.g. crossing midnight to 6/9)
  await loadTimeline({ sec: 'latest', play: true });   // locate to the latest moment of the latest day (applies to both single-stream playback and split playback)
};
// ---- Prev / Next (jump to the start of the adjacent recording segment) ----


init();
</script>
</body>
</html>
"""


# --------------------------------------------------------------------------- #
def parse_args(argv):
    """A trailing all-digit argument is treated as the port; the rest as root directories."""
    roots, port = [], DEFAULT_PORT
    for a in argv:
        if a.isdigit():
            port = int(a)
        else:
            roots.append(a)
    if not roots:
        roots = list(DEFAULT_ROOTS)
    return roots, port


def main():
    global ROOTS, PORT
    ROOTS, PORT = parse_args(sys.argv[1:])

    cams = list_cameras()
    print("=" * 60)
    print(" Xiaomi Recordings Playback Service")
    print(" Roots   :", ", ".join(ROOTS))
    if cams:
        print(" Cameras :")
        for c in cams:
            print("    -", c["label"])
    else:
        print(" Warning: no XiaomiCamera_* directory found; check that the roots / mount points are correct.")
    print(" Open in browser: http://<local IP>:%d/   (or http://127.0.0.1:%d/)" % (PORT, PORT))
    print(" Press Ctrl+C to stop")
    print("=" * 60)

    httpd = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        httpd.server_close()


if __name__ == "__main__":
    main()
