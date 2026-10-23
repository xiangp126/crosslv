"""The stage drawing: the engine's frame around the story's device side.

The engine draws the host and device zones, one row per function (name, PCI address and GVMI, the HCA stage chip, the
rail to the device), the token layer and the pass or fail banner. The story's scene_parts(L, f) gives the title, the
three zone labels, the device side (under the tokens) and its overlays (over them).
"""
from .fmt import esc

DEFS = ('<defs><pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
        '<rect width="6" height="6" class="hatch-bg"/><line x1="0" y1="0" x2="0" y2="6" class="hatch-line"/></pattern>'
        '<marker id="arr" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        '<path d="M0 0L8 4L0 8z" class="arrhead"/></marker></defs>')


def stage_svg(L, story, f):
    parts = story.scene_parts(L, f)
    lanes = list(story.LANES)
    extra = 60 * max(0, len(lanes) - 3)          # three rows fit the standard height; each more adds 60
    v = f['verdict']
    passed = bool(v['passed'] and v['status'] and v['status'][1] == 0)
    banner = 'TEST PASSED · test status 0' if passed else 'TEST FAILED · test status %s' % (v['status'][1] if v['status'] else '?')
    p = ['<svg class="scene" id="scene" viewBox="0 0 1000 %d" role="img" aria-labelledby="scene-title">'
         '<title id="scene-title">%s</title>%s' % (236 + extra, esc(parts['title']), DEFS)]
    p.append('<rect class="zone host" x="6" y="22" width="292" height="%d" rx="10"/>'
             '<text class="zlab" x="20" y="16">%s</text>'
             '<rect class="zone dev" x="652" y="22" width="342" height="%d" rx="10"/>'
             '<text class="zlab" x="666" y="16">%s</text>'
             '<text class="zlab mid" x="475" y="16" text-anchor="middle">%s</text>' % (
                 204 + extra, esc(parts['host']), 204 + extra, esc(parts['device_label']), esc(parts['link'])))
    for i, fn in enumerate(lanes):
        y = 64 + 60 * i
        c = fn.lower()
        info = L.fn_info.get(fn)
        sub = '%s · GVMI %d' % (info['dbdf'][5:], int(info['gvmi'], 16)) if info else 'not in this log'
        p.append('<g class="fnrow %s" id="row-%s" data-fn="%s" data-y="%d"><rect class="fnbox" x="14" y="%d" width="280" height="44" rx="8"/>'
                 '<circle class="fndot" cx="38" cy="%d" r="6"/>'
                 '<text class="fnname" x="52" y="%d">%s</text><text class="fnsub" x="52" y="%d">%s</text>'
                 '<rect class="chip-bg" id="chipbg-%s" x="160" y="%d" width="128" height="22" rx="11"/>'
                 '<text class="chip-t" id="chip-%s" x="224" y="%d" text-anchor="middle">DISABLED_HCA</text></g>' % (
                     c, c, fn, y, y - 22, y, y - 3, fn, y + 13, sub, c, y - 11, c, y + 4))
        p.append('<line class="rail %s" x1="298" x2="652" y1="%d" y2="%d"/>' % (c, y, y))
    p.append(parts['device'])
    p.append('<g id="tokens"></g>')
    p.append(parts['overlays'])
    p.append('<g id="banner" class="banner%s"><rect x="664" y="%d" width="318" height="36" rx="8"/>'
             '<text x="823" y="%d" text-anchor="middle">%s</text></g>' % ('' if passed else ' fail', 184 + extra, 207 + extra, banner))
    p.append('</svg>')
    return ''.join(p)
