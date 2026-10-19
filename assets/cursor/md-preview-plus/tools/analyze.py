# Timeline of the preview area after going back, from the frames flash.mjs recorded: per frame, its
# difference from the final frame and the share of background-coloured pixels (a blank preview is ~1.0).
# The area is the preview's iframe as summary.json records it once shown again ("shown": x, y, w, h).
#   /usr/bin/python3 analyze.py <out dir of flash.mjs>     (needs numpy and PIL)
import sys, os, json
import numpy as np
from PIL import Image
d = sys.argv[1]
s = json.load(open(os.path.join(d, 'summary.json')))
x, y, w, h = (round(v) for v in s['shown'])
fs = sorted(f for f in os.listdir(d) if f.startswith('f') and f.endswith('.png'))
def area(f):
    a = np.asarray(Image.open(os.path.join(d, f)).convert('RGB')).astype(np.int16)
    return a[y:y + h, x:x + w]
fin = area(fs[-1])
bg = np.median(fin.reshape(-1, 3), axis=0)
for f in fs:
    a = area(f)
    diff = np.abs(a - fin).mean()
    near_bg = (np.abs(a - bg).sum(axis=2) < 12).mean()
    print(f"{f:22s} diff_to_final={diff:6.2f}  background_share={near_bg:5.2f}")
print('page log:', s['log'])
print('covered iframe:', s['covered'], 'shown:', s['shown'], 'scroll:', s['scroll'], 'cursor after the link:', s.get('cursor'))
