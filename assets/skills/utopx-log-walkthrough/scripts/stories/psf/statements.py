"""PSF story: the FW slide flows, the slide statements checked against the log, and the flow introductions."""
from wt.fmt import GERRIT, REDMINE

FLOWS = {
    1: dict(name='PSF initialization', color='f1', slide=[
        '01 ENABLE_HCA', '02 QUERY_PAGES (BOOT)', '03 MANAGE_PAGES: enable global mode + first range',
        '04 MANAGE_PAGES: optional extra ranges', '05 INIT_HCA'],
        bottom='ICM is managed by the device. Like GPS.'),
    2: dict(name='Start a consumer', color='f2', slide=[
        'One PSF command path can bootstrap many consumer functions.',
        'ENABLE_HCA(target) → boot page request for target VHCA ID → PSF supplies pages.'],
        bottom='PSF readiness gates dependent function initialization.'),
    3: dict(name='Runtime page management', color='f3', slide=[
        'Request, supply, and return loop.',
        'Allocate: PAGE_REQUEST pages > 0 → supply pages. Return: PAGE_REQUEST pages < 0 or release_all.'],
        bottom='SW does not participate in this process.'),
    4: dict(name='Teardown (iron orchestration)', color='f4', slide=[
        '01 Return-pages or graceful teardown is received', '02 Device reclaims pages from all vHCAs, including PSF',
        '03 PSF state is cleaned up', '04 Ready for reinitialized'],
        bottom='Teardown is device-driven and PSF finishes last.'),
}

SCORE = [
    # flow, slide text, verdict, what the log shows, step id
    (1, 'QUERY_PAGES tells software whether ICM global mode is supported.', 'yes',
     'The PSF\'s boot QUERY_PAGES returns <code>icm_mng_global = 1</code>.', 'psf-query-pages'),
    (1, 'Global mode turns on when PSF supplies the first ICM range in MANAGE_PAGES.', 'yes',
     'The first range carries <code>icm_mng_global = 1</code>; afterwards the PSF\'s capabilities read '
     '<code>page_request_disable = 1</code>, which FW sets from global mode being on.', 'psf-range-1'),
    (1, 'MANAGE_PAGES: optional extra ranges.', 'yes', '{ranges}, {total} pages, all accepted. Needs '
     '<a href="' + GERRIT + '1519292">1519292</a>; without it the second range fails with <code>0xFF2C2D</code>.', 'psf-ranges'),
    (1, 'PSF self-bootstrap does not require a page-request EQ.', 'yes',
     'The PSF creates no event queue at all and completes INIT_HCA.', 'psf-caps'),
    (1, 'Pre-init uses self-target addressing; post-init uses target VHCA IDs.', 'yes',
     'Ranges before INIT_HCA use <code>function_id 0</code>; the return at teardown uses <code>function_id 2</code>, the PSF\'s VHCA ID.',
     'psf-return'),
    (1, 'Trust QUERY_PAGES rather than hard-coding NUM_BOOT_PAGES.', 'part',
     'utopx takes {bootpages} boot pages from the reply. It does not yet check the PSF\'s reply against an expected value.', 'psf-query-pages'),
    (1, 'PSF finishes its own bootstrap before any dependent network function starts.', 'yes',
     'The PSF is READY before either PF sends its first command.', 'pf-enable'),
    (2, 'One PSF command path can bootstrap many consumer functions.', 'no',
     'Not in this run. All {psfcmds} PSF commands target the PSF itself; utopx does not send page commands from the PSF '
     'for another function yet (its log: "other func is not supported in test").', 'pf-enable'),
    (2, 'ENABLE_HCA(target) → boot page request for target VHCA ID → PSF supplies pages.', 'part',
     'The consumers here are the host PFs, enabling themselves. They are told they need 0 boot and 0 init pages: the pages '
     'come from the PSF pool inside the device.', 'pf0-boot-pages'),
    (2, 'PSF readiness gates dependent function initialization.', 'part',
     'Seen as ordering: utopx starts the PFs after the PSF is READY. Starting a PF before the PSF was not tried.', 'pf-enable'),
    (3, 'SW does not participate in this process.', 'yes',
     '{pfcmds} PF commands, {pfobj} objects created; {qps} QUERY_PAGES replies all 0, {mps} MANAGE_PAGES all with 0 entries, '
     '0 page requests among {eqes} events.', 'no-page-request'),
    (4, 'Teardown is device-driven and PSF finishes last.', 'yes',
     '{consumer_names} TEARDOWN_HCA and DISABLE_HCA first; the PSF\'s TEARDOWN_HCA comes after the last DISABLE_HCA.', 'psf-teardown'),
    (4, 'In ICM global mode, software does not reclaim pages through the normal flow.', 'yes',
     'Every reclaim comes back empty, including the PSF\'s return of {retin} pages.', 'psf-return'),
    (4, 'Device reclaim effectively transitions the system into the internal FLR path.', 'no',
     'Happens inside FW; a utopx log cannot show it.', 'psf-return'),
    (4, 'PSF state is cleaned up; ready to be initialized again.', 'blocked',
     'The PSF\'s DISABLE_HCA after teardown fails in FW with <code>0x5D52EE</code> '
     '(<a href="' + REDMINE + '5357823">Redmine 5357823</a>, P1); utopx skips it for now, so re-initialization was not run.',
     'psf-no-disable'),
]

VERDICT = {'yes': ('Seen', 'ok'), 'part': ('Partly', 'part'), 'no': ('Not in this run', 'na'), 'blocked': ('Blocked', 'bad')}

FLOW_INTRO = {
    1: 'The PSF is the first function utopx brings up, and it goes through all five slide steps on its own command '
       'interface. It sends {ranges}, {total} pages in all, and is READY before any PF sends a command.',
    2: 'The consumers in this run are {consumers}. {each} enables itself after the PSF is READY, asks for boot and '
       'init pages, and is told 0: its ICM comes from the PSF pool inside the device. The PSF never sends a command for '
       'another function here, so the PSF-driven path on the slide is not covered by this run.',
    3: 'The PFs run {iters} iterations of random commands: {pfcmds} commands, {pfobj} of them creating objects. Software is '
       'never asked for a page: every QUERY_PAGES returns 0, every MANAGE_PAGES carries 0 entries, and no page request '
       'arrives.',
    4: 'utopx closes the PFs first and the PSF last. Every reclaim software sends comes back empty, the PSF\'s return of '
       '{retin} pages included. The last slide step, turning the PSF off so it can be initialized again, is blocked by a FW '
       'issue (Redmine 5357823), and utopx skips it for now.',
}

FLOW4_PS4 = ('utopx closes the PFs first and the PSF last. The PSF sends no page command: in FW its TEARDOWN_HCA takes the pool '
             'back (FW code, not in the log), and every MANAGE_PAGES the PFs send at teardown carries 0 entries. The PSF\'s '
             'DISABLE_HCA is accepted, with 1537640, the fix for FW issue Redmine 5357823; initializing the PSF again was not run.')


FLOW4_STOPPED = ('utopx closes the PFs first and the PSF last. The PSF sends no page command at teardown, and every '
                 'MANAGE_PAGES the PFs send carries 0 entries. The run stops after the PSF\'s TEARDOWN_HCA, before the PSF is '
                 'disabled: see the last step.')


def variant(f):
    """How the run ends: 'wa' (the PSF returns its pages, local workaround), 'ps4' (1533759 PS4: the PSF's DISABLE_HCA
    goes out after its TEARDOWN_HCA), or 'stopped' (neither: the run ends before)."""
    if f['ret_in']:
        return 'wa'
    return 'ps4' if 'psf-disable' in f.get('built', ('psf-disable',)) else 'stopped'


def flow_intro(fl, f):
    if fl == 4:
        return {'wa': FLOW_INTRO[4], 'ps4': FLOW4_PS4, 'stopped': FLOW4_STOPPED}[variant(f)]
    return FLOW_INTRO[fl]


def score_rows(f):
    """The FW slide statements against the log. A statement whose step the page does not have says why it is not shown."""
    built = set(f.get('built', ()))
    why = {name.replace('_', '-'): reason for name, reason in f.get('skipped', [])}
    out = []
    for fl, text, v, what, sid in variant_rows(f):
        if built and sid not in built:
            v, what = 'no', 'Not shown: %s.' % why.get(sid, 'the run does not get there')
        out.append((fl, text, v, what, sid))
    return out


def variant_rows(f):
    """A 1533759 PS4 run has no PSF return and gets its DISABLE_HCA through."""
    if variant(f) == 'wa':
        return SCORE
    stopped = variant(f) == 'stopped'
    rows = []
    for fl, text, v, what, sid in SCORE:
        if text.startswith('Pre-init uses self-target'):
            v, sid = 'part', 'psf-caps'
            what = ('Pre-init seen: the ranges before INIT_HCA use <code>function_id 0</code>. Post-init only the capability says '
                    'so (<code>icm_mng_function_id_mode = 1</code>, VHCA_ID): no command names the PSF by its VHCA ID after '
                    'INIT_HCA in this run.')
        elif text.startswith('In ICM global mode, software does not reclaim'):
            what, sid = ('The PSF sends no page command at teardown (1533759 PS4), and FW still accepts its DISABLE_HCA with no '
                         'page returned. Every MANAGE_PAGES the PFs send at teardown carries 0 entries. That FW takes the pool back '
                         'inside TEARDOWN_HCA is FW code, not in the log.'), 'psf-teardown'
            if stopped:
                v, what = 'part', ('The PSF sends no page command at teardown, and every MANAGE_PAGES the PFs send at teardown '
                                   'carries 0 entries. The run stops before the PSF is disabled.')
        elif text.startswith('Device reclaim effectively'):
            sid = 'psf-teardown'
        elif text.startswith('PSF state is cleaned up'):
            v, sid = 'part', 'psf-disable'
            what = ('The PSF\'s DISABLE_HCA after teardown is accepted (status 0x00), with <a href="%s1537640">1537640</a>, the '
                    'fix for <a href="%s5357823">Redmine 5357823</a>. Initializing the PSF again was not run.' % (GERRIT, REDMINE))
        rows.append((fl, text, v, what, sid))
    return rows
