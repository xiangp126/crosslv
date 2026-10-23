"""Tests on synthetic logs (tests/synth.py): the parser, the PSF story in each of its log shapes, the failure step, the
debug gate, the page checks. Run from the skill directory:

    python3 -B -m unittest discover -s tests -v
"""
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scripts'))
sys.dont_write_bytecode = True

import synth  # noqa: E402
import walkthrough  # noqa: E402
from wt import checks, golden  # noqa: E402
from wt.log import Log  # noqa: E402
from wt.render import fold_label  # noqa: E402

PS4_STEPS = ['psf-enable', 'psf-issi', 'psf-query-pages', 'psf-udriver', 'psf-range-1', 'psf-ranges', 'psf-caps', 'psf-init', 'pf-enable',
             'pf0-boot-pages', 'pf0-init', 'pf0-regular', 'page-request-eq', 'no-page-request', 'pf0-teardown', 'pf0-reclaim',
             'pf0-disable', 'psf-teardown', 'psf-disable']


class Run:
    """One synthetic log and the page built from it."""

    def __init__(self, tmp, name, **kw):
        self.log = os.path.join(tmp, name + '.log')
        with open(self.log, 'w', encoding='utf-8') as f:
            f.write(synth.psf_run(**kw).text())
        self.frag = os.path.join(tmp, name + '.frag.html')
        self.page_path = os.path.join(tmp, name + '.html')
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.rc = walkthrough.main(['build', self.log, '--out', self.frag, '--standalone', self.page_path])
        self.out, self.err = out.getvalue(), err.getvalue()
        if self.rc == 0:
            with open(self.page_path, encoding='utf-8') as f:
                self.page = f.read()
            self.data = golden.page_data(self.page)
            self.regions = golden.regions(self.page)
            self.ids = [s['id'] for s in self.data['steps']]

    def left_out(self):
        return re.findall(r'^left out (\w+): (.*)$', self.out, flags=re.M)

    def text(self, region):
        return '\n'.join(self.regions[region])

    def stage(self, sid):
        return self.data['stages'][self.ids.index(sid)]

    def check(self):
        return checks.run(self.page_path, self.log)


class PsfPages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='wt-test-')
        cls.runs = {}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_of(self, name, **kw):
        if name not in self.runs:
            self.runs[name] = Run(self.tmp, name, **kw)
        r = self.runs[name]
        self.assertEqual(r.rc, 0, r.err)
        return r

    def assertClean(self, r):
        rep = r.check()
        self.assertEqual(rep.errors, [])
        self.assertEqual(rep.warnings, [])

    def test_ps4_run(self):
        r = self.run_of('ps4')
        self.assertEqual(r.ids, PS4_STEPS)
        self.assertEqual(r.left_out(), [])
        self.assertClean(r)
        say, cho = r.data['say'], r.data['choreo']
        self.assertIn('0x40000000', say['psf-range-1'])
        self.assertIn('247,612', say['psf-range-1'])
        self.assertTrue(say['psf-ranges'].startswith('Four more ranges are accepted'))
        self.assertIn('718,814 pages', say['psf-ranges'])
        pf_cmds = sum(1 for o in Log(r.log).ops if o['fn'] in ('PF0', 'PF1'))
        self.assertEqual(say['no-page-request'], '3 iterations, %d PF commands, 3 events. None of them is a page request.' % pf_cmds)
        self.assertEqual([c[0] for c in cho['pf-enable']['cmds']], ['PF1', 'PF0'])
        self.assertTrue(cho['pf-enable']['par'])
        self.assertEqual(cho['psf-ranges']['pool'], 5)
        self.assertTrue(cho['psf-disable']['passed'])
        self.assertEqual(r.stage('psf-init')['PSF'], 'READY')
        self.assertEqual(r.stage('pf0-regular')['PF0'], 'READY')
        self.assertEqual(r.stage('psf-teardown')['PSF'], 'CAN_DISABLE')
        self.assertEqual(r.stage('psf-disable'), {'PSF': 'DISABLED_HCA', 'PF0': 'DISABLED_HCA', 'PF1': 'DISABLED_HCA'})
        self.assertIn('TEST PASSED', r.text('hero'))
        self.assertIn('The pool: five ranges', r.text('flow-1 head'))
        self.assertIn('PF0 and PF1 come up at the same time', r.text('flow-2 head'))
        self.assertNotIn('run-fails', r.ids)

    def test_chips_follow_each_command(self):
        r = self.run_of('ps4')
        psf = lambda sid: [s['PSF'] if s else None for s in r.data['chips'][sid]]  # noqa: E731
        self.assertEqual(psf('psf-issi'), ['ENABLED_HCA', 'QUERY_ISSI', 'SET_ISSI'])
        self.assertEqual(psf('psf-caps'), ['BOOT_PAGES_ALLOCTED', 'QUERY_HCA_CAP_MAX', 'SET_HCA_CAP', 'INIT_PAGES_ALLOCTED'])
        self.assertEqual([s['PF0'] for s in r.data['chips']['pf0-boot-pages']], ['SET_ISSI', 'BOOT_PAGES_QUERY', 'BOOT_PAGES_ALLOCTED'])
        # in the teardown flow utopx prints the stage change just before the command: it still belongs to that command
        self.assertEqual([s['PF0'] for s in r.data['chips']['pf0-teardown']], ['READY', 'TEARDOWN'])
        self.assertEqual([s['PF0'] for s in r.data['chips']['pf0-reclaim']], ['TEARDOWN', 'RECLAIM_PAGES_REGULAR'])
        for i, sid in enumerate(r.ids):
            seq = r.data['chips'][sid]
            if seq:
                self.assertEqual(seq[-1], r.data['stages'][i], sid)
        self.assertEqual(r.data['say']['psf-issi'], 'Before the page commands, utopx and FW agree on the command interface version: ISSI 1.')
        self.assertIn('only bit 1 set (its last byte reads 0x02, every other byte 0)', r.text('step psf-issi'))

    def test_two_builds_are_identical(self):
        r = self.run_of('ps4')
        again = Run(self.tmp, 'ps4-again')
        self.assertEqual(golden.compare(r.page.replace('ps4.log', 'X'), again.page.replace('ps4-again.log', 'X')), [])

    def test_wa_run(self):
        r = self.run_of('wa', variant='wa')
        self.assertEqual(r.ids, PS4_STEPS[:-1] + ['psf-return', 'psf-no-disable'])
        self.assertClean(r)
        self.assertEqual(r.data['say']['psf-return'], 'utopx asks for all 718,814 pages back. FW returns 0 entries.')
        self.assertEqual(r.data['choreo']['psf-no-disable']['wa'], 'PSF')
        self.assertIn('Redmine 5357823', r.text('flow-4 head'))

    def test_one_range(self):
        r = self.run_of('one', sizes=(609521,))
        self.assertEqual(r.left_out(), [('psf_ranges', 'the run sends 1 range')])
        self.assertNotIn('psf-ranges', r.ids)
        self.assertClean(r)
        self.assertIn('The pool: one range, 609,521 pages', r.text('flow-1 head'))
        self.assertIn('Not in this run' + 'Not shown: the run sends 1 range.', r.text('summary').replace('\n', ''))
        self.assertIn("udriver maps the first 2381 MiB", r.data['say']['psf-udriver'])
        self.assertIn('595 × 1024 pages + 1 × 241', r.text('scene'))

    def test_pf1_nodnic(self):
        r = self.run_of('nodnic', pf1='nodnic')
        self.assertEqual(r.ids, PS4_STEPS)
        self.assertClean(r)
        self.assertEqual([c[0] for c in r.data['choreo']['pf-enable']['cmds']], ['PF0'])
        step = r.text('step pf-enable')
        self.assertIn('PF0 enables itself', step)
        self.assertIn('PF1 runs as NODNIC', step)
        self.assertIn('PF0: DISABLE_HCA', r.text('step pf0-disable'))
        self.assertEqual(r.data['say']['pf0-disable'], 'PF0 is off. PF1 runs as NODNIC.')
        self.assertIn('one host PF, PF0 (PF1 runs as NODNIC). It enables itself', r.text('flow-2 head'))
        self.assertNotIn('come up at the same time', r.text('flow-2 head'))

    def test_stopped_run_ends_in_a_failure_step(self):
        r = self.run_of('stopped', variant='stopped', pf1='nodnic', sizes=(609521,))
        self.assertEqual(r.ids[-1], 'run-fails')
        self.assertIn(('psf_disable', 'no DISABLE_HCA from PSF'), r.left_out())
        self.assertClean(r)
        self.assertEqual(r.data['steps'][-1]['title'], 'The run stops: Fast Teardown failed')
        self.assertEqual(r.data['choreo']['run-fails']['banner'], 'fail')
        self.assertIn('TEST FAILED · test status 1 · MAIN_FATAL at CmdTeardownFlow.cpp:69 in QuickTeardown', r.text('hero'))
        fail = r.text('step run-fails')
        self.assertIn('tries MANAGE_PAGES, DISABLE_HCA and drops each one: none is sent', fail)
        self.assertIn('Why DISABLE_HCA is dropped', fail)
        self.assertIn('FATAL in QuickTeardown', fail)
        self.assertIn('The run stops after the PSF\'s TEARDOWN_HCA', r.text('flow-4 head'))
        self.assertIn('TEST FAILED · test status 1', r.text('scene'))

    def test_refused_disable(self):
        r = self.run_of('refused', variant='refused')
        self.assertEqual(r.ids, PS4_STEPS + ['run-fails'])
        self.assertClean(r)
        self.assertEqual(r.data['steps'][-2]['title'], "The PSF's DISABLE_HCA is refused")
        self.assertEqual(r.data['choreo']['psf-disable']['cmds'][0][2:4], ['status 0x03', 'bad'])
        self.assertFalse(r.data['choreo']['psf-disable']['passed'])
        self.assertIn('FW refuses it', r.text('step psf-disable'))
        self.assertIn('status != OK', r.data['steps'][-1]['title'])

    def test_run_across_midnight(self):
        r = self.run_of('midnight', start=(23, 59, 59))
        self.assertEqual(r.ids, PS4_STEPS)
        self.assertClean(r)
        rel = [s['rel'] for s in r.data['steps']]
        self.assertEqual(rel, sorted(rel))
        self.assertLess(rel[-1], 60)
        self.assertTrue(all(56 <= x <= 988 for x in r.data['mapX']))
        times = [s['time'] for s in r.data['steps']]
        self.assertTrue(times[0].startswith('23:59') and times[-1].startswith('00:00'))

    def test_non_debug_log_is_refused(self):
        r = Run(self.tmp, 'nodebug', debug=False)
        self.assertEqual(r.rc, 2)
        self.assertIn('not a debug log', r.err)
        self.assertIn('--xml_conf_file debug_conf.xml', r.err)
        self.assertFalse(os.path.exists(r.page_path))

    def test_check_catches_a_changed_line_and_a_wrong_fold(self):
        r = self.run_of('ps4')
        bad = os.path.join(self.tmp, 'tampered.html')
        page = r.page.replace('Performing Quick Init on vhca', 'Performing Quick Unit on vhca', 1)
        page = re.sub(r'⋯ (\d+) lines not shown', lambda m: '⋯ %d lines not shown' % (int(m.group(1)) + 1), page, count=1)
        with open(bad, 'w', encoding='utf-8') as f:
            f.write(page)
        errors = checks.run(bad, r.log).errors
        self.assertTrue(any('shows text that is not in the log' in e for e in errors), errors)
        self.assertTrue(any('says' in e and 'the gap is' in e for e in errors), errors)


class SourceLines(unittest.TestCase):
    """Source lines the story cites are found in the run's trees and linked; without trees no number is shown."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='wt-test-')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def build_with(self, name, trees):
        os.makedirs(os.path.join(self.tmp, name), exist_ok=True)
        if trees is not None:
            with open(os.path.join(self.tmp, name, 'run.runinfo.json'), 'w') as f:
                json.dump({'trees': trees}, f)
        return Run(os.path.join(self.tmp, name), 'run')

    def test_resolved_on_the_server(self):
        trees = synth.make_trees(os.path.join(self.tmp, 'server'))
        r = self.build_with('linked', trees)
        self.assertEqual(r.rc, 0, r.err)
        self.assertEqual(r.check().errors, [])
        fw, ut = trees['golan_fw']['commit'], trees['utopx']['commit']
        gitiles = 'https://git-nbu.nvidia.com/r/plugins/gitiles/'
        self.assertIn('<a class="cref" href="%sgolan_fw/+/%s/src/main/page_supplier_func.c#10" title="golan_fw %s, the commit the run '
                      'used"><code>page_supplier_func.c:10-14</code></a>' % (gitiles, fw, fw[:10]), r.page)
        self.assertIn('<code>page_supplier_func.c:18-20</code>', r.page)
        self.assertIn('<code>icm_access_layer.c:30-32</code>', r.page)
        self.assertIn('href="%sfw_ver/utopx/+/%s/src/hca/CmdManagePages.cpp#7"' % (gitiles, ut), r.page)
        self.assertIn('<code>common_constraints.conf:3</code>', r.page)
        self.assertIn('the tested FW, <code>%s</code>' % fw[:10], r.page)
        self.assertIn('Source lines', r.text('summary'))

    def test_local_commit_links_the_server_copy(self):
        trees = synth.make_trees(os.path.join(self.tmp, 'local'), local_change=True)
        r = self.build_with('approx', trees)
        self.assertEqual(r.rc, 0, r.err)
        # the run's tree has every utopx line one lower; the link opens the server copy at its own line
        self.assertRegex(r.page, r'<a class="cref approx" href="[^"]+CmdManagePages\.cpp#7" title="The run used utopx [0-9a-f]{10}, '
                                 r'a local commit; the link opens the same code at [0-9a-f]{10}, lines 7 there"><code>'
                                 r'CmdManagePages\.cpp:8</code></a>')

    def test_without_trees_no_number_is_shown(self):
        r = self.build_with('bare', None)
        self.assertEqual(r.rc, 0, r.err)
        self.assertIn('source lines: the run info has no golan_fw tree', r.out)
        self.assertIn('<code class="cref">page_supplier_func.c</code>', r.page)
        self.assertEqual(r.check().errors, [])

    def test_a_missing_line_stops_the_build(self):
        trees = synth.make_trees(os.path.join(self.tmp, 'gone'))
        os.remove(os.path.join(trees['utopx']['path'], 'config', 'common_constraints.conf'))
        subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-q', '-am', 'drop'], cwd=trees['utopx']['path'],
                       check=True, capture_output=True)
        trees['utopx']['commit'] = 'HEAD'
        r = self.build_with('missing', trees)
        self.assertEqual(r.rc, 1)
        self.assertIn('source line not found: pool_size_conf', r.err)
        self.assertFalse(os.path.exists(r.page_path))

    def test_check_flags_a_hand_written_line(self):
        r = self.build_with('bare2', None)
        bad = os.path.join(self.tmp, 'bare2', 'hand.html')
        with open(bad, 'w', encoding='utf-8') as f:
            f.write(r.page.replace('</footer>', ' See <code>VHCA.cpp:4325</code>.</footer>'))
        self.assertIn('source line VHCA.cpp:4325 is not resolved from the run\'s tree', checks.run(bad, r.log).errors)


class Parser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='wt-test-')
        path = os.path.join(cls.tmp, 'p.log')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(synth.psf_run(iters=2).text())
        cls.L = Log(path)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_functions_and_checker_copies(self):
        L = self.L
        self.assertEqual({fn: v['vhca'] for fn, v in L.fn_info.items()}, {'PSF': '0x59', 'PF0': '0x57', 'PF1': '0x58'})
        for v in ('0x5a', '0x7b', '0xbc'):
            self.assertTrue(L.is_checker('updating VHCA=%s:GVMI=0x2:TYPE=PSF' % v))
        self.assertFalse(L.is_checker('VHCA=0x59:GVMI=0x2:TYPE=PSF'))
        self.assertFalse(any('\x1b' in t for t in L.lines[1:]))

    def test_sub_op_opcodes(self):
        ops = [o['opcode'] for o in self.L.ops]
        self.assertEqual(ops.count('MODIFY_QP RST2INIT_QP'), 2)
        o = self.L.get_op('MODIFY_QP RST2INIT_QP', 'PF1')
        what, has_cmd = fold_label(self.L, o['n'] - 1, o['n'] + 1)
        self.assertTrue(has_cmd)
        self.assertIn('PF1 MODIFY_QP RST2INIT_QP', what)

    def test_interleaved_commands_keep_their_own_lines(self):
        L = self.L
        cq = L.get_op('CREATE_CQ', 'PF0')
        qp = L.get_op('MODIFY_QP RST2INIT_QP', 'PF1')
        self.assertLess(cq['n'], qp['n'])
        for o, dump in ((cq, 'create_cq_in'), (qp, 'modify_qp_in')):
            lines = L.op_lines(o)
            self.assertTrue(all(L.owner[k] in L.threads(o) for k in lines))
            self.assertEqual(sum(1 for k in lines if dump in L.lines[k]), 1)
            self.assertTrue(any('Ver done' in L.lines[k] for k in lines))

    def test_verdict(self):
        v = self.L.verdict()
        self.assertIsNotNone(v['passed'])
        self.assertEqual(v['status'][1], 0)
        self.assertEqual((v['main_fatal'], v['fatal'], v['ufatal']), (None, [], []))


if __name__ == '__main__':
    unittest.main()
