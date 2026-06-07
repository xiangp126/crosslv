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
import urllib.request
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

# go2rtc(Frigate 机器):播放器把它的 video-stream 组件 JS 同源代理出去,绕开跨域 ES 模块的 CORS 限制
GO2RTC = "http://192.168.10.240:1984"
_JS_CACHE = {}
_JS_LOCK = threading.Lock()

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
    return re.sub(r"^[cC]700", "C700", share)   # 显示名用大写 C(C700_01);真实挂载路径不受影响

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

    def _jsproxy(self, path):
        # 同源代理 go2rtc 的 video-rtc.js / video-stream.js(带短缓存),供四分屏组件用
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
    --text:#c9d3da; --dim:#97a2ab; --accent:#ffb02e; --accent2:#ff5a3c;
    --cover:#2f7d5b; --cover2:#3ba277; --grid:#161c22;
    --mono:ui-monospace,"SF Mono","JetBrains Mono",Menlo,Consolas,monospace;
    --ui:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",sans-serif;
  }
  *{box-sizing:border-box}
  html,body{margin:0;height:100%}
  body{background:var(--bg);color:var(--text);font-family:var(--ui);
       display:flex;flex-direction:column;min-height:100vh}
  header{display:flex;align-items:center;gap:9px;padding:10px 16px;
         background:linear-gradient(#12161b,#0e1216);border-bottom:1px solid var(--line)}
  header .sep{width:1px;height:22px;background:var(--line);flex:0 0 auto}   /* 分组竖线 */
  /* 视图模式分段开关(连体,当前态琥珀高亮) */
  .modebar{display:inline-flex;border:1px solid var(--line);border-radius:8px;overflow:hidden}
  .modebar button{border:0;border-radius:0;background:#171c22;color:var(--dim);
    padding:7px 14px;border-left:1px solid var(--line);font-size:13px}
  .modebar button:first-child{border-left:0}
  .modebar button:hover:not(.on):not(:disabled){color:var(--text);background:#1d242b}
  .modebar button.on{background:var(--accent);color:#0a0c0f;font-weight:600}
  .modebar button:disabled{opacity:.4;cursor:not-allowed}
  #qualSel{max-width:190px}
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
  #live{position:absolute;inset:0;display:none;background:#000}
  #live video-stream{position:relative;display:block;width:100%;height:100%;background:#000;overflow:hidden}
  #live video-stream video{width:100%;height:100%;object-fit:contain;display:block}
  #live video-stream .info{display:none}   /* 隐藏组件自带 RTC 角标 */
  body.live-mode #vid,
  body.live-mode .transport,
  body.live-mode .liveTag{display:none !important}   /* 方案二:时间轴(.dates/.tlwrap)在直播时也保留 */
  .liveTag{position:absolute;top:10px;right:12px;font-family:var(--mono);
    font-size:11px;color:#0a0c0f;background:var(--accent2);padding:3px 8px;
    border-radius:5px;font-weight:700;display:none}
  .grid{position:absolute;inset:0;display:none;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:2px;background:#000;z-index:4}
  .grid video-stream{position:relative;display:block;width:100%;height:100%;background:#000;overflow:hidden}
  .grid video-stream video{width:100%;height:100%;object-fit:contain;display:block}
  .grid video-stream .info{display:none}   /* 隐藏组件自带的 RTC 角标 */
  video-stream .cellbadge, .pbcell .cellbadge{position:absolute;top:8px;right:48px;z-index:6;pointer-events:none;
    font-family:var(--mono);font-size:11px;color:#fff;background:var(--accent2);
    padding:2px 7px;border-radius:5px;font-weight:700;box-shadow:0 0 8px rgba(255,90,60,.6)}
  body.grid-mode .grid{display:grid}
  body.grid-mode #vid,
  body.grid-mode #live,
  body.grid-mode .liveTag,
  body.grid-mode .transport,
  body.grid-mode .dates,
  body.grid-mode .tlwrap{display:none !important}
  #qualSel{display:none}                                   /* 画质下拉只在直播/直播分屏时显示 */
  body.live-mode #qualSel, body.grid-mode #qualSel{display:inline-block}
  /* 回放分屏:复用 .grid 布局,但保留时间轴/控件;格子是 <video> 包在 .pbcell 里 */
  .grid .pbcell{position:relative;background:#000;overflow:hidden}
  .grid .pbcell video{width:100%;height:100%;object-fit:contain;display:block}
  .pbcell .pbname{background:rgba(10,12,15,.72);color:#fff;box-shadow:none}   /* 相机名角标:中性色,区别于红色实时标 */
  .grid .pbcell.master{outline:2px solid var(--accent);outline-offset:-2px}   /* 基准相机:高亮边框 */
  .pbcell.master .pbname{background:var(--accent);color:#0a0c0f}
  .grid .gzoom{position:absolute;top:50%;right:8px;transform:translateY(-50%);z-index:8;cursor:pointer;user-select:none;color:#fff;
    background:rgba(10,12,15,.66);border:1px solid var(--line);border-radius:7px;padding:5px 9px;font-size:16px;line-height:1}
  .grid .gzoom:hover{background:rgba(10,12,15,.92);border-color:#34424e}
  .grid.zoomed > :not(.zoom){display:none}            /* 放大时隐藏其余格 */
  .grid > .zoom{grid-column:1 / -1;grid-row:1 / -1}    /* 放大格铺满网格区域 */
  body.pbgrid-mode .grid{display:grid}
  body.pbgrid-mode #vid,
  body.pbgrid-mode #live,
  body.pbgrid-mode .liveTag{display:none}
  #pbPlayAll,#pbPauseAll,#pbSyncBtn{display:none}                       /* 全部播放/暂停/同步:仅回放分屏显示 */
  body.pbgrid-mode #playBtn{display:none}                               /* 回放分屏用"全部播放/暂停"取代单路播放键 */
  body.pbgrid-mode #pbPlayAll,body.pbgrid-mode #pbPauseAll,body.pbgrid-mode #pbSyncBtn{display:inline-block}
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
  .day small{display:block;color:#828d97;font-size:10px}
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
  <span class="dot"></span>
  <h1 id="title">小米录像</h1>
  <div class="modebar" id="modebar">
    <button data-mode="play"     title="单路录像回放">回放</button>
    <button data-mode="live"     title="单路实时直播">直播</button>
    <button data-mode="livegrid" title="全部摄像头实时(分屏)">⊞ 直播分屏</button>
    <button data-mode="pbgrid"   title="全部录像同步回放(分屏,共用时间轴)">⊞ 回放分屏</button>
  </div>
  <span class="spacer"></span>
  <select id="camSel" title="摄像头"></select>
  <select id="qualSel" title="直播画质(原画=直发,转码=兼容)"></select>
  <button class="ghost" id="refreshBtn" title="重新扫描录像 / 重连直播">↻ 刷新</button>
</header>

<main>
  <div class="stage">
    <video id="vid" preload="metadata" playsinline controls></video>
    <div id="live"></div>
    <div class="liveTag" id="liveTag">● 录制中</div>
    <div class="grid" id="grid"></div>
  </div>

  <div class="transport">
    <button id="playBtn">▶︎ 播放</button>
    <button id="pbPlayAll" title="四格一起播放(不重载;需要对齐用「⇄ 同步」)">▶︎ 全部播放</button>
    <button id="pbPauseAll" title="四格同时暂停">⏸ 全部暂停</button>
    <button id="pbSyncBtn" title="把偏离/独立的格对齐回基准(轻量,不重载已同步的格)">⇄ 同步</button>
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
        <span class="pill" id="meta"></span>
      </span>
      <span class="hint">点轨道跳转 · <kbd>空格</kbd>播放 · <kbd>←</kbd><kbd>→</kbd>±10s · <kbd>,</kbd><kbd>.</kbd>上/下一段 · <kbd>R</kbd>刷新 · <kbd>L</kbd>实时/回放</span>
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

// 实时画面（go2rtc / Frigate 机器）。
// 若浏览器原生支持 HEVC(MSE)——Safari、macOS 上的 Chrome——就直接放相机的 H265 子流(_sub)：
// go2rtc 只封装不转码 → 原画质、.240 几乎零负担。否则(如 Firefox 不支持 HEVC)退回 go2rtc
// 转码出的 H264(_1080p) + WebRTC。
const GO2RTC = 'http://192.168.10.240:1984';
// WebRTC 收 H265:桌面 Chrome136+/Safari 支持;Firefox/Edge默认/老 Safari 不支持 → 只给转码档。
function webrtcCanH265(){
  try{ return ((RTCRtpReceiver.getCapabilities('video') || {}).codecs || [])
              .some(c => /h265|hevc/i.test(c.mimeType)); }
  catch(_){ return false; }
}
const RTC_H265 = webrtcCanH265();
// 画质档:支持 WebRTC-H265 就给原画 1080P 直发;转码1080P 始终兜底。原画=直发免转码,转码=go2rtc 转 H264。
const QUALS = [];
if(RTC_H265) QUALS.push({label:'原画1080P · WebRTC', suffix:'_sub1080', mode:'webrtc'});
QUALS.push({label:'转码1080P · WebRTC', suffix:'_1080p', mode:'webrtc'});
let qualIdx = 0;
function liveSuffix(){ return QUALS[qualIdx].suffix; }
function liveModeNow(){ return QUALS[qualIdx].mode; }
const START_LIVE = true;      // 打开网页默认进单路直播（改 false=默认进最新录像）
let liveMode = false;
let gridMode = false;   // 四分屏(全部摄像头实时)
let pbGrid = false;     // 回放四分屏(全部摄像头录像,共用时间轴)

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
  updateLiveBtn();
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
  if(START_LIVE && liveAvailable()) setLive(true);   // 打开默认进单路直播(改 false=默认进最新录像)
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
    el.onclick = () => { const w = currentWall(); if(liveMode) setLive(false); selectDay(d.date, w.sec, w.play); };
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
  if(pbGrid){                          // 回放四分屏:换天 → 重拉 4 路、整屏跳到目标时刻
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
  if(gridMode) setGrid(false);   // 任何回放操作退出四分屏
  curIdx = idx; const s = segs[idx];
  $('liveTag').style.display = s.live ? 'block' : 'none';
  vid.src = '/video?cam=' + encodeURIComponent(cam) + '&file=' + encodeURIComponent(s.file);
  const onMeta = () => {
    vid.removeEventListener('loadedmetadata', onMeta);
    try{ vid.currentTime = Math.max(0, offsetSec); }catch(e){}
    if(autoplay && !gridMode && !pbGrid){ vid.play().catch(()=>{}); }   // 分屏模式下不让后台单路录像自动播
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
  if(pbGrid){ gridSeekAll(sec, true); return; }   // 回放四分屏:整屏跳到同一时刻
  if(liveMode) setLive(false);   // 点/拖时间轴 → 切到录像
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
  if(dragging) return;
  if(pbGrid){ const v = pbVids[pbMaster]; if(v && v._seg) moveHead(v._seg.s0 + v.currentTime); return; }
  if(curIdx < 0) return;
  const s = segs[curIdx];
  moveHead(s.s0 + vid.currentTime);
}
vid.addEventListener('timeupdate', updateHead);

// ---- 一段播完自动接下一段（连续回放）----
vid.addEventListener('ended', () => {
  if(gridMode || pbGrid) return;   // 分屏模式下,后台单路录像播完不接续(否则会经 loadSegment 退出分屏)
  if(curIdx >= 0 && curIdx + 1 < segs.length){
    loadSegment(curIdx + 1, 0, true);
  }
});

// ---- 控件 ----
// 当前播放位置（日期 + 当天秒数 + 是否在播），用于跨摄像头对齐到同一时刻
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
  if(pbGrid){ if(pbSegs[cam]){ pbMaster = cam; segs = pbSegs[cam]; pbMarkMaster(); renderTrack(); updateHead(); } return; }  // 回放四分屏:换选择=换主时钟相机(高亮+时间轴跟着换)
  loadTimeline(w);                                            // 时间轴始终更新到新摄像头
  if(liveMode){ liveAvailable() ? setLive(true) : setLive(false); }   // 直播跟随切换;新摄像头无直播则退出
};
$('refreshBtn').onclick = async () => {
  if(gridMode){ setGrid(true); return; }   // 四分屏:重建(重载)全部直播
  if(liveMode){ setLive(true); return; }   // 直播:重建组件(重连到实时端)
  if(pbGrid){ const w = currentWall(); await reloadCameras(); await pbFetchDay(dateStr); segs = pbSegs[pbMaster] || []; renderTrack(); gridSeekAll(w.sec != null ? w.sec : 0, w.play); return; }  // 回放四分屏:重扫+整屏回到当前时刻
  const w = currentWall(); await reloadCameras(); loadTimeline(w);   // 回放:重新扫描录像、保持当前位置
};

// ---- 实时画面（go2rtc）：标题栏「● 实时」切换；浏览器直连 go2rtc，不经过 wrt32x ----
function liveLabel(){ const o = $('camSel').selectedOptions[0]; return o ? o.textContent : ''; }
function liveAvailable(){ return /^c700_0[1-4]$/i.test(liveLabel()); }   // 备用盘 c700_05 无直播源
// ===== 视图模式:回放 / 直播 / 直播分屏 / 回放分屏(分段开关统一切换)=====
function currentMode(){ return pbGrid ? 'pbgrid' : gridMode ? 'livegrid' : liveMode ? 'live' : 'play'; }
function updateModeBar(){
  const cur = currentMode();
  document.querySelectorAll('#modebar button').forEach(b => b.classList.toggle('on', b.dataset.mode === cur));
  const liveSeg = document.querySelector('#modebar button[data-mode="live"]');
  if(liveSeg) liveSeg.disabled = !liveAvailable();   // 当前相机无 go2rtc 流 → 禁用"直播"
}
function setMode(m){
  const cur = currentMode();
  if(m === cur) return;
  if(cur === 'pbgrid') setPbGrid(false);        // 先退回"单路回放"基线
  else if(cur === 'livegrid') setGrid(false);
  else if(cur === 'live') setLive(false);
  if(m === 'live') setLive(true);                // 再进入目标模式
  else if(m === 'livegrid') setGrid(true);
  else if(m === 'pbgrid') setPbGrid(true);
  updateModeBar();
}
function updateLiveBtn(){ updateModeBar(); }   // 兼容旧调用点(camSel.onchange / reloadCameras)
function setLive(on){
  if(gridMode) setGrid(false);   // 切单路时退出四分屏
  if(pbGrid) pbTeardown();        // 退出回放四分屏
  clearLiveTimers();
  on = on && liveAvailable();
  liveMode = on;
  document.body.classList.toggle('live-mode', on);
  updateModeBar();
  $('title').textContent = on ? '小米录像 · 实时直播' : '小米录像 · 时间轴回放';
  const box = $('live');
  box.innerHTML = '';               // 清空(也用于停止旧的拉流)
  if(on){
    vid.pause();
    const v = document.createElement('video-stream');
    v.mode = liveModeNow();         // 按画质档:webrtc 或 mse
    v.media = 'video,audio';        // 带音频
    v.background = true;            // 不因不可见而停流
    box.appendChild(v);             // 先入 DOM(组件创建内部 <video>)
    const url = GO2RTC + '/api/ws?src=' + encodeURIComponent(liveLabel() + liveSuffix());
    v.src = url;
    if(v.video){ v.video.controls = true; v.video.muted = true; }   // 原生控件(含全屏);默认静音以便自动播放,想听点开音量
    attachResume(v, url);           // 暂停后再播→重连到实时端(尤其 MSE 档,避免落后)
    attachLiveBadge(v);  // 右上角:● 实时 + 实际协议(RTC/MSE)
    watchStall(v, url);  // 卡死自愈:冻住超阈值自动重连
    box.style.display = 'block';
  } else {
    box.style.display = 'none';     // 移除组件=停止拉流
  }
}
document.querySelectorAll('#modebar button').forEach(b => b.onclick = () => setMode(b.dataset.mode));
// ---- 四分屏:同时看全部摄像头的实时画面 ----
function liveGridLabels(){ return [...$('camSel').options].map(o => o.textContent).filter(l => /^c700_0[1-4]$/i.test(l)); }
// 在直播组件右上角贴 "● 实时 · 协议",协议从组件实际状态读出:
// WebRTC 时 <video> 用 srcObject(MediaStream);MSE 时 src 是 blob:。
// 自建"放大/还原"(直播分屏 + 回放分屏通用):点一下该格铺满网格区域,再点还原。页面内放大,不进系统全屏(绕开 Safari 退出全屏画面上移的 bug)。
function addZoom(cellEl){
  const g = $('grid');
  const z = document.createElement('span'); z.className = 'gzoom'; z.textContent = '⤢'; z.title = '放大 / 还原';
  z.onclick = (e) => {
    e.stopPropagation();
    const on = !cellEl.classList.contains('zoom');
    g.querySelectorAll('.zoom').forEach(x => x.classList.remove('zoom'));
    g.querySelectorAll('.gzoom').forEach(x => x.textContent = '⤢');
    cellEl.classList.toggle('zoom', on); g.classList.toggle('zoomed', on);
    if(on) z.textContent = '⤡';
  };
  cellEl.appendChild(z);
}

function attachLiveBadge(v){
  const b = document.createElement('span'); b.className = 'cellbadge'; b.textContent = '● 实时'; v.appendChild(b);
  const upd = () => {
    const el = v.video; if(!el) return;
    const proto = el.srcObject ? 'RTC' : ((el.src || '').startsWith('blob:') ? 'MSE' : '…');
    b.textContent = '● 实时 · ' + proto;
  };
  if(v.video){ v.video.addEventListener('loadeddata', upd); v.video.addEventListener('playing', upd); }
  setTimeout(upd, 800);   // 兜底:连上后再刷新一次
  return b;
}

function setGrid(on){
  if(pbGrid) pbTeardown();          // 退出回放四分屏
  clearLiveTimers();
  gridMode = on;
  document.body.classList.toggle('grid-mode', on);
  updateModeBar();
  $('title').textContent = on ? '小米录像 · 四分屏直播' : (liveMode ? '小米录像 · 实时直播' : '小米录像 · 时间轴回放');
  const g = $('grid');
  g.innerHTML = '';                 // 先清空(也用于停止旧的拉流)
  if(on){
    vid.pause();
    // 错峰连接:4 路 WebRTC 握手隔 400ms 逐个发起,避免同时建连互相抢占导致有格不刷新
    liveGridLabels().forEach((lbl, i) => {
      setTimeout(() => {
        if(!gridMode) return;      // 期间已退出四分屏就别再连
        const v = document.createElement('video-stream');
        v.mode = liveModeNow();    // 按画质档:webrtc 或 mse
        v.media = 'video,audio';   // 带音频(各格默认静音,想听哪路再点开音量)
        v.background = true;       // 不因不可见而停流
        g.appendChild(v);          // 先入 DOM(组件创建内部 <video>)
        const url = GO2RTC + '/api/ws?src=' + encodeURIComponent(lbl + liveSuffix());  // 按画质档选流
        v.src = url;               // 设 src 触发连接
        if(v.video){ v.video.controls = true; v.video.muted = true; }   // 原生控件(含全屏);默认静音,想听再点开
        attachResume(v, url);      // 暂停后再播→重连到实时端
        attachLiveBadge(v);  // 右上角:● 实时 + 实际协议(RTC/MSE)
        addZoom(v);          // 左/右上角放大键(页面内放大)
        watchStall(v, url);  // 卡死自愈:冻住超阈值自动重连
      }, i * 400);
    });
  }
}
// ===== 直播卡死自愈 =====
// WebRTC/MSE 偶尔会"连着但不再来帧":画面冻住,连接没断所以组件不会自动重连。
// 监视 <video>.currentTime,连续约 6 秒没前进(且不是用户手动暂停)就重连该路。
let liveTimers = [];
function clearLiveTimers(){ liveTimers.forEach(t => clearInterval(t)); liveTimers = []; }
// 每 1s 查一次播放进度;冻结满 3s 就重连;重连后给 4s 宽限(等它建连,别又误判卡)。
// 轮询本身只是读 currentTime,开销可忽略;真正有成本的是"重连",所以阈值不宜太小(否则把能自愈的瞬时小卡也重连,反而更抖)。
function watchStall(v, url){
  let last = -1, frozen = 0, grace = 0;
  liveTimers.push(setInterval(() => {
    const el = v.video;
    if(!el || el.paused){ last = -1; frozen = 0; return; }               // 用户暂停不算卡
    if(grace > 0){ grace--; last = el.currentTime; frozen = 0; return; } // 刚重连,先让它建连
    if(el.currentTime === last){ frozen++; if(frozen >= 3){ frozen = 0; grace = 4; v.src = url; } }  // 冻结 3s→重连
    else { last = el.currentTime; frozen = 0; }
  }, 1000));
}
// 暂停后再播 → 重连到直播实时端(MSE 档暂停会落后;WebRTC 重连也无妨)
function attachResume(v, url){
  if(!v.video) return;
  let wasPaused = false;
  v.video.addEventListener('pause', () => { wasPaused = true; });
  v.video.addEventListener('play',  () => { if(wasPaused){ wasPaused = false; v.src = url; } });
}

// ===== 回放四分屏:4 路录像共用一条时间轴,拖动/播放/倍速联动 =====
let pbSegs = {};      // { camId: [seg...] } 当天各相机片段
let pbVids = {};      // { camId: <video> }
let pbMaster = null;  // 主时钟相机(驱动播放头/时间轴显示)
let pbSyncTimer = null;  // 定期对时定时器

function pbCams(){ return [...$('camSel').options].filter(o => /^c700_0[1-4]$/i.test(o.textContent)).map(o => ({id:o.value, label:o.textContent})); }

async function pbFetchDay(date){      // 并发拉 4 路当天片段
  pbSegs = {};
  await Promise.all(pbCams().map(async c => {
    const r = await api('/api/segments?cam=' + encodeURIComponent(c.id) + '&date=' + date);
    pbSegs[c.id] = (r.segments || []).map(s => { const st = new Date(s.start), en = new Date(s.end);
      return { file:s.file, live:s.live, start:st, end:en, s0:(st-dayStart)/1000, s1:(en-dayStart)/1000 }; });
  }));
}

function pbSeek(v, t){ v._progT = Date.now(); try{ v.currentTime = Math.max(0, t); }catch(_){} }   // 程序化定位:记时间戳;seeking 用时间窗区分用户拖动(一次 seek 可能多次 seeking)

function pbBest(id, sec){            // 该相机最接近 sec(当天秒)的片段
  const arr = pbSegs[id] || [];
  for(let i=0;i<arr.length;i++) if(sec>=arr[i].s0 && sec<arr[i].s1) return {idx:i, offset:sec-arr[i].s0};
  let best=-1, bd=Infinity, bo=0;
  for(let i=0;i<arr.length;i++){ const s=arr[i]; let d,o;
    if(sec<s.s0){d=s.s0-sec;o=0;} else {d=sec-s.s1;o=Math.max(0,s.s1-s.s0-1);}
    if(d<bd){bd=d;best=i;bo=o;} }
  return best<0 ? null : {idx:best, offset:bo};
}

function pbLoadCell(id, sec, autoplay){
  const v = pbVids[id]; if(!v) return;
  const arr = pbSegs[id] || [];
  const b = pbBest(id, sec);
  if(!b){ v.removeAttribute('src'); v.load(); v._seg=null; v._idx=-1; return; }   // 当天该相机无录像→黑屏
  v._idx = b.idx; v._seg = arr[b.idx];
  v.src = '/video?cam=' + encodeURIComponent(id) + '&file=' + encodeURIComponent(arr[b.idx].file);
  const onMeta = () => { v.removeEventListener('loadedmetadata', onMeta);
    pbSeek(v, b.offset);
    if(autoplay) v.play().catch(()=>{}); };
  v.addEventListener('loadedmetadata', onMeta);
  v.load();
}

function gridSeekAll(sec, play){
  const cams = pbCams();
  cams.forEach(c => { const v = pbVids[c.id]; if(v) v._manual = false; });   // 整体跳转=清除单格独立标记,重新同步
  if(!play){ cams.forEach(c => pbLoadCell(c.id, sec, false)); updateHead(); return; }
  // 同步起播:四路各自定位但先不播,等都缓冲好(或 2s 兜底)再一起 play,避免快的先跑、慢的后到
  let pending = 0, started = false;
  const startAll = () => { if(started) return; started = true;
    cams.forEach(c => { const v = pbVids[c.id]; if(v && v._seg) v.play().catch(()=>{}); }); updateHead(); };
  cams.forEach(c => {
    const v = pbVids[c.id]; if(!v) return;
    const arr = pbSegs[c.id] || [];
    const b = pbBest(c.id, sec);
    if(!b){ v.removeAttribute('src'); v.load(); v._seg = null; v._idx = -1; return; }   // 该相机此刻无录像
    v._idx = b.idx; v._seg = arr[b.idx];
    pending++;
    const onReady = () => { v.removeEventListener('canplay', onReady); if(--pending <= 0) startAll(); };
    v.addEventListener('canplay', onReady);
    v.src = '/video?cam=' + encodeURIComponent(c.id) + '&file=' + encodeURIComponent(arr[b.idx].file);
    const onMeta = () => { v.removeEventListener('loadedmetadata', onMeta); pbSeek(v, b.offset); };
    v.addEventListener('loadedmetadata', onMeta);
    v.load();
  });
  if(pending === 0) updateHead();      // 没有任何可播的相机
  else setTimeout(startAll, 2000);     // 兜底:某路 canplay 不触发也不至于整屏卡住
}
function pbPlaying(){ const v = pbVids[pbMaster]; return v ? !v.paused : false; }
function pbToggle(){ const playing = pbPlaying();
  pbCams().forEach(c => { const v = pbVids[c.id]; if(!v) return; playing ? v.pause() : v.play().catch(()=>{}); });
  $('playBtn').textContent = playing ? '▶︎ 播放' : '⏸ 暂停';
}
function pbAlignAll(){      // ⇄ 同步:全部暂停冻结时刻 → 各路对齐到基准 → 保持暂停(由用户手动「全部播放」)
  const m = pbVids[pbMaster]; if(!m || !m._seg) return;
  const T = m._seg.s0 + m.currentTime;                 // 冻结这一刻的基准时刻
  const cams = pbCams();
  cams.forEach(c => { const v = pbVids[c.id]; if(v) v.pause(); });   // 全部暂停(含基准),时间不再走
  cams.forEach(c => {                                  // 各路对齐到 T(基准只参照,不动位置;全程保持暂停)
    if(c.id === pbMaster) return;
    const v = pbVids[c.id]; if(!v) return;
    v._manual = false;
    const arr = pbSegs[c.id] || [];
    const b = pbBest(c.id, T); if(!b) return;
    if(b.idx === v._idx && v.readyState >= 1){
      try{ v.currentTime = Math.max(0, b.offset); }catch(_){}        // 同段已加载:便宜 seek
    } else {
      v._idx = b.idx; v._seg = arr[b.idx];                          // 跨段/未加载:重载到位(不播)
      v.src = '/video?cam=' + encodeURIComponent(c.id) + '&file=' + encodeURIComponent(arr[b.idx].file);
      const om = () => { v.removeEventListener('loadedmetadata', om); try{ v.currentTime = Math.max(0, b.offset); }catch(_){} };
      v.addEventListener('loadedmetadata', om); v.load();
    }
  });
  $('playBtn').textContent = '▶︎ 播放';                // 同步后保持暂停
  updateHead();
}
function pbTeardown(){ pbStopSync(); pbGrid=false; document.body.classList.remove('pbgrid-mode'); $('grid').innerHTML=''; pbVids={}; updateModeBar(); }

// 定期对时(简单版):每 2 秒,把偏离主相机基准超 1.5s 的格拨回去。同段微调 currentTime;跨段重定位。
function pbStopSync(){ if(pbSyncTimer){ clearInterval(pbSyncTimer); pbSyncTimer = null; } }
function pbStartSync(){
  pbStopSync();
  pbSyncTimer = setInterval(() => {
    const m = pbVids[pbMaster];
    if(!m || !m._seg || m.paused) return;          // 主相机没在播就不对时
    const mw = m._seg.s0 + m.currentTime;
    pbCams().forEach(c => {
      if(c.id === pbMaster) return;
      const v = pbVids[c.id]; if(!v || v.paused || !v._seg || v._manual) return;   // 手动拖过的格不强行对时
      if(Math.abs((v._seg.s0 + v.currentTime) - mw) < 1.5) return;   // 阈值内不动
      const arr = pbSegs[c.id] || [];
      const b = pbBest(c.id, mw); if(!b) return;
      if(b.idx === v._idx){ pbSeek(v, b.offset); }   // 同段:微调
      else {                                                                            // 跨段:重定位
        v._idx = b.idx; v._seg = arr[b.idx];
        v.src = '/video?cam=' + encodeURIComponent(c.id) + '&file=' + encodeURIComponent(arr[b.idx].file);
        const om = () => { v.removeEventListener('loadedmetadata', om); pbSeek(v, b.offset); v.play().catch(()=>{}); };
        v.addEventListener('loadedmetadata', om); v.load();
      }
    });
  }, 2000);
}

function pbMarkMaster(){      // 高亮基准相机那一格,角标加" · 基准"
  pbCams().forEach(c => {
    const v = pbVids[c.id]; if(!v || !v.parentElement) return;
    const isM = (c.id === pbMaster);
    v.parentElement.classList.toggle('master', isM);
    const badge = v.parentElement.querySelector('.pbname');
    if(badge) badge.textContent = c.label + (isM ? ' · 基准' : '');
  });
}

async function setPbGrid(on){
  if(on){
    const w = currentWall();          // 进入前的当前时刻
    if(liveMode) setLive(false);
    if(gridMode) setGrid(false);
    pbGrid = true;
    document.body.classList.add('pbgrid-mode');
    updateModeBar();
    $('title').textContent = '小米录像 · 回放四分屏';
    vid.pause();
    const g = $('grid'); g.innerHTML = ''; pbVids = {};
    const cams = pbCams();
    pbMaster = (cams.find(c => c.id === cam) ? cam : (cams[0] && cams[0].id)) || null;
    cams.forEach(c => {
      const cell = document.createElement('div'); cell.className = 'pbcell';
      const v = document.createElement('video'); v.muted = true; v.playsInline = true; v.preload = 'metadata'; v.controls = true;  // 原生控件:播放/进度/音量/全屏
      const b = document.createElement('span'); b.className = 'cellbadge pbname'; b.textContent = c.label;
      cell.appendChild(v); cell.appendChild(b); g.appendChild(cell);
      addZoom(cell);   // 放大键(页面内放大,不进系统全屏)
      // 用户拖原生进度条 → 本格转"独立",定期对时跳过它;按"全部播放"或拖主时间轴恢复同步
      v.addEventListener('seeking', () => { if(Date.now() - (v._progT || 0) > 1500) v._manual = true; });   // 离上次程序化定位 >1.5s 的 seek 才算用户手动
      pbVids[c.id] = v;
      v.addEventListener('timeupdate', updateHead);          // 主相机驱动播放头(updateHead 内判断)
      v.addEventListener('ended', () => {                    // 接续本相机下一段
        const arr = pbSegs[c.id] || []; const ni = (v._idx|0) + 1;
        if(ni < arr.length){ v._idx = ni; v._seg = arr[ni];
          v.src = '/video?cam=' + encodeURIComponent(c.id) + '&file=' + encodeURIComponent(arr[ni].file);
          const om = () => { v.removeEventListener('loadedmetadata', om); v.play().catch(()=>{}); };
          v.addEventListener('loadedmetadata', om); v.load(); }
      });
    });
    pbMarkMaster();                   // 标出基准相机(高亮边框)
    await pbFetchDay(dateStr);
    segs = pbSegs[pbMaster] || [];    // 时间轴显示主相机的覆盖
    curIdx = -1; renderTrack();
    $('empty').style.display = segs.length ? 'none' : '';
    gridSeekAll((w && w.sec != null && isFinite(w.sec)) ? w.sec : 0, !!(w && w.play));
    pbStartSync();                    // 启动定期对时
  } else {
    const w = currentWall();          // pbGrid 仍 true → 取主相机当前时刻
    pbTeardown();
    $('title').textContent = '小米录像 · 时间轴回放';
    selectDay(dateStr, (w && w.sec != null) ? w.sec : null, !!(w && w.play));   // 回到单画面同一时刻
  }
}
// 回放分屏:全部播放(重新对齐到当前时刻再齐播)/ 全部暂停
$('pbPlayAll').onclick  = () => { pbCams().forEach(c => { const v = pbVids[c.id]; if(v && v._seg) v.play().catch(()=>{}); }); $('playBtn').textContent = '⏸ 暂停'; };   // 纯恢复播放,不重载(对齐用「⇄ 同步」)
$('pbPauseAll').onclick = () => { pbCams().forEach(c => { const v = pbVids[c.id]; if(v) v.pause(); }); $('playBtn').textContent = '▶︎ 播放'; };
$('pbSyncBtn').onclick = pbAlignAll;

// 画质下拉:填充选项 + 切换时重建当前直播(单画面/四分屏都适用)
QUALS.forEach((q, i) => { const o = document.createElement('option'); o.value = i; o.textContent = q.label; $('qualSel').appendChild(o); });
$('qualSel').onchange = e => { qualIdx = +e.target.value; if(gridMode) setGrid(true); else if(liveMode) setLive(true); };
$('playBtn').onclick = () => { if(pbGrid){ pbToggle(); return; } if(vid.paused) vid.play().catch(()=>{}); else vid.pause(); };
vid.addEventListener('play',  () => $('playBtn').textContent = '⏸ 暂停');
vid.addEventListener('pause', () => $('playBtn').textContent = '▶︎ 播放');
$('back10').onclick = () => { if(pbGrid){ const w = currentWall(); gridSeekAll(Math.max(0,(w.sec||0)-10), pbPlaying()); return; } vid.currentTime = Math.max(0, vid.currentTime - 10); };
$('fwd10').onclick  = () => { if(pbGrid){ const w = currentWall(); gridSeekAll((w.sec||0)+10, pbPlaying()); return; } vid.currentTime = vid.currentTime + 10; };
$('rateSel').onchange = e => { const r = parseFloat(e.target.value); vid.playbackRate = r; pbCams().forEach(c => { const v = pbVids[c.id]; if(v) v.playbackRate = r; }); };
$('latestBtn').onclick = () => {
  if(pbGrid){ if(segs.length) gridSeekAll(segs[segs.length-1].s1 - 2, true); return; }
  if(segs.length){ const i = segs.length - 1; loadSegment(i, Math.max(0, segs[i].s1 - segs[i].s0 - 2), true); }
};
// ---- 上一段 / 下一段（跳到相邻录像片段的开头）----
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
  if(liveMode) setLive(false);   // 上一段/下一段 → 切到录像
  let i = (curIdx < 0) ? 0 : curIdx + delta;
  i = Math.max(0, Math.min(segs.length - 1, i));
  loadSegment(i, 0, true);
}
$('prevSeg').onclick = () => jumpSeg(-1);
$('nextSeg').onclick = () => jumpSeg(1);

document.addEventListener('keydown', e => {
  if(['INPUT','SELECT','TEXTAREA'].includes(document.activeElement.tagName)) return;
  if(e.key === 'r' || e.key === 'R'){ $('refreshBtn').click(); return; }   // R = 刷新(直播/回放都可用)
  if(e.key === 'l' || e.key === 'L'){ setMode(currentMode()==='live'    ? 'play' : 'live');     return; }   // L = 直播 ↔ 回放
  if(e.key === 'g' || e.key === 'G'){ setMode(currentMode()==='livegrid'? 'play' : 'livegrid'); return; }   // G = 直播分屏
  if(e.key === 'p' || e.key === 'P'){ setMode(currentMode()==='pbgrid'  ? 'play' : 'pbgrid');   return; }   // P = 回放分屏
  if(liveMode || gridMode) return; // 直播四分屏下不响应回放快捷键(回放四分屏照常响应)
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
