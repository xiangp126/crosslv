"""Checks on a built page. Errors make the page unfit to publish; warnings are read and either fixed or accepted.

Without a log: links, page data, JavaScript syntax, note order, notes without a marked line.
With --log: every shown line matches the log, and every fold's label and command count match the log.
"""
import html
import json
import os
import re
import shutil
import subprocess
import tempfile

from .golden import page_data
from .htmltree import parse

CJK = re.compile('[\u4e00-\u9fff]')
# what a fold label may name besides commands
FOLD_KINDS = {'DMA buffer allocation', "checker's copy of the function", 'generator drops', 'bookkeeping'}


class Report:
    def __init__(self):
        self.errors, self.warnings = [], []

    def error(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)


def check_links(root, rep):
    ids = {n.attrs['id'] for n in root.walk() if 'id' in n.attrs}
    for n in root.walk():
        href = n.attrs.get('href') or ''
        if href.startswith('#') and href[1:] and href[1:] not in ids:
            rep.error('dangling link %s' % href)


def check_data(page, root, rep):
    try:
        d = page_data(page)
    except ValueError as e:
        rep.error('page data does not parse: %s' % e)
        return None
    if d is None:
        rep.error('no page data (script#walk-data)')
        return None
    arts = [n.attrs.get('id') for n in root.walk() if n.tag == 'article' and 'step' in n.cls()]
    ids = [s.get('id') for s in d.get('steps', [])]
    if ids != arts:
        rep.error('page data steps %s differ from the step cards %s' % (ids, arts))
    for sid in ids:
        if sid not in d.get('choreo', {}):
            rep.error('step %s has no choreography' % sid)
        if sid not in d.get('say', {}):
            rep.error('step %s has no caption' % sid)
    return d


def check_js(page, rep):
    node = shutil.which('node')
    if not node:
        rep.warn('node not found: JavaScript syntax not checked')
        return
    blocks = re.findall(r'<script(?![^>]*application/json)[^>]*>(.*?)</script>', page, flags=re.S)
    if not blocks:
        rep.error('no script in the page')
        return
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as f:
        f.write('\n;\n'.join(blocks))
        path = f.name
    try:
        r = subprocess.run([node, '--check', path], capture_output=True, text=True)
        if r.returncode:
            rep.error('JavaScript does not parse: %s' % (r.stderr.strip().splitlines() or ['?'])[-1])
    finally:
        os.unlink(path)


def step_items(art):
    """The log region of a step card in order: ('line', n, node), ('skip', label, node) and ('note', n, node)."""
    items = []
    log = art.first(lambda n: n.tag == 'div' and 'log' in n.cls() and 'context' not in n.cls()
                    and 'rawlog' not in n.cls())
    if log is None:
        return items
    for k in log.kids:
        if not hasattr(k, 'tag'):
            continue
        c = k.cls()
        if 'l' in c and k.attrs.get('id', '').startswith('L'):
            items.append(('line', int(k.attrs['id'][1:]), k))
        elif 'skip' in c:
            lab = k.first(lambda n: n.tag == 'span')
            items.append(('skip', ' '.join((lab.text() if lab else k.text()).split()), k))
        elif 'note' in c:
            b = k.first(lambda n: 'badge' in n.cls() or 'nb' in n.cls())
            num = re.search(r'\d+', b.text()) if b is not None else None
            items.append(('note', int(num.group(0)) if num else None, k))
    return items


def check_notes(root, rep):
    for art in root.find_all(lambda n: n.tag == 'article' and 'step' in n.cls()):
        sid = art.attrs.get('id')
        seen, order = set(), []
        for kind, val, node in step_items(art):
            if kind == 'line':
                for b in node.find_all(lambda n: 'badge' in n.cls() and 'data-n' in n.attrs):
                    seen.add(int(b.attrs['data-n']))
            elif kind == 'note' and val is not None:
                order.append(val)
                if val not in seen:
                    rep.warn('step %s: note %d sits under no line marked %d' % (sid, val, val))
        if order != sorted(order):
            rep.warn('step %s: notes are not in line order: %s' % (sid, order))


SRCLINE = re.compile(r'\b[\w.-]+\.(?:c|cc|cpp|h|hpp|conf|py|js|sh):\d+')


def check_source_lines(root, rep):
    """A file:line in the page's own text must come from the resolver (class cref) or from the log (class logsrc); log
    lines, folds and the raw log are the log's text and are not looked at."""
    def walk(node, ok):
        for k in node.kids:
            if isinstance(k, str):
                if not ok:
                    for m in SRCLINE.finditer(k):
                        rep.error('source line %s is not resolved from the run\'s tree' % m.group(0))
                continue
            c = set(k.cls())
            if k.tag in ('script', 'style', 'title') or c & {'l', 'skip', 'rawbox', 'gap'}:
                continue
            if 'unresolved' in c:
                rep.error('source line %s was not found in the run\'s tree' % k.text())
                continue
            walk(k, ok or bool(c & {'cref', 'logsrc'}))
    walk(root, False)


def squeeze(s):
    return re.sub(r' {2,}', ' ', s.strip())


def text_without(node, cls):
    """The text of a node, leaving out the elements of one class (the function tag added in front of a line)."""
    out = []
    for k in node.kids:
        if isinstance(k, str):
            out.append(k)
        elif cls not in k.cls():
            out.append(text_without(k, cls))
    return ''.join(out)


def check_against_log(root, log, rep):
    """Every shown line must say what the log says; every fold must name the commands it hides."""
    lines = [None]
    with open(log, encoding='utf-8', errors='replace') as f:
        ansi = re.compile(r'\x1b\[[0-9;]*m')
        for raw in f:
            lines.append(ansi.sub('', raw.rstrip('\n')))
    oprx = re.compile(r'LOG_OP : ([A-Z_0-9]+(?: [A-Z_0-9]+)*)\s*:\s*\[G\]\[VHCA=(0x[0-9a-f]+)')
    for art in root.find_all(lambda n: n.tag == 'article' and 'step' in n.cls()):
        sid = art.attrs.get('id')
        items = step_items(art)
        prev = None
        for i, (kind, val, node) in enumerate(items):
            if kind == 'line':
                n = val
                if n >= len(lines):
                    rep.error('step %s: line %d is past the end of the log' % (sid, n))
                    continue
                msg = node.first(lambda x: 'msg' in x.cls())
                shown = squeeze(text_without(msg, 'fntag')) if msg is not None else ''
                if shown and shown not in squeeze(lines[n]):
                    rep.error('step %s: line %d shows text that is not in the log: %r' % (sid, n, shown[:80]))
                prev = n
            elif kind == 'skip':
                nxt = next((v for k, v, _ in items[i + 1:] if k == 'line'), None)
                m = re.match(r'⋯ ([\d,]+) lines? not shown', val)
                if not m or prev is None or nxt is None:
                    continue
                gap = int(m.group(1).replace(',', ''))
                if gap != nxt - prev - 1:
                    rep.error('step %s: fold after line %d says %d lines, the gap is %d' % (sid, prev, gap, nxt - prev - 1))
                hidden = sum(1 for k in range(prev + 1, nxt) if oprx.search(lines[k]))
                named = 0
                for part in val.split(' · ', 1)[-1].split(', '):
                    m2 = re.match(r'([\d,]+) commands \(', part)
                    m3 = re.match(r'(.+) ×([\d,]+)$', part)
                    if m2:
                        named += int(m2.group(1).replace(',', ''))
                    elif m3 and m3.group(1) not in FOLD_KINDS:
                        named += int(m3.group(2).replace(',', ''))
                if hidden != named:
                    rep.error('step %s: fold after line %d names %d commands, the log has %d' % (sid, prev, named, hidden))


def run(page_path, log=None):
    rep = Report()
    with open(page_path, encoding='utf-8') as f:
        page = f.read()
    root = parse(page)
    check_links(root, rep)
    check_data(page, root, rep)
    check_js(page, rep)
    check_notes(root, rep)
    check_source_lines(root, rep)
    if CJK.search(re.sub(r'<script.*?</script>', '', page, flags=re.S)):
        rep.warn('the page text contains CJK characters')
    if log:
        check_against_log(root, log, rep)
    return rep


def main(args):
    rep = run(args.page, args.log)
    for e in rep.errors:
        print('ERROR', e)
    for w in rep.warnings:
        print('WARN ', w)
    print('check: %d errors, %d warnings' % (len(rep.errors), len(rep.warnings)))
    return 1 if rep.errors else 0
