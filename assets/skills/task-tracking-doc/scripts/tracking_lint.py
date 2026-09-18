#!/usr/bin/env python3
"""Read-only health check for a TRACKING.md.

Checks what an LLM does unreliably and a human does by hand:
table column alignment, staleness, stalled in-flight rows, numbering reuse,
broken section cross-references, and conclusions without a control row.

Usage:
    tracking_lint.py <TRACKING.md>              full report
    tracking_lint.py <TRACKING.md> --summary    status board + in-flight rows only
    tracking_lint.py <TRACKING.md> --stale-days N   staleness threshold (default 3)
    tracking_lint.py <TRACKING.md> --inflight-days N  in-flight threshold (default 7)

Exit code 0 = clean, 1 = findings. Never writes anything.
"""
import argparse
import datetime as dt
import os
import re
import sys

INFLIGHT = ('🔵', '🟡')
ALL_MARKS = ('✅', '🟡', '🔵', '⬜', '❌', '🔴')


def is_legend(line):
    """A legend row lists several markers at once; it is not data."""
    return sum(1 for m in ALL_MARKS if m in line) >= 3
DATE_RE = re.compile(r'(20\d{2})-(\d{2})-(\d{2})')
LASTUPD_RE = re.compile(r'Last updated[:：]\s*\*{0,2}\s*(20\d{2}-\d{2}-\d{2})')
# "见 §4.19" / "见 §16.4c" / "详见 §7bis"
XREF_RE = re.compile(r'§\s*([0-9]+(?:\.[0-9A-Za-z]+)*(?:bis|ter|quater|quinquies|sexies|septies|octies)?)')
HEADING_RE = re.compile(r'^(#{1,6})\s+(.*)$')
# leading number of a heading: "## 4.16 ..." / "#### 1.6.3 ..." / "## 7bis ..."
# A real section number is 1-2 digits, optionally multi-level or a latin ordinal.
# 3+ bare digits are dates (0827) or machine numbers (171), not section numbers.
HEADNUM_RE = re.compile(
    r'^\s*(?:[★⚠✅❌🔴🟡🔵⬜️\s]*)'
    r'([0-9]{1,2}(?:\.[0-9A-Za-z]+)+'          # 1.5 / 4.16 / 1.6.3
    r'|[0-9]{1,2}(?:bis|ter|quater|quinquies|sexies|septies|octies)'  # 7bis
    r'|[0-9]{1,2}\.'                            # "3." with the dot
    r')')


def strip_inline(s):
    """Remove inline code spans and escaped pipes so | counting is honest."""
    s = re.sub(r'`[^`]*`', '', s)
    return s.replace(r'\|', '')


def is_sep(line):
    body = line.strip()
    if not body.startswith('|'):
        return False
    core = body.replace('|', '').replace(' ', '')
    return bool(core) and set(core) <= set('-:')


def check_tables(lines, out):
    bad = tables = 0
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith('|') and i + 1 < len(lines) and is_sep(lines[i + 1]):
            tables += 1
            want = strip_inline(lines[i]).count('|')
            j = i
            while j < len(lines) and lines[j].lstrip().startswith('|'):
                got = strip_inline(lines[j]).count('|')
                if got != want:
                    out.append(('table', j + 1,
                                'column count %d, table header says %d: %s'
                                % (got, want, lines[j].strip()[:70])))
                    bad += 1
                j += 1
            i = j
        else:
            i += 1
    return tables, bad


def check_staleness(path, lines, out, stale_days):
    m = None
    for ln in lines[:60]:
        m = LASTUPD_RE.search(ln)
        if m:
            break
    if not m:
        out.append(('stale', 0, 'no "Last updated:" line in the first 60 lines — '
                                'the skeleton requires one'))
        return
    stamped = dt.date(*map(int, m.group(1).split('-')))
    newest, newest_f = None, None
    root = os.path.dirname(os.path.abspath(path)) or '.'
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith('.')]
        for fn in filenames:
            fp = os.path.join(dirpath, fn)
            if os.path.abspath(fp) == os.path.abspath(path):
                continue
            try:
                mtime = dt.date.fromtimestamp(os.path.getmtime(fp))
            except OSError:
                continue
            if newest is None or mtime > newest:
                newest, newest_f = mtime, fp
    if newest and (newest - stamped).days > stale_days:
        out.append(('stale', 0,
                    'Last updated %s but %s changed %s (%d days newer) — '
                    'work happened that was not recorded'
                    % (stamped, os.path.relpath(newest_f, root), newest,
                       (newest - stamped).days)))


def check_inflight(lines, out, inflight_days, today):
    for n, ln in enumerate(lines, 1):
        if not any(k in ln for k in INFLIGHT) or is_legend(ln):
            continue
        dates = DATE_RE.findall(ln)
        if not dates:
            continue
        newest = max(dt.date(int(a), int(b), int(c)) for a, b, c in dates)
        age = (today - newest).days
        if age > inflight_days:
            out.append(('inflight', n,
                        'in-flight for %d days (last date %s): %s'
                        % (age, newest, ln.strip()[:70])))


def collect_numbers(lines):
    nums, order = {}, []
    for n, ln in enumerate(lines, 1):
        h = HEADING_RE.match(ln)
        if not h:
            continue
        m = HEADNUM_RE.match(h.group(2))
        if not m:
            continue
        num = m.group(1).rstrip('.')
        order.append((num, n, len(h.group(1))))
        nums.setdefault(num, []).append(n)
    return nums, order


def check_numbering(lines, out):
    nums, order = collect_numbers(lines)
    for num, where in nums.items():
        if len(where) > 1:
            out.append(('number', where[1],
                        'section number %s reused (also at line %d) — '
                        'old "§%s" references now ambiguous' % (num, where[0], num)))
    return nums


def check_xrefs(lines, nums, out):
    known = set(nums)
    # a bare "§4" should match "4.16" style children too
    prefixes = set()
    for k in known:
        parts = k.split('.')
        for i in range(1, len(parts) + 1):
            prefixes.add('.'.join(parts[:i]))
    for n, ln in enumerate(lines, 1):
        # "见 db_cq.md §11" refers into another document — not our business
        if '.md' in ln:
            continue
        for ref in XREF_RE.findall(ln):
            if ref.endswith('.x') or ref.endswith('.X'):   # "§4.x" is a wildcard
                continue
            if ref not in known and ref not in prefixes:
                out.append(('xref', n, 'cross-reference §%s points at no section '
                                       '(if it means another document, name the file)' % ref))


def check_controls(lines, out):
    """Tables that argue a verdict should carry a control row."""
    trigger = re.compile(r'VERDICT|判据|证伪')
    control = re.compile(r'对照|control|baseline')
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith('|') and i + 1 < len(lines) and is_sep(lines[i + 1]):
            j = i
            while j < len(lines) and lines[j].lstrip().startswith('|'):
                j += 1
            block = lines[i:j]
            head = '\n'.join(lines[max(0, i - 3):i])
            if trigger.search(block[0]) or trigger.search(head):
                if not any(control.search(b) for b in block):
                    out.append(('control', i + 1,
                                'verdict/criteria table with no control row — '
                                'a zero result here cannot be distinguished from a false negative'))
            i = j
        else:
            i += 1


def print_summary(lines):
    board_start = None
    for n, ln in enumerate(lines):
        if HEADING_RE.match(ln) and ('状态看板' in ln or 'Status board' in ln):
            board_start = n
            break
    if board_start is not None:
        print('=== 状态看板 ===')
        for ln in lines[board_start:board_start + 40]:
            if ln.lstrip().startswith('|') or ln.startswith('**当前在途'):
                print('  ' + ln.rstrip())
            elif HEADING_RE.match(ln) and ln != lines[board_start]:
                break
    else:
        print('=== 状态看板 === (未找到 —— 骨架要求有这一节)')
    print()
    print('=== 在途项 ===')
    hits = [(n, ln) for n, ln in enumerate(lines, 1)
            if any(k in ln for k in INFLIGHT) and not is_legend(ln)]
    if not hits:
        print('  (无)')
    for n, ln in hits[:25]:
        print('  L%-5d %s' % (n, ln.strip()[:110]))
    if len(hits) > 25:
        print('  ... 另有 %d 行' % (len(hits) - 25))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('path')
    ap.add_argument('--summary', action='store_true')
    ap.add_argument('--stale-days', type=int, default=3)
    ap.add_argument('--inflight-days', type=int, default=7)
    a = ap.parse_args()

    if not os.path.isfile(a.path):
        print('no such file: %s' % a.path, file=sys.stderr)
        return 2
    lines = open(a.path, encoding='utf-8').read().split('\n')

    if a.summary:
        print_summary(lines)
        return 0

    out = []
    tables, bad = check_tables(lines, out)
    check_staleness(a.path, lines, out, a.stale_days)
    check_inflight(lines, out, a.inflight_days, dt.date.today())
    nums = check_numbering(lines, out)
    check_xrefs(lines, nums, out)
    check_controls(lines, out)

    print('%s — %d lines, %d tables, %d numbered sections'
          % (os.path.basename(a.path), len(lines), tables, len(nums)))
    if not out:
        print('OK: no findings')
        return 0
    hard = [o for o in out if o[0] != 'control']
    order = ['table', 'stale', 'inflight', 'number', 'xref', 'control']
    label = {'table': '表格列数不齐', 'stale': '文档陈旧', 'inflight': '在途滞留',
             'number': '编号重复', 'xref': '断链',
             'control': '结论缺对照 [提示,不计入失败]'}
    for kind in order:
        rows = [o for o in out if o[0] == kind]
        if not rows:
            continue
        print('\n%s (%d)' % (label[kind], len(rows)))
        for _, ln, msg in rows[:20]:
            print('  %s %s' % (('L%d' % ln) if ln else '   ', msg))
        if len(rows) > 20:
            print('  ... 另有 %d 条' % (len(rows) - 20))
    return 1 if hard else 0


if __name__ == '__main__':
    sys.exit(main())
