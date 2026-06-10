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
    "/Volumes/c700_05",   # wrt32x  spare disk, empty for now — future 5th camera
]
DEFAULT_PORT = 8800

# go2rtc (Frigate machine): the player same-origin proxies its video-stream component JS,
# bypassing the CORS restriction on cross-origin ES modules.
GO2RTC = "http://192.168.10.240:1984"
_JS_CACHE = {}
_JS_LOCK = threading.Lock()

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
                        e = datetime.datetime.now()
                        if e <= s:
                            e = s + datetime.timedelta(seconds=1)
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
    --text:#c9d3da; --dim:#97a2ab; --accent:#ffb02e; --accent2:#ff5a3c;
    --cover:#2f7d5b; --cover2:#3ba277; --grid:#161c22;
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
  header .dot{width:7px;height:7px;border-radius:50%;background:var(--accent);box-shadow:0 0 8px rgba(255,176,46,.55);flex:0 0 auto}
  header h1{font-size:13px;letter-spacing:.16em;text-transform:uppercase;font-weight:600;margin:0;color:#cdd5dc;white-space:nowrap}
  /* Mobile: hide brand + empty right spacer so the controls aren't pushed to the very bottom edge */
  @media (max-width:760px){ .nav-left, .nav-right{display:none} }
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
  /* Maximize / exit button: only appear when the player frame is hovered (both ⛶ and ✕); always-on on touch */
  .gridfullbtn{opacity:0;transition:opacity .15s}
  .stage:hover .gridfullbtn{opacity:1}
  @media (hover:none){ .gridfullbtn{opacity:1} }
  .grid video-stream{position:relative;display:block;width:100%;height:100%;background:#000;overflow:hidden;touch-action:manipulation}
  .grid video-stream video{width:100%;height:100%;object-fit:contain;display:block}
  .grid video-stream .info{display:none}   /* hide the component's built-in RTC badge */
  video-stream .cellbadge, .pbcell .cellbadge{position:absolute;top:8px;right:48px;z-index:6;pointer-events:none;
    font-family:var(--mono);font-size:11px;color:#fff;background:var(--accent2);
    padding:2px 7px;border-radius:5px;font-weight:700;box-shadow:0 0 8px rgba(255,90,60,.6)}
  body.grid-mode .grid{display:grid}
  body.grid-mode #vid,
  body.grid-mode #live,
  body.grid-mode .liveTag,
  body.grid-mode .transport{display:none !important}   /* live split also keeps the bottom timeline (.dates/.tlwrap); all four modes share the same display */
  /* Quality dropdown: always visible (nav bar identical in both modes, never hidden or empty). Changing it during playback only presets the next live quality, no side effect */
  /* Playback split: reuse the .grid layout, but keep the timeline/controls; cells are <video> wrapped in .pbcell */
  .grid .pbcell{position:relative;background:#000;overflow:hidden;touch-action:manipulation}
  .grid .pbcell video{width:100%;height:100%;object-fit:contain;display:block}
  .pbcell .pbname{background:rgba(10,12,15,.72);color:#fff;box-shadow:none;text-transform:uppercase}   /* camera name badge (shows uppercase C700, value stays lowercase) */
  .grid .pbcell.master{outline:2px solid var(--accent);outline-offset:-2px}   /* reference camera: highlighted border */
  .pbcell.master .pbname{background:var(--accent);color:#0a0c0f}
  .grid .gzoom{position:absolute;top:50%;right:8px;transform:translateY(-50%);z-index:8;cursor:pointer;user-select:none;color:#fff;
    background:rgba(10,12,15,.66);border:1px solid var(--line);border-radius:7px;padding:5px 9px;font-size:16px;line-height:1}
  .grid .gzoom:hover{background:rgba(10,12,15,.92);border-color:#34424e}
  .grid .gref{position:absolute;top:50%;left:8px;transform:translateY(-50%);z-index:8;cursor:pointer;user-select:none;color:#fff;
    background:rgba(10,12,15,.66);border:1px solid var(--line);border-radius:7px;padding:5px 9px;font-size:16px;line-height:1}
  .grid .gref:hover{background:rgba(10,12,15,.92);border-color:#34424e}
  /* Per-cell controls (refresh / zoom / camera picker): only appear when the cell is hovered (focused); always-on for touch (no hover) */
  .grid .gref, .grid .gzoom, .grid .cellcam{opacity:0;transition:opacity .15s}
  .grid video-stream:hover .gref, .grid video-stream:hover .gzoom, .grid video-stream:hover .cellcam,
  .grid .pbcell:hover .gref, .grid .pbcell:hover .gzoom, .grid .pbcell:hover .cellcam{opacity:1}
  @media (hover:none){ .grid .gref, .grid .gzoom, .grid .cellcam{opacity:1} }
  .grid .cellcam{position:absolute;top:8px;left:8px;z-index:9;font-family:var(--mono);font-size:11px;color:#fff;
    background:rgba(10,12,15,.7);border:1px solid var(--line);border-radius:6px;padding:3px 4px;text-transform:uppercase;cursor:pointer}
  .grid .cellcam:hover{border-color:#34424e}
  .grid.zoomed > :not(.zoom){display:none}            /* hide the other cells when zoomed */
  .grid > .zoom{grid-column:1 / -1;grid-row:1 / -1}    /* the zoomed cell fills the whole grid area */
  body.pbgrid-mode .grid{display:grid}
  body.pbgrid-mode #vid,
  body.pbgrid-mode #live,
  body.pbgrid-mode .liveTag{display:none}
  #pbPlayAll,#pbPauseAll,#pbSyncBtn{display:none}                       /* Play all / Pause all / Sync: shown only in playback split */
  body.pbgrid-mode #playBtn{display:none}                               /* playback split uses "Play all/Pause all" instead of the single-stream play key */
  body.pbgrid-mode #pbPlayAll,body.pbgrid-mode #pbPauseAll,body.pbgrid-mode #pbSyncBtn{display:inline-block}
  .transport{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
  .transport .grow{flex:1}
  .pill{font-family:var(--mono);font-size:12px;color:var(--dim)}
  /* Date bar */
  .dates{display:flex;gap:8px;overflow-x:auto;padding-bottom:4px}
  .dates::-webkit-scrollbar{height:6px}
  .dates::-webkit-scrollbar-thumb{background:#222b33;border-radius:3px}
  .day{flex:0 0 auto;font-family:var(--mono);font-size:12px;color:var(--dim);
    background:var(--panel2);border:1px solid var(--line);border-radius:7px;
    padding:7px 11px;cursor:pointer;text-align:center;line-height:1.3}
  .day small{display:block;color:#828d97;font-size:10px}
  .day:hover{border-color:#34424e;color:var(--text)}
  .day.on{color:#0a0c0f;background:var(--accent);border-color:var(--accent)}
  .day.on small{color:#7a5410}
  /* Select date: always-on dial (date/hour/min/sec, 3D wheel) + a live clock on top + Go to / Back to live buttons.
     No card frame around it; flush to the edge, same width as the time bar / player frame (matching the time bar) */
  .dppanel{padding:4px 0 0;margin-bottom:8px}
  .dpbar{display:flex;align-items:center;gap:10px;width:100%;background:none;border:0;
    padding:6px 2px;cursor:pointer;color:var(--text)}
  .dpbarL{font-size:13px;color:var(--dim)}
  .dpclock{font-family:var(--mono);font-size:17px;color:var(--text);font-weight:600}
  .dpchev{margin-left:auto;color:var(--dim);font-size:12px;transition:transform .15s}
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
    background:linear-gradient(180deg,transparent 64px,rgba(244,180,38,.10) 64px,rgba(244,180,38,.10) 96px,transparent 96px)}
  .whcol[data-k="date"]{width:104px}
  .whcol::-webkit-scrollbar{display:none}
  .whitem{height:32px;line-height:32px;text-align:center;font-family:var(--mono);font-size:18px;
    color:var(--text);opacity:.32;scroll-snap-align:center;scroll-snap-stop:always;transition:opacity .12s,color .12s}
  .whitem.sel{opacity:1;color:var(--accent);font-weight:700}
  .whcol[data-k="date"] .whitem{font-size:15px}
  .dpacts{margin-left:8px}
  .dpacts .dlbl,.dpacts .wharr{visibility:hidden;pointer-events:none}   /* spacer: align the button with the centered highlight row of the wheels */
  .dpgowrap{height:160px;display:flex;align-items:center}
  #dpGo{background:var(--accent);color:#0a0c0f;border-color:var(--accent);font-weight:700;font-size:14px;padding:10px 14px;white-space:nowrap}
  /* Timeline */
  /* Remove the outer card (border/background/radius) and left/right padding, so the timeline track aligns to the same width as the date bar above and the player frame */
  .tlwrap{padding:14px 0 10px}
  .tlhead{display:flex;justify-content:space-between;font-family:var(--mono);
          font-size:11px;color:var(--dim);margin-bottom:8px}
  .track{position:relative;height:46px;border-radius:6px;cursor:crosshair;touch-action:none;
    background:
      repeating-linear-gradient(90deg,var(--grid) 0,var(--grid) 1px,transparent 1px,transparent calc(100%/24));
    background-color:var(--panel2);border:1px solid var(--line);overflow:hidden}
  .cover{position:absolute;top:0;bottom:0;background:linear-gradient(var(--cover2),var(--cover));
         opacity:.85}
  .cover.live{background:linear-gradient(var(--accent),#d98f1d)}
  .playhead{position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--accent2);
    box-shadow:0 0 8px var(--accent2);pointer-events:none;display:none}
  .tip{position:fixed;transform:translateX(-50%);white-space:nowrap;
    font-family:var(--mono);font-size:11px;color:#0a0c0f;background:var(--accent);
    padding:3px 7px;border-radius:5px;pointer-events:none;display:none;z-index:50;
    box-shadow:0 2px 8px rgba(0,0,0,.5)}
  .tip::after{content:"";position:absolute;left:50%;top:100%;transform:translateX(-50%);
    border:4px solid transparent;border-top-color:var(--accent)}
  .tlnav{display:flex;align-items:center;gap:8px}
  .tlnav button{padding:3px 9px;font-size:13px;line-height:1.2}
  .ticks{display:flex;justify-content:space-between;font-family:var(--mono);
    font-size:10px;color:#aab4bd;margin-top:5px;padding:0 1px}
  .empty{font-family:var(--mono);font-size:12px;color:var(--dim);
    text-align:center;padding:14px 0}
  .hint{font-family:var(--mono);font-size:11px;color:#aab4bd}
  kbd{font-family:var(--mono);background:#171c22;border:1px solid var(--line);
    border-bottom-width:2px;border-radius:4px;padding:1px 5px;font-size:10px;color:var(--text)}
</style>
<script type="module" src="/video-stream.js"></script>
</head>
<body>
<header>
  <div class="navin">
    <div class="nav-left">
      <span class="dot"></span>
      <h1>Xiaomi Recordings</h1>
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
      <select id="camSel" title="Camera"></select>
      <select id="qualSel" title="Live quality (Direct = direct feed, Transcode = compatible)"></select>
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
    <button id="pbSyncBtn" title="Realign drifted/independent cells back to the reference (lightweight, does not reload already-synced cells)">⇄ Sync</button>
    <button id="back10">⟲ 10s</button>
    <button id="fwd10">10s ⟳</button>
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
    <button class="dpbar" id="dpbar" title="Tap to pick a date/time to jump to">
      <span class="dpbarL">📅</span>
      <span class="dpclock" id="dpclock">—</span>
      <span class="dpchev" id="dpchev">▾</span>
    </button>
    <div class="dpbody" id="dpbody">
      <div class="dpwheels">
        <div class="dpcol"><span class="dlbl">Date</span><button class="wharr whup" data-k="date" aria-label="Previous day">▲</button><div class="whcol" data-k="date"></div><button class="wharr whdn" data-k="date" aria-label="Next day">▼</button></div>
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
  <div class="dates" id="dates"></div>

  <div class="tlwrap">
    <div class="tlhead">
      <span class="tlnav">
        <button id="prevSeg" title="Previous recording segment">⏮ Prev</button>
        <span id="tlDate">—</span>
        <button id="nextSeg" title="Next recording segment">Next ⏭</button>
      </span>
    </div>
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
// Quality tracks: if WebRTC-H265 is supported, offer original 1080P direct feed; transcoded 1080P is always the fallback. Direct = direct feed without transcoding, Transcode = go2rtc transcodes to H264.
const QUALS = [];
if(RTC_H265) QUALS.push({label:'Direct', suffix:'_sub1080', mode:'webrtc'});   // original direct out (no transcode, original quality); default when WebRTC-H265 is supported
QUALS.push({label:'Transcode', suffix:'_1080p', mode:'webrtc'});               // H264 transcode fallback (the only option for browsers without H265)
let qualIdx = 0;   // default track 0: original direct out when supported, otherwise transcode
function liveSuffix(){ return QUALS[qualIdx].suffix; }
function liveModeNow(){ return QUALS[qualIdx].mode; }
const START_LIVE = true;      // opening the page defaults to single-stream live (set false = default to the latest recording)
let liveMode = false;
let gridMode = false;   // live split (splitN>1 and live)
let pbGrid = false;     // playback split (splitN>1 and playback, sharing the timeline)
// Split: choose 1/2/4/6 cells, each cell assigned one camera. cellCams[i] = the camera label (c700_0X) for cell i
const ALL_CAMS = ['c700_01','c700_02','c700_03','c700_04','c700_05','c700_06'];   // internal names (used to pull streams / find recordings, do not change)
// UI display names (display only, unrelated to go2rtc). Change here to use different names:
const CAM_NAMES = { c700_01:'CAM 1', c700_02:'CAM 2', c700_03:'CAM 3', c700_04:'CAM 4', c700_05:'CAM 5', c700_06:'CAM 6' };
function dispCam(lbl){ return CAM_NAMES[lbl] || lbl; }
let splitN = 1;                                   // current split count (1 = single stream)
let cellCams = ALL_CAMS.slice(0, 4);              // cameras per cell, default first N streams; truncated/padded by N when changing split count

let cam = null;
let dateStr = null;
let segs = [];          // segments of the current day [{file,start(Date),end(Date),live, s0(seconds relative to start of day), s1}]
let curIdx = -1;
let dayStart = null;    // the Date for 00:00 of the current day
let firstLoad = true;   // only the first load auto-jumps to the latest; afterwards switching date/camera keeps the current position

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
    setLive(true);     // go live first: live from the first frame, no brief flash of playback
    loadTimeline();    // load the timeline in the background (no await); its loadSegment goes to the hidden #vid, does not autoplay, does not affect live
  } else {
    await loadTimeline();   // playback default: locate to the latest and play
  }
}

// ---- Load the available dates of a camera ----
async function loadTimeline(want){
  const t = await api('/api/timeline?cam=' + encodeURIComponent(cam));
  const days = t.days || [];
  const keys = days.map(d => d.date);
  const box = $('dates'); box.innerHTML = '';
  days.forEach(d => {
    const el = document.createElement('div');
    el.className = 'day'; el.dataset.date = d.date;
    el.innerHTML = d.date.slice(5) + '<small>' + d.count + ' seg</small>';
    // when switching date, keep the current timeline position (same moment, jump to the nearest)
    el.onclick = () => { const w = currentWall(); if(liveMode) setLive(false); selectDay(d.date, w.sec, w.play); };
    box.appendChild(el);
  });
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
  document.querySelectorAll('.day').forEach(e => {
    const on = e.dataset.date === d;
    e.classList.toggle('on', on);
    if(on) e.scrollIntoView({inline:'center', block:'nearest'});
  });
  $('tlDate').textContent = d;
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
  if(gridMode) setGrid(false);   // any playback action exits the live split
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
}

// ---- Track: drag/click; the playhead follows the cursor and shows the precise time bubble at that position ----
let dragging = false;
let cancelDrag = false;   // moving cursor/finger above or below the track while dragging = cancel this drag (no jump on release)
const track = $('track');

function moveHead(sec){            // sec = seconds relative to 00:00 of the day
  const ph = $('playhead');
  ph.style.display = 'block';
  ph.style.left = (Math.min(DAY, Math.max(0, sec))/DAY*100) + '%';
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
function seekTo(sec){
  if(pbGrid){ gridSeekAll(sec, true); return; }   // playback split: whole screen jumps to the same moment
  if(gridMode){ setPbGrid(true).then(() => gridSeekAll(sec, true)); return; }   // dragging the timeline in live split → enter [split playback] and jump to that moment (not single-stream playback)
  if(liveMode) setLive(false);   // clicking/dragging the timeline → switch to recordings
  const i = segIndexAt(sec);     // whatever the user sets is it: locate to the segment covering that moment, precise to that second
  if(i >= 0) loadSegment(i, sec - segs[i].s0, true);
}

track.addEventListener('pointerdown', e => {
  if(!segs.length || !dayStart) return;
  dragging = true; cancelDrag = false;
  try{ track.setPointerCapture(e.pointerId); }catch(_){}
  const sec = trackSec(e); moveHead(sec); showTip(e);     // move the line immediately + show the time
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
  if(dragging) moveHead(sec);      // while dragging the line follows the cursor
  showTip(e);                      // hovering also shows the time at that point
});
track.addEventListener('pointerleave', () => { if(!dragging) hideTip(); });
function endDrag(e){
  if(!dragging) return;
  dragging = false;
  try{ track.releasePointerCapture(e.pointerId); }catch(_){}
  hideTip();
  if(cancelDrag){ cancelDrag = false; updateHead(); return; }   // cancel: no jump, the playhead returns to the actual position
  seekTo(trackSec(e));             // only jump/load on release
}
track.addEventListener('pointerup', endDrag);
track.addEventListener('pointercancel', () => { dragging = false; cancelDrag = false; hideTip(); updateHead(); });
// Press Esc while dragging to cancel (desktop)
document.addEventListener('keydown', e => { if(e.key === 'Escape' && dragging){ dragging = false; cancelDrag = false; hideTip(); updateHead(); } });

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
function liveAvailable(){ return /^c700_0[1-4]$/.test(liveLabel()); }   // the spare disk c700_05 has no live source
// ===== View modes: Playback / Live / Live split / Playback split (toggled uniformly by the segmented switches) =====
function currentMode(){ return pbGrid ? 'pbgrid' : gridMode ? 'livegrid' : liveMode ? 'live' : 'play'; }
function curTime(){ const m = currentMode(); return (m==='live' || m==='livegrid') ? 'live' : 'play'; }
function curSplit(){ return splitN > 1; }
function ensureCellCams(){   // keep the existing per-cell cameras, pad/truncate to the current splitN (pad with the default first few streams)
  const n = Math.max(1, splitN);
  while(cellCams.length < n) cellCams.push(ALL_CAMS[cellCams.length] || ALL_CAMS[0]);
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
}
function setMode(m){
  const cur = currentMode();
  if(m === cur) return;
  // Sync the split count to keep the nav bar consistent with the actual mode (the L/G/P shortcuts call setMode directly, not applyMode, otherwise you would get "nav shows split, content is single stream" mismatch)
  if(m === 'live' || m === 'play') splitN = 1;          // single view
  else if(splitN < 2) splitN = 4;                        // entering grid: at least 2, default 4
  ensureCellCams();
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
function buildDials(){   // called after loadTimeline has rendered the dates; the dial rests at the current date+time (does not trigger a jump)
  const keys = [...document.querySelectorAll('.day')].map(e => e.dataset.date);   // only days that have recordings
  if(!keys.length) return;
  const w = currentWall(); const cs = (w && isFinite(w.sec)) ? Math.floor(w.sec) : 0;
  const r = n => Array.from({length:n}, (_, i) => ({val:i, txt:String(i).padStart(2,'0')}));
  whFill('date', keys.map(k => ({val:k, txt:k.slice(5) + ' ' + WD[new Date(k+'T00:00:00').getDay()]})), Math.max(0, keys.indexOf(dateStr)));
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
// Go to time: stop precisely at the selected moment (what you see is what you get; if it is a gap, stop at that moment). Only clicking this button jumps, and collapses the bar after jumping
$('dpGo').onclick = async () => {
  const d = whVal('date'); if(!d) return;
  const sec = Number(whVal('h'))*3600 + Number(whVal('m'))*60 + Number(whVal('s'));   // use the real values (correct whichever copy you land on in a looping column)
  $('dppanel').classList.remove('open');
  if(gridMode || pbGrid){                                 // live split / playback split → enter [playback split] and whole screen jumps to that moment
    if(!pbGrid) await setPbGrid(true);                    // live split → switch to playback split (current day)
    if(d !== dateStr) await selectDay(d, sec, false);     // changing day: the pbGrid branch re-pulls that day and whole screen jumps to sec
    else gridSeekAll(sec, true);                          // same day: whole screen jumps to sec
    return;
  }
  if(liveMode) setLive(false);                            // single stream
  if(d !== dateStr){ await selectDay(d, null, false); }   // changing day: load that day first (no pre-positioning)
  seekTo(sec);                                            // locate precisely to the selected moment
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
  const b = document.createElement('span'); b.className = 'cellbadge'; b.textContent = '● Live'; v.appendChild(b);
  const upd = () => {
    const el = v.video; if(!el) return;
    const proto = el.srcObject ? 'RTC' : ((el.src || '').startsWith('blob:') ? 'MSE' : '…');
    b.textContent = '● ' + proto;
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
  try{ v.background = false; v.disconnectedCallback && v.disconnectedCallback(); }catch(_){}
  const nv = makeGridCell(v._lbl); nv._idx = v._idx; nv._tries = v._tries || 0;   // carry over the index/retry count
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
function cellWatch(v){
  let last = -1, frozen = 0, grace = 6, started = false;
  const id = setInterval(() => {
    if(!gridMode || !document.contains(v)){ clearInterval(id); return; }   // already replaced/exited the split: stop the timer
    const el = v.video; if(!el) return;
    if(el.currentTime > 0.1){ started = true; showCellMsg(v, ''); }
    if(grace > 0){ grace--; return; }                    // connection grace period (~6s)
    if(!started){                                         // never produced a frame
      if((v._tries || 0) >= 2){ showCellMsg(v, 'No signal'); clearInterval(id); return; }   // still no frames after 2 reconnects → No signal, stop
      v._tries = (v._tries || 0) + 1; gridReconnect(v); return;
    }
    if(el.paused){ last = -1; frozen = 0; return; }       // already played, user paused: not a stall
    if(el.currentTime === last){ if(++frozen >= 3) gridReconnect(v); }   // frozen 3s → reconnect this cell
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
    // Stagger connections: each stream's WebRTC handshake is fired 400ms apart, to avoid simultaneous connections fighting and leaving some cells unrefreshed
    liveGridLabels().forEach((lbl, i) => {
      setTimeout(() => {
        if(!gridMode) return;      // if the split was exited in the meantime, do not connect
        const v = makeGridCell(lbl); v._idx = i;
        g.appendChild(v);          // add to DOM first (the component creates the inner <video>)
        wireCell(v);               // set src to connect + camera dropdown/badge/zoom/single-cell refresh/single-cell self-heal
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

function pbCamId(lbl){ const o = [...$('camSel').options].find(o => o.dataset.lbl === lbl); return o ? o.value : null; }   // internal name → disk id (unconnected 05/06 return null)
// One {key=cell index, label, id} per cell. Keyed by index → supports any per-cell camera, duplicates, reserved (no id)
function pbCams(){ return cellCams.slice(0, splitN).map((lbl, i) => ({ key: String(i), label: lbl, id: pbCamId(lbl) })); }

async function pbFetchDay(date){      // concurrently pull each cell's segments for the day (cells without an id = empty)
  pbSegs = {};
  await Promise.all(pbCams().map(async c => {
    if(!c.id){ pbSegs[c.key] = []; return; }
    const r = await api('/api/segments?cam=' + encodeURIComponent(c.id) + '&date=' + date);
    pbSegs[c.key] = (r.segments || []).map(s => { const st = new Date(s.start), en = new Date(s.end);
      return { file:s.file, live:s.live, start:st, end:en, s0:(st-dayStart)/1000, s1:(en-dayStart)/1000 }; });
  }));
}

function pbSeek(v, t){ v._progT = Date.now(); try{ v.currentTime = Math.max(0, t); }catch(_){} }   // programmatic positioning: record the timestamp; distinguish user drags from seeking via a time window (one seek may fire seeking multiple times)

function pbBest(key, sec){            // the segment of this cell closest to sec (seconds of the day)
  const arr = pbSegs[key] || [];
  for(let i=0;i<arr.length;i++) if(sec>=arr[i].s0 && sec<arr[i].s1) return {idx:i, offset:sec-arr[i].s0};
  let best=-1, bd=Infinity, bo=0;
  for(let i=0;i<arr.length;i++){ const s=arr[i]; let d,o;
    if(sec<s.s0){d=s.s0-sec;o=0;} else {d=sec-s.s1;o=Math.max(0,s.s1-s.s0-1);}
    if(d<bd){bd=d;best=i;bo=o;} }
  return best<0 ? null : {idx:best, offset:bo};
}

function pbLoadCell(key, sec, autoplay){
  const v = pbVids[key]; if(!v) return;
  const arr = pbSegs[key] || [];
  const b = pbBest(key, sec);
  if(!b){ v.removeAttribute('src'); v.load(); v._seg=null; v._idx=-1; showCellMsg(v.parentElement, 'No recording'); return; }   // this cell has no recordings for the day
  showCellMsg(v.parentElement, '');
  v._idx = b.idx; v._seg = arr[b.idx];
  v.src = '/video?cam=' + encodeURIComponent(v._id) + '&file=' + encodeURIComponent(arr[b.idx].file);
  const onMeta = () => { v.removeEventListener('loadedmetadata', onMeta);
    pbSeek(v, b.offset);
    if(autoplay) v.play().catch(()=>{}); };
  v.addEventListener('loadedmetadata', onMeta);
  v.load();
}

function gridSeekAll(sec, play){
  const cams = pbCams();
  cams.forEach(c => { const v = pbVids[c.key]; if(v) v._manual = false; });   // a whole-screen jump = clear the per-cell independent flag, resync everything
  if(!play){ cams.forEach(c => pbLoadCell(c.key, sec, false)); updateHead(); return; }
  // Synchronized start: each stream positions itself but does not play yet, waits until all are buffered (or a 2s fallback) before playing together, to avoid the fast ones running ahead while the slow ones arrive later
  let pending = 0, started = false;
  const startAll = () => { if(started) return; started = true;
    cams.forEach(c => { const v = pbVids[c.key]; if(v && v._seg) v.play().catch(()=>{}); }); updateHead(); };
  cams.forEach(c => {
    const v = pbVids[c.key]; if(!v) return;
    const arr = pbSegs[c.key] || [];
    const b = pbBest(c.key, sec);
    if(!b){ v.removeAttribute('src'); v.load(); v._seg = null; v._idx = -1; showCellMsg(v.parentElement, 'No recording'); return; }   // this cell has no recording at this moment
    showCellMsg(v.parentElement, '');
    v._idx = b.idx; v._seg = arr[b.idx];
    pending++;
    const onReady = () => { v.removeEventListener('canplay', onReady); if(--pending <= 0) startAll(); };
    v.addEventListener('canplay', onReady);
    v.src = '/video?cam=' + encodeURIComponent(v._id) + '&file=' + encodeURIComponent(arr[b.idx].file);
    const onMeta = () => { v.removeEventListener('loadedmetadata', onMeta); pbSeek(v, b.offset); };
    v.addEventListener('loadedmetadata', onMeta);
    v.load();
  });
  if(pending === 0) updateHead();      // no playable cell at all
  else setTimeout(startAll, 2000);     // fallback: even if some stream's canplay does not fire, the whole screen does not get stuck
}
function pbPlaying(){ const v = pbVids[pbMaster]; return v ? !v.paused : false; }
function pbToggle(){ const playing = pbPlaying();
  pbCams().forEach(c => { const v = pbVids[c.key]; if(!v) return; playing ? v.pause() : v.play().catch(()=>{}); });
  $('playBtn').textContent = playing ? '▶︎ Play' : '⏸ Pause';
}
function pbAlignAll(){      // ⇄ Sync: pause all and freeze the moment → align each stream to the reference → stay paused (user manually presses «Play all»)
  const m = pbVids[pbMaster]; if(!m || !m._seg) return;
  const T = m._seg.s0 + m.currentTime;                 // freeze the reference moment at this instant
  const cams = pbCams();
  cams.forEach(c => { const v = pbVids[c.key]; if(v) v.pause(); });   // pause all (including the reference), time no longer advances
  cams.forEach(c => {                                  // align each stream to T (the reference is just a reference, its position not moved; stays paused throughout)
    if(c.key === pbMaster) return;
    const v = pbVids[c.key]; if(!v) return;
    v._manual = false;
    const arr = pbSegs[c.key] || [];
    const b = pbBest(c.key, T); if(!b) return;
    if(b.idx === v._idx && v.readyState >= 1){
      try{ v.currentTime = Math.max(0, b.offset); }catch(_){}        // same segment already loaded: cheap seek
    } else {
      v._idx = b.idx; v._seg = arr[b.idx];                          // cross-segment/not loaded: reload into place (no play)
      v.src = '/video?cam=' + encodeURIComponent(v._id) + '&file=' + encodeURIComponent(arr[b.idx].file);
      const om = () => { v.removeEventListener('loadedmetadata', om); try{ v.currentTime = Math.max(0, b.offset); }catch(_){} };
      v.addEventListener('loadedmetadata', om); v.load();
    }
  });
  $('playBtn').textContent = '▶︎ Play';                // stay paused after syncing
  updateHead();
}
function pbTeardown(){ pbStopSync(); pbGrid=false; document.body.classList.remove('pbgrid-mode'); $('grid').innerHTML=''; pbVids={}; updateModeBar(); }

// Periodic resync (simple version): every 2 seconds, nudge cells that have drifted more than 1.5s from the master reference back. Same segment fine-tunes currentTime; cross-segment repositions.
function pbStopSync(){ if(pbSyncTimer){ clearInterval(pbSyncTimer); pbSyncTimer = null; } }
function pbStartSync(){
  pbStopSync();
  pbSyncTimer = setInterval(() => {
    const m = pbVids[pbMaster];
    if(!m || !m._seg || m.paused) return;          // do not resync if the master camera is not playing
    const mw = m._seg.s0 + m.currentTime;
    pbCams().forEach(c => {
      if(c.key === pbMaster) return;
      const v = pbVids[c.key]; if(!v || v.paused || !v._seg || v._manual) return;   // do not force-resync cells the user has manually dragged
      if(Math.abs((v._seg.s0 + v.currentTime) - mw) < 1.5) return;   // do not touch if within the threshold
      const arr = pbSegs[c.key] || [];
      const b = pbBest(c.key, mw); if(!b) return;
      if(b.idx === v._idx){ pbSeek(v, b.offset); }   // same segment: fine-tune
      else {                                                                            // cross-segment: reposition
        v._idx = b.idx; v._seg = arr[b.idx];
        v.src = '/video?cam=' + encodeURIComponent(v._id) + '&file=' + encodeURIComponent(arr[b.idx].file);
        const om = () => { v.removeEventListener('loadedmetadata', om); pbSeek(v, b.offset); v.play().catch(()=>{}); };
        v.addEventListener('loadedmetadata', om); v.load();
      }
    });
  }, 2000);
}

function pbMarkMaster(){      // highlight the reference cell, append " · Ref" to its badge
  pbCams().forEach(c => {
    const v = pbVids[c.key]; if(!v || !v.parentElement) return;
    const isM = (c.key === pbMaster);
    v.parentElement.classList.toggle('master', isM);
    const badge = v.parentElement.querySelector('.pbname');
    if(badge) badge.textContent = dispCam(c.label) + (isM ? ' · Ref' : '');
  });
}
function pbReassign(idx, newLabel){   // change a cell's camera (playback): re-pull that cell's segments for the day and position to the current master moment, other cells untouched
  cellCams[idx] = newLabel;
  const key = String(idx), v = pbVids[key]; if(!v) return;
  v._id = pbCamId(newLabel); v._lbl = newLabel; v._manual = false;
  const badge = v.parentElement && v.parentElement.querySelector('.pbname');
  if(badge) badge.textContent = dispCam(newLabel) + (key === pbMaster ? ' · Ref' : '');
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
    const w = currentWall();          // the current moment before entering
    if(liveMode) setLive(false);
    if(gridMode) setGrid(false);
    pbGrid = true;
    document.body.classList.add('pbgrid-mode');
    updateModeBar();
    document.title = 'Xiaomi Recordings · Playback Split';
    vid.pause();
    const g = $('grid'); killStreams(g); g.innerHTML = ''; pbVids = {};
    g.dataset.n = splitN;             // grid layout (2/4/6)
    const cams = pbCams();
    // Reference = the cell showing the same camera as the current single stream, otherwise the first cell with an id, otherwise the first cell
    pbMaster = ((cams.find(c => c.id && c.id === cam) || cams.find(c => c.id) || cams[0] || {}).key) || null;
    cams.forEach(c => {
      const cell = document.createElement('div'); cell.className = 'pbcell';
      const v = document.createElement('video'); v.muted = true; v.playsInline = true; v.preload = 'metadata'; v.controls = true;  // native controls: play/progress/volume/fullscreen
      v._id = c.id; v._lbl = c.label;
      const b = document.createElement('span'); b.className = 'cellbadge pbname'; b.textContent = dispCam(c.label);
      cell.appendChild(v); cell.appendChild(b); g.appendChild(cell);
      addZoom(cell);   // zoom key (in-page zoom, not system fullscreen)
      addCellCam(cell, +c.key, pbReassign);   // camera dropdown per cell (playback)
      // User drags the native progress bar → this cell becomes "independent", periodic resync skips it; press "Play all" or drag the master timeline to restore sync
      v.addEventListener('seeking', () => { if(Date.now() - (v._progT || 0) > 1500) v._manual = true; });   // only a seek >1.5s after the last programmatic positioning counts as a user manual drag
      pbVids[c.key] = v;
      v.addEventListener('timeupdate', updateHead);          // the reference cell drives the playhead (decided inside updateHead)
      v.addEventListener('ended', () => {                    // continue to this cell's next segment
        const arr = pbSegs[c.key] || []; const ni = (v._idx|0) + 1;
        if(ni < arr.length){ v._idx = ni; v._seg = arr[ni];
          v.src = '/video?cam=' + encodeURIComponent(v._id) + '&file=' + encodeURIComponent(arr[ni].file);
          const om = () => { v.removeEventListener('loadedmetadata', om); v.play().catch(()=>{}); };
          v.addEventListener('loadedmetadata', om); v.load(); }
      });
    });
    pbMarkMaster();                   // mark the reference camera (highlighted border)
    await pbFetchDay(dateStr);
    segs = pbSegs[pbMaster] || [];    // the timeline shows the master camera's coverage
    curIdx = -1; renderTrack();
    $('empty').style.display = segs.length ? 'none' : '';
    gridSeekAll((w && w.sec != null && isFinite(w.sec)) ? w.sec : 0, !!(w && w.play));
    pbStartSync();                    // start periodic resync
  } else {
    const w = currentWall();          // pbGrid is still true → take the master camera's current moment
    pbTeardown();
    document.title = 'Xiaomi Recordings · Timeline Playback';
    selectDay(dateStr, (w && w.sec != null) ? w.sec : null, !!(w && w.play));   // back to the single view at the same moment
  }
}
// Playback split: Play all (realign to the current moment then play together) / Pause all
$('pbPlayAll').onclick  = () => { pbCams().forEach(c => { const v = pbVids[c.key]; if(v && v._seg) v.play().catch(()=>{}); }); $('playBtn').textContent = '⏸ Pause'; };   // purely resume playback, no reload (use «⇄ Sync» to align)
$('pbPauseAll').onclick = () => { pbCams().forEach(c => { const v = pbVids[c.key]; if(v) v.pause(); }); $('playBtn').textContent = '▶︎ Play'; };
$('pbSyncBtn').onclick = pbAlignAll;

// Quality dropdown: fill options + rebuild the current live on change (applies to both single view and split)
QUALS.forEach((q, i) => { const o = document.createElement('option'); o.value = i; o.textContent = q.label; $('qualSel').appendChild(o); });
$('qualSel').onchange = e => { qualIdx = +e.target.value; if(gridMode) setGrid(true); else if(liveMode) setLive(true); };
$('playBtn').onclick = () => { if(pbGrid){ pbToggle(); return; } if(vid.paused) vid.play().catch(()=>{}); else vid.pause(); };
vid.addEventListener('play',  () => $('playBtn').textContent = '⏸ Pause');
vid.addEventListener('pause', () => $('playBtn').textContent = '▶︎ Play');
$('back10').onclick = () => { if(pbGrid){ const w = currentWall(); gridSeekAll(Math.max(0,(w.sec||0)-10), pbPlaying()); return; } vid.currentTime = Math.max(0, vid.currentTime - 10); };
$('fwd10').onclick  = () => { if(pbGrid){ const w = currentWall(); gridSeekAll((w.sec||0)+10, pbPlaying()); return; } vid.currentTime = vid.currentTime + 10; };
$('rateSel').onchange = e => { const r = parseFloat(e.target.value); vid.playbackRate = r; pbCams().forEach(c => { const v = pbVids[c.key]; if(v) v.playbackRate = r; }); };
$('latestBtn').onclick = async () => {
  await reloadCameras();                          // rescan: surface a possibly new latest day (e.g. crossing midnight to 6/9)
  await loadTimeline({ sec: 'latest', play: true });   // locate to the latest moment of the latest day (applies to both single-stream playback and split playback)
};
// ---- Prev / Next (jump to the start of the adjacent recording segment) ----
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
