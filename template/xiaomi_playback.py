#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
xiaomi_playback.py  --  小米摄像头 SMB 录像的轻量时间轴回放服务

小米把每个摄像头的录像平铺在一个文件夹里，文件夹名形如
    XiaomiCamera_00_B88880974A38/
文件名形如
    00_20260603160305_20260603160947.mp4
即  <通道>_<起始 YYYYMMDDHHMMSS>_<结束 YYYYMMDDHHMMSS>.mp4

本服务只读“文件名”来重建每天的时间轴（绝不打开视频文件去解析），然后按需用
HTTP Range 单段流式传输，所以：
  * 几千个文件解析一遍不到一秒；
  * 播放时只流当前那一个 ~128MB 片段，磁盘上总共多少 GB 与浏览器/内存无关；
  * 拖动进度条 / 点时间轴可以正常 seek。

支持多个根目录（多块盘 / 多个摄像头）。每块盘上若有一个或多个
XiaomiCamera_* 子目录，会全部聚合到同一个下拉框里。

用法：
    python3 xiaomi_playback.py [ROOT ...] [PORT]

    ROOT  包含 XiaomiCamera_* 这些文件夹的“上级目录”，可给多个
          （也可以直接指向单个摄像头文件夹）。
          不给时默认 /Volumes/c700_01 /Volumes/c700_02 （macOS CIFS 挂载点）。
    PORT  末尾若是纯数字则当端口用，默认 8800。

例：
    python3 xiaomi_playback.py /Volumes/c700_01 /Volumes/c700_02 8800
    python3 xiaomi_playback.py /mnt/sda1 /mnt/sda2

然后浏览器打开  http://<本机IP>:8800/   （或 http://127.0.0.1:8800/）
"""

import os
import re
import sys
import time
import datetime
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import json

# --------------------------------------------------------------------------- #
# 配置 / 常量
# --------------------------------------------------------------------------- #
DEFAULT_ROOTS = [
    "/Volumes/c700_01",   # wrt32x    /mnt/sda1  XiaomiCamera_00_B88880974A38
    "/Volumes/c700_02",   # wrt32x    /mnt/sda2  XiaomiCamera_00_B88880A0FD7C
    "/Volumes/c700_03",   # wrt1200ac /mnt/sdb1  XiaomiCamera_00_B88880976D02
    "/Volumes/c700_04",   # wrt1200ac /mnt/sdb2  XiaomiCamera_00_B88880976D36
    "/Volumes/c700_05",   # wrt32x  spare disk, empty for now — future 5th camera
]
DEFAULT_PORT = 8800

# 文件名识别：00_<14位起>_<14位止>.mp4
FN_RE = re.compile(r"(\d{14})_(\d{14})\.mp4$", re.IGNORECASE)
# 摄像头文件夹识别（小米默认前缀）
CAM_RE = re.compile(r"xiaomicamera", re.IGNORECASE)

# 摄像头显示名：默认用“分享名”（挂载点名，如 c700_01）。若想要更直观的名字，
# 在这里按 MAC 填上即可覆盖（留空 "" 表示用分享名）。键用 12 位 MAC。
CAM_NAMES = {
    "B88880974A38": "",   # c700_01 · wrt32x    · sda1
    "B88880A0FD7C": "",   # c700_02 · wrt32x    · sda2
    "B88880976D02": "",   # c700_03 · wrt1200ac · sdb1
    "B88880976D36": "",   # c700_04 · wrt1200ac · sdb2
}


def _cam_label(folder, share):
    """下拉框显示名：CAM_NAMES 里手填的友好名优先；否则用分享名 share（如 c700_01）。
    folder 形如 XiaomiCamera_00_<MAC>。"""
    m = re.search(r"([0-9A-Fa-f]{12})$", folder or "")
    if m:
        name = CAM_NAMES.get(m.group(1).upper())
        if name:
            return name
    return share

CACHE_TTL = 15.0  # 秒：扫描结果缓存时长，过后自动重扫以发现新文件

ROOTS = list(DEFAULT_ROOTS)
PORT = DEFAULT_PORT

_seg_cache = {}            # cam_id -> (scan_time, segments)
_seg_lock = threading.Lock()
_reg_cache = {"t": 0.0, "reg": {}}   # 摄像头注册表缓存
_reg_lock = threading.Lock()


# --------------------------------------------------------------------------- #
# 摄像头注册表：把 (root, 文件夹) 映射成安全的 cam_id，杜绝路径穿越
# --------------------------------------------------------------------------- #
def _build_registry():
    """返回 OrderedDict: cam_id -> {"id","label","dir"}。
    每个根目录下的 XiaomiCamera_* 子目录各算一个摄像头；若根目录下没有这种子目录
    （直接装着录像片段，或还是空的备用盘），就把根目录本身当作一个摄像头——所以
    空盘 c700_05 也会以分享名出现在下拉框里（暂时没录像），等将来有摄像头往里写
    时会自动接上（届时 cid 从 "i:." 变成 "i:XiaomiCamera_..."，标签仍是分享名）。"""
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
                if multi and lbl == share:        # 同一盘多个摄像头时用 MAC 尾段区分
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
    """返回 [{id,label}]，跨所有根目录。"""
    return [{"id": c["id"], "label": c["label"]} for c in registry().values()]


def cam_dir(cam_id):
    """把 cam_id 解析成磁盘目录；只走注册表，不拼接不可信输入 → 无路径穿越。"""
    c = registry().get(cam_id)
    if c and os.path.isdir(c["dir"]):
        return c["dir"]
    return None


# --------------------------------------------------------------------------- #
# 索引：只读文件名
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
    """扫描某摄像头目录下所有可识别片段（带短缓存）。"""
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
                    live = e <= s  # 起止相等/倒置 = 正在录制的那一段
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
    """有录像的日期列表（含每日片段数粗略统计），按日期升序。"""
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
    """与某一天（00:00~24:00 本地时间）有重叠的所有片段，已排序。"""
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
        pass  # 安静

    # -- 小工具 -----------------------------------------------------------
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

    # -- 路由 -------------------------------------------------------------
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

    # -- 视频流（支持 Range，用于 seek）----------------------------------
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
                if gs == "" and ge != "":          # 末尾 N 字节
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
# 前端（控制室风格单页）
# --------------------------------------------------------------------------- #
HTML_PAGE = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>小米录像回放</title>
<style>
  :root{
    --bg:#0a0c0f; --panel:#12161b; --panel2:#0e1216; --line:#1e252d;
    --text:#c9d3da; --dim:#6b7785; --accent:#ffb02e; --accent2:#ff5a3c;
    --cover:#2f7d5b; --cover2:#3ba277; --grid:#161c22;
    --mono:ui-monospace,"SF Mono","JetBrains Mono",Menlo,Consolas,monospace;
    --ui:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",sans-serif;
  }
  *{box-sizing:border-box}
  html,body{margin:0;height:100%}
  body{background:var(--bg);color:var(--text);font-family:var(--ui);
       display:flex;flex-direction:column;min-height:100vh}
  header{display:flex;align-items:center;gap:14px;padding:10px 16px;
         background:linear-gradient(#12161b,#0e1216);border-bottom:1px solid var(--line)}
  header .dot{width:9px;height:9px;border-radius:50%;background:var(--accent2);
              box-shadow:0 0 10px var(--accent2)}
  header h1{font-size:14px;letter-spacing:.18em;text-transform:uppercase;
            font-weight:600;margin:0;color:#e7edf2}
  header .spacer{flex:1}
  select,button{font-family:var(--ui);font-size:13px;color:var(--text);
    background:#171c22;border:1px solid var(--line);border-radius:6px;
    padding:7px 10px;cursor:pointer}
  select:hover,button:hover{border-color:#33414d}
  button.ghost{background:transparent}
  .accent{color:var(--accent)}
  main{flex:1;display:flex;flex-direction:column;gap:14px;padding:16px;
       max-width:1180px;width:100%;margin:0 auto}
  .stage{position:relative;background:#000;border:1px solid var(--line);
         border-radius:10px;overflow:hidden;aspect-ratio:16/9}
  video{width:100%;height:100%;display:block;background:#000}
  .liveTag{position:absolute;top:10px;right:12px;font-family:var(--mono);
    font-size:11px;color:#0a0c0f;background:var(--accent2);padding:3px 8px;
    border-radius:5px;font-weight:700;display:none}
  .transport{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
  .transport .grow{flex:1}
  .pill{font-family:var(--mono);font-size:12px;color:var(--dim)}
  /* 日期条 */
  .dates{display:flex;gap:8px;overflow-x:auto;padding-bottom:4px}
  .dates::-webkit-scrollbar{height:6px}
  .dates::-webkit-scrollbar-thumb{background:#222b33;border-radius:3px}
  .day{flex:0 0 auto;font-family:var(--mono);font-size:12px;color:var(--dim);
    background:var(--panel2);border:1px solid var(--line);border-radius:7px;
    padding:7px 11px;cursor:pointer;text-align:center;line-height:1.3}
  .day small{display:block;color:#475561;font-size:10px}
  .day:hover{border-color:#34424e;color:var(--text)}
  .day.on{color:#0a0c0f;background:var(--accent);border-color:var(--accent)}
  .day.on small{color:#7a5410}
  /* 时间轴 */
  .tlwrap{background:var(--panel);border:1px solid var(--line);border-radius:10px;
          padding:14px 16px 10px}
  .tlhead{display:flex;justify-content:space-between;font-family:var(--mono);
          font-size:11px;color:var(--dim);margin-bottom:8px}
  .track{position:relative;height:46px;border-radius:6px;cursor:crosshair;
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
    font-size:10px;color:#3f4b56;margin-top:5px;padding:0 1px}
  .empty{font-family:var(--mono);font-size:12px;color:var(--dim);
    text-align:center;padding:14px 0}
  .hint{font-family:var(--mono);font-size:11px;color:#475561}
  kbd{font-family:var(--mono);background:#171c22;border:1px solid var(--line);
    border-bottom-width:2px;border-radius:4px;padding:1px 5px;font-size:10px;color:var(--dim)}
</style>
</head>
<body>
<header>
  <span class="dot"></span>
  <h1>小米录像 · 时间轴回放</h1>
  <span class="spacer"></span>
  <span class="pill" id="meta"></span>
  <select id="camSel" title="摄像头"></select>
  <button class="ghost" id="refreshBtn" title="重新扫描文件名">↻ 刷新</button>
</header>

<main>
  <div class="stage">
    <video id="vid" preload="metadata" playsinline controls></video>
    <div class="liveTag" id="liveTag">● LIVE</div>
  </div>

  <div class="transport">
    <button id="playBtn">▶︎ 播放</button>
    <button id="back10">⟲ 10s</button>
    <button id="fwd10">10s ⟳</button>
    <span class="grow"></span>
    <span class="pill">倍速</span>
    <select id="rateSel">
      <option value="0.5">0.5×</option>
      <option value="1" selected>1×</option>
      <option value="2">2×</option>
      <option value="4">4×</option>
      <option value="8">8×</option>
      <option value="16">16×</option>
    </select>
    <button id="latestBtn">跳到最新</button>
  </div>

  <div class="dates" id="dates"></div>

  <div class="tlwrap">
    <div class="tlhead">
      <span class="tlnav">
        <button id="prevSeg" title="上一段录像">⏮ 上一段</button>
        <span id="tlDate">—</span>
        <button id="nextSeg" title="下一段录像">下一段 ⏭</button>
      </span>
      <span class="hint">点轨道跳转 · <kbd>空格</kbd>播放 · <kbd>←</kbd><kbd>→</kbd>±10s · <kbd>,</kbd><kbd>.</kbd>上/下一段</span>
    </div>
    <div class="track" id="track">
      <div class="playhead" id="playhead"></div>
      <div class="tip" id="tip"></div>
    </div>
    <div class="ticks" id="ticks"></div>
    <div class="empty" id="empty" style="display:none">这一天没有录像</div>
  </div>
</main>

<script>
const DAY = 86400; // 秒
const $ = id => document.getElementById(id);
const vid = $('vid');

let cam = null;
let dateStr = null;
let segs = [];          // 当天片段 [{file,start(Date),end(Date),live, s0(相对当天秒), s1}]
let curIdx = -1;
let dayStart = null;    // 当天 00:00 的 Date
let firstLoad = true;   // 仅首次加载自动跳到最新；之后切日期/摄像头都保持当前位置

const pad = n => String(n).padStart(2, '0');
function hms(sec){
  sec = Math.max(0, Math.floor(sec));
  return pad(Math.floor(sec/3600)) + ':' + pad(Math.floor(sec/60)%60) + ':' + pad(sec%60);
}

async function api(p){ const r = await fetch(p); return r.json(); }

// ---- 初始化摄像头 ----
// ---- 拉取/刷新摄像头列表（尽量保留当前选择；新接入的摄像头会自动出现）----
async function reloadCameras(){
  const cams = await api('/api/cameras');
  const sel = $('camSel'); const prev = cam;
  sel.innerHTML = '';
  cams.forEach(c => {
    const o = document.createElement('option');
    o.value = c.id; o.textContent = c.label;
    sel.appendChild(o);
  });
  if(cams.length){
    cam = cams.some(c => c.id === prev) ? prev : cams[0].id;
    sel.value = cam;
  }
  return cams.length;
}

async function init(){
  const n = await reloadCameras();
  if(!n){
    $('empty').style.display = '';
    $('empty').textContent = '在根目录下没找到 XiaomiCamera_* 目录（检查挂载点 / 启动参数）';
    return;
  }
  await loadTimeline();
}

// ---- 加载某摄像头的可用日期 ----
async function loadTimeline(want){
  const t = await api('/api/timeline?cam=' + encodeURIComponent(cam));
  const days = t.days || [];
  const keys = days.map(d => d.date);
  const box = $('dates'); box.innerHTML = '';
  $('meta').textContent = days.length ? (days.length + ' 天有录像') : '无录像';
  days.forEach(d => {
    const el = document.createElement('div');
    el.className = 'day'; el.dataset.date = d.date;
    el.innerHTML = d.date.slice(5) + '<small>' + d.count + ' 段</small>';
    // 切日期时保持当前时间轴位置（同一时刻，就近跳转）
    el.onclick = () => { const w = currentWall(); selectDay(d.date, w.sec, w.play); };
    box.appendChild(el);
  });
  if(days.length){
    let target, sec, play;
    if(want && want.date && keys.includes(want.date)){
      target = want.date; sec = want.sec; play = !!want.play;     // 切摄像头/刷新：保持同一天同一时刻
    } else {
      target = days[days.length - 1].date;                       // 默认最新一天
      if(firstLoad){ sec = 'latest'; play = true; }              // 首次加载：定位到最新时刻
      else { sec = want ? want.sec : null; play = !!(want && want.play); }
    }
    firstLoad = false;
    selectDay(target, sec, play);
    $('empty').style.display = 'none';
  } else {
    segs = []; renderTrack(); $('empty').style.display = '';
    $('empty').textContent = '这一天没有录像';
  }
}

// ---- 选某一天 ----
async function selectDay(d, targetSec, play){
  dateStr = d;
  dayStart = new Date(d + 'T00:00:00');
  document.querySelectorAll('.day').forEach(e => {
    const on = e.dataset.date === d;
    e.classList.toggle('on', on);
    if(on) e.scrollIntoView({inline:'center', block:'nearest'});
  });
  $('tlDate').textContent = d;
  const r = await api('/api/segments?cam=' + encodeURIComponent(cam) + '&date=' + d);
  segs = (r.segments || []).map(s => {
    const st = new Date(s.start), en = new Date(s.end);
    return { file:s.file, live:s.live, start:st, end:en,
             s0:(st - dayStart)/1000, s1:(en - dayStart)/1000 };
  });
  curIdx = -1;
  renderTrack();
  $('empty').style.display = segs.length ? 'none' : '';
  if(segs.length){
    if(targetSec === 'latest'){              // 首次加载：定位到最新片段末尾
      const i = segs.length - 1;
      loadSegment(i, Math.max(0, segs[i].s1 - segs[i].s0 - 2), !!play);
    } else if(targetSec != null && isFinite(targetSec)){
      const b = bestSegForSec(targetSec);    // 对齐到最接近目标时刻处
      loadSegment(b.idx, b.offset, !!play);
    } else {
      loadSegment(0, 0, false);
    }
  }
}

// ---- 画时间轴 ----
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

// ---- 找覆盖某“当天秒数”的片段 ----
function segIndexAt(sec){
  for(let i=0; i<segs.length; i++){ if(sec >= segs[i].s0 && sec < segs[i].s1) return i; }
  return -1;
}
function nextSegAfter(sec){
  for(let i=0; i<segs.length; i++){ if(segs[i].s0 >= sec) return i; }
  return -1;
}
// 找最接近某“当天秒数”的片段（跨摄像头对齐到同一时刻用）
function bestSegForSec(sec){
  const cover = segIndexAt(sec);
  if(cover >= 0) return { idx: cover, offset: sec - segs[cover].s0 };
  let best = 0, bestDist = Infinity, bestOff = 0;
  for(let i=0; i<segs.length; i++){
    const s = segs[i];
    let dist, off;
    if(sec < s.s0){ dist = s.s0 - sec; off = 0; }                    // 在该段之前 → 段首
    else { dist = sec - s.s1; off = Math.max(0, s.s1 - s.s0 - 1); }  // 在该段之后 → 段尾
    if(dist < bestDist){ bestDist = dist; best = i; bestOff = off; }
  }
  return { idx: best, offset: bestOff };
}

// ---- 载入并定位某片段 ----
function loadSegment(idx, offsetSec, autoplay){
  if(idx < 0 || idx >= segs.length) return;
  curIdx = idx; const s = segs[idx];
  $('liveTag').style.display = s.live ? 'block' : 'none';
  vid.src = '/video?cam=' + encodeURIComponent(cam) + '&file=' + encodeURIComponent(s.file);
  const onMeta = () => {
    vid.removeEventListener('loadedmetadata', onMeta);
    try{ vid.currentTime = Math.max(0, offsetSec); }catch(e){}
    if(autoplay){ vid.play().catch(()=>{}); }
    updateHead();
  };
  vid.addEventListener('loadedmetadata', onMeta);
  vid.load();
}

// ---- 轨道：拖动/点击；播放头跟随光标，并显示该位置的精确时间气泡 ----
let dragging = false;
const track = $('track');

function moveHead(sec){            // sec = 相对当天 00:00 的秒
  const ph = $('playhead');
  ph.style.display = 'block';
  ph.style.left = (Math.min(DAY, Math.max(0, sec))/DAY*100) + '%';
}
function trackSec(e){
  const rect = track.getBoundingClientRect();
  const frac = Math.min(1, Math.max(0, (e.clientX - rect.left)/rect.width));
  return frac * DAY;
}
function showTip(e){              // 跟随光标的时间气泡；固定定位，避免被轨道 overflow:hidden 裁掉
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
  let i = segIndexAt(sec);
  if(i >= 0){ loadSegment(i, sec - segs[i].s0, true); }
  else { const n = nextSegAfter(sec); if(n >= 0) loadSegment(n, 0, true); }
}

track.addEventListener('pointerdown', e => {
  if(!segs.length || !dayStart) return;
  dragging = true;
  try{ track.setPointerCapture(e.pointerId); }catch(_){}
  const sec = trackSec(e); moveHead(sec); showTip(e);     // 立刻挪线 + 显示时间
});
track.addEventListener('pointermove', e => {
  if(!segs.length) return;
  const sec = trackSec(e);
  if(dragging) moveHead(sec);      // 拖动时线跟着光标走
  showTip(e);                      // 悬停也显示该处时间
});
track.addEventListener('pointerleave', () => { if(!dragging) hideTip(); });
function endDrag(e){
  if(!dragging) return;
  dragging = false;
  try{ track.releasePointerCapture(e.pointerId); }catch(_){}
  hideTip();
  seekTo(trackSec(e));             // 松手才真正跳转/加载
}
track.addEventListener('pointerup', endDrag);
track.addEventListener('pointercancel', () => { dragging = false; hideTip(); });

// ---- 播放时让播放头跟进度走（拖动中不抢）----
function updateHead(){
  if(dragging || curIdx < 0) return;
  const s = segs[curIdx];
  moveHead(s.s0 + vid.currentTime);
}
vid.addEventListener('timeupdate', updateHead);

// ---- 一段播完自动接下一段（连续回放）----
vid.addEventListener('ended', () => {
  if(curIdx >= 0 && curIdx + 1 < segs.length){
    loadSegment(curIdx + 1, 0, true);
  }
});

// ---- 控件 ----
// 当前播放位置（日期 + 当天秒数 + 是否在播），用于跨摄像头对齐到同一时刻
function currentWall(){
  return {
    date: dateStr,
    sec: (curIdx >= 0) ? (segs[curIdx].s0 + vid.currentTime) : null,
    play: !vid.paused,
  };
}
$('camSel').onchange = e => { const w = currentWall(); cam = e.target.value; loadTimeline(w); };
$('refreshBtn').onclick = async () => { const w = currentWall(); await reloadCameras(); loadTimeline(w); };
$('playBtn').onclick = () => { if(vid.paused) vid.play().catch(()=>{}); else vid.pause(); };
vid.addEventListener('play',  () => $('playBtn').textContent = '⏸ 暂停');
vid.addEventListener('pause', () => $('playBtn').textContent = '▶︎ 播放');
$('back10').onclick = () => { vid.currentTime = Math.max(0, vid.currentTime - 10); };
$('fwd10').onclick  = () => { vid.currentTime = vid.currentTime + 10; };
$('rateSel').onchange = e => { vid.playbackRate = parseFloat(e.target.value); };
$('latestBtn').onclick = () => {
  if(segs.length){ const i = segs.length - 1; loadSegment(i, Math.max(0, segs[i].s1 - segs[i].s0 - 2), true); }
};
// ---- 上一段 / 下一段（跳到相邻录像片段的开头）----
function jumpSeg(delta){
  if(!segs.length) return;
  let i = (curIdx < 0) ? 0 : curIdx + delta;
  i = Math.max(0, Math.min(segs.length - 1, i));
  loadSegment(i, 0, true);
}
$('prevSeg').onclick = () => jumpSeg(-1);
$('nextSeg').onclick = () => jumpSeg(1);

document.addEventListener('keydown', e => {
  if(['INPUT','SELECT','TEXTAREA'].includes(document.activeElement.tagName)) return;
  if(e.code === 'Space'){ e.preventDefault(); $('playBtn').click(); }
  else if(e.code === 'ArrowLeft'){ $('back10').click(); }
  else if(e.code === 'ArrowRight'){ $('fwd10').click(); }
  else if(e.key === ','){ $('prevSeg').click(); }   // 上一段
  else if(e.key === '.'){ $('nextSeg').click(); }   // 下一段
});

init();
</script>
</body>
</html>
"""


# --------------------------------------------------------------------------- #
def parse_args(argv):
    """末尾纯数字参数当端口；其余当根目录。"""
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
    print(" 小米录像回放服务")
    print(" 根目录 :", ", ".join(ROOTS))
    if cams:
        print(" 摄像头 :")
        for c in cams:
            print("    -", c["label"])
    else:
        print(" 警告：未发现任何 XiaomiCamera_* 目录，请检查根目录 / 挂载点是否正确。")
    print(" 打开浏览器: http://<本机IP>:%d/   (或 http://127.0.0.1:%d/)" % (PORT, PORT))
    print(" 按 Ctrl+C 停止")
    print("=" * 60)

    httpd = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
        httpd.server_close()


if __name__ == "__main__":
    main()
