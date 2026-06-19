# Precise sync — in-browser OCR of the burned-in timestamp

Precise mode aligns the 4 playback cells to the reference's **real** time (±1 s) by OCR-reading the
white timestamp the camera burns into the top-left of every frame, instead of trusting the (drifting,
per-file) assumed time that Coarse mode uses. All OCR runs **in the browser**; camera frames never
leave the LAN.

This doc records the design, the model choice, and the **full local deployment** of the OCR engine —
including the upgrade from PP-OCRv3 to **PP-OCRv4-server** done on 2026-06-16.

---

## 1. Pipeline (in `xiaomi_playback.py`, all client-side JS)

1. **Crop** the top-left timestamp band from the *source* frame by ratio (`0.40 × 0.08` of
   `videoWidth × videoHeight`) → resolution-/layout-independent (works at any screen/split size).
2. **Preprocess** to the model's input: resize to **height 48** (keep aspect), **BGR** channel order,
   normalize to `[-1, 1]` (`x/127.5 - 1`), NCHW. *Raw colour — no binarization* (the neural model wants
   natural pixels).
3. **Infer** with **onnxruntime-web** (WASM backend, `numThreads=1` → no SharedArrayBuffer/COOP needed).
4. **CTC greedy decode** the `[1, T, 6625]` output: argmax per timestep, collapse repeats, drop blank
   (index 0); map indices through the dict (`['blank'] + ppocr_keys + ' ']`).
5. **`parseClock()`** pulls `HH:MM:SS` (regex, with a last-6-digits fallback) → seconds of day.
6. **Calibrate the offset (AVERAGED)**: `offset = tReal − (s0 + currentTime)`. The burned clock is
   **whole-seconds**, so a single read is low by the unknown sub-second fraction `f ∈ [0,1)` — and `f`
   differs per cell, so the old "two frames agree → average the pair" left cells **> 2 s apart** (the user's
   "needs two Precise clicks"). `calibrateOffset` now gathers **~8 reads** (`|offset| ≤ 120 s`, median-filtered
   to drop misreads, **≥ 3 consistent** required) and returns their **mean**. Reads spread over > 1 s sample
   `f` across `[0,1)`, so every cell's mean carries the **same ~0.5 s bias** → it cancels in the *relative*
   alignment and the cells land together in **one** click.
7. **Align**: all-or-nothing. Only if **every** cell verifies are offsets applied; else it stays in Precise
   and retries on each segment change (or on another `◎ Precise` click). After a cell crosses into a new clip
   its offset is re-calibrated **once** (the per-crossing `recal` — necessary because each file's
   `currentTime ↔ real` mapping differs; its read shows in the debug window). The offset-aware maintenance
   loop then holds the alignment.

Engine: **PaddleOCR PP-OCRv4-server rec** primary, **tesseract.js** fallback (`OCR_ENGINE='paddle'`; on a
paddle init/run error the dispatcher falls back to tesseract). Frames stay local — **no cloud/public OCR**.

## 2. Files on the router (`/mnt/sda3/opt/ocr/`, served same-origin at `/ocr/`)

| File | Size | Purpose |
|------|------|---------|
| `ort.min.js` | ~0.4 MB | onnxruntime-web loader (UMD). `<script src="/ocr/ort.min.js">`. |
| `ort-wasm-simd-threaded.wasm` + `.mjs` | ~11 MB | ort WASM backend + its ESM loader (**both required**). |
| `ort-wasm-simd-threaded.jsep.wasm` + `.mjs` | ~21 MB | jsep variant (hosted for completeness). |
| **`rec_v4_server.onnx`** | **~90 MB** | **PP-OCRv4-server recognition model** (the one in use). |
| `rec_v3.onnx` | ~10.7 MB | old PP-OCRv3 (kept; not referenced). |
| `ppocr_keys.txt` | 26 KB | 6623-char dict (identical for v3 and v4). |
| `tesseract.min.js`, `worker.min.js`, `tesseract-core-simd-lstm.wasm[.js]`, `eng*.traineddata.gz` | — | tesseract.js fallback engine. |

Server side: `OCR_DIR = "/mnt/sda3/opt/ocr"`, route `/ocr/<file>` in `_ocr_file()`. **Content-types matter**
(`_OCR_CT`): `.mjs` and `.js` → `text/javascript` (ESM import is refused otherwise), `.wasm` →
`application/wasm`, `.onnx` → `application/octet-stream`, `.txt` → `text/plain`.

> **Not in the repo.** These engine files live only on sda3. After a reimage that wipes sda3, re-host them
> (§5).

## 3. Why PP-OCRv4-server (the model choice)

Symptom: a cell whose timestamp digits sit over a **cluttered / low-contrast background** (e.g. CAM4's
`13:21:14` over shelving) was mis-read — colons dropped, digits duplicated — so that cell never verified
and fell back to Coarse. The date part (over a clean wall) read fine; only the time mangled.

Verified **offline** (Python + onnxruntime on the real crops `camN_crop.png` pulled via ffmpeg):

| model | size | CAM2 (clean bg) | CAM3 | **CAM4 (cluttered bg)** |
|-------|------|------|------|------|
| PP-OCRv3 (mobile) | 10.7 MB | ✅ `13:20:54` | ✅ `13:14:03` | ❌ `13221:147` |
| PP-OCRv4-mobile | 10.8 MB | ✅ | ✅ | ❌ `613821:14` |
| en_number (v1, digit-only) | 1.9 MB | ❌ garbled | ❌ | ❌ |
| **PP-OCRv4-server** | **90 MB** | ✅ | ✅ | ✅ **`13:21:14`** |

Only **v4-server** reads the cluttered case. Contrast-enhancement preprocessing (autocontrast / stretch /
grayscale) did **not** rescue the smaller models — it's a model-capacity issue, not a contrast one. The
digit-only `en_number` model is an old v2.0 and far less accurate. So the size cost is unavoidable for this.

**Trade-offs (accepted):** 90 MB model → first Precise click loads it in ~4.5 s, then the browser HTTP-caches
it (`Cache-Control: max-age=86400`); inference is heavier than v3 but Precise is on-demand. **iPad still can't
run Precise** (too heavy) — use Mac/iPhone; the dispatcher falls back to tesseract on failure either way.

## 4. Deployment process actually used (2026-06-16, v3 → v4-server)

1. **Got the ONNX** from the RapidOCR HuggingFace mirror (PyPI mirror only had rapidocr 1.2.3 = v3):
   ```sh
   # list what the HF repo has:
   curl -s "https://huggingface.co/api/models/SWHL/RapidOCR/tree/main?recursive=true" | grep rec.*onnx
   # download the server rec model:
   curl -fsSL -o rec_v4_server.onnx \
     "https://huggingface.co/SWHL/RapidOCR/resolve/main/PP-OCRv4/ch_PP-OCRv4_rec_infer.onnx"   # mobile
   curl -fsSL -o rec_v4_server.onnx \
     "https://huggingface.co/SWHL/RapidOCR/resolve/main/PP-OCRv4/ch_PP-OCRv4_rec_server_infer.onnx"  # SERVER (used)
   ```
2. **Dict**: extracted from the model's ONNX metadata (`metadata_props['character']`) → confirmed **identical**
   to the v3 dict already hosted, so `ppocr_keys.txt` was reused unchanged.
3. **Verified offline** the model reads the real crops (table in §3) before touching the live site.
4. **Hosted** on the router + sha256-checked + HTTP-checked:
   ```sh
   cat rec_v4_server.onnx | ssh -p 8822 root@192.168.10.200 'cat > /mnt/sda3/opt/ocr/rec_v4_server.onnx'
   curl -s -o /dev/null -w '%{http_code} %{size_download}\n' http://192.168.10.200:8800/ocr/rec_v4_server.onnx
   ```
5. **Swapped the code**: one line in `getPaddle()` —
   `ort.InferenceSession.create('/ocr/rec_v3.onnx', …)` → `'/ocr/rec_v4_server.onnx'`. Deploy + restart.
6. **Verified in-browser** (headless WebKit, which decodes H265 like Safari): `ort.InferenceSession.create`
   loaded the 90 MB model (~4.5 s) and a dummy inference returned dims `[1, 40, 6625]` — no error.

(Earlier, the whole OCR engine was first stood up by hosting the onnxruntime-web runtime + the rec model +
dict + the **`.mjs` loaders** — the `.mjs` being the gotcha that initially made paddle silently fall back to
tesseract until they were hosted with a `text/javascript` content-type.)

## 5. Re-host after a wipe (runbook)

```sh
D=/mnt/sda3/opt/ocr
ssh -p 8822 root@192.168.10.200 "mkdir -p $D"
# 1) onnxruntime-web runtime (v1.19.2):
for f in ort.min.js ort-wasm-simd-threaded.wasm ort-wasm-simd-threaded.mjs \
         ort-wasm-simd-threaded.jsep.wasm ort-wasm-simd-threaded.jsep.mjs; do
  curl -fsSL "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.19.2/dist/$f" \
    | ssh -p 8822 root@192.168.10.200 "cat > $D/$f"
done
# 2) PP-OCRv4-server rec model:
curl -fsSL "https://huggingface.co/SWHL/RapidOCR/resolve/main/PP-OCRv4/ch_PP-OCRv4_rec_server_infer.onnx" \
  | ssh -p 8822 root@192.168.10.200 "cat > $D/rec_v4_server.onnx"
# 3) dict (PaddleOCR ch ppocr_keys_v1.txt — 6623 lines; or extract from the model's metadata 'character'):
curl -fsSL "https://raw.githubusercontent.com/PaddlePaddle/PaddleOCR/main/ppocr/utils/ppocr_keys_v1.txt" \
  | ssh -p 8822 root@192.168.10.200 "cat > $D/ppocr_keys.txt"
# 4) tesseract.js fallback: tesseract.min.js, worker.min.js, tesseract-core-simd-lstm.wasm[.js], eng.traineddata.gz
```
Then confirm `_OCR_CT` in `xiaomi_playback.py` maps `.mjs`/`.js`→`text/javascript`, `.wasm`→`application/wasm`.

## 6. Self-verification harness (how this was tested without the user)

`assets/xiaomi/xiaomi_playback.py` changes are verified with a **Playwright WebKit** harness (WebKit decodes
the H265 recordings like Safari; headless Chromium can't). The Bash sandbox blocks the browser's network, so
the node scripts are run with the sandbox disabled (read-only page loads). It drives the app via globals
(`gridSeekAll(sec, true)`), reads each `<video>`'s `currentTime/readyState/videoWidth/buffered`, and computes
real-time `= pbVids[k]._seg.s0 + currentTime` to check sync drift. **Caveat:** headless WebKit has a low
concurrent-media limit (~1–2 of 4 cells load) so full 4-split is only checkable in real Safari; OCR models are
verified **offline** (Python onnxruntime on ffmpeg-extracted crops), and WebRTC live is not headless-testable.
