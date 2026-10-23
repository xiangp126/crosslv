"""Small synthetic utopx debug logs for the tests.

The lines have the formats of a real debug log (records, LOG_OP lines, cmdif dumps, HCA stage transitions, the checker's
copy of each function, GEN/EXE/VER threads), a few lines per command. psf_run() writes one PSF ICM global-mode run in the
shapes the PSF story handles.
"""
import os

FN = {
    'PSF': dict(vhca=0x59, gvmi=2, dbdf='0000:81:00.2', type='PSF', checker=0x5a),
    'PF0': dict(vhca=0x57, gvmi=0, dbdf='0000:81:00.0', type='PF', checker=0x7b),
    'PF1': dict(vhca=0x58, gvmi=1, dbdf='0000:81:00.1', type='PF', checker=0xbc),
}


class Synth:
    def __init__(self, start=(12, 30, 0), ansi=True):
        self.lines = []
        self.ms = ((start[0] * 60 + start[1]) * 60 + start[2]) * 1000
        self.tid = 2000
        self.ansi = ansi

    def now(self):
        ms = self.ms % 86400000
        return '%02d:%02d:%02d.%03d' % (ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, ms % 1000)

    def tick(self, ms=1):
        self.ms += ms

    def rec(self, src, thr, level, tag, msg):
        line = '%-34s (%s)  %s [%s] %15s : %s' % (src, thr, self.now(), level, tag, msg)
        self.lines.append('\x1b[34m%s\x1b[0m' % line if self.ansi else line)
        return len(self.lines)

    def raw(self, text):
        self.lines.append(text)

    def text(self):
        return '\n'.join(self.lines) + '\n'

    @staticmethod
    def who(fn, checker=False):
        f = FN[fn]
        gvmi = '0' if f['gvmi'] == 0 else '0x%x' % f['gvmi']   # a real log prints PF0 as GVMI=0
        return 'VHCA=0x%x:GVMI=%s:TYPE=%s' % (f['checker'] if checker else f['vhca'], gvmi, f['type'])

    def trans(self, thr, fn, a, b, checker=False):
        return self.rec('VHCA.cpp:4221', thr, 'D', 'General', 'HCA State Transition: %s HCA_STAGE_%s --> HCA_STAGE_%s' % (
            self.who(fn, checker), a, b))

    def threads(self, kind):
        self.tid += 1
        if kind == 'TST':
            t = 'TST:0:0:%d' % self.tid
            return t, t, t
        suf = '0:%d:%d' % (self.tid // 100, self.tid % 100)
        return 'GEN:' + suf, 'EXE:' + suf, 'VER:' + suf

    def cmd(self, fn, opcode, rest='isPreCond: false', inp=(), out=(), io=((16, 0), (16, 0)), status=0, syndrome=0,
            trans=None, after=(), before=(), kind='TST', debug=True, trans_first=False):
        """One command: lines it prints before its LOG_OP, the LOG_OP line and the stage transition utopx makes as it
        sends (trans_first: just before the LOG_OP line, as utopx prints it in the teardown flow), then (debug) the input
        dump, doorbell, output dump, verification, the checker's copy, `after` records, and Ver done. Returns the LOG_OP
        line number."""
        f = FN[fn]
        gen, exe, ver = self.threads(kind)
        for src, tag, msg in before:
            self.rec(src, gen, 'D', tag, msg)
        self.tick()
        if trans and trans_first:
            self.trans(gen, fn, *trans)
        n = self.rec('UtopxOp.cpp:788', gen, 'I', 'LOG_OP', '%-20s : [G][VHCA=0x%x:GVMI=0x%x:PORT=0x0:DBDF=%s:HIX=0x0]   %s' % (
            opcode, f['vhca'], f['gvmi'], f['dbdf'], rest))
        if trans and not trans_first:
            self.trans(gen, fn, *trans)
        if not debug:
            return n
        name = opcode.split()[0]
        self.rec('CmdExecuter.cpp:91', exe, 'D', 'LOG_KEY_CMDIF', ' -------- %s_in --------' % name.lower())
        for k, v in (('uid', '0x0000'), ('opcode', '0x0100')) + tuple(inp):
            self.raw(' %-20s : %s' % (k, v))
        self.raw('')
        self.raw(' SLOT 0x13')
        self.raw(' INPUT %d %d' % io[0])
        self.raw(' OUTPUT %d %d' % io[1])
        self.rec('UtopxCmdIfAgent.cpp:232', exe, 'D', 'HIGH', 'Sending cmdif doorbell')
        self.tick()
        self.rec('CmdExecuter.cpp:111', exe, 'D', 'LOG_KEY_CMDIF', '%s:   -------- %s_out --------' % (name, name.lower()))
        self.raw(' %-20s : 0x%02x' % ('status', status))
        self.raw(' %-20s : 0x%08x' % ('syndrome', syndrome))
        for k, v in out:
            self.raw(' %-20s : %s' % (k, v))
        self.raw('')
        self.rec('ContextChecker.cpp:208', ver, 'D', 'HIGH', 'Verifying %s ; with status OK 0 ; error test mode = 0' % name)
        self.rec('CmdVhcaOtherFunc.cpp:778', ver, 'D', 'HIGH', ' updating %s' % self.who(fn, checker=True))
        if trans:
            self.trans(ver, fn, *trans, checker=True)
        for src, tag, msg in after:
            self.rec(src, ver, 'I', tag, msg)
        self.rec('ContextChecker.cpp:470', ver, 'D', 'VER_CONTEXT', 'Ver done')
        return n

    def interleaved(self, *cmds):
        """Several commands at once, their records interleaved as concurrent generator threads print them. Each cmds item
        is a dict of cmd() arguments; a dump stays in one piece after its record, as in a real log."""
        per = []
        for kw in cmds:
            sub = Synth(ansi=self.ansi)
            sub.ms, sub.tid = self.ms, self.tid
            sub.cmd(kind='GEN', **kw)
            self.tid = sub.tid
            chunks, cur = [], []
            for line in sub.lines:
                if line and not line.startswith(' ') and cur:
                    chunks.append(cur)
                    cur = []
                cur.append(line)
            chunks.append(cur)
            per.append(chunks)
        while any(per):
            for q in per:
                if q:
                    self.lines.extend(q.pop(0))
        self.tick(len(cmds))


def issi_cmds(s, fn, **kw):
    """QUERY_ISSI and SET_ISSI right after ENABLE_HCA: FW supports ISSI 1 only (bit 1 of the last byte of the mask)."""
    mask = tuple(('supported_issi      [%x ]' % j, '0x02' if j == 0x4f else '0x00') for j in range(0x50))
    s.cmd(fn, 'QUERY_ISSI', rest='[UID=0x0]   isPreCond: false', out=(('current_issi', '0x0000'),) + mask,
          io=((16, 0), (112, 0)), trans=('ENABLED_HCA', 'QUERY_ISSI'), **kw)
    s.cmd(fn, 'SET_ISSI', rest='setting issi= 0x1 isPreCond: false', inp=(('current_issi', '0x0001'),),
          trans=('QUERY_ISSI', 'SET_ISSI'), **kw)


def range_cmds(s, sizes, statuses, first_addr=0x40000000, debug=True):
    """The PSF's ranges: allocation lines, the first and last page address, MANAGE_PAGES PROVIDE_PAGES_RANGE."""
    addr = first_addr
    for i, n in enumerate(sizes):
        last = addr + (n - 1) * 4096
        before = [('PagesManager.cpp:62', 'PAGES_FLOW',
                   '%s AllocPages: requesting numPages: %d. pagesToAllocate: %d' % (Synth.who('PSF'), n, n)),
                  ('DmaDesc.cpp:14', 'PAGES_FLOW', 'Allocating %d huge:0' % (n * 4096)),
                  ('CmdManagePages.cpp:85', 'HIGH', 'The first page address=0x%x, and the last page address=0x%x, with the '
                   'number of pages=0x%x' % (addr, last, n))]
        s.cmd('PSF', 'MANAGE_PAGES', rest='PROVIDE_PAGES_RANGE input_num_entries=0x%xembedded_function=0x0 isPreCond: false' % n,
              inp=(('op_mod', '0x0003 ALLOCATION_SUCCESS_RANGE'), ('function_id', '0x0000'), ('icm_mng_global', '0x1'),
                   ('input_num_entries', '0x%08x' % n)),
              out=(('output_num_entries', '0x00000000'),), io=((24, 1), (16, 0)), status=statuses[i],
              syndrome=0xff2c2d if statuses[i] else 0, before=before, debug=debug)
        addr = last + 4096 + 0x100000


def psf_run(variant='ps4', sizes=(247612, 195402, 14432, 56783, 204585), pf1='hca', iters=3, start=(12, 30, 0),
            debug=True, ansi=True):
    """One PSF run. variant: 'ps4' (the PSF's DISABLE_HCA after its TEARDOWN_HCA, accepted), 'refused' (the same
    DISABLE_HCA refused, the run fails), 'wa' (the PSF returns its pages, DISABLE_HCA skipped), 'stopped' (utopx drops the
    PSF's DISABLE_HCA, FATAL). pf1: 'hca' or 'nodnic'. debug=False writes no cmdif dumps."""
    s = Synth(start, ansi)
    s.raw('Running: /auto/x/utopx.exe --device=/dev/mst/mt4131_pciconf0 --seed=902270181 --daemon --num_of_clients=0 '
          '--xml_conf_file %s --conf_file config/cmdif_test.conf --iter=%d --ops_per_it=40 '
          '-e icm_mng_global_keeps.icm_mng_global_enabled=1' % ('debug_conf.xml' if debug else 'regular_conf.xml', iters))
    t0 = 'TST:0:0:2000'
    s.rec('UtopxFunctionManager.cpp:2323', t0, 'I', 'General', 'udriver version 3.9')
    s.rec('VHCA.cpp:977', t0, 'I', 'General', 'fw version is: 40.51.299')
    for fn in FN:
        s.trans(t0, fn, 'NONE', 'DISABLED_HCA')
        s.trans(t0, fn, 'NONE', 'DISABLED_HCA', checker=True)
    pfs = ['PF1', 'PF0'] if pf1 == 'hca' else ['PF0']
    gen = dict(kind='TST', debug=debug)

    # flow 1: the PSF
    s.rec('CmdInitFlow.cpp:518', t0, 'I', 'General', 'Performing Quick Init on vhca %s' % Synth.who('PSF'))
    s.cmd('PSF', 'ENABLE_HCA', inp=(('op_mod', '0x0000'), ('function_id', '0x0000')), trans=('DISABLED_HCA', 'ENABLED_HCA'), **gen)
    issi_cmds(s, 'PSF', **gen)
    s.cmd('PSF', 'QUERY_PAGES', inp=(('op_mod', '0x0001 boot_pages'), ('function_id', '0x0000')),
          out=(('function_id', '0x0000'), ('icm_mng_global', '0x1'), ('num_pages', '0x00000019')),
          trans=('SET_ISSI', 'BOOT_PAGES_QUERY'), **gen)
    range_cmds(s, sizes, [0] * len(sizes), debug=debug)
    s.trans('TST:0:0:%d' % s.tid, 'PSF', 'BOOT_PAGES_QUERY', 'BOOT_PAGES_ALLOCTED')
    caps = (('page_request_disable', '0x%x'), ('icm_mng_function_id_mode', '0x1'), ('fast_teardown', '0x1'), ('max_num_eqs', '0x40'))
    fields = lambda prd: tuple((k, v % prd if '%' in v else v) for k, v in caps)  # noqa: E731
    s.cmd('PSF', 'QUERY_HCA_CAP', rest='[UID=0x0]   MaximumCap GeneralDeviceCap isPreCond: false', inp=(('op_mod', '0x0001'),),
          out=fields(1), io=((16, 0), (4112, 0)), trans=('BOOT_PAGES_ALLOCTED', 'QUERY_HCA_CAP_MAX'), **gen)
    s.cmd('PSF', 'SET_HCA_CAP', rest='[UID=0x0]   GeneralDeviceCap isPreCond: false', inp=(('op_mod', '0x0000'),) + fields(0),
          io=((4112, 0), (16, 0)), trans=('QUERY_HCA_CAP_MAX', 'SET_HCA_CAP'), **gen)
    s.cmd('PSF', 'QUERY_HCA_CAP', rest='[UID=0x0]   CurrentCap GeneralDeviceCap isPreCond: false', inp=(('op_mod', '0x0001'),),
          out=fields(1), io=((16, 0), (4112, 0)), trans=('SET_HCA_CAP', 'INIT_PAGES_ALLOCTED'), **gen)
    s.tick(80)
    s.cmd('PSF', 'INIT_HCA', rest='test stage=0x1 hca_stage=0x10 log_max_qp=0x0  isPreCond: false',
          trans=('INIT_PAGES_ALLOCTED', 'READY'),
          after=(('VHCA.cpp:4223', 'General', '%s has completed bringup flow, is now in state HCA_STAGE_READY' % Synth.who('PSF')),),
          **gen)
    s.tick(280)

    # flow 2: the PFs enable themselves and get 0 pages; PF1 may run as NODNIC
    pf = dict(kind='GEN', debug=debug)
    for fn in pfs:
        s.cmd(fn, 'ENABLE_HCA', inp=(('op_mod', '0x0000'), ('function_id', '0x0000')), trans=('DISABLED_HCA', 'ENABLED_HCA'), **pf)
        s.tick(3)
    if pf1 == 'nodnic':
        for op in ('NODNIC_ENABLE_DEVICE', 'NODNIC_QUERY_REGISTERS', 'NODNIC_ENABLE_PORTS'):
            s.cmd('PF1', op, **pf)
    for fn in reversed(pfs):
        issi_cmds(s, fn, **pf)
        s.cmd(fn, 'QUERY_PAGES', inp=(('op_mod', '0x0001 boot_pages'), ('function_id', '0x0000')),
              out=(('function_id', '0x0000'), ('icm_mng_global', '0x0'), ('num_pages', '0x00000000')),
              trans=('SET_ISSI', 'BOOT_PAGES_QUERY'), **pf)
        s.cmd(fn, 'MANAGE_PAGES', rest='PROVIDE_PAGES input_num_entries=0x0embedded_function=0x0 isPreCond: false',
              inp=(('op_mod', '0x0001 ALLOCATION_SUCCESS'), ('function_id', '0x0000'), ('input_num_entries', '0x00000000')),
              out=(('output_num_entries', '0x00000000'),), trans=('BOOT_PAGES_QUERY', 'BOOT_PAGES_ALLOCTED'),
              before=(('PagesManager.cpp:62', 'PAGES_FLOW', '%s AllocPages: requesting numPages: 0. pagesToAllocate: 0' % Synth.who(fn)),),
              **pf)
    for fn in reversed(pfs):
        for kind in ('GeneralDeviceCap', 'RoceCap'):
            s.cmd(fn, 'QUERY_HCA_CAP', rest='[UID=0x0]   MaximumCap %s isPreCond: false' % kind, inp=(('op_mod', '0x0001'),), **pf)
        s.cmd(fn, 'QUERY_PAGES', inp=(('op_mod', '0x0002 init_pages'), ('function_id', '0x0000')),
              out=(('function_id', '0x0000'), ('icm_mng_global', '0x0'), ('num_pages', '0x00000000')),
              trans=('QUERY_HCA_CAP_CUR', 'INIT_PAGES_QUERY'), **pf)
        s.cmd(fn, 'INIT_HCA', rest='test stage=0x1 hca_stage=0x13 log_max_qp=0xa  isPreCond: false',
              trans=('QUERY_RSV_RESOURCES', 'DONE_INIT'), **pf)
        s.cmd(fn, 'QUERY_PAGES', inp=(('op_mod', '0x0003 regular_pages'), ('function_id', '0x0000')),
              out=(('function_id', '0x0000'), ('icm_mng_global', '0x0'), ('num_pages', '0x00000000')),
              trans=('MODIFY_NIC_VPORT_CONTEXT', 'READY'),
              after=(('VHCA.cpp:4223', 'General', '%s has completed bringup flow, is now in state HCA_STAGE_READY' % Synth.who(fn)),),
              **pf)
        s.cmd(fn, 'CREATE_EQ', rest='[UID=0xffff] [0x0_0xffff:_EQ:0x489:NONE:N:GenDB   EventType:EVENT_TYPE_PAGE_REQUEST  '
              'log_eq_size=0x5] isPreCond: false',
              after=(('UtopxOpTemplates.cpp:491', 'HIGH', 'Created [0x0_0x0:_EQ:0x50e:0x5:N:GenDB   EventType:EVENT_TYPE_PAGE_REQUEST  '
                      'log_eq_size=0x5]'),), **pf)

    # flow 3: iterations of random commands, two at a time, with a sub-op opcode
    for i in range(iters):
        s.tick(400)
        s.rec('UtopxRandomTest.cpp:6467', 'TST:0:1:0', 'D', 'General', 'Handling Pages events...')
        s.interleaved(dict(fn='PF0', opcode='CREATE_CQ', rest='[UID=0x0] log_cq_size=0x4 isPreCond: false', debug=debug),
                      dict(fn=pfs[0], opcode='MODIFY_QP RST2INIT_QP', rest='[UID=0x0] qpn=0x%x isPreCond: false' % (0x100 + i),
                           debug=debug))
        s.rec('PollCqEq.cpp:621', 'TST:0:30:0', 'D', 'HIGH', 'eqe_index=0x0 On 0x0_0x0:_EQ:0xaec:0x6:N:GenDB')
        for line in (' -------- eqe_head --------', ' event_sub_type       : 0x00', ' event_type           : 0x0a',
                     ' -------- cmd_inter_comp_event --------', ' command_completion_vector : 0x00000001',
                     ' -------- eqe_tail --------', ' owner                : 0x0', ' signature            : 0xab'):
            s.raw(line)
        s.rec('UtopxRandomTest.cpp:6469', 'TST:0:1:0', 'D', 'General', 'Handling Pages events done')

    # flow 4: the PFs, then the PSF
    s.tick(500)
    for fn in reversed(pfs):
        s.rec('VHCA.cpp:7532', 'TST:0:0:%d' % (s.tid + 1), 'I', 'General', 'Tear down vhca %s' % Synth.who(fn))
        s.cmd(fn, 'TEARDOWN_HCA', rest='test stage: TEST_STAGE_TEARDOWN , hca_stage: HCA_STAGE_TEARDOWN , profile: false '
              'isPreCond: false', inp=(('profile', '0x0000 Graceful_close'),), trans=('READY', 'TEARDOWN'), trans_first=True, **gen)
        s.cmd(fn, 'MANAGE_PAGES', rest='PROVIDE_PAGES input_num_entries=0x0embedded_function=0x0 isPreCond: false',
              inp=(('op_mod', '0x0001 ALLOCATION_SUCCESS'), ('function_id', '0x0000'), ('input_num_entries', '0x00000000')),
              out=(('output_num_entries', '0x00000000'),), trans=('TEARDOWN', 'RECLAIM_PAGES_REGULAR'), trans_first=True,
              before=(('PagesManager.cpp:62', 'PAGES_FLOW', '%s AllocPages: requesting numPages: 0. pagesToAllocate: 0' % Synth.who(fn)),),
              **gen)
    for fn in reversed(pfs):
        s.cmd(fn, 'MANAGE_PAGES', rest='PROVIDE_PAGES input_num_entries=0x0embedded_function=0x0 isPreCond: false',
              inp=(('op_mod', '0x0001 ALLOCATION_SUCCESS'), ('function_id', '0x0000'), ('input_num_entries', '0x00000000')),
              out=(('output_num_entries', '0x00000000'),), trans=('RECLAIM_PAGES_INIT', 'CAN_DISABLE'), **gen)
        s.cmd(fn, 'DISABLE_HCA', inp=(('function_id', '0x0000'),), trans=('CAN_DISABLE', 'DISABLED_HCA'), trans_first=True, **gen)
    if pf1 == 'nodnic':
        s.cmd('PF1', 'NODNIC_DISABLE_DEVICE', **pf)
    s.tick(10)
    ps4 = variant in ('ps4', 'refused')
    s.cmd('PSF', 'TEARDOWN_HCA', rest='test stage: TEST_STAGE_TEARDOWN , hca_stage: HCA_STAGE_READY , profile: false '
          'isPreCond: false', inp=(('profile', '0x0000 Graceful_close'),),
          trans=('READY', 'CAN_DISABLE' if ps4 else 'TEARDOWN'), **gen)
    t_end = 'TST:0:0:%d' % (s.tid + 50)
    passed = True
    if ps4:
        s.tick(80)
        refused = variant == 'refused'
        s.cmd('PSF', 'DISABLE_HCA', inp=(('function_id', '0x0000'),), trans=('CAN_DISABLE', 'DISABLED_HCA'),
              status=0x3 if refused else 0, syndrome=0x5d52ee if refused else 0, **gen)
        if refused:
            s.rec('ContextChecker.cpp:187', t_end, 'I', 'FATAL', 'status != OK is supported only in error test on command '
                  'DISABLE_HCA DETAILS: syndrome=0x5d52ee')
            passed = False
    else:
        if variant == 'wa':
            total = sum(sizes)
            s.cmd('PSF', 'MANAGE_PAGES', rest='RECLAIM_PAGES input_num_entries=0x%xembedded_function=0x0 isPreCond: false' % total,
                  inp=(('op_mod', '0x0002 HCA_RETURN_PAGES'), ('function_id', '0x0002'), ('input_num_entries', '0x%08x' % total)),
                  out=(('output_num_entries', '0x00000000'),), trans=('TEARDOWN', 'DISABLED_HCA'),
                  after=(('PagesManager.cpp:121', 'PAGES_FLOW', 'returning numPages: 0 to vhca %s' % Synth.who('PSF')),
                         ('CmdManagePages.cpp:300', 'PAGES_FLOW', 'ReturnPagesPostExe num of pages=0x0')), **gen)
        drop = 'TST:0:0:%d' % (s.tid + 20)
        for op in (['MANAGE_PAGES', 'DISABLE_HCA'] if variant == 'stopped' else ['DISABLE_HCA']):
            s.rec('GeneralOp.cpp:343', drop, 'D', 'General', 'Generating op %s on client 0' % op)
            s.rec('CmdVhcaOtherFunc.cpp:139', drop, 'D', 'DROP', "%-20s: couldn't find target vhca for %s" % (op, op))
            s.rec('CmdTeardownFlow.cpp:65', drop, 'I', 'General', 'Operation failed %s ' % op)
        if variant == 'stopped':
            s.rec('CmdTeardownFlow.cpp:69', drop, 'I', 'FATAL', 'Fast Teardown failed DETAILS: [%s  TYPE=PSF; '
                  'HCA_STAGE=HCA_STAGE_TEARDOWN; quarantine state VhcaNotQuarantine] ' % Synth.who('PSF'))
            passed = False
    if not passed:
        msg = 'Fast Teardown failed' if variant == 'stopped' else 'status != OK is supported only in error test on command DISABLE_HCA'
        where = 'CmdTeardownFlow.cpp:69, in Func QuickTeardown' if variant == 'stopped' else 'ContextChecker.cpp:187, in Func CmdFatalWithMsg'
        s.tick(2000)
        s.rec('UtopxFatalHandler.cpp:229', t_end, 'I', 'UFATAL', '%s. "%s DETAILS: [...] "' % (where, msg))
        s.rec('UtopxFatalHandler.cpp:146', t_end, 'I', 'UFATAL', 'FATAL_ID: 0 MAIN_FATAL: %s. "%s DETAILS: [...] "' % (where, msg))
        s.rec('UtopxFatalHandler.cpp:150', t_end, 'F', 'General', 'Test failed')
    s.tick(5)
    s.rec('GeneralRandomTest.cpp:380', t_end, 'I', 'General', 'Test-status is %d' % (0 if passed else 1))
    s.rec('GeneralRandomTest.cpp:391', t_end, 'I', 'General', '')
    s.raw('')
    s.raw('\t\t              [TEST %s]              ' % ('PASSED' if passed else 'FAILED'))
    return s


# Trees for the PSF story's source references (stories/psf/refs.py): each anchor at a known line.
FW_FILES = {
    'src/main/page_supplier_func.c': ['/* PSF */'] * 9 + [
        'static void psf_pool_handle_teardown_hca_reclaim(void)',     # 10
        '{',
        '    memset(SP_gps, 0, BYTE_SIZE(*SP_gps) >> 2);',
        '    icm_mng_global_mode = 0;',
        '}',                                                           # 14
        '',
        'uint32 psf_teardown_hca(uint32 gvmi)',                        # 16
        '{',
        '    if (is_icm_mng_global_mode_enabled()) {',                 # 18
        '        psf_pool_handle_teardown_hca_reclaim();',
        '    }',                                                       # 20
        '    return 0;',
        '}'],
    'src/main/icm_access_layer.c': ['/* ICM */'] * 29 + [
        '    if (is_gvmi_psf(gvmi) && (HCA_STATE_PRE_INIT_ICM_DONE == toc->hca_state)) {',   # 30
        '        return disable_pre_init(gvmi);',
        '    }'],
}
UTOPX_FILES = {
    'src/hca/CmdManagePages.cpp': ['// utopx'] * 4 + [
        '        pageManager->SetReqPages(pageManager->GetNumPagesProvided()*-1);',             # 5
        '        in->op_mod = (req_pages < 0) ? RECLAIM_PAGES : PROVIDE_PAGES;',              # 6
        '                UFATAL_IF("PROVIDE_PAGES_RANGE pages are not contiguous", "first=");',  # 7
        '                pages.resize(1);',                                                     # 8
        '        in->input_num_entries = GenUint32(1, numPagesLeft);'],                       # 9
    'config/common_constraints.conf': ['# conf'] * 2 + [
        'icm_mng_global_keeps.total_icm_pages_to_allocate = [512000-1280000]'],               # 3
}


def make_trees(tmp, local_change=False):
    """A golan_fw and a utopx tree, each a clone of a bare 'server' repository with the files above pushed to it. With
    local_change, one local-only commit on top shifts every utopx line down by one. Returns run info 'trees'."""
    import subprocess

    def git(cwd, *args):
        return subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@t', '-c', 'init.defaultBranch=master'] + list(args),
                              cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()
    os.makedirs(tmp, exist_ok=True)
    trees = {}
    for repo, files in (('golan_fw', FW_FILES), ('utopx', UTOPX_FILES)):
        server = os.path.join(tmp, repo + '.git')
        work = os.path.join(tmp, repo)
        git(tmp, 'init', '-q', '--bare', server)
        git(tmp, 'clone', '-q', server, work)
        for path, lines in files.items():
            os.makedirs(os.path.join(work, os.path.dirname(path)), exist_ok=True)
            with open(os.path.join(work, path), 'w') as f:
                f.write('\n'.join(lines) + '\n')
        git(work, 'add', '-A')
        git(work, 'commit', '-q', '-m', 'files')
        git(work, 'push', '-q', 'origin', 'HEAD:master')
        git(work, 'fetch', '-q')
        if local_change and repo == 'utopx':
            for path, lines in files.items():
                with open(os.path.join(work, path), 'w') as f:
                    f.write('\n'.join(['// local'] + lines) + '\n')
            git(work, 'commit', '-q', '-am', 'local')
        trees[repo] = dict(path=work, commit=git(work, 'rev-parse', 'HEAD'))
    return trees
