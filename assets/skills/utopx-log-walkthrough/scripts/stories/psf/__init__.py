"""PSF ICM global-mode story: the steps, the stage and the statements of a PSF walkthrough page.

It is also the template for a new story: copy this package, then change match(), the steps and the scene.
"""
import os

from wt.failure import failed, fatal_summary
from wt.fmt import GERRIT, GERRIT_UDRIVER, GERRIT_UTOPX, REDMINE, esc

from . import scene, statements, steps
from .refs import CODEREFS  # noqa: F401  (the engine reads story.CODEREFS)

NAME = 'psf'
TITLE = 'PSF Log Walkthrough v2'
LANES = steps.FN_ORDER
FLOWS = statements.FLOWS
FLOW_SHORT = {1: 'PSF init', 2: 'Consumers', 3: 'Runtime', 4: 'Teardown'}
CSS_FILES = ('story.css',)
JS_FILES = ('story.js',)
VERDICT = statements.VERDICT
DIR = os.path.dirname(os.path.abspath(__file__))
SUMMARY_SUB = ('Every tick is one command, placed by time. The PSF works at the two ends of the run; the PFs do everything in '
               'between. The line marks the step on the stage; the dots under the axis jump to a step.')

def match(L):
    """None when this story can tell the log; otherwise why not."""
    return None if 'PSF' in L.fn_info else 'the log has no PSF function'


def build_steps(L):
    st, facts = steps.build(L)
    for adjuster in (steps.add_udriver_step, steps.detail_caps_step, steps.name_pf_enable_step, steps.ps4_teardown):
        st = steps.adjust(adjuster, L, st, facts['skipped'])
    st = steps.finish(L, st, facts)
    facts['built'] = [s.sid for s in st]
    return st, facts


def fill(L, f):
    """Values the statements and the flow introductions format in."""
    pf_cmds = f['pf_ops']['PF0'] + f['pf_ops']['PF1']
    pf_obj = f['pf_create']['PF0'] + f['pf_create']['PF1']
    qps = sum(1 for fn, n in f['qp_pf'] if fn != 'PSF')
    mps = sum(1 for fn, n in f['mp_pf'] if fn != 'PSF')
    eqes = sum(f['eq_types'].values())
    cons = steps.consumers(L)
    q = steps.qp_mode(L, 'PSF', 1) or L.get_op('QUERY_PAGES', 'PSF')
    n = len(f['sizes'])
    return dict(psfcmds=f['pf_ops']['PSF'], nranges=n, ranges='%d range%s' % (n, '' if n == 1 else 's'), total=f'{f["total"]:,}',
                pfcmds=f'{pf_cmds:,}', pfobj=pf_obj, qps=qps, mps=mps, eqes=eqes, retin=f'{f["ret_in"]:,}',
                bootpages=steps.fval(L, q, 'num_pages'), iters=f['polls'],
                consumers=('the two host PFs' if len(cons) == 2 else 'one host PF, %s' % cons[0] if len(cons) == 1 else
                           '%s host PFs' % steps.words(len(cons))) + (
                    ' (%s runs as NODNIC)' % ' and '.join(steps.nodnic(L)) if steps.nodnic(L) else ''),
                consumer_names=' and '.join(sorted(cons)) or 'the PFs', each='It' if len(cons) == 1 else 'Each')


def result(L, f):
    """The Result line of the header."""
    v = f['verdict']
    if not failed(v) and v['passed']:
        return '<dd class="pass">TEST PASSED · %s commands · %d FATAL</dd>' % (f'{len(L.ops):,}', len(v['fatal']))
    fs = fatal_summary(L)
    return '<dd class="fail">%s · test status %s%s</dd>' % (
        'TEST FAILED' if v['failed'] else 'no TEST PASSED line', v['status'][1] if v['status'] else 'not printed',
        (' · MAIN_FATAL at <code class="logsrc">%s</code>%s: %s' % (fs['where'] or '?', ' in %s' % fs['func'] if fs['func'] else '',
                                                                   esc(fs['msg']))) if fs else '')


def hero(L, f):
    ri = L.info
    fns = ', '.join('%s %s' % (fn, L.fn_info[fn]['dbdf'][5:]) for fn in LANES if fn in L.fn_info)
    box = ' · '.join(x for x in (ri.get('box') or 'box not recorded', ri.get('device_name')) if x)
    fw = ri.get('fw') or ('%s (from the log)' % ri['fw_version'] if ri.get('fw_version') else 'not recorded')
    utopx = ri.get('utopx') or ('tree %s' % ri['tree'] if ri.get('tree') else 'not recorded')
    ud = ri.get('udriver')
    ud = ud['text'] if isinstance(ud, dict) else '%s (as the log prints it)' % ri.get('udriver_log')
    glob = next((e for e in ri.get('eopts', []) if 'icm_mng_global' in e), None)
    glob = 'global mode on via <code>-e %s</code>' % esc(glob) if glob else 'no <code>-e icm_mng_global…</code> option on the command line'
    run = 'seed %s · %s iterations × %s ops · %s · %s' % (ri.get('seed'), ri.get('iters'), ri.get('ops'), esc(ri.get('xml') or ''),
                                                         ri.get('run') or ri.get('started') or 'start time not recorded')
    return ('<header class="hero"><div class="eyebrow">PSF ICM global mode · utopx on ConnectX-8</div><h1>PSF Log Walkthrough</h1>'
            '<p class="lede">One utopx run, played back step by step. The stage shows what each command does to the PSF, the '
            'PFs and the pool, and how udriver maps the memory the PSF hands to FW; under it, the real log lines with every '
            'note right below the line it explains. Each step names the statement of the FW slides <i>PSF ICM global mode '
            'executive refresh</i> it shows, and says so when the run cannot show one.</p>\n'
            '<dl class="facts">'
            '<div><dt>Result</dt>%s</div>'
            '<div><dt>Box</dt><dd>%s · %s</dd></div>'
            '<div><dt>FW</dt><dd>%s</dd></div>'
            '<div><dt>utopx</dt><dd>%s · udriver %s · %s</dd></div>'
            '<div><dt>Run</dt><dd>%s</dd></div>'
            '<div><dt>Log</dt><dd>%s (%s lines)</dd></div></dl></header>') % (
                result(L, f), box, fns, fw.format(g=GERRIT, u=GERRIT_UTOPX), utopx.format(g=GERRIT, u=GERRIT_UTOPX), ud, glob,
                run, esc(os.path.basename(L.path)), f'{f["nlines"]:,}')


def scene_parts(L, f):
    return scene.parts(L, f, steps.udriver_numbers(L, f), L.info)


def bands(L, f):
    """Each flow's span on the run map, in seconds: PSF start, first PF start, last PF READY, first PF teardown, run end.
    A boundary the log does not have takes the one before it."""
    cons = steps.consumers(L)
    ens = [L.get_op('ENABLE_HCA', fn) for fn in cons]
    ready = [k for k in (L.first(r'VHCA=%s:GVMI=\w+:TYPE=PF has completed bringup' % L.fn_info[fn]['vhca']) for fn in cons) if k]
    tds = [o for o in L.ops if o['opcode'] == 'TEARDOWN_HCA' and o['fn'] in cons]
    b = [f['t0'], min(o['t'] for o in ens) if ens else None, L.tabs[max(ready)] if ready else None,
         min(o['t'] for o in tds) if tds else None, f['t_end']]
    for i in range(1, len(b)):
        b[i] = b[i - 1] if b[i] is None else b[i]
    return [(b[0], b[1]), (b[1], b[2]), (b[2], b[3]), (b[3], b[4])]


def callout(metas):
    ud = next((i for i, m in enumerate(metas) if m['id'] == 'psf-udriver'), None)
    if ud is None:
        return ''
    return ('<div class="udcallout"><span class="lab">Where udriver comes in</span><p>A PROVIDE_PAGES_RANGE gives FW one address '
            'and a page count, so the pool memory must be one contiguous window of device addresses. utopx gets that window '
            'from a new udriver call, <code>udriver_dma_map_v2(..., single_chunk_mapping = 1, ...)</code>, released in '
            'udriver 3.09 (<a href="%s1428108">1428108</a>). When utopx once used the old call for the first range (it set '
            'the global flag too late, #21), the range came out in 1024-page pieces and FW refused the PSF\'s INIT_HCA (#22).</p>'
            '<a class="jump" href="#psf-udriver" data-go="%d">Step %d: udriver '
            'maps the first range →</a></div>') % (GERRIT_UDRIVER, ud, ud + 1)


def statement_rows(f):
    return statements.score_rows(f)


def flow_intro(fl, f):
    return statements.flow_intro(fl, f)


def flow_extra(fl, L, st_list, trans, f, fl_fill):
    """The block under a flow's head: the pool bar (flow 1), the PFs side by side (flow 2), the runtime counts (flow 3)."""
    if fl == 1:
        if not f['sizes']:
            return ''
        n = len(f['sizes'])
        segs_html = ''.join('<span style="flex:%d" title="range %d: %s pages, %s–%s">%s</span>' % (
            s, i + 1, f'{s:,}', a[0], a[1], ('R%d · %.0f MiB' % (i + 1, s * 4096 / 2**20)) if s / f['total'] > 0.06 else 'R%d' % (i + 1))
            for i, (s, a) in enumerate(zip(f['sizes'], f['addr'])))
        leg = ' · '.join('R%d %s pages (%.0f MiB)' % (i + 1, f'{s:,}', s * 4096 / 2**20) for i, s in enumerate(f['sizes']))
        # the smallest range but the last, and how many pages were still left when it was drawn
        drew = ''
        if n > 1:
            small = min(range(n - 1), key=lambda i: f['sizes'][i])
            left = f['total'] - sum(f['sizes'][:small])
            drew = ' R%d drew %s of the %s pages left%s.' % (small + 1, f'{f["sizes"][small]:,}', f'{left:,}', (
                ', which is why its segment is so narrow') if f['sizes'][small] / f['total'] <= 0.06 else '')
        ud = next((i for i, s in enumerate(st_list) if s.sid == 'psf-udriver'), None)
        return ('<div><span class="lab">The pool: %s range%s, %s pages of 4 KiB, %.2f GiB</span><div class="poolbar">%s</div>'
                '<p class="udnote">%s. utopx draws all of it at random ([[ref:range_count_random]], '
                '[[ref:pool_size_conf]]): the pool size (512,000–1,280,000 pages), the number of '
                'ranges (1–6), and each range but the last anywhere from 1 page to what is still left; the last range '
                'takes the rest.%s Hover a segment for its IOVA range.</p>%s</div>') % (
                    steps.words(n), 's' if n != 1 else '', f'{f["total"]:,}', f['total'] * 4096 / 2**30, segs_html, leg, drew,
                    ('<p class="udnote">Before the first range goes out, udriver maps its %s pages as one IOVA window '
                     '(<a href="#psf-udriver" data-go="%d">step %d</a>).</p>' % (f'{f["sizes"][0]:,}', ud, ud + 1)) if ud is not None else '')
    if fl == 2:
        return steps.pf_side_by_side(L, st_list, trans)
    if fl == 3:
        pf_obj = f['pf_create']['PF0'] + f['pf_create']['PF1']
        names = ' and '.join(fn for fn in ('PF0', 'PF1') if f['pf_ops'][fn]) or 'the PFs'
        qnz = sum(1 for fn, x in f['qp_pf'] if fn not in (None, 'PSF') and x)
        mnz = sum(1 for fn, x in f['mp_pf'] if fn not in (None, 'PSF') and x)
        return ('<div class="statgrid"><div class="stat"><div class="v">%s</div><div class="k">commands from %s, %d of '
                'them creating objects</div></div><div class="stat"><div class="v">%d of %d</div><div class="k">PF QUERY_PAGES '
                'replies asking for pages</div></div><div class="stat"><div class="v">%d of %d</div><div class="k">PF MANAGE_PAGES '
                'carrying a page</div></div><div class="stat"><div class="v">%d of %d</div><div class="k">events that are page '
                'requests (%d checks, one per iteration)</div></div></div>') % (
                    fl_fill['pfcmds'], names, pf_obj, qnz, fl_fill['qps'], mnz, fl_fill['mps'], f['eq_types'].get('0x0b', 0),
                    fl_fill['eqes'], f['polls'])
    return ''


def footer(L, f):
    return ('<footer>Built from %s with skill <code>utopx-log-walkthrough</code> (story psf). FW slides: <i>PSF ICM global mode '
            'executive refresh</i> (15 Oct 2026). <a href="%s1519292">1519292</a> fixes the second-range rejection; %s; '
            '<a href="%s1428108">1428108</a> adds <code>udriver_dma_map_v2</code>.</footer>') % (
                esc(os.path.basename(L.path)), GERRIT,
                ('<a href="%s5357823">Redmine 5357823</a> tracks the PSF\'s DISABLE_HCA after teardown' % REDMINE) if f['ret_in'] else
                ('<a href="%s1537640">1537640</a> lets FW accept the PSF\'s DISABLE_HCA after teardown (<a href="%s5357823">Redmine '
                 '5357823</a>)' % (GERRIT, REDMINE)), GERRIT_UDRIVER)


def page_data(L, f, mapx):
    """Story keys of the page data the stage script reads."""
    return dict(sizes=f['sizes'], addr=[[a[0], a[1]] for a in f['addr']], mapX=mapx,
                pfCmds=f['pf_ops']['PF0'] + f['pf_ops']['PF1'], events=sum(f['eq_types'].values()), iters=f['polls'])
