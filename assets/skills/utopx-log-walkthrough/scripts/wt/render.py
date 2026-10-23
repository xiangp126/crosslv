"""Render log lines, folds, notes, step cards and the command tables between steps."""
import collections
import re

from .fmt import esc
from .log import squeeze

def render_line(L, k, marks, with_id=True):
    t = L.lines[k]
    r = L.rec.get(k)
    ms = [(rx, n) for rx, n, *at in marks if not at or k in at[0]]

    def hl(text):
        spans = []
        for rx, n in ms:
            for m in re.finditer(rx, text):
                spans.append((m.start(), m.end(), n))
        spans.sort()
        out, pos, used = [], 0, []
        for s, e, n in spans:
            if s < pos:
                continue
            out.append(esc(text[pos:s]))
            out.append('<mark data-n="%d">%s</mark>' % (n, esc(text[s:e])))
            pos = e
            used.append(n)
        out.append(esc(text[pos:]))
        return ''.join(out), used

    lid = ' id="L%d"' % k if with_id else ''
    if r:
        src, thr, tm, lvl, tag, msg = r
        body, used = hl(squeeze(msg))
        cls = 'l rec'
        if tag == 'LOG_OP':
            cls += ' op'
        elif tag == 'LOG_KEY_CMDIF':
            cls += ' dump'
        elif 'State Transition' in msg or 'completed bringup' in msg:
            cls += ' state'
        badges = ''.join('<span class="badge" data-n="%d">%d</span>' % (n, n) for n in sorted(set(used)))
        return ('<div class="%s"%s><a class="ln" href="#L%d">%d</a><span class="bd">%s</span>'
                '<span class="src">%s</span><span class="th">%s</span><span class="tm">%s</span>'
                '<span class="tg">%s</span><span class="msg">%s</span></div>') % (
            cls, lid, k, k, badges, esc(src), esc(thr), esc(tm), esc(tag), body)
    body, used = hl(squeeze(t))
    badges = ''.join('<span class="badge" data-n="%d">%d</span>' % (n, n) for n in sorted(set(used)))
    return ('<div class="l fld"%s><a class="ln" href="#L%d">%d</a><span class="bd">%s</span><span class="msg">%s</span></div>' % (
        lid, k, k, badges, body))


def stage_at(transitions, line, fns):
    """utopx's HCA_STAGE of each function after the given log line (only the generator copies)."""
    st = {fn: 'DISABLED_HCA' for fn in fns}
    for n, fn, a, b in transitions:
        if n <= line:
            st[fn] = b
    return st


def transitions_of(L):
    gen = {v['vhca']: fn for fn, v in L.fn_info.items()}
    out = []
    for n in L.findall(r'HCA State Transition: VHCA='):
        m = re.search(r'VHCA=(0x[0-9a-f]+):GVMI=\w+:TYPE=\w+ HCA_STAGE_(\w+) --> HCA_STAGE_(\w+)', L.lines[n])
        if m and m.group(1) in gen:
            out.append((n, gen[m.group(1)], m.group(2), m.group(3)))
    return out


def op_fields(L, o, names):
    """(line, value) of the first dump field of each name among one command's lines, plus its INPUT and OUTPUT sizes."""
    got = {}
    for k in L.op_lines(o):
        s = L.lines[k].strip()
        m = re.match(r'(INPUT|OUTPUT) (\d+) (\d+)', s)
        if m:
            got.setdefault(m.group(1), (k, '%s %s' % (m.group(2), m.group(3))))
            continue
        m = re.match(r'(\w+)\s*:\s*(\S+)', s)
        if m and m.group(1) in names:
            got.setdefault(m.group(1), (k, m.group(2)))
    return got


def line_html(L, k, marks):
    h = render_line(L, k, marks, with_id=True)
    used = [int(x) for x in re.findall(r'<mark data-n="(\d+)"', h)]
    # The log names a function only by VHCA, GVMI and PCI address: tag each command and stage line with PSF, PF0 or PF1.
    if re.match(r'<div class="l rec (op|state)"', h):
        m = re.search(r'VHCA=(0x[0-9a-f]+)\b', L.lines[k])
        fn = m and {v['vhca']: f for f, v in L.fn_info.items()}.get(m.group(1))
        if fn:
            h = h.replace('<span class="msg">', '<span class="msg"><span class="fntag %s">%s</span>' % (fn.lower(), fn), 1)
    return h, used


def fold_label(L, a, b):
    """What a fold hides: the PSF, PF0 and PF1 commands by name first, so a command never passes for bookkeeping,
    then the kinds of the other lines. Also says whether there was a command."""
    # the commands come from the parser's own list (L.ops), the one the header's count uses: its OPRE also takes opcodes
    # with a sub-op, such as "MODIFY_QP RST2INIT_QP"
    if not hasattr(L, 'op_at'):
        L.op_at = {o['n']: o for o in L.ops}
    cmds, kinds = collections.Counter(), collections.Counter()
    for k in range(a, b + 1):
        r = L.rec.get(k)
        if not r:
            continue
        if k in L.op_at:
            cmds['%s %s' % (L.op_at[k]['fn'], L.op_at[k]['opcode'])] += 1
        elif 'DmaDesc' in r[0]:
            kinds['DMA buffer allocation'] += 1
        elif L.is_checker(L.lines[k]):
            kinds["checker's copy of the function"] += 1
        elif r[4] == 'DROP' or 'Printing Log drop' in r[5]:
            kinds['generator drops'] += 1
        else:
            kinds['bookkeeping'] += 1
    if len(cmds) > 3:
        by_fn = collections.Counter(c.split()[0] for c in cmds.elements())
        parts = ['%s commands (%s)' % (f'{sum(cmds.values()):,}', ', '.join('%s %d' % kv for kv in sorted(by_fn.items())))]
    else:
        parts = ['%s ×%d' % kv for kv in cmds.most_common()]
    parts += ['%s ×%s' % (n, f'{c:,}') for n, c in kinds.most_common(2)]
    return ', '.join(parts), bool(cmds)


def skip_html(L, a, b):
    gap = b - a + 1
    what, has_cmd = fold_label(L, a, b)
    label = '⋯ %s line%s not shown%s' % (f'{gap:,}', '' if gap == 1 else 's',
                                         (' · ' + esc(what)) if what and (gap > 3 or has_cmd) else '')
    if gap > 60:
        return '<div class="skip"><span>%s</span></div>' % label
    rows = ''.join('<div class="l hid"><span class="ln">%d</span><span class="msg">%s</span></div>' % (
        k, esc(squeeze(L.lines[k])) or '&nbsp;') for k in range(a, b + 1))
    return ('<details class="skip"><summary><span>%s</span><span class="show">show</span></summary>'
            '<div class="hidden-lines">%s</div></details>') % (label, rows)


def note_html(n, text):
    return '<div class="note" data-n="%d"><span class="nk">%d</span><div class="nt">%s</div></div>' % (n, n, text)


def gap_html(L, a, b):
    if b - a <= 1:
        return ''
    inside = [o for o in L.ops if a < o['n'] < b]
    head = '⋯ %s log lines between the steps' % f'{b - a - 1:,}'
    if not inside:
        return '<div class="gap"><span>%s, no commands</span></div>' % head
    by = collections.OrderedDict()
    for o in inside:
        by.setdefault(o['fn'], collections.Counter())[o['opcode']] += 1
    parts = []
    for fn, c in by.items():
        tot = sum(c.values())
        top = ', '.join('%s%s' % (op, '' if n == 1 else ' ×%d' % n) for op, n in c.most_common(3))
        parts.append('<b class="fn-%s">%s</b> %s: %s%s' % (fn.lower(), fn, f'{tot:,}', esc(top), ', …' if len(c) > 3 else ''))
    cap = 40
    rows = ''.join('<tr><td class="num">%d</td><td>%s</td><td class="fn-%s">%s</td><td>%s</td><td class="rest">%s</td></tr>' % (
        o['n'], esc(o['time']), o['fn'].lower(), o['fn'], esc(o['opcode']), esc(squeeze(o['rest'])[:80])) for o in inside[:cap])
    more = '<p class="more">and %s more commands</p>' % f'{len(inside) - cap:,}' if len(inside) > cap else ''
    return ('<details class="gap"><summary><span>%s</span><span class="gap-parts">%s</span></summary><div class="tablewrap">'
            '<table class="cmds"><thead><tr><th>line</th><th>time</th><th>function</th><th>command</th><th>detail</th></tr></thead>'
            '<tbody>%s</tbody></table></div>%s</details>') % (head, ' · '.join(parts), rows, more)


def step_html(L, st, idx, t0):
    """One step card: header, the earlier context lines, the log lines with folds and notes, attachments, raw log."""
    first, last = st.lines[0], st.lines[-1]
    k0 = first if first in L.rec else next((k for k in st.lines if k in L.rec), None)
    tm = L.rec[k0][2] if k0 else ''
    rel = max(0.0, L.tabs[k0] - t0) if k0 else 0.0  # a step may open a few lines before its command
    out = ['<article class="step f%d" id="%s" data-step="%d" tabindex="-1">' % (st.flow, st.sid, idx - 1)]
    pills = ''.join('<q class="ppt f%d">%s</q>' % (fl, esc(q)) for fl, q in st.slide)
    out.append('<header class="step-head"><span class="stepno">%d</span><div class="sh-main"><h3>%s</h3>'
               '<div class="meta"><span>L%s–%s</span><span>%s</span><span>t + %.2f s</span></div>%s</div>'
               '<button class="play-here" type="button" data-go="%d" aria-label="Play from step %d">'
               '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 2.5v11l9-5.5z"/></svg>Play from here</button></header>' % (
                   idx, esc(st.title), f'{first:,}', f'{last:,}', esc(tm), rel,
                   ('<div class="pills"><span class="lab">On the FW slides</span>%s</div>' % pills) if pills else '', idx - 1, idx))
    placed = set()
    if st.context:
        ctx, used_all = [], []
        for k in st.context:
            h, used = line_html(L, k, st.context_marks)
            ctx.append(h)
            used_all += [n for n in used if n not in used_all and n in st.notes]
        out.append('<div class="log context" role="region" aria-label="earlier log line"><div class="ctx-lab">%s</div>%s%s</div>' % (
            esc(st.context_label), ''.join(ctx), ''.join(note_html(n, st.notes[n]) for n in used_all)))
        placed.update(used_all)
    out.append('<div class="log" role="region" aria-label="log lines %d to %d">' % (first, last))
    prev = None
    for k in st.lines:
        if prev is not None and k > prev + 1:
            out.append(skip_html(L, prev + 1, k - 1))
        h, used = line_html(L, k, st.marks)
        out.append(h)
        for n in used:
            if n not in placed and n in st.notes:
                out.append(note_html(n, st.notes[n]))
                placed.add(n)
        prev = k
    for n in sorted(st.notes):
        if n not in placed:
            out.append(note_html(n, st.notes[n]))
    out.append('</div>')
    out.extend(st.attachments)
    span = last - first + 1
    cap = st.raw_cap
    raw = list(range(first, last + 1))
    if span > cap:
        raw = list(range(first, first + cap * 2 // 3)) + [None] + list(range(last - cap // 3 + 1, last + 1))
    rows = []
    for k in raw:
        if k is None:
            rows.append('<div class="skip"><span>⋯ %s lines elided ⋯</span></div>' % f'{span - cap + 1:,}')
            continue
        rows.append('<div class="l raw"><span class="ln">%d</span><span class="msg">%s</span></div>' % (k, esc(squeeze(L.lines[k])) or '&nbsp;'))
    out.append('<details class="rawbox"><summary>Raw log, L%s–%s (%s lines%s)</summary><div class="log rawlog">%s</div></details>' % (
        f'{first:,}', f'{last:,}', f'{span:,}', ', middle elided' if span > cap else '', ''.join(rows)))
    out.append('</article>')
    return '\n'.join(out), dict(id=st.sid, flow=st.flow, title=st.title, time=tm, rel=round(rel, 3), first=first, last=last)
