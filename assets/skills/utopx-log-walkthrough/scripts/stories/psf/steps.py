"""PSF story: the steps. Each one picks log lines, marks fields on them and writes the notes, the stage caption
and the stage choreography, both computed from the log by stage()."""
import collections
import copy
import re

from wt.fmt import GERRIT, GERRIT_AUTOMATION, GERRIT_UDRIVER, GERRIT_UTOPX, REDMINE, esc
from wt.log import NUMRE, secs
from wt.model import Skip, Step
from wt.render import op_fields, transitions_of

from .scene import udriver_explainer

FN_ORDER = ('PSF', 'PF0', 'PF1')

WORDS = ('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen '
         'eighteen nineteen').split()
TENS = 'twenty thirty forty fifty sixty seventy eighty ninety'.split()
ORDINALS = 'first second third fourth fifth sixth seventh eighth ninth tenth'.split()


def words(n):
    """A count in words up to 99, digits beyond."""
    if n < 20:
        return WORDS[n]
    if n < 100:
        return TENS[n // 10 - 2] + ('' if n % 10 == 0 else '-' + WORDS[n % 10])
    return f'{n:,}'


def ordinal(n):
    return ORDINALS[n - 1] if 1 <= n <= len(ORDINALS) else '%dth' % n


def reply(L, o, dump):
    """Status and syndrome of a command's reply dump (dump = e.g. 'manage_pages_out') as ints, and the line and time the
    dump starts at; {} when the command has no reply in the log."""
    k = next((k for k in L.op_lines(o) if '-------- %s --------' % dump in L.lines[k]), None)
    if k is None:
        return {}
    got = dict(line=k, time=L.rec[k][2] if k in L.rec else None)
    for j in range(k + 1, min(k + 5, len(L.lines))):
        m = re.match(r'\s*(status|syndrome)\s*:\s*(0x[0-9a-f]+)', L.lines[j])
        if m:
            got.setdefault(m.group(1), int(m.group(2), 16))
    return got


def reply_status(L, o, dump):
    """The status in a command's reply dump, or None."""
    return reply(L, o, dump).get('status')


def consumers(L):
    """The functions that enable themselves as HCAs after the PSF, in the order of their ENABLE_HCA."""
    ens = [o for o in (L.get_op('ENABLE_HCA', fn) for fn in L.fn_info if fn != 'PSF') if o]
    return [o['fn'] for o in sorted(ens, key=lambda o: o['n'])]


def pfs(fns):
    """How a sentence names a group of functions: 'PF0', 'the two PFs', 'the three PFs'."""
    return fns[0] if len(fns) == 1 else 'the %s PFs' % words(len(fns))


def qp_mode(L, fn, mode):
    """The QUERY_PAGES a function sends with that op_mod (1 boot, 2 init, 3 regular), or None."""
    for o in L.ops:
        if o['fn'] == fn and o['opcode'] == 'QUERY_PAGES':
            v = op_fields(L, o, {'op_mod'}).get('op_mod')
            if v and int(v[1], 16) == mode:
                return o
    return None


def disable_before(L, o):
    """The last DISABLE_HCA a function other than the PSF sends before a command, or None."""
    ds = [d for d in L.ops if d['opcode'] == 'DISABLE_HCA' and d['fn'] != 'PSF' and d['n'] < o['n']]
    return ds[-1] if ds else None


def nodnic(L):
    """Functions that run as NODNIC: NODNIC_* commands and no ENABLE_HCA."""
    return [fn for fn in L.fn_info if fn != 'PSF' and not L.get_op('ENABLE_HCA', fn)
            and any(o['fn'] == fn and o['opcode'].startswith('NODNIC_') for o in L.ops)]

# One sentence per step for the stage caption.
def udriver_notes(L, fpa, ri):
    """The notes of the udriver step. fpa: the line where utopx prints the first range's first and last page address."""
    first, last, npages = re.search(r'first page address=(0x[0-9a-f]+), and the last page address=(0x[0-9a-f]+).*'
                                    r'number of pages=(0x[0-9a-f]+)', L.lines[fpa]).groups()
    pages = int(npages, 16)
    contiguous = int(last, 16) - int(first, 16) == (pages - 1) * 4096
    ud = ri.get('udriver')
    return {
        1: ('utopx loads udriver <b>%s</b> at start; the log prints it as %s because <code>CheckUdriverVersion()</code> prints '
            'major.minor without padding. Artifact <code>%s</code>, pinned in <code>build.sh</code> by '
            '<a href="%s1526478">1526478</a>. 3.09 is the first released udriver that has <code>udriver_dma_map_v2()</code>, '
            'added by <a href="%s1428108">1428108</a>.' % (ud['version'], ri.get('udriver_log'), ud['artifact'], GERRIT_UTOPX,
                                                           GERRIT_UDRIVER)) if isinstance(ud, dict) else
           ('utopx loads udriver %s at start, as the log prints it (major.minor without padding: 3.9 is 3.09). '
            '<code>udriver_dma_map_v2()</code> is in udriver 3.09 and later (<a href="%s1428108">1428108</a>).' % (
                ri.get('udriver_log') or '(version not printed)', GERRIT_UDRIVER)),
        2: 'utopx needs %s pages (%.0f MiB) for the first range.' % (f'{pages:,}', pages * 4096 / 2**20),
        3: 'One buffer of %s bytes (%s × 4096). Global mode is on in the PSF\'s page ledger, so <code>DmaDesc</code> '
           'asks for a single-chunk mapping and <code>FunctionHandle</code> calls '
           '<code>udriver_dma_map_v2(dev, mem, len, single_chunk_mapping = 1, &amp;dma)</code>.' % (f'{pages * 4096:,}', f'{pages:,}'),
        4: (('<b>One contiguous IOVA window</b>: %s pages from <code>%s</code> to <code>%s</code> with no gap, '
             'last − first = (%s − 1) × 4 KiB. ' % (npages, first, last, npages)) if contiguous else
            ('<b>Not one window</b>: %s pages from <code>%s</code> to <code>%s</code>, but last − first is not (%s − 1) × 4 KiB. '
             % (npages, first, last, npages))) +
           'utopx checks exactly this before it sends the range '
           '([[ref:range_contiguous]]); the first address and the page count are all FW receives. Pinning and mapping '
           'took %(dur).1f s (%(a)s → %(b)s).',
    }


def facts_of(L):
    """Values several steps and the page use, computed once. A missing piece is None or empty, never an error; what an
    earlier version asserted is a check now (facts['checks']), and a failed check shows up in the statements table."""
    ops = L.ops
    psf_en = L.get_op('ENABLE_HCA', 'PSF')
    t0 = psf_en['t'] if psf_en else ops[0]['t']
    ranges = [o for o in ops if o['fn'] == 'PSF' and o['opcode'] == 'MANAGE_PAGES' and 'PROVIDE_PAGES_RANGE' in o['rest']]
    sizes = [int(re.search(NUMRE, o['rest']).group(1), 16) for o in ranges]
    addr = []
    for o in ranges:
        k = next((k for k in L.op_lines(o) if 'The first page address' in L.lines[k]), None)
        m = k and re.search(r'first page address=(0x[0-9a-f]+), and the last page address=(0x[0-9a-f]+)', L.lines[k])
        addr.append((m.group(1), m.group(2), k) if m else (None, None, k))
    total = sum(sizes)
    # A run with the local WA returns the PSF's pages at teardown; 1533759 PS4 sends no such command.
    ret = next((o for o in ops if o['fn'] == 'PSF' and o['opcode'] == 'MANAGE_PAGES' and 'RECLAIM_PAGES' in o['rest']), None)
    ret_in = int(re.search(NUMRE, ret['rest']).group(1), 16) if ret else 0

    pf_ops = collections.Counter(o['fn'] for o in ops)
    pf_create = collections.Counter(o['fn'] for o in ops if re.match(r'(CREATE_|ALLOC_)', o['opcode']))
    kinds = collections.Counter(o['opcode'] for o in ops if o['fn'] != 'PSF' and re.match(r'(CREATE_|ALLOC_)', o['opcode']))
    eq_types = collections.Counter()
    for n in L.findall(r'-------- eqe_head --------'):
        for k in range(n + 1, n + 4):
            m = re.search(r'event_type\s*:\s*(0x[0-9a-f]+)', L.lines[k])
            if m:
                eq_types[m.group(1)] += 1
                break
    polls = L.findall(r'Handling Pages events\.\.\.')
    polls_done = L.findall(r'Handling Pages events done')
    psf_eq = [o for o in ops if o['fn'] == 'PSF' and 'EQ' in o['opcode']]
    qp_pf = []
    for n in L.findall(r'-------- query_pages_out --------'):
        th = L.owner[n]
        fn = None
        for o in ops:
            if o['opcode'] == 'QUERY_PAGES' and th.split(':', 1)[1] == o['thr'].split(':', 1)[1]:
                fn = o['fn']
        num = next((int(re.search(r'num_pages\s*:\s*(0x[0-9a-f]+)', L.lines[k]).group(1), 16)
                    for k in range(n, n + 12) if 'num_pages' in L.lines[k]), None)
        qp_pf.append((fn, num))
    mp_pf = []
    for n in L.findall(r'-------- manage_pages_in --------'):
        th = L.owner[n]
        fn = next((o['fn'] for o in ops if o['opcode'] == 'MANAGE_PAGES' and o['thr'].split(':', 1)[1] == th.split(':', 1)[1]), None)
        ent = next((int(re.search(r'input_num_entries\s*:\s*(0x[0-9a-f]+)', L.lines[k]).group(1), 16)
                    for k in range(n, n + 12) if 'input_num_entries' in L.lines[k]), None)
        mp_pf.append((fn, ent))
    v = L.verdict()
    status = v['status']
    end = status[0] if status and status[0] in L.tabs else max(L.rec)
    checks = dict(
        return_all=not ret or total == ret_in,                          # the PSF's return asks for every page it gave
        polls_paired=len(polls) == len(polls_done),                    # every page-request check finishes
        pf_query_zero=all(num == 0 for fn, num in qp_pf if fn != 'PSF'),   # no PF is told to supply a page
        pf_manage_zero=all(e == 0 for fn, e in mp_pf if fn != 'PSF'),      # no PF MANAGE_PAGES carries a page
        psf_no_eq=not psf_eq,                                          # the PSF creates no event queue
        no_page_request='0x0b' not in eq_types)                        # no page-request event arrives
    return dict(t0=t0, t_end=L.tabs[end], sizes=sizes, total=total, ret=ret, ret_in=ret_in, pf_ops=pf_ops,
                pf_create=pf_create, kinds=kinds, eq_types=eq_types, polls=len(polls), polls_done=len(polls_done),
                poll_lines=polls, polls_done_lines=polls_done, psf_eq=len(psf_eq), qp_pf=qp_pf, mp_pf=mp_pf,
                passed=v['passed'], status0=status[0] if status and status[1] == 0 else None, verdict=v, checks=checks,
                nlines=len(L.lines) - 1, addr=addr, ranges=ranges, skipped=[])


def build(log):
    """The PSF steps in log order. A step whose commands or lines the log does not have is left out; facts['skipped'] says why."""
    L = log
    PSF = L.fn_info['PSF']
    ops = L.ops
    facts = facts_of(L)
    t0 = facts['t0']
    ranges, sizes, addr, total = facts['ranges'], facts['sizes'], facts['addr'], facts['total']
    ret, ret_in = facts['ret'], facts['ret_in']
    eq_types, polls, polls_done = facts['eq_types'], facts['poll_lines'], facts['polls_done_lines']
    qp_pf, mp_pf = facts['qp_pf'], facts['mp_pf']
    passed, status0 = facts['passed'], facts['status0']

    def opl(o, fields=None, keep=()):
        return [k for k in L.op_lines(o) if L.keep(k, fields, keep)]

    def op(opcode, fn, nth=0, rest=None):
        o = L.get_op(opcode, fn, nth=nth, rest=rest)
        if o is None:
            raise Skip('no %s from %s%s' % (opcode, fn, ' (number %d)' % (nth + 1) if nth else ''))
        return o

    def find(rx, after=0):
        n = L.first(rx, after)
        if n is None:
            raise Skip('no line matches %s' % rx)
        return n

    S, skipped = [], facts['skipped']

    def add(builder):
        """Build one step now. A step the log cannot show is left out, with the reason in facts['skipped']."""
        try:
            S.append(builder())
        except Skip as e:
            skipped.append((builder.__name__, str(e)))
        except (IndexError, KeyError, StopIteration, AttributeError, TypeError, ValueError, ZeroDivisionError) as e:
            skipped.append((builder.__name__, 'error %s: %s' % (type(e).__name__, e)))
        return builder

    mib = lambda pages: pages * 4096 / 2**20  # noqa: E731

    @add
    def psf_enable():
        o_en = op('ENABLE_HCA', 'PSF')
        quick = find(r'Performing Quick Init on vhca VHCA=%s' % PSF['vhca'])
        return Step('psf-enable', 1, 'utopx starts with the PSF: ENABLE_HCA', [quick] + opl(o_en), [
            (r'Performing Quick Init on vhca VHCA=0x[0-9a-f]+:GVMI=0x[0-9a-f]+:TYPE=PSF', 1),
            (r'function_id : 0x0000', 2),
            (r'HCA_STAGE_DISABLED_HCA --> HCA_STAGE_ENABLED_HCA', 3), (r'status : 0x00', 3),
        ], {
            1: 'The first function utopx brings up is the PSF: VHCA %s in utopx\'s model, GVMI %s on the device, PCI %s. '
               'The two PFs send nothing until it is done.' % (PSF['vhca'], int(PSF['gvmi'], 16), PSF['dbdf'][5:]),
            2: '<code>function_id 0</code>: the PSF enables itself.',
            3: 'FW accepts. utopx moves its model of the PSF from DISABLED_HCA to ENABLED_HCA.',
        }, slide=[(1, '01 ENABLE_HCA')])

    @add
    def psf_issi():
        qi, si = op('QUERY_ISSI', 'PSF'), op('SET_ISSI', 'PSF')
        lq, ls = set(L.op_lines(qi)), set(L.op_lines(si))
        mask_rx = r'supported_issi\s*\[\s*([0-9a-f]+)\s*\]\s*:\s*(0x[0-9a-f]+)'
        mask = [(int(m.group(1), 16), int(m.group(2), 16)) for k in sorted(lq) for m in [re.search(mask_rx, L.lines[k])] if m]
        # the mask is a byte array, most significant byte first: bit b of byte j is ISSI (len - 1 - j) * 8 + b
        issis = [(len(mask) - 1 - j) * 8 + b for j, v in mask for b in range(8) if v >> b & 1]
        cur, setv = fval(L, qi, 'current_issi'), fval(L, si, 'current_issi')
        fields = {'current_issi', 'status', 'syndrome'}
        lines = opl(qi, fields, keep=(r'supported_issi\s*\[\s*[0-9a-f]+\s*\]\s*:\s*0x0*[1-9a-f]',)) + opl(si, fields)
        return Step('psf-issi', 1, 'QUERY_ISSI and SET_ISSI: the command interface version', lines, [
            (r'QUERY_ISSI : \[G\]\[VHCA=0x[0-9a-f]+', 1), (r'HCA_STAGE_ENABLED_HCA --> HCA_STAGE_QUERY_ISSI', 1),
            (r'current_issi : 0x[0-9a-f]+', 2, lq), (r'supported_issi \[[0-9a-f]+ \] : 0x0*[1-9a-f][0-9a-f]*', 2),
            (r'setting issi= 0x[0-9a-f]+', 3), (r'HCA_STAGE_QUERY_ISSI --> HCA_STAGE_SET_ISSI', 3),
            (r'current_issi : 0x[0-9a-f]+', 3, ls), (r'status : 0x00', 3, ls),
        ], {
            1: 'Right after ENABLE_HCA, before any page command, utopx asks FW which versions of the command interface it '
               'supports (ISSI). It moves the PSF to QUERY_ISSI in its own model as it sends.',
            2: 'FW answers: current ISSI %s, and the <code>supported_issi</code> bit mask has %s set%s.' % (
                cur, 'only bit %d' % issis[0] if len(issis) == 1 else 'bits %s' % ', '.join(map(str, issis)) if issis else 'no bit',
                ' (its last byte reads 0x%02x, every other byte 0)' % mask[-1][1] if mask and len(issis) == 1 and issis[0] < 8 else ''),
            3: 'utopx sets ISSI %s (<code>setting issi= 0x%x</code>) and %s. The PSF is at SET_ISSI; its next command is the '
               'boot QUERY_PAGES.' % (setv, setv or 0, 'FW accepts' if reply_status(L, si, 'set_issi_out') == 0 else 'FW refuses it'),
        }, slide=[])

    @add
    def psf_query_pages():
        o_qp = op('QUERY_PAGES', 'PSF')
        return Step('psf-query-pages', 1, 'QUERY_PAGES (boot): the device offers global mode', opl(o_qp), [
            (r'op_mod : 0x0001 boot_pages', 1),
            (r'icm_mng_global : 0x1', 2),
            (r'num_pages : 0x00000019', 3),
        ], {
            1: 'Boot-pages query, sent before INIT_HCA.',
            2: '<b>icm_mng_global = 1.</b> The device reports that ICM global mode is available for this function. '
               'utopx takes the global-mode path because of this bit.',
            3: '<b>num_pages = 0x19 (25).</b> utopx records the boot-page count from this reply; nothing is hard-coded. '
               '<span class="gapnote">utopx has no expected value for either field on the PSF; it only fails a run '
               'when a non-PSF function reports icm_mng_global = 1.</span>',
        }, slide=[(1, '02 QUERY_PAGES (BOOT)'), (1, 'QUERY_PAGES tells software whether ICM global mode is supported.'),
                  (1, 'Trust QUERY_PAGES rather than hard-coding NUM_BOOT_PAGES.')])

    @add
    def psf_range_1():
        if not ranges:
            raise Skip('the PSF sends no PROVIDE_PAGES_RANGE')
        o_r1 = ranges[0]
        return Step('psf-range-1', 1, 'MANAGE_PAGES with the first range turns global mode on', opl(o_r1), [
            (r'AllocPages: requesting numPages: \d+', 1), (r'first page address=0x[0-9a-f]+', 1), (r'last page address=0x[0-9a-f]+', 1),
            (r'op_mod : 0x0003 ALLOCATION_SUCCESS_RANGE', 2),
            (r'function_id : 0x0000', 3),
            (r'icm_mng_global : 0x1', 4),
            (r'status : 0x00', 5),
        ], {
            1: 'utopx allocates %s pages (%.0f MiB) as one contiguous IOVA range, %s to %s.' % (
                f'{sizes[0]:,}', mib(sizes[0]), addr[0][0], addr[0][1]),
            2: '<code>ALLOCATION_SUCCESS_RANGE</code> (PROVIDE_PAGES_RANGE): one command describes the whole range, '
               'instead of a list of page addresses.',
            3: '<code>function_id 0</code>: self-target addressing before INIT_HCA.',
            4: 'Software asks for global mode with this first range.',
            5: 'FW accepts: the PSF now owns a pool.',
        }, slide=[(1, '03 MANAGE_PAGES: enable global mode + first range'),
                  (1, 'Global mode turns on when PSF supplies the first ICM range in MANAGE_PAGES.'),
                  (1, 'Pre-init uses self-target addressing.')])

    @add
    def psf_ranges():
        if len(ranges) < 2:
            raise Skip('the run sends %d range' % len(ranges))
        n_more = len(ranges) - 1
        status = [reply_status(L, o, 'manage_pages_out') for o in ranges[1:]]
        ok = sum(1 for x in status if x == 0)
        more = []
        for o in ranges[1:]:
            more += [k for k in L.op_lines(o) if L.keep(k, fields={'input_num_entries', 'status', 'syndrome'}, keep=(r'The first page address',))
                     and not re.search(r'Verifying MANAGE|AllocPages', L.lines[k])]
        trans = find(r'TYPE=PSF HCA_STAGE_BOOT_PAGES_QUERY --> HCA_STAGE_BOOT_PAGES_ALLOCTED')
        r2 = set(L.op_lines(ranges[1]))
        title = '%s more range%s, %s' % (words(n_more).capitalize(), 's' if n_more > 1 else '',
                                        ('all accepted' if n_more > 1 else 'accepted') if ok == n_more else
                                        '%d accepted, %d rejected' % (ok, n_more - ok))
        return Step('psf-ranges', 1, title, more + [trans], [
            (r'status : 0x00', 1, r2), (r'syndrome : 0x00000000', 1, r2),
            (r'input_num_entries : 0x[0-9a-f]+', 2),
            (r'HCA_STAGE_BOOT_PAGES_QUERY --> HCA_STAGE_BOOT_PAGES_ALLOCTED', 3),
        ], {
            1: '<b>The second range is accepted.</b> Before <a href="%s1519292">1519292</a> (PS10) the FW rejected it with syndrome '
               '<code>0xFF2C2D</code>: on 10-17, 12 of 15 seeds stopped at exactly this command. This image has the fix.' % GERRIT,
            2: ('Ranges 2 to %d: %s pages.' % (len(sizes), ', '.join(f'{s:,}' for s in sizes[1:]))) if n_more > 1 else
               'Range 2: %s pages.' % f'{sizes[1]:,}',
            3: 'After the %s range the pool holds %s pages in %d ranges (%.2f GiB). utopx marks the boot pages done.' % (
                ordinal(len(sizes)), f'{total:,}', len(sizes), total * 4096 / 2**30),
        }, slide=[(1, '04 MANAGE_PAGES: optional extra ranges')])

    @add
    def psf_caps():
        o_cap = op('QUERY_HCA_CAP', 'PSF', rest='MaximumCap GeneralDeviceCap')
        o_cur = op('QUERY_HCA_CAP', 'PSF', rest='CurrentCap GeneralDeviceCap')
        cf = {'op_mod', 'page_request_disable', 'icm_mng_function_id_mode', 'fast_teardown', 'max_num_eqs'}
        return Step('psf-caps', 1, 'Capabilities read after the ranges', opl(o_cap, cf) + opl(o_cur, cf), [
            (r'page_request_disable : 0x1', 1),
            (r'icm_mng_function_id_mode : 0x1', 2),
        ], {
            1: '<b>page_request_disable = 1.</b> FW sets this bit when global mode is on or the function is not a page supplier '
               '(<code>is_page_request_disable_cur_cap_sup()</code>). For the PSF it means global mode is now on. '
               'The PSF never creates an event queue in this run (0 CREATE_EQ on it) and still completes INIT_HCA. '
               '<span class="gapnote">utopx does not check this bit against global mode yet (FWV uArch §3.2 item 3).</span>',
            2: '<b>icm_mng_function_id_mode = 1</b> (<code>FUNCTION_ID_TYPE_VHCA_ID</code>): after INIT_HCA, page commands name a '
               'function by its VHCA ID. The teardown below uses it.',
        }, slide=[(1, 'PSF self-bootstrap does not require a page-request EQ.'), (1, 'Post-init uses target VHCA IDs.')])

    @add
    def psf_init():
        o_init = op('INIT_HCA', 'PSF')
        return Step('psf-init', 1, 'INIT_HCA: the PSF is READY', opl(o_init), [
            (r'HCA_STAGE_INIT_PAGES_ALLOCTED --> HCA_STAGE_READY', 1), (r'has completed bringup flow, is now in state HCA_STAGE_READY', 1),
            (r'status : 0x00', 2),
        ], {
            1: 'utopx marks the PSF READY.',
            2: 'FW answers INIT_HCA with status 0 at %s, %.1f s after ENABLE_HCA. Most of that time went into allocating and '
               'mapping %.2f GiB of host memory for the ranges.' % (
                L.rec[[k for k in L.op_lines(o_init) if 'init_hca_out' in L.lines[k]][0]][2],
                secs(L.rec[[k for k in L.op_lines(o_init) if 'init_hca_out' in L.lines[k]][0]][2]) - t0, total * 4096 / 2**30),
        }, slide=[(1, '05 INIT_HCA'), (1, 'PSF finishes its own bootstrap before any dependent network function starts.')])

    @add
    def pf_enable():
        o_init = op('INIT_HCA', 'PSF')
        ens = [op('ENABLE_HCA', fn) for fn in consumers(L)]
        if not ens:
            raise Skip('no PF sends ENABLE_HCA')
        e1 = ens[0]
        psf_ready_reply = [k for k in L.op_lines(o_init) if 'init_hca_out' in L.lines[k]][0]
        gen_only = lambda o: [k for k in opl(o) if L.owner[k].startswith('GEN')]  # noqa: E731
        who = 'Both PFs enable themselves' if len(ens) == 2 else '%s enables itself' % e1['fn'] if len(ens) == 1 else \
            'All %s PFs enable themselves' % words(len(ens))
        nod = nodnic(L)
        return Step('pf-enable', 2, 'The PFs start only after the PSF', [k for o in ens for k in gen_only(o)], [
            (r'ENABLE_HCA : \[G\]\[VHCA=0x[0-9a-f]+:GVMI=0x[0-9a-f]+:', 1),
            (r'HCA_STAGE_DISABLED_HCA --> HCA_STAGE_ENABLED_HCA', 2),
        ], {
            1: 'First PF command at %s, %.2f s after FW answered the PSF\'s INIT_HCA (%s). %s '
               '(<code>function_id 0</code>), the way a host driver does.%s' % (
                   e1['time'], secs(e1['time']) - secs(L.rec[psf_ready_reply][2]), L.rec[psf_ready_reply][2], who,
                   (' %s run%s as NODNIC: no ENABLE_HCA, QUERY_PAGES or INIT_HCA.' % (' and '.join(nod), 's' if len(nod) == 1 else ''))
                   if nod else ''),
            2: '%s enabled.' % ' and '.join(o['fn'] for o in ens),
        }, slide=[(2, 'PSF readiness gates dependent function initialization.')])

    @add
    def pf0_boot_pages():
        q0 = qp_mode(L, 'PF0', 1)
        if q0 is None:
            raise Skip('no boot QUERY_PAGES from PF0')
        m0 = L.get_op('MANAGE_PAGES', 'PF0', after=q0['n'])
        if m0 is None:
            raise Skip('no MANAGE_PAGES from PF0 after its boot QUERY_PAGES')
        return Step('pf0-boot-pages', 2, 'PF0 boot pages: the device needs none from software', opl(q0) + opl(m0), [
            (r'op_mod : 0x0001 boot_pages', 1),
            (r'num_pages : 0x00000000', 2),
            (r'icm_mng_global : 0x0', 3),
            (r'AllocPages: requesting numPages: 0', 4), (r'input_num_entries : 0x00000000', 4), (r'output_num_entries : 0x00000000', 4),
        ], {
            1: 'PF0 asks how many boot pages it needs.',
            2: '<b>0.</b> Its boot ICM comes from the PSF pool inside the device.',
            3: 'PF0 is a consumer, not a pool owner. utopx fails the run if a non-PSF function reports 1 here.',
            4: 'utopx still runs the MANAGE_PAGES step, with 0 entries. FW accepts it.',
        }, slide=[(2, 'ENABLE_HCA(target) → boot page request for target VHCA ID → PSF supplies pages.')])

    @add
    def pf0_init():
        qi = qp_mode(L, 'PF0', 2)
        if qi is None:
            raise Skip('no init QUERY_PAGES from PF0')
        i0 = op('INIT_HCA', 'PF0')
        others = [fn for fn in consumers(L) if fn != 'PF0']
        return Step('pf0-init', 2, 'PF0 init pages: zero again, then INIT_HCA', opl(qi) + opl(i0), [
            (r'op_mod : 0x0002 init_pages', 1), (r'num_pages : 0x00000000', 1),
            (r'HCA_STAGE_QUERY_RSV_RESOURCES --> HCA_STAGE_DONE_INIT', 2), (r'status : 0x00', 2),
        ], {
            1: 'Init pages: 0 as well.',
            2: 'PF0 initializes without a single page from software.%s' % (
                ' %s run%s the same steps right after (see the gap below).' % (' and '.join(others), 's' if len(others) == 1 else '')
                if others else ''),
        }, slide=[(2, 'ENABLE_HCA(target) → boot page request for target VHCA ID → PSF supplies pages.')])

    @add
    def pf0_regular():
        qr = qp_mode(L, 'PF0', 3)
        if qr is None:
            raise Skip('no regular QUERY_PAGES from PF0')
        ready = lambda fn: L.first(r'VHCA=%s:GVMI=\w+:TYPE=PF has completed bringup' % L.fn_info[fn]['vhca'])  # noqa: E731
        r0 = find(r'VHCA=%s:GVMI=\w+:TYPE=PF has completed bringup' % L.fn_info['PF0']['vhca'])
        later = []
        for fn in consumers(L):
            k = ready(fn) if fn != 'PF0' else None
            if k:
                dt = secs(L.rec[k][2]) - secs(L.rec[r0][2])
                later.append('; %s follows %.1f s later' % (fn, dt) if dt >= 0 else '; %s was READY %.1f s earlier' % (fn, -dt))
        return Step('pf0-regular', 3, 'PF0 is READY; regular pages: zero', opl(qr), [
            (r'has completed bringup flow, is now in state HCA_STAGE_READY', 1),
            (r'op_mod : 0x0003 regular_pages', 2), (r'num_pages : 0x00000000', 2),
        ], {
            1: 'PF0 READY%s.' % ''.join(later),
            2: 'Regular pages: 0. Outside global mode, this reply is where a driver learns how many pages to give.',
        }, slide=[(3, 'SW does not participate in this process.')])

    @add
    def page_request_eq():
        eqs = [o for o in ops if o['opcode'] == 'CREATE_EQ' and o['fn'] != 'PSF' and 'EVENT_TYPE_PAGE_REQUEST' in o['rest']]
        if not eqs:
            raise Skip('no PF creates a page-request event queue')
        ceq = next((o for o in eqs if o['fn'] == 'PF0'), eqs[0])
        others = {}
        for o in eqs:
            if o['fn'] != ceq['fn']:
                others.setdefault(o['fn'], o)
        created = [k for k in L.op_lines(ceq) if re.search(r'Created \[.*EVENT_TYPE_PAGE_REQUEST', L.lines[k])]
        return Step('page-request-eq', 3, '%s creates a page-request event queue' % ceq['fn'], [ceq['n']] + created, [
            (r'EventType:EVENT_TYPE_PAGE_REQUEST', 1),
        ], {
            1: '%s creates the usual page-request event queue%s.' % (ceq['fn'], ''.join(
                '; %s creates its own at L%d' % (fn, o['n']) for fn, o in others.items())),
        }, slide=[(3, 'Allocate: PAGE_REQUEST pages > 0 → supply pages. Return: PAGE_REQUEST pages < 0 or release_all.')])

    @add
    def no_page_request():
        if not polls or not polls_done:
            raise Skip('no per-iteration page-request check in the log')
        eqe = L.first(r'eqe_index=0x0 On')
        reqs = eq_types.get('0x0b', 0)
        only_completions = set(eq_types) == {'0x0a'}
        notes = {
            2: 'utopx runs its page-request check once per iteration, %d times (the first at L%d, this is the last). %s' % (
                len(polls), polls[0], 'No page-request event shows up anywhere in the log.' if not reqs else
                '%d page-request events show up in the log.' % reqs),
        }
        if eqe:
            notes[1] = ('<b>No page request ever arrives.</b> This is what an event looks like when one does arrive: all %d events '
                        'utopx reads in this run are command completions (<code>event_type 0x0a</code>); a page request would be '
                        '<code>0x0b</code>.' % sum(eq_types.values())) if only_completions and not reqs else (
                        'The events utopx reads in this run, by type: %s; a page request is <code>0x0b</code>.' % ', '.join(
                            '%s ×%d' % kv for kv in sorted(eq_types.items())))
        title = '%s iterations, %s' % (words(len(polls)).capitalize(), 'no page request' if not reqs else
                                       '%d page request%s' % (reqs, '' if reqs == 1 else 's'))
        return Step('no-page-request', 3, title, (list(range(eqe, eqe + 8)) if eqe else []) + [polls[-1], polls_done[-1]], [
            (r'event_type : 0x0a', 1),
            (r'Handling Pages events\.\.\.', 2), (r'Handling Pages events done', 2),
        ], notes, slide=[(3, 'SW does not participate in this process.')])

    @add
    def pf0_teardown():
        td0 = op('TEARDOWN_HCA', 'PF0')
        tdv = find(r'Tear down vhca VHCA=%s:' % L.fn_info['PF0']['vhca'])
        nxt = next((o for o in ops if o['opcode'] == 'TEARDOWN_HCA' and o['fn'] not in ('PSF', 'PF0') and o['n'] > td0['n']), None)
        return Step('pf0-teardown', 4, 'PF0: graceful TEARDOWN_HCA', [tdv] + opl(td0), [
            (r'profile : 0x0000 Graceful_close', 1),
            (r'status : 0x00', 2),
        ], {
            1: 'Graceful close of PF0.',
            2: 'FW accepts.%s' % (' %s gets the same command next.' % nxt['fn'] if nxt else ''),
        }, slide=[(4, '01 Return-pages or graceful teardown is received')])

    @add
    def pf0_reclaim():
        td0 = op('TEARDOWN_HCA', 'PF0')
        rc = [o for o in ops if o['fn'] == 'PF0' and o['opcode'] == 'MANAGE_PAGES' and o['n'] > td0['n']]
        if not rc:
            raise Skip('no MANAGE_PAGES from PF0 after its TEARDOWN_HCA')
        rc0 = rc[0]
        pf_mp = [e for fn, e in mp_pf if fn not in (None, 'PSF')]
        senders = sorted({fn for fn, e in mp_pf if fn not in (None, 'PSF')})
        carry = sum(1 for e in pf_mp if e)
        return Step('pf0-reclaim', 4, 'Nothing to reclaim from PF0', opl(rc0), [
            (r'AllocPages: requesting numPages: 0\b', 1),
            (r'HCA_STAGE_TEARDOWN --> HCA_STAGE_RECLAIM_PAGES_REGULAR', 2),
            (r'op_mod : 0x0001 ALLOCATION_SUCCESS', 3), (r'input_num_entries : 0x00000000', 3), (r'output_num_entries : 0x00000000', 3),
        ], {
            1: 'In the reclaim stage utopx asks back the pages it gave PF0: the request is minus the pages given '
               '([[ref:reclaim_request]]). It gave none, so the request is 0.',
            2: 'utopx enters its normal page-reclaim stage.',
            3: 'A request of 0 goes out as a provide (<code>op_mod ALLOCATION_SUCCESS</code>; RECLAIM only below 0, '
               '[[ref:reclaim_op_mod]]) with 0 entries, and nothing is taken back. %s' % (
                   ('Each of the %d MANAGE_PAGES %s send%s in this run carries 0 entries.' % (
                       len(pf_mp), pfs(senders), 's' if len(senders) == 1 else '')) if not carry else
                   ('%d of the %d MANAGE_PAGES %s send%s in this run carry entries.' % (
                       carry, len(pf_mp), pfs(senders), 's' if len(senders) == 1 else ''))),
        }, slide=[(4, 'In ICM global mode, software does not reclaim pages through the normal flow.')])

    @add
    def pf0_disable():
        d0 = op('DISABLE_HCA', 'PF0')
        d1 = next((o for o in ops if o['opcode'] == 'DISABLE_HCA' and o['fn'] not in ('PSF', 'PF0') and o['n'] > d0['n']), None)
        answer = lambda o: L.rec[next(k for k in L.op_lines(o) if 'disable_hca_out' in L.lines[k])][2]  # noqa: E731
        if d1 is None:
            nod = nodnic(L)
            l0 = set(L.op_lines(d0))
            return Step('pf0-disable', 4, 'PF0: DISABLE_HCA', opl(d0, fields={'function_id', 'status', 'syndrome'}), [
                (r'HCA_STAGE_CAN_DISABLE --> HCA_STAGE_DISABLED_HCA', 1, l0), (r'status : 0x00', 1, l0),
            ], {
                1: 'PF0 sends DISABLE_HCA at %s; FW answers at %s with status 0.%s' % (d0['time'], answer(d0), (
                    ' %s run%s as NODNIC and send%s no DISABLE_HCA.' % ((' and '.join(nod),) + (('s',) * 2 if len(nod) == 1 else ('',) * 2)))
                    if nod else ''),
            }, slide=[])
        fn1 = d1['fn']
        m1 = [o for o in ops if o['fn'] == fn1 and o['opcode'] == 'MANAGE_PAGES' and d0['n'] < o['n'] < d1['n']]
        m1_lines = [k for o in m1 for k in L.op_lines(o) if not L.is_checker(L.lines[k]) and re.search(
            r'LOG_OP|HCA_STAGE_RECLAIM_PAGES_INIT --> HCA_STAGE_CAN_DISABLE|(input|output)_num_entries\s*:', L.lines[k])]
        l0, l1, lm = set(L.op_lines(d0)), set(L.op_lines(d1)), set(m1_lines)
        n1 = 3 if m1_lines else 2
        marks = [(r'HCA_STAGE_CAN_DISABLE --> HCA_STAGE_DISABLED_HCA', 1, l0), (r'status : 0x00', 1, l0)]
        notes = {1: 'PF0 sends DISABLE_HCA at %s; FW answers at %s with status 0.' % (d0['time'], answer(d0))}
        if m1_lines:
            marks += [(r'HCA_STAGE_RECLAIM_PAGES_INIT --> HCA_STAGE_CAN_DISABLE', 2, lm), (r'(input|output)_num_entries : 0x00000000', 2, lm)]
            notes[2] = ('%s\'s last page command before its DISABLE_HCA: a MANAGE_PAGES with 0 entries, like PF0\'s in the step '
                        'before. It moves %s from RECLAIM_PAGES_INIT to CAN_DISABLE.' % (fn1, fn1))
        marks += [(r'HCA_STAGE_CAN_DISABLE --> HCA_STAGE_DISABLED_HCA', n1, l1), (r'status : 0x00', n1, l1)]
        notes[n1] = '%s sends DISABLE_HCA at %s; FW answers at %s with status 0. No consumer is left.' % (fn1, d1['time'], answer(d1))
        return Step('pf0-disable', 4, 'PF0 and %s: DISABLE_HCA' % fn1, opl(d0, fields={'function_id', 'status', 'syndrome'}) + m1_lines
                    + opl(d1, fields={'function_id', 'status', 'syndrome'}), marks, notes, slide=[])

    @add
    def psf_teardown():
        tdp = op('TEARDOWN_HCA', 'PSF')
        d1 = disable_before(L, tdp)
        left = [fn for fn in consumers(L) if not any(o['opcode'] == 'DISABLE_HCA' and o['fn'] == fn and o['n'] < tdp['n'] for o in ops)]
        return Step('psf-teardown', 4, 'The PSF goes last: TEARDOWN_HCA', opl(tdp), [
            (r'profile : 0x0000 Graceful_close', 1),
            (r'HCA_STAGE_READY --> HCA_STAGE_(TEARDOWN|CAN_DISABLE)', 2), (r'status : 0x00', 2),
        ], {
            1: 'Graceful close of the PSF.',
            2: ('Sent at %s, %d ms after %s\'s DISABLE_HCA' % (tdp['time'], round((secs(tdp['time']) - secs(d1['time'])) * 1000), d1['fn'])
                if d1 else 'Sent at %s' % tdp['time']) + (
                ': no consumer is left when the PSF goes down.' if not left else
                ', while %s %s still enabled.' % (' and '.join(left), 'is' if len(left) == 1 else 'are')),
        }, slide=[(4, 'Teardown is device-driven and PSF finishes last.'),
                  (4, 'PSF completes last so dependents stop using ICM before PSF outbound is reopened.')])

    if not ret:
        # 1533759 PS4: TEARDOWN_HCA takes the PSF to CAN_DISABLE and DISABLE_HCA follows; FW accepts it with 1537640.
        @add
        def psf_disable():
            tdp = op('TEARDOWN_HCA', 'PSF')
            dp = op('DISABLE_HCA', 'PSF')
            dl = opl(dp, fields={'function_id', 'status', 'syndrome'})
            icmd = next((k for k in dl if 'LOG_KEY_ICMD_DATA' in L.lines[k]), None)
            ver = next((k for k in dl if 'Verifying DISABLE_HCA' in L.lines[k]), None)
            if icmd and ver:
                dl = [k for k in dl if k < icmd or k >= ver]  # utopx's ICMD reads after the command are not part of this step
            end = [k for k in (status0, passed) if k] if status0 and passed else []
            rp = reply(L, dp, 'disable_hca_out')
            ok = rp.get('status') == 0
            notes = {
                1: 'utopx sends DISABLE_HCA %d ms after the PSF\'s TEARDOWN_HCA, with no page command in between: '
                   '<a href="%s1533759">1533759</a> PS4 skips the page reclaim for a global-mode PSF.' % (
                       round((secs(dp['time']) - secs(tdp['time'])) * 1000), 'https://git-nbu.nvidia.com/r/c/fw_ver/utopx/+/'),
                2: 'utopx moves the PSF to DISABLED_HCA in its own model as it sends the command; the doorbell and FW\'s reply come '
                   'after. FW\'s answer is the status below.',
                3: '<code>function_id 0</code>: the PSF names itself, as in its ENABLE_HCA.',
                4: ('<b>FW accepts.</b> Before <a href="%s1537640">1537640</a> it refused this command with <code>0x5D52EE</code> '
                    '(<a href="%s5357823">Redmine 5357823</a>): the PSF\'s hca_state stayed at INIT_HCA_DONE, so DISABLE_HCA took the '
                    'post-init path, which refuses a function disabling its own GVMI. 1537640 sets it back to PRE_INIT_ICM_DONE in '
                    'TEARDOWN_HCA (FW code, not in the log).' % (GERRIT, REDMINE)) if ok else
                   ('<b>FW refuses it</b>: status <code>0x%02x</code>, syndrome <code>0x%X</code>.' % (
                       rp.get('status', -1), rp.get('syndrome', 0)) if rp else '<b>No reply from FW in the log.</b>'),
            }
            if end:
                notes[5] = 'The run ends clean: test status 0, TEST PASSED.'
            return Step('psf-disable', 4, 'The PSF\'s DISABLE_HCA is %s' % ('accepted' if ok else 'refused'), dl + end, [
                (r'DISABLE_HCA : \[G\]\[VHCA=0x[0-9a-f]+', 1, {dp['n']}),
                (r'HCA_STAGE_CAN_DISABLE --> HCA_STAGE_DISABLED_HCA', 2),
                (r'function_id : 0x0000', 3),
                (r'status : 0x00', 4), (r'syndrome : 0x00000000', 4),
                (r'Test-status is 0', 5), (r'\[TEST PASSED\]', 5),
            ], notes, slide=[(4, '03 PSF state is cleaned up')])
        return S, facts

    @add
    def psf_return():
        return Step('psf-return', 4, 'Return pages: %s asked, none handed back' % f'{ret_in:,}', opl(ret, keep=(r'returning numPages',)), [
            (r'op_mod : 0x0002 HCA_RETURN_PAGES', 1),
            (r'function_id : 0x0002', 2),
            (r'input_num_entries : 0x[0-9a-f]+', 3), (r'RECLAIM_PAGES input_num_entries=0x[0-9a-f]+?(?=embedded)', 3),
            (r'output_num_entries : 0x00000000', 4), (r'returning numPages: 0 to vhca', 4), (r'ReturnPagesPostExe num of pages=0x0', 4),
            (r'HCA_STAGE_TEARDOWN --> HCA_STAGE_DISABLED_HCA', 5),
        ], {
            1: 'Return-pages command (<code>HCA_RETURN_PAGES</code>).',
            2: '<code>function_id 2</code>: after INIT_HCA the PSF is named by its VHCA ID (2, same as its GVMI), as its capability said.',
            3: 'utopx asks for all %s pages it put in the %s range%s (<code>0x%x</code> is their sum).' % (
                f'{ret_in:,}', words(len(sizes)), 's' if len(sizes) != 1 else '', ret_in),
            4: '<b>FW hands back no entries.</b> In global mode the device takes the pool back itself when the PSF is torn down, '
               'so the normal reclaim has nothing to return. What sits between the request and the reply is utopx allocating '
               'reply buffers for up to %s entries.' % f'{ret_in:,}',
            5: 'utopx moves the PSF to DISABLED_HCA in its model without sending DISABLE_HCA; see the next step.',
        }, slide=[(4, '02 Device reclaims pages from all vHCAs, including PSF'),
                  (4, 'In ICM global mode, software does not reclaim pages through the normal flow.'),
                  (4, 'Post-init uses target VHCA IDs.')], raw_cap=90)

    @add
    def psf_no_disable():
        dis = find(r'Generating op DISABLE_HCA', after=ret['n'])
        fail = find(r'Operation failed DISABLE_HCA', after=dis)
        dis_lines = [k for k in range(dis, fail + 1) if re.search(r'Generating op DISABLE_HCA|couldn.t find target vhca for DISABLE_HCA|Operation failed DISABLE_HCA', L.lines[k])]
        end = [status0, passed] if status0 and passed else []
        return Step('psf-no-disable', 4, 'No DISABLE_HCA for the PSF yet (FW issue 5357823)', dis_lines + end, [
            (r'Operation failed DISABLE_HCA', 1), (r'couldn.t find target vhca for DISABLE_HCA', 1),
            (r'Test-status is 0', 2), (r'\[TEST PASSED\]', 2),
        ], {
            1: '<b>Blocked step.</b> utopx finds no legal target for DISABLE_HCA on the PSF and skips it. When the command was sent '
               '(runs on 10-22), FW rejected it with syndrome <code>0x5D52EE</code>: after a global-mode TEARDOWN_HCA the PSF\'s '
               'hca_state stays above PRE_INIT_ICM_DONE (0x20), so DISABLE_HCA takes the post-init path, which refuses a function '
               'disabling its own GVMI. Filed as '
               '<a href="%s5357823">Redmine 5357823</a> (P1, FW). Until it is fixed, utopx carries a local change that skips the command, '
               'and "ready to be initialized again" cannot be shown.' % REDMINE,
            **({2: 'The run ends clean: test status 0, TEST PASSED.'} if end else {}),
        }, slide=[(4, '03 PSF state is cleaned up'), (4, '04 Ready for reinitialized')])
    return S, facts



def adjust(fn, L, steps, skipped):
    """Run one step adjuster. When the log lacks what it needs, the steps stay as they were and skipped says why."""
    before = copy.deepcopy(steps)
    try:
        return fn(L, steps)
    except Skip as e:
        skipped.append((fn.__name__, str(e)))
    except (IndexError, KeyError, StopIteration, AttributeError, TypeError, ValueError, ZeroDivisionError) as e:
        skipped.append((fn.__name__, 'error %s: %s' % (type(e).__name__, e)))
    return before


def step_of(steps, sid):
    st = next((s for s in steps if s.sid == sid), None)
    if st is None:
        raise Skip('no %s step' % sid)
    return st


def add_udriver_step(L, steps):
    """Split the allocation lines off psf-range-1 into their own step, and renumber what is left."""
    i = steps.index(step_of(steps, 'psf-range-1'))
    r1 = steps[i]
    op = next(k for k in r1.lines if k in L.rec and L.rec[k][4] == 'LOG_OP')
    alloc = [k for k in r1.lines if k < op]
    dma = [k for k in range(alloc[0], op) if 'DmaDesc.cpp' in L.lines[k] and 'Allocating' in L.lines[k]]
    ver = L.find(r'udriver version')
    unotes = udriver_notes(L, next(k for k in alloc if 'The first page address' in L.lines[k]), L.info)
    ta, tb = L.rec[dma[0]][2], L.rec[next(k for k in alloc if 'The first page address' in L.lines[k])][2]
    unotes[4] = unotes[4] % dict(dur=secs(tb) - secs(ta), a=ta[-6:], b=tb[-6:])
    ud = Step('psf-udriver', 1, 'udriver maps the first range as one IOVA window', sorted(set(alloc + dma)), [
        (r'AllocPages: requesting numPages: \d+', 2),
        (r'Allocating \d+ huge:0', 3),
        (r'first page address=0x[0-9a-f]+', 4), (r'last page address=0x[0-9a-f]+', 4), (r'number of pages=0x[0-9a-f]+', 4),
    ], unotes, slide=[(1, '03 MANAGE_PAGES: enable global mode + first range')], raw_cap=40)
    ud.context = [ver]
    ud.context_marks = [(r'udriver version [\d.]+', 1)]
    ud.context_label = 'Earlier in the log, at start-up'
    keep = [k for k in r1.lines if k >= op]
    # Notes 2-4 of the old step become 1-3; its last one (FW accepts) becomes 6, after the two added below.
    renum = {2: 1, 3: 2, 4: 3, 5: 6}
    marks = [(rx, renum[n], *at) for rx, n, *at in r1.marks if n in renum]
    notes = {renum[n]: v for n, v in r1.notes.items() if n in renum}
    # The start address is the command's one list entry. The cmdif dump prints the header fields and then
    # INPUT <bytes> <entries>, not the entry, so the address is in the log only where utopx prints it before the command.
    fpa = next(k for k in alloc if 'The first page address' in L.lines[k])
    first, npages = re.search(r'first page address=(0x[0-9a-f]+).*number of pages=(0x[0-9a-f]+)', L.lines[fpa]).groups()
    inp = next(k for k in range(op, max(r1.lines)) if re.search(r'^\s*INPUT \d+ 1\s*$', L.lines[k]))
    nbytes = int(re.search(r'INPUT (\d+)', L.lines[inp]).group(1))
    marks += [(r'input_num_entries : 0x[0-9a-f]+', 4), (r'INPUT \d+ \d+', 5)]
    notes[4] = 'The page count: %s = %s pages of 4 KiB.' % (npages, f'{int(npages, 16):,}')
    notes[5] = ('<b>The start address is in the command, but this dump does not print it.</b> <code>INPUT %d 1</code> is the '
                'input\'s size and its list: %d bytes, the %d-byte header above plus one 8-byte entry. That entry is the start '
                'address, <code>%s</code>: of the %s page addresses utopx keeps only the first (<code>pages.resize(1)</code>, '
                '[[ref:range_first_page]]). The dump shows the header fields only, so the value is in the log only '
                'where utopx prints it just before the command, <a href="#L%d">L%s</a> in step %d.') % (
                    nbytes, nbytes, nbytes - 8, first, f'{int(npages, 16):,}', fpa, f'{fpa:,}', i + 1)
    steps[i] = Step(r1.sid, 1, r1.title, sorted(set(keep + [inp])), marks, notes, slide=r1.slide,
                      raw_cap=r1.raw_cap)
    rs = next((s for s in steps if s.sid == 'psf-ranges'), None)
    if rs:
        rs.notes[2] += (' Each is sent like range 1: a start address, printed in its <i>first page address</i> line, '
                    'plus this count.')
    steps.insert(i, ud)
    return steps


CAP_FIELDS = (
    ('page_request_disable', 'FW sends software no page requests. FW sets it for the PSF in global mode: utopx wrote 0 and '
     'reads 1 back.'),
    ('icm_mng_function_id_mode', 'VHCA_ID mode: after INIT_HCA, page commands name a function by its VHCA ID. That is why the '
     'return at teardown uses <code>function_id 2</code>.'),
    ('fast_teardown', 'Fast teardown is supported. This run tears down gracefully and does not use it.'),
    ('max_num_eqs', 'The PSF may create up to this many EQs. It creates none in this run.'),
)


def detail_caps_step(L, steps):
    """Step psf-caps with all three capability commands of the PSF, the SET_HCA_CAP between the two queries included."""
    i = steps.index(step_of(steps, 'psf-caps'))
    num = lambda sid: next((k + 1 for k, s in enumerate(steps) if s.sid == sid), None)  # noqa: E731
    has_ret = any(s.sid == 'psf-return' for s in steps)  # only the runs with the local WA return the PSF's pages
    ops = (L.op('QUERY_HCA_CAP', 'PSF', rest='MaximumCap GeneralDeviceCap'), L.op('SET_HCA_CAP', 'PSF'),
           L.op('QUERY_HCA_CAP', 'PSF', rest='CurrentCap GeneralDeviceCap'))
    names = {'op_mod', 'status'} | {name for name, _ in CAP_FIELDS}
    fx = [op_fields(L, o, names) for o in ops]
    after = [next(t for t in transitions_of(L) if t[1] == 'PSF' and t[0] > o['n']) for o in ops]
    lines = [k for o in ops for k in L.op_lines(o) if L.keep(k, names, (r'^\s*(INPUT|OUTPUT) \d+ \d+',))]
    lcur = set(L.op_lines(ops[2]))
    marks = [
        (r'MaximumCap GeneralDeviceCap', 1, {ops[0]['n']}),
        (r'SET_HCA_CAP', 2, {ops[1]['n']}),
        (r'page_request_disable : 0x0', 3),
        (r'CurrentCap GeneralDeviceCap', 4, {ops[2]['n']}),
        (r'page_request_disable : 0x1', 5, lcur),
        (r'icm_mng_function_id_mode : 0x1', 6, lcur),
        (r'HCA_STAGE_SET_HCA_CAP --> HCA_STAGE_INIT_PAGES_ALLOCTED', 7),
    ]
    v = lambda j, name: fx[j][name][1]
    notes = {
        1: '<b>① QUERY_HCA_CAP, maximum.</b> <code>op_mod %s</code>: the general device capabilities, maximum values: what this '
           'function can turn on, and how far. Only the 16-byte header goes in (<code>INPUT %s</code>); FW answers with status and '
           'a whole <code>cmd_hca_cap</code> (<code>OUTPUT %s</code>).' % (v(0, 'op_mod'), v(0, 'INPUT'), v(0, 'OUTPUT')),
        2: '<b>② SET_HCA_CAP.</b> utopx writes the capabilities it chose: the header plus a whole <code>cmd_hca_cap</code> '
           '(<code>INPUT %s</code>). FW answers with status only (<code>OUTPUT %s</code>, <code>status %s</code>).' % (
               v(1, 'INPUT'), v(1, 'OUTPUT'), v(1, 'status')),
        3: 'utopx writes <code>page_request_disable = 0</code>.',
        4: '<b>③ QUERY_HCA_CAP, current.</b> <code>op_mod %s</code>: the values in effect after the SET. The header goes in; status '
           'and a whole <code>cmd_hca_cap</code> come back.' % v(2, 'op_mod'),
        5: '<b>page_request_disable = 1</b>, although utopx wrote 0: FW decides this bit. It is set when global mode is on or the '
           'function is not a page supplier (<code>is_page_request_disable_cur_cap_sup()</code>); for the PSF it means global mode '
           'is now on. The PSF never creates an event queue in this run (0 CREATE_EQ on it) and still completes INIT_HCA. '
           '<span class="gapnote">utopx does not check this bit against global mode yet (FWV uArch §3.2 item 3).</span>',
        6: '<b>icm_mng_function_id_mode = 1</b> (<code>FUNCTION_ID_TYPE_VHCA_ID</code>): after INIT_HCA, page commands name a '
           'function by its VHCA ID. ' + (
               'The return at teardown (step %d) names the PSF with <code>function_id 2</code>.' % num('psf-return') if has_ret else
               'No command in this run names the PSF that way after INIT_HCA: its DISABLE_HCA at the end uses '
               '<code>function_id 0</code>.'),
        7: '<b>No init pages for the PSF.</b> Right after ③ utopx moves the PSF to INIT_PAGES_ALLOCTED without a QUERY_PAGES; its '
           'next command is INIT_HCA%s.%s' % (' (step %d)' % num('psf-init') if num('psf-init') else '',
                                             ' PF0 still asks for init pages (step %d).' % num('pf0-init') if num('pf0-init') else ''),
    }
    old = steps[i]
    st = Step(old.sid, 1, 'Capabilities: query, set, read back', lines + [t[0] for t in after], marks, notes,
                slide=old.slide, raw_cap=old.raw_cap)
    heads = ('① QUERY_HCA_CAP, maximum', '② SET_HCA_CAP', '③ QUERY_HCA_CAP, current')
    rows = [
        ('Line, time', ['L%s · %s' % (f'{o["n"]:,}', o['time'][-6:]) for o in ops]),
        ('op_mod', ['<code>%s</code> general, maximum' % v(0, 'op_mod'), '<code>%s</code> general' % v(1, 'op_mod'),
                    '<code>%s</code> general, current' % v(2, 'op_mod')]),
        ('Asks', ['What this function can turn on, and how far', 'Sets the values software chose',
                  'What is in effect after the SET']),
        ('Goes in', ['The header only, <code>INPUT %s</code>' % v(0, 'INPUT'),
                     'The header and a whole <code>cmd_hca_cap</code>, <code>INPUT %s</code>' % v(1, 'INPUT'),
                     'The header only, <code>INPUT %s</code>' % v(2, 'INPUT')]),
        ('FW returns', ['<code>status %s</code> and a whole <code>cmd_hca_cap</code>, <code>OUTPUT %s</code>' % (v(j, 'status'), v(j, 'OUTPUT'))
                        if j != 1 else '<code>status %s</code> only, <code>OUTPUT %s</code>' % (v(j, 'status'), v(j, 'OUTPUT'))
                        for j in range(3)]),
        ('utopx stage after it', ['%s (L%s)' % (t[3], f'{t[0]:,}') for t in after]),
    ]
    trs = ''.join('<tr><th scope="row">%s</th>%s</tr>' % (h, ''.join('<td>%s</td>' % c for c in cs)) for h, cs in rows)
    fields = [(name, meaning if has_ret or name != 'icm_mng_function_id_mode' else
               'VHCA_ID mode: after INIT_HCA, page commands name a function by its VHCA ID. No such command for the PSF in this run.')
              for name, meaning in CAP_FIELDS]
    frs = ''.join('<tr><th scope="row"><code>%s</code></th>%s<td>%s</td></tr>' % (
        name, ''.join('<td>%d</td>' % int(v(j, name), 16) for j in range(3)), meaning) for name, meaning in fields)
    pf0 = [o for o in L.ops if o['fn'] == 'PF0' and o['opcode'] in ('QUERY_HCA_CAP', 'SET_HCA_CAP')
           and o['n'] < next(t[0] for t in transitions_of(L) if t[1] == 'PF0' and t[3] == 'READY')]
    kinds = {m.group(1) for o in pf0 for m in [re.search(r'(?:MaximumCap|CurrentCap) (\w+)', o['rest'])] if m}
    first_pf = min(o['n'] for o in L.ops if o['fn'] in consumers(L) and o['opcode'] == 'QUERY_HCA_CAP')
    each = 'Each PF' if len(consumers(L)) > 1 else 'PF0'
    st.explainer = (
        '<div class="explainer"><div class="ex-head"><span class="lab">Capabilities, three commands</span>'
        '<span class="ex-sub">the order a driver uses too: query the maximum, set, read back</span></div>'
        '<div class="tablewrap"><table class="vs plain"><thead><tr><th></th>%s</tr></thead><tbody>%s</tbody></table></div>'
        '<div class="tablewrap"><table class="vs plain"><thead><tr><th>Field</th><th>① maximum</th><th>② SET writes</th>'
        '<th>③ current</th><th>Meaning</th></tr></thead><tbody>%s</tbody></table></div>'
        '<ul class="ex-points"><li><code>cmd_hca_cap</code> has hundreds of fields, and each of the three commands prints all of '
        'them. The log above shows only the four in the table.</li>'
        '<li>The PSF queries only the general device capabilities. %s queries %d kinds in %d capability commands '
        '(GeneralDeviceCap2, RoceCap, EthernetOffloadCap and more), from L%s.</li></ul></div>') % (
            ''.join('<th>%s</th>' % h for h in heads), trs, frs, each, len(kinds), len(pf0), f'{first_pf:,}')
    st.attachments.append(st.explainer)
    steps[i] = st
    return steps


def name_pf_enable_step(L, steps):
    """Step pf-enable: say which ENABLE_HCA is PF0 and which PF1, and that the two do not wait for each other."""
    st = step_of(steps, 'pf-enable')
    ens = sorted((L.get_op('ENABLE_HCA', fn) for fn in consumers(L)), key=lambda o: o['n'])
    first = ens[0]
    who = lambda o: '%s</b> (%s, utopx VHCA %s, GVMI %d)' % (o['fn'], o['dbdf'][5:], o['vhca'], int(o['gvmi'], 16))  # noqa: E731
    rx = r'ENABLE_HCA : \[G\]\[VHCA=0x[0-9a-f]+:GVMI=0x[0-9a-f]+:'
    st.marks = [(rx, 1, {first['n']}), (r'HCA_STAGE_DISABLED_HCA --> HCA_STAGE_ENABLED_HCA', 2)]
    st.notes[1] = st.notes[1].replace('First PF command at', '<b>%s sends the first PF command at' % who(first), 1)
    if len(ens) < 2:
        return steps
    second = ens[1]
    st.marks.append((rx, 3, {second['n']}))
    qps = [q for q in (L.get_op('QUERY_PAGES', o['fn']) for o in ens[:2]) if q]
    st.notes[3] = ('<b>%s, %d ms later. The two PFs come up in parallel and do not wait for each other, so their order is not '
                   'fixed: here %s enables first, and %s sends the next command, its boot QUERY_PAGES, first.') % (
                       who(second), round((secs(second['time']) - secs(first['time'])) * 1000), first['fn'],
                       min(qps, key=lambda o: o['n'])['fn'])
    return steps


def pf_side_by_side(L, steps, trans):
    """Flow 2: the two PFs' bring-up side by side. utopx runs them at the same time; the steps follow PF0 only."""
    fns = tuple(sorted(consumers(L)))[:2]
    pf0_steps = [k + 1 for k, s in enumerate(steps) if s.sid in ('pf0-boot-pages', 'pf0-init', 'pf0-regular', 'page-request-eq')]
    if len(fns) < 2 or not pf0_steps:
        return ''
    at = lambda o: 'L%s · %s' % (f'{o["n"]:,}', o['time'][-6:])  # noqa: E731
    qp = {fn: [qp_mode(L, fn, m) for m in (1, 2, 3)] for fn in fns}
    if not all(all(qp[fn]) for fn in fns):
        return 
    np = {fn: [op_fields(L, o, {'num_pages'}).get('num_pages', (0, '?'))[1] for o in qp[fn]] for fn in fns}
    ready = {fn: next(t for t in trans if t[1] == fn and t[3] == 'READY') for fn in fns}
    caps = {fn: [o for o in L.ops if o['fn'] == fn and o['opcode'] in ('QUERY_HCA_CAP', 'SET_HCA_CAP') and o['n'] < ready[fn][0]]
            for fn in fns}
    rows = [
        ('ENABLE_HCA', [at(L.op('ENABLE_HCA', fn)) for fn in fns]),
        ('QUERY_PAGES boot', ['%s · %d pages' % (at(qp[fn][0]), int(np[fn][0], 16)) for fn in fns]),
        ('MANAGE_PAGES, 0 pages', [at(L.op('MANAGE_PAGES', fn)) for fn in fns]),
        ('Capabilities (%d commands each)' % len(caps['PF0']), ['from ' + at(caps[fn][0]) for fn in fns]),
        ('QUERY_PAGES init', ['%s · %d pages' % (at(qp[fn][1]), int(np[fn][1], 16)) for fn in fns]),
        ('INIT_HCA', [at(L.op('INIT_HCA', fn)) for fn in fns]),
        ('QUERY_PAGES regular, then READY', ['%s · %d pages' % (at(qp[fn][2]), int(np[fn][2], 16)) for fn in fns]),
    ]
    trs = ''.join('<tr><th scope="row">%s</th>%s</tr>' % (h, ''.join('<td>%s</td>' % c for c in cs)) for h, cs in rows)
    ms = lambda a, b: round((secs(b['time']) - secs(a['time'])) * 1000)
    ea, eb = sorted((L.op('ENABLE_HCA', fn) for fn in fns), key=lambda o: o['n'])
    qa, qb = sorted((qp[fn][0] for fn in fns), key=lambda o: o['n'])
    zero = all(int(x, 16) == 0 for fn in fns for x in np[fn])
    return ('<div><span class="lab">PF0 and PF1 come up at the same time</span>'
            '<div class="tablewrap"><table class="vs plain"><thead><tr><th></th>%s</tr></thead>'
            '<tbody>%s</tbody></table></div>'
            '<p class="udnote">utopx generates commands for both PFs and sends them interleaved; which one goes first is not fixed. '
            '%s\'s ENABLE_HCA went out %d ms before %s\'s, and %s\'s boot QUERY_PAGES %d ms before %s\'s. Steps %d–%d follow '
            'PF0; %s runs the same flow, and its lines are in the rows marked "lines not shown".%s</p></div>') % (
                ''.join('<th><span class="fntag %s">%s</span>%s · VHCA %s · GVMI %d</th>' % (
                    fn.lower(), fn, L.fn_info[fn]['dbdf'][5:], L.fn_info[fn]['vhca'], int(L.fn_info[fn]['gvmi'], 16)) for fn in fns),
                trs, ea['fn'], ms(ea, eb), eb['fn'], qa['fn'], ms(qa, qb), qb['fn'], pf0_steps[0], pf0_steps[-1],
                ' and '.join(fn for fn in fns if fn != 'PF0'),
                ' All %s QUERY_PAGES replies are 0.' % words(sum(len(np[fn]) for fn in fns)) if zero else '')


def ps4_teardown(L, steps):
    """Runs with 1533759 PS4 (and FW with 1537640): TEARDOWN_HCA takes the PSF to CAN_DISABLE and FW takes the pool back;
    no return follows, and the PSF's DISABLE_HCA is accepted."""
    if not any(s.sid == 'psf-disable' for s in steps):
        return steps
    st = step_of(steps, 'psf-teardown')
    tdp = L.op('TEARDOWN_HCA', 'PSF')
    d1 = disable_before(L, tdp)
    if d1 is None:
        raise Skip('no DISABLE_HCA before the PSF\'s TEARDOWN_HCA')
    ans = L.rec[next(k for k in L.op_lines(d1) if 'disable_hca_out' in L.lines[k])][2]
    st.marks = [(r'TEARDOWN_HCA : \[G\]\[VHCA=0x[0-9a-f]+', 1, {tdp['n']}), (r'HCA_STAGE_READY --> HCA_STAGE_CAN_DISABLE', 2),
                (r'profile : 0x0000 Graceful_close', 3), (r'status : 0x00', 4)]
    st.notes = {
        1: 'Sent at %s, %d ms after FW answered %s\'s DISABLE_HCA (%s): no consumer is left when the PSF goes down.' % (
            tdp['time'], round((secs(tdp['time']) - secs(ans)) * 1000), d1['fn'], ans),
        2: '<b>READY → CAN_DISABLE.</b> utopx (<a href="%s1533759">1533759</a> PS4) takes a global-mode PSF straight to '
           'CAN_DISABLE and does not wait for its pages. In FW this command takes the pool back (FW code, box below).' % GERRIT_UTOPX,
        3: 'Graceful close of the PSF: profile REGULAR, the one in which FW takes the pool back (FW code, box below).',
        4: 'FW accepts the TEARDOWN_HCA.',
    }
    st.fwcode = (
        '<div class="fwcode"><b>In FW (code, not log).</b> With this profile, REGULAR (<code>0x0000 Graceful_close</code>, the '
        'marked line above), <code>psf_teardown_hca()</code> calls <code>psf_pool_handle_teardown_hca_reclaim()</code>: it zeroes '
        'the pool bookkeeping (<code>SP_gps</code>) and clears <code>icm_mng_global_mode</code> and '
        '<code>first_manage_pages_received</code> ([[ref:psf_pool_reclaim]]). <a href="%s1537640">1537640</a> adds '
        'one line after it: the PSF\'s hca_state goes back to PRE_INIT_ICM_DONE ([[ref:psf_teardown_global]] in the '
        'tested FW, [[tree:golan_fw]]), so the DISABLE_HCA in the next step takes the pre-init path and completes '
        '([[ref:disable_hca_psf_pre_init]]). Other profiles keep the pool. The pool is gone before anything asks for it, '
        'and utopx sends no return for the PSF.</div>' % GERRIT)
    st.attachments.append(st.fwcode)
    return steps


# The teardown box and the WA box of a run with the local workaround (no 1533759 PS4: the PSF returns its pages).
WA_FWCODE = ('<div class="fwcode"><b>In FW (code, not log).</b> With this profile, REGULAR (<code>0x0000 Graceful_close</code>, the '
            'marked line above), <code>psf_teardown_hca()</code> calls <code>psf_pool_handle_teardown_hca_reclaim()</code>: it '
            'zeroes the pool bookkeeping (<code>SP_gps</code>) and clears <code>icm_mng_global_mode</code> and '
            '<code>first_manage_pages_received</code> ([[ref:psf_pool_reclaim]] and [[ref:psf_teardown_global]] in '
            'the tested FW). Other profiles keep the pool. This is why the return in the next step comes back empty.</div>')
WA_BOX = ('<div class="wa"><b>WA, not committed.</b> The jump from TEARDOWN to DISABLED_HCA without a command comes from a '
          'local utopx change (<code>patches/psf_seed902270181_1022_102315.diff</code>) used for this run.</div>')


def rep_of(L, o):
    """What the stage shows as a command's reply: ('status 0x00', 'ok'), a failing status ('bad'), or no reply."""
    st = reply_status(L, o, o['opcode'].split()[0].lower() + '_out') if o else None
    if st is None:
        return 'no reply', 'blocked'
    return 'status 0x%02x' % st, 'ok' if st == 0 else 'bad'


def fval(L, o, name):
    """A dump field of one command as an int: the first one printed (the input's, or the output's when the input has none)."""
    v = op_fields(L, o, {name}).get(name) if o else None
    try:
        return int(v[1], 16) if v else None
    except ValueError:
        return None


def stage(L, st, f):
    """(caption, choreography) of one step, from the log. Choreography: cmds = [function, request label, reply label,
    reply kind]; kinds ok, zero (a reply that says "nothing"), info, blocked, bad. glob and pool are cumulative."""
    sizes, addr, n = f['sizes'], f['addr'], len(f['sizes'])
    psf = lambda opcode, **kw: L.get_op(opcode, 'PSF', **kw)  # noqa: E731
    # a stage command: function, request, reply, reply kind, and the command's LOG_OP line (the chips follow it)
    c = lambda fn, label, o: [fn, label] + list(rep_of(L, o)) + [o['n'] if o else None]  # noqa: E731
    q = qp_mode(L, 'PSF', 1) or psf('QUERY_PAGES')
    img, boot = fval(L, q, 'icm_mng_global'), fval(L, q, 'num_pages')
    offered = 'offered' if img == 1 else 'off'
    o_max = psf('QUERY_HCA_CAP', rest='MaximumCap GeneralDeviceCap')
    o_set = psf('SET_HCA_CAP')
    o_cur = psf('QUERY_HCA_CAP', rest='CurrentCap GeneralDeviceCap')
    on = 'confirmed' if fval(L, o_cur, 'page_request_disable') == 1 else 'on'
    passed = bool(f['passed'] and f['status0'])
    graceful = lambda o: o and any('Graceful_close' in L.lines[k] for k in L.op_lines(o) if 'profile' in L.lines[k])  # noqa: E731
    sid = st.sid
    if sid == 'psf-enable':
        return ('utopx brings up the PSF first. It enables itself with function_id 0.',
                dict(cmds=[c('PSF', 'ENABLE_HCA', psf('ENABLE_HCA'))], glob='off'))
    if sid == 'psf-issi':
        qi, si = psf('QUERY_ISSI'), psf('SET_ISSI')
        setv = fval(L, si, 'current_issi')
        return ('Before the page commands, utopx and FW agree on the command interface version: ISSI %s.' % setv,
                dict(cmds=[['PSF', 'QUERY_ISSI', 'current_issi %s' % fval(L, qi, 'current_issi'), 'info', qi['n']],
                           c('PSF', 'SET_ISSI · %s' % setv, si)], glob='off'))
    if sid == 'psf-query-pages':
        say = ('The boot QUERY_PAGES reply offers ICM global mode: icm_mng_global = 1, %d boot pages.' % boot if img == 1 else
               'The boot QUERY_PAGES reply does not offer ICM global mode: icm_mng_global = %s, %s boot pages.' % (img, boot))
        return say, dict(cmds=[['PSF', 'QUERY_PAGES boot', 'icm_mng_global %s · %s pages' % (img, boot), 'info', q['n']]], glob=offered)
    if sid == 'psf-udriver':
        return ('udriver maps the first %.0f MiB as one contiguous IOVA window, so one address and a page count describe it.' % (
            sizes[0] * 4096 / 2**20), dict(cmds=[], glob=offered, scene='udriver'))
    if sid == 'psf-range-1':
        r = rep_of(L, f['ranges'][0])
        say = 'The first range is a start address, %s, and a page count, %s, sent with icm_mng_global = %s. %s' % (
            addr[0][0], f'{sizes[0]:,}', fval(L, f['ranges'][0], 'icm_mng_global'),
            'FW accepts it: the PSF now owns a pool.' if r[1] == 'ok' else 'FW answers %s.' % r[0])
        return say, dict(cmds=[c('PSF', 'RANGE 1 · %s + %s pages' % (addr[0][0], f'{sizes[0]:,}'), f['ranges'][0])], glob='on', pool=1)
    if sid == 'psf-ranges':
        cmds = [c('PSF', 'RANGE %d · %s' % (i + 1, f'{sizes[i]:,}'), o) for i, o in enumerate(f['ranges']) if i]
        bad = sum(1 for x in cmds if x[3] != 'ok')
        more = n - 1
        say = ('%s more range%s %s accepted (this FW has 1519292). The pool reaches %s pages, %.2f GiB.' % (
            words(more).capitalize(), 's' if more > 1 else '', 'are' if more > 1 else 'is', f'{f["total"]:,}',
            f['total'] * 4096 / 2**30)) if not bad else '%d of %d more ranges are not accepted.' % (bad, more)
        return say, dict(cmds=cmds, glob='on', pool=n)
    if sid == 'psf-caps':
        prd = [fval(L, o, 'page_request_disable') for o in (o_max, o_set, o_cur)]
        say = ('Before INIT_HCA the PSF settles its capabilities with FW: query the maximum, set, read back. '
               + ('page_request_disable reads 1 although utopx wrote 0: FW sets it in global mode.' if prd[1:] == [0, 1] else
                  'page_request_disable: %s maximum, %s written, %s read back.' % tuple(prd)))
        return say, dict(cmds=[['PSF', 'QUERY_HCA_CAP max', 'page_request_disable %s' % prd[0], 'info', o_max['n']],
                               c('PSF', 'SET_HCA_CAP · page_request_disable %s' % prd[1], o_set),
                               ['PSF', 'QUERY_HCA_CAP cur', 'page_request_disable %s%s' % (
                                   prd[2], ' · VHCA_ID' if fval(L, o_cur, 'icm_mng_function_id_mode') == 1 else ''), 'info',
                                o_cur['n']]],
                         glob=on, pool=n)
    if sid == 'psf-init':
        ready = L.first(r'VHCA=%s:GVMI=\w+:TYPE=PSF has completed bringup' % L.fn_info['PSF']['vhca'])
        first_pf = min((o['n'] for o in L.ops if o['fn'] != 'PSF'), default=None)
        say = ('INIT_HCA: the PSF is READY before any PF sends a command.' if ready and first_pf and ready < first_pf else
               'INIT_HCA: the PSF is READY.')
        return say, dict(cmds=[c('PSF', 'INIT_HCA', psf('INIT_HCA'))], glob=on, pool=n)
    if sid == 'pf-enable':
        ens = sorted((L.get_op('ENABLE_HCA', fn) for fn in consumers(L)), key=lambda o: o['n'])
        t_init = reply(L, psf('INIT_HCA'), 'init_hca_out').get('time')
        gap = secs(ens[0]['time']) - secs(t_init) if t_init else None
        if len(ens) > 1:
            apart = round((secs(ens[1]['time']) - secs(ens[0]['time'])) * 1000)
            say = '%s and %s start %s, %.2f s after FW answers the PSF\'s INIT_HCA: their ENABLE_HCA go out %d ms apart.' % (
                ens[0]['fn'], ens[1]['fn'], 'together' if apart < 100 else 'one after the other', gap, apart)
        else:
            say = '%s starts %.2f s after FW answers the PSF\'s INIT_HCA.' % (ens[0]['fn'], gap)
        return say, dict(cmds=[c(o['fn'], 'ENABLE_HCA', o) for o in ens], glob=on, pool=n, par=True)
    if sid == 'pf0-boot-pages':
        q0 = qp_mode(L, 'PF0', 1)
        m0 = L.get_op('MANAGE_PAGES', 'PF0', after=q0['n'])
        np0 = fval(L, q0, 'num_pages')
        say = ('PF0 asks for boot pages and is told 0. Its ICM comes from inside the device.' if np0 == 0 else
               'PF0 asks for boot pages and is told %s.' % np0)
        return say, dict(cmds=[['PF0', 'QUERY_PAGES boot', 'num_pages %s' % np0, 'zero' if np0 == 0 else 'info', q0['n']],
                               c('PF0', 'MANAGE_PAGES · %s entries' % fval(L, m0, 'input_num_entries'), m0)],
                         glob=on, pool=n, feed=True)
    if sid == 'pf0-init':
        qi, i0 = qp_mode(L, 'PF0', 2), L.get_op('INIT_HCA', 'PF0')
        npi = fval(L, qi, 'num_pages')
        say = ('Init pages: 0 again. PF0 completes INIT_HCA without a page from software.' if npi == 0 else
               'Init pages: %s. Then PF0\'s INIT_HCA.' % npi)
        return say, dict(cmds=[['PF0', 'QUERY_PAGES init', 'num_pages %s' % npi, 'zero' if npi == 0 else 'info', qi['n']],
                               c('PF0', 'INIT_HCA', i0)], glob=on, pool=n, feed=True)
    if sid == 'pf0-regular':
        qr = qp_mode(L, 'PF0', 3)
        npr = fval(L, qr, 'num_pages')
        say = ('PF0 is READY, and its regular-pages reply is 0 as well.' if npr == 0 else
               'PF0 is READY; its regular-pages reply is %s.' % npr)
        return say, dict(cmds=[['PF0', 'QUERY_PAGES regular', 'num_pages %s' % npr, 'zero' if npr == 0 else 'info', qr['n']]],
                         glob=on, pool=n, feed=True)
    if sid == 'page-request-eq':
        eqs = [o for o in L.ops if o['opcode'] == 'CREATE_EQ' and o['fn'] != 'PSF' and 'EVENT_TYPE_PAGE_REQUEST' in o['rest']]
        ceq = next((o for o in eqs if o['fn'] == 'PF0'), eqs[0])
        return ('%s still creates the usual page-request event queue.' % ceq['fn'],
                dict(cmds=[c(ceq['fn'], 'CREATE_EQ page request', ceq)], glob=on, pool=n, feed=True))
    if sid == 'no-page-request':
        cmds = f['pf_ops']['PF0'] + f['pf_ops']['PF1']
        ev, req = sum(f['eq_types'].values()), f['eq_types'].get('0x0b', 0)
        say = ('%d iterations, %s PF commands, %d events. %s' % (
            f['polls'], f'{cmds:,}', ev, 'None of them is a page request.' if not req else '%d of them are page requests.' % req)
            if ev else '%d iterations, %s PF commands; the log prints no event.' % (f['polls'], f'{cmds:,}'))
        return say, dict(cmds=[], glob=on, pool=n, feed=True, scene='run')
    if sid == 'pf0-teardown':
        td0 = L.get_op('TEARDOWN_HCA', 'PF0')
        g = 'graceful ' if graceful(td0) else ''
        return ('Teardown starts with the PFs: a %sTEARDOWN_HCA on PF0.' % g,
                dict(cmds=[c('PF0', 'TEARDOWN_HCA' + (' graceful' if g else ''), td0)], glob=on, pool=n, feed=True))
    if sid == 'pf0-reclaim':
        td0 = L.get_op('TEARDOWN_HCA', 'PF0')
        rc0 = L.get_op('MANAGE_PAGES', 'PF0', after=td0['n'])
        e_in, e_out = fval(L, rc0, 'input_num_entries'), fval(L, rc0, 'output_num_entries')
        say = ('utopx asks back the pages it gave PF0: none, so its MANAGE_PAGES carries 0 entries.' if e_in == 0 else
               'utopx asks back the pages it gave PF0: its MANAGE_PAGES carries %s entries.' % e_in)
        return say, dict(cmds=[['PF0', 'MANAGE_PAGES · %s entries' % e_in, 'output %s entries' % e_out, 'zero', rc0['n']]],
                         glob=on, pool=n, feed=True)
    if sid == 'pf0-disable':
        d0 = L.get_op('DISABLE_HCA', 'PF0')
        d1 = next((o for o in L.ops if o['opcode'] == 'DISABLE_HCA' and o['fn'] not in ('PSF', 'PF0') and o['n'] > d0['n']), None)
        nod = nodnic(L)
        say = ('PF0 and %s are off. No consumer is left.' % d1['fn']) if d1 else 'PF0 is off.%s' % (
            ' %s runs as NODNIC.' % ' and '.join(nod) if nod else '')
        return say, dict(cmds=[c('PF0', 'DISABLE_HCA', d0)] + ([c(d1['fn'], 'DISABLE_HCA', d1)] if d1 else []), glob=on, pool=n)
    if sid == 'psf-teardown':
        tdp = psf('TEARDOWN_HCA')
        d1 = disable_before(L, tdp)
        ans = reply(L, d1, 'disable_hca_out').get('time') if d1 else None
        say = 'The PSF goes last: a %sTEARDOWN_HCA%s. In FW it takes the pool back (FW code).' % (
            'graceful ' if graceful(tdp) else '', ', %d ms after FW answered %s\'s DISABLE_HCA' % (
                round((secs(tdp['time']) - secs(ans)) * 1000), d1['fn']) if ans else '')
        return say, dict(cmds=[c('PSF', 'TEARDOWN_HCA' + (' graceful' if graceful(tdp) else ''), tdp)], glob='cleared', pool=n,
                         gone=True)
    if sid == 'psf-return':
        ret = f['ret']
        out = fval(L, ret, 'output_num_entries')
        return ('utopx asks for all %s pages back. FW returns %s entries.' % (f'{f["ret_in"]:,}', out),
                dict(cmds=[['PSF', 'RETURN %s pages' % f'{f["ret_in"]:,}', 'output %s entries' % out, 'zero', ret['n']]], glob='cleared',
                     pool=n, gone=True, wa='PSF'))
    if sid == 'psf-no-disable':
        return ('The PSF\'s DISABLE_HCA is skipped by a local utopx workaround (FW issue 5357823).' + (
            ' The run passes.' if passed else ''),
            dict(cmds=[['PSF', 'DISABLE_HCA', 'not sent · WA', 'blocked', None]], glob='cleared', pool=n, gone=True, wa='PSF',
                 passed=passed))
    if sid == 'psf-disable':
        dp = psf('DISABLE_HCA')
        r = rep_of(L, dp)
        say = (('The PSF\'s DISABLE_HCA is accepted (status 0x00): 1537640 lets FW take the PSF off after a global-mode '
                'teardown.' + (' The run passes.' if passed else '')) if r[1] == 'ok' else
               'FW does not accept the PSF\'s DISABLE_HCA: %s.' % r[0])
        return say, dict(cmds=[c('PSF', 'DISABLE_HCA', dp)], glob='cleared', pool=n, gone=True, passed=passed)
    return st.caption, st.choreo


def finish(L, steps, f):
    """Give every step its caption and choreography, computed from the log, and the attachments the builders do not set."""
    for st in steps:
        st.caption, st.choreo = stage(L, st, f)
        if st.sid == 'psf-udriver':
            st.attachments.append(udriver_explainer(udriver_numbers(L, f)))
        if st.sid == 'psf-teardown' and not st.attachments and any(s.sid == 'psf-return' for s in steps):
            st.attachments.append(WA_FWCODE)
        if st.sid == 'psf-return':
            st.attachments.append(WA_BOX)
    return steps


def udriver_numbers(L, f):
    """The first range as the udriver figures draw it: pages, the old call's 1024-page chunks, the IOVA window."""
    pages = f['sizes'][0] if f['sizes'] else 0
    chunks = -(-pages // 1024)
    tail = pages - 1024 * (chunks - 1) if chunks else 0
    first, last = (f['addr'][0][0], f['addr'][0][1]) if f['addr'] else ('?', '?')
    contiguous = first != '?' and last and int(last, 16) - int(first, 16) == (pages - 1) * 4096
    init = rep_of(L, L.get_op('INIT_HCA', 'PSF'))
    return dict(pages=pages, mib=pages * 4096 / 2**20, chunks=chunks, tail=tail, first=first, last=last, contiguous=contiguous,
                init=init[0].replace('0x00', '0'), box=L.info.get('box'))
