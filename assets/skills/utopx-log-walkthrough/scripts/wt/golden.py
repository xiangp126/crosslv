"""Compare two walkthrough pages: the visible text region by region, and the embedded page data.

Use it whenever the engine or a story changes: rebuild a page that is already published and compare it with
the published copy. Every difference must be one you meant to make.
"""
import difflib
import json
import re

from .htmltree import parse


def norm(text):
    lines = [' '.join(x.split()) for x in text.split('\n')]
    return [x for x in lines if x]


def regions(page):
    """Region name -> visible text lines, in page order."""
    root = parse(page)
    out = {}

    def put(name, node):
        if node is not None:
            out[name] = norm(node.text(titles=True))

    t = root.first(lambda n: n.tag == 'title')
    if t is not None:
        out['title'] = norm(t.text())
    put('hero', root.first(lambda n: n.tag == 'header' and 'hero' in n.cls()))
    put('scene', root.first(lambda n: n.tag == 'svg' and 'scene' in n.cls()))
    put('summary', root.first(lambda n: n.tag == 'section' and n.attrs.get('id') == 'summary'))
    for sec in root.find_all(lambda n: n.tag == 'section' and 'flow' in n.cls()):
        put('%s head' % sec.attrs.get('id'), sec.first(lambda n: 'flow-head' in n.cls()))
    prev = 'start'
    gaps = 0
    for n in root.walk():
        if n.tag == 'article' and 'step' in n.cls():
            prev = 'step ' + n.attrs.get('id', '?')
            put(prev, n)
        elif 'gap' in n.cls() and n.tag in ('div', 'details'):
            gaps += 1
            put('gap after %s' % prev, n)
    put('footer', root.first(lambda n: n.tag == 'footer'))
    return out


def page_data(page):
    m = re.search(r'<script type="application/json" id="walk-data">(.*?)</script>', page, flags=re.S)
    return json.loads(m.group(1)) if m else None


def diff_data(a, b, path='', out=None):
    out = [] if out is None else out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b), key=str):
            if k not in a:
                out.append('%s.%s: added %s' % (path, k, short(b[k])))
            elif k not in b:
                out.append('%s.%s: removed %s' % (path, k, short(a[k])))
            else:
                diff_data(a[k], b[k], '%s.%s' % (path, k), out)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            diff_data(x, y, '%s[%d]' % (path, i), out)
    elif a != b:
        out.append('%s: %s -> %s' % (path or '.', short(a), short(b)))
    return out


def short(v, n=160):
    s = json.dumps(v, ensure_ascii=False)
    return s if len(s) <= n else s[:n] + '...'


def rename_keys(d, renames):
    """Apply key renames inside every choreography entry (old name -> new name)."""
    if not renames or not isinstance(d, dict) or not isinstance(d.get('choreo'), dict):
        return d
    for c in d['choreo'].values():
        for old, new in renames.items():
            if old in c:
                c[new] = c.pop(old)
    return d


def compare(old_page, new_page, renames=None):
    """Return a list of report lines; empty when the pages show the same text and carry the same data."""
    report = []
    ra, rb = regions(old_page), regions(new_page)
    for name in list(ra) + [k for k in rb if k not in ra]:
        a, b = ra.get(name), rb.get(name)
        if a == b:
            continue
        if a is None or b is None:
            report.append('== region %s: only in the %s page' % (name, 'new' if a is None else 'old'))
            continue
        report.append('== region %s' % name)
        report.extend(x.rstrip('\n') for x in difflib.unified_diff(a, b, 'old', 'new', n=0, lineterm=''))
    da, db = page_data(old_page), page_data(new_page)
    if da is None or db is None:
        if da is not db:
            report.append('== data: missing in the %s page' % ('old' if da is None else 'new'))
    else:
        dd = diff_data(rename_keys(da, renames), db)
        if dd:
            report.append('== data')
            report.extend(dd)
    return report


def main(args):
    renames = dict(x.split('=', 1) for x in args.rename)
    with open(args.old, encoding='utf-8') as f:
        old = f.read()
    with open(args.new, encoding='utf-8') as f:
        new = f.read()
    report = compare(old, new, renames)
    try:
        for line in report:
            print(line)
        print('golden: %s' % ('same text and data' if not report else '%d report lines' % len(report)))
    except BrokenPipeError:
        pass
    return 1 if report else 0
