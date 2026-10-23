"""The run map: every command as a tick on its function's lane, by time, with the flow bands and a dot per step."""
import collections

def run_map(L, metas, facts, lanes, bands):
    """lanes: function -> y; bands: [(start, end)] in seconds, one per flow."""
    t0, t1 = facts['t0'], facts['t_end']
    W, X0, X1 = 1000, 56, 988

    def x(t):
        return X0 + (t - t0) / (t1 - t0) * (X1 - X0)
    names = list(lanes)
    who = names[0] if len(names) == 1 else ', '.join(names[:-1]) + ' and ' + names[-1]
    out = ['<svg class="runmap" viewBox="0 0 %d 176" role="img" aria-label="Every command of the run by time: %s">' % (W, who)]
    for i, (a, b) in enumerate(bands, 1):
        out.append('<rect class="band f%d" x="%.1f" y="16" width="%.1f" height="118"/>' % (i, x(a), max(1.5, x(b) - x(a))))
        out.append('<text class="bandlab f%d" x="%.1f" y="11">Flow %d</text>' % (i, x(a) + 2, i))
    for name, y in lanes.items():
        out.append('<line class="lane" x1="%d" x2="%d" y1="%d" y2="%d"/><text class="lanelab" x="%d" y="%d">%s</text>' % (
            X0, X1, y, y, X0 - 8, y + 4, name))
    ticks = collections.defaultdict(list)
    for op in L.ops:
        ticks[op['fn']].append(x(op['t']))
    for fn, xs in ticks.items():
        y = lanes[fn]
        d = ''.join('M%.1f %dv14' % (xx, y - 7) for xx in xs)
        out.append('<path class="tick %s" d="%s"/>' % (fn.lower(), d))
    for s in range(0, int(t1 - t0) + 1, 2):
        xx = x(t0 + s)
        out.append('<line class="axis" x1="%.1f" x2="%.1f" y1="134" y2="139"/><text class="axlab" x="%.1f" y="168">%d s</text>' % (xx, xx, xx, s))
    for i, m in enumerate(metas):
        xx = x(t0 + m['rel'])
        out.append('<a href="#%s" class="smark f%d" data-go="%d" aria-label="Step %d"><circle cx="%.1f" cy="149" r="4.5"/></a>' % (
            m['id'], m['flow'], i, i + 1, xx))
    out.append('<g class="playhead" id="playhead"><line x1="0" x2="0" y1="16" y2="134"/><path d="M-5 16h10l-5 6z"/></g>')
    out.append('</svg>')
    xs = [round(x(t0 + m['rel']), 1) for m in metas]
    return '\n'.join(out), xs
