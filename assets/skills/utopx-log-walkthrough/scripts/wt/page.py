"""Lay out a walkthrough page: hero, stage and transport, run map, statements, flow sections with the steps, footer."""
import json
import os

from .fmt import esc
from .render import gap_html, stage_at, step_html
from .runmap import run_map
from .scene import stage_svg

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=IBM+Plex+Sans+Condensed:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap">')


def story_asset(story, name):
    with open(os.path.join(story.DIR, name), encoding='utf-8') as f:
        return f.read()


def engine_asset(name):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), name), encoding='utf-8') as f:
        return f.read()


def howto(L, lanes):
    first, rest = lanes[0], lanes[1:]
    ids = lambda fn: (L.fn_info[fn]['vhca'], int(L.fn_info[fn]['gvmi'], 16))  # noqa: E731
    who = 'utopx names the %s VHCA %s, the device knows it as GVMI %d' % ((first,) + ids(first))
    if rest:
        who += '; ' + ', '.join('%s is %s / GVMI %d' % ((fn,) + ids(fn)) for fn in rest)
    return ('<div class="howto"><div><b>Line numbers</b> are the log file\'s own. Each "⋯ lines not shown" row says what it '
            'leaves out: the commands by name first, then utopx bookkeeping. Open it, or "Raw log", to see the lines.[[crefs-note]]</div>'
            '<div><b>Two IDs per function.</b> %s.</div><div><b>Stage labels</b> are '
            'utopx\'s own HCA_STAGE_* for each function, as the log records them. FW-internal states are not in the log and '
            'are not drawn; where the stage shows something only the FW code tells, it says so.</div></div></section>') % who


def chip_steps(L, trans, st, lanes):
    """The HCA stage chips through one step: before its first command, then after each command, None for a command the
    log has no line for. A command's stage changes are the ones its own threads print, before or after its LOG_OP line
    (utopx prints a teardown change before the command, an init change after it); after the last command the chips
    show the step's end. None when no command has a line: the chips then show the step's end only."""
    lines = [c[4] if len(c) > 4 else None for c in st.choreo.get('cmds', [])]
    if not any(lines):
        return None
    op_at = {o['n']: o for o in L.ops}
    span = {}
    for n in lines:
        if n:
            own = L.op_lines(op_at[n]) if n in op_at else [n]
            span[n] = (min(own), max(own))
    first = next(n for n in lines if n)
    seq = [stage_at(trans, min(span[first][0], st.lines[0]) - 1, lanes)]
    for k, n in enumerate(lines):
        if not n:
            seq.append(None)
            continue
        nxt = next((m for m in lines[k + 1:] if m), None)
        seq.append(stage_at(trans, min(span[n][1], span[nxt][0] - 1) if nxt else st.lines[-1], lanes))
    return seq


def page(L, story, steps, facts, trans):
    f = facts
    fill = story.fill(L, f)
    t0 = f['t0']
    bodies, metas = [], []
    for i, st in enumerate(steps, 1):
        h, m = step_html(L, st, i, t0)
        bodies.append(h)
        metas.append(m)
    lanes = {fn: 40 + 38 * i for i, fn in enumerate(story.LANES)}
    runmap, mapx = run_map(L, metas, f, lanes, story.bands(L, f))
    stages = [stage_at(trans, m['last'], story.LANES) for m in metas]
    # the engine's style and stage script, with the story's after them (its script defines the hooks the engine calls)
    css = engine_asset('page.css') + ''.join(story_asset(story, n) for n in story.CSS_FILES)
    js = ''.join(story_asset(story, n) for n in story.JS_FILES) + engine_asset('stage.js')

    out = ['<title>%s</title>' % esc(story.TITLE), '<meta name="claude:viewport-fit-sides" content="cover">'] + list(FONTS) + [
        '<style>%s</style>' % css, '<div class="wrap">']
    out.append(story.hero(L, f))

    # stage + transport
    segs = []
    for fl in sorted(story.FLOWS):
        idxs = [k for k, m in enumerate(metas) if m['flow'] == fl]
        dots = ''.join('<button class="dot" type="button" aria-label="Step %d: %s"><span class="fill"></span></button>' % (
            k + 1, esc(metas[k]['title'])) for k in idxs)
        segs.append('<div class="fseg f%d" data-flow="%d" style="--n:%d"><span class="flab" title="Flow %d · %s">%d · %s</span>'
                    '<div class="dots">%s</div></div>' % (fl, fl, len(idxs), fl, esc(story.FLOWS[fl]['name']), fl,
                                                           story.FLOW_SHORT[fl], dots))
    out.append('<div class="stage-wrap"><div class="stage"><div class="scene-scroll">%s</div><div class="caption"><span class="cap-n" id="cap-n"></span>'
               '<div class="cap-text"><span class="cap-t" id="cap-t"></span><span class="cap-s" id="cap-s"></span></div></div></div>'
               '<div class="transport" role="group" aria-label="Playback">'
               '<button class="tbtn" id="t-prev" type="button" aria-label="Previous step"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M11 2.5v11L3.5 8z"/></svg></button>'
               '<button class="tbtn primary" id="t-play" type="button" aria-label="Play"></button>'
               '<button class="tbtn" id="t-next" type="button" aria-label="Next step"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M5 2.5v11L12.5 8z"/></svg></button>'
               '<div class="flowbar">%s</div><span class="stepcount" id="stepcount"></span>'
               '<button class="tbtn small" id="t-speed" type="button" aria-label="Playback speed">1×</button>'
               '<button class="tbtn small" id="t-mini" type="button" aria-pressed="false">Hide stage</button></div></div>' % (
                   stage_svg(L, story, f), ''.join(segs)))

    out.append('<main>')
    out.append('<section id="summary" class="panel"><h2>The run at a glance</h2><p class="sub">%s</p><div class="mapwrap">%s</div>' % (
        story.SUMMARY_SUB, runmap))
    out.append(story.callout(metas))
    out.append('<h2 style="margin-top:22px">FW slide statements against this log</h2><p class="sub">Not every statement can be '
               'seen from software. Those are marked as such, not counted as passed.</p><div class="tablewrap"><table class="score">'
               '<thead><tr><th>Flow</th><th>On the FW slides</th><th>In this log</th><th>What the log shows</th></tr></thead><tbody>')
    for fl, text, v, what, sid in story.statement_rows(f):
        lab, cls = story.VERDICT[v]
        k = next((i for i, m in enumerate(metas) if m['id'] == sid), None)
        link = ' <a href="#%s" data-go="%d">Step %d →</a>' % (sid, k, k + 1) if k is not None else ''
        out.append('<tr class="f%d"><td><span class="fl-tag">Flow %d</span></td><td><q>%s</q></td><td><span class="verdict %s">%s</span></td>'
                   '<td>%s%s</td></tr>' % (fl, fl, esc(text), cls, lab, what.format(**fill), link))
    out.append('</tbody></table></div>')
    out.append(howto(L, list(story.LANES)))

    prev_end = None
    k = 0
    for fl in sorted(story.FLOWS):
        F = story.FLOWS[fl]
        numbered = F['slide'][0][:2].isdigit()
        lis = ''.join('<li>%s</li>' % esc(x[3:] if numbered else x) for x in F['slide'])
        lst = 'ol' if numbered else 'ul'
        extra = story.flow_extra(fl, L, steps, trans, f, fill)
        out.append('<section class="flow f%d" id="flow-%d"><div class="flow-head"><h2><span class="fl">Flow %d</span>%s</h2>'
                   '<div class="fh-grid"><div><span class="lab">On the FW slides</span><%s>%s</%s><p class="bottomline"><span>Bottom '
                   'line</span> %s</p></div><div><span class="lab">In this log</span><p style="margin:6px 0 0">%s</p></div></div>%s</div>' % (
                       fl, fl, fl, esc(F['name']), lst, lis, lst, esc(F['bottom']), story.flow_intro(fl, f).format(**fill), extra))
        for st in steps:
            if st.flow != fl:
                continue
            if prev_end is not None:
                out.append(gap_html(L, prev_end, st.lines[0]))
            out.append(bodies[k])
            prev_end = st.lines[-1]
            k += 1
        out.append('</section>')
    out.append('</main>')
    out.append(story.footer(L, f))
    out.append('</div>')
    data = dict(steps=metas, stages=stages, choreo={st.sid: st.choreo for st in steps}, say={st.sid: st.caption for st in steps},
                chips={st.sid: chip_steps(L, trans, st, story.LANES) for st in steps})
    data.update(story.page_data(L, f, mapx))
    out.append('<script type="application/json" id="walk-data">%s</script>' % json.dumps(data, ensure_ascii=False).replace('</', '<\\/'))
    out.append('<script>%s</script>' % js)
    return '\n'.join(out)
