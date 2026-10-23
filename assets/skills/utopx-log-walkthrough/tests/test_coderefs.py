"""wt.coderefs against throwaway git repositories: a bare 'server', a clone with it as origin, local commits on top.

  cd ~/myGit/crosslv/assets/skills/utopx-log-walkthrough && python3 -B -m unittest tests.test_coderefs -v
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from wt import coderefs  # noqa: E402
from wt.coderefs import CodeRef, CodeRefError, html, label, resolve  # noqa: E402

A_C = '''/* a */
int f(void)
{
    step_one();
    step_two();
    return 0;
}
int g(void)
{
    step_two();
    return 1;
}
'''

ENV = dict(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1', GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t',
           GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@t')
_saved = {}


def setUpModule():
    for k, v in ENV.items():
        _saved[k] = os.environ.get(k)
        os.environ[k] = v


def tearDownModule():
    for k, v in _saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def git(cwd, *args):
    return subprocess.run(['git', '-C', cwd] + list(args), check=True, capture_output=True, text=True).stdout.strip()


def commit(work, files, msg):
    for name, text in files.items():
        p = os.path.join(work, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w') as f:
            f.write(text)
    git(work, 'add', '-A')
    git(work, 'commit', '-q', '-m', msg)
    return git(work, 'rev-parse', 'HEAD')


class CodeRefsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        setUpModule()
        cls.tmp = tempfile.mkdtemp()
        server = os.path.join(cls.tmp, 'server.git')
        subprocess.run(['git', 'init', '-q', '--bare', '-b', 'master', server], check=True)
        cls.work = work = os.path.join(cls.tmp, 'work')
        subprocess.run(['git', 'clone', '-q', server, work], check=True, capture_output=True)
        git(work, 'checkout', '-q', '-b', 'master')
        cls.A = commit(work, {'src/a.c': A_C, 'src/b.c': 'int b;\n'}, 'A')
        git(work, 'push', '-q', 'origin', 'HEAD:master')                     # A is on the server
        # a patchset: A with g() returning 2, kept only as refs/changes/34/1234/2
        cls.P = commit(work, {'src/a.c': A_C.replace('return 1;', 'return 2;')}, 'P')
        git(work, 'update-ref', 'refs/changes/34/1234/2', cls.P)
        git(work, 'reset', '-q', '--hard', cls.A)
        cls.B = commit(work, {'src/b.c': 'int b = 1;\n'}, 'B')               # local, a.c unchanged
        cls.C = commit(work, {'src/a.c': '/* moved */\n' + A_C}, 'C')        # local, a.c lines move
        git(work, 'reset', '-q', '--hard', cls.B)
        cls.D = commit(work, {'src/a.c': A_C + 'int h(void);\n'}, 'D')       # local, a.c changed below g() only
        git(work, 'reset', '-q', '--hard', cls.B)
        cls.R = commit(work, {'src/a.c': A_C.replace('return 1;', 'return 2;')}, 'R')   # local, a.c as in the patchset
        git(work, 'reset', '-q', '--hard', cls.B)
        cls.E = commit(work, {'src/a.c': A_C + 'int k(void)\n{\n}\n'}, 'E')    # local, a function the server lacks
        cls.patch = os.path.join(cls.tmp, 'run.diff')
        with open(cls.patch, 'w') as f:
            f.write('--- a/src/a.c\n+++ b/src/a.c\n@@ -1,2 +1,3 @@\n /* a */\n+int added;\n int f(void)\n')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)
        tearDownModule()

    def trees(self, sha, **kw):
        return {'golan_fw': dict(path=self.work, commit=sha, **kw)}

    def test_anchor_and_rule1(self):
        r = resolve(CodeRef('golan_fw', 'src/a.c', r'^int f\('), self.trees(self.A))
        self.assertEqual((r['line'], r['end'], r['text']), (2, None, 'int f(void)'))
        self.assertEqual(r['url'], 'https://git-nbu.nvidia.com/r/plugins/gitiles/golan_fw/+/%s/src/a.c#2' % self.A)
        self.assertTrue(r['exact'])
        self.assertEqual(r['commit'], self.A)

    def test_range_by_regex_and_count(self):
        r = resolve(CodeRef('golan_fw', 'src/a.c', r'^int f\(', end=r'^\}'), self.trees(self.A))
        self.assertEqual((r['line'], r['end']), (2, 7))
        r = resolve(CodeRef('golan_fw', 'src/a.c', r'^int f\(', end=3), self.trees(self.A))
        self.assertEqual((r['line'], r['end']), (2, 4))
        self.assertEqual(label(r), 'a.c:2-4')

    def test_nth_and_within(self):
        r = resolve(CodeRef('golan_fw', 'src/a.c', r'step_two', nth=1), self.trees(self.A))
        self.assertEqual(r['line'], 10)
        r = resolve(CodeRef('golan_fw', 'src/a.c', r'step_two', within=r'^int g\('), self.trees(self.A))
        self.assertEqual(r['line'], 10)
        with self.assertRaisesRegex(CodeRefError, 'block'):
            resolve(CodeRef('golan_fw', 'src/a.c', r'step_two', within=r'^int z\('), self.trees(self.A))

    def test_ambiguous_and_missing(self):
        with self.assertRaisesRegex(CodeRefError, 'matches 2 lines'):
            resolve(CodeRef('golan_fw', 'src/a.c', r'step_two'), self.trees(self.A))
        with self.assertRaisesRegex(CodeRefError, 'not found'):
            resolve(CodeRef('golan_fw', 'src/a.c', r'step_three'), self.trees(self.A))
        with self.assertRaisesRegex(CodeRefError, 'no src/zz.c'):
            resolve(CodeRef('golan_fw', 'src/zz.c', r'x'), self.trees(self.A))
        with self.assertRaisesRegex(CodeRefError, 'no commit'):
            resolve(CodeRef('golan_fw', 'src/a.c', r'x'), self.trees('0123456789abcdef'))
        with self.assertRaisesRegex(CodeRefError, 'no utopx tree'):
            resolve(CodeRef('utopx', 'src/a.c', r'x'), self.trees(self.A))

    def test_rule2_same_file(self):
        r = resolve(CodeRef('golan_fw', 'src/a.c', r'^int g\('), self.trees(self.B))
        self.assertEqual(r['line'], 8)
        self.assertEqual(r['commit'], self.B)
        self.assertEqual(r['url'], 'https://git-nbu.nvidia.com/r/plugins/gitiles/golan_fw/+/%s/src/a.c#8' % self.A)
        self.assertTrue(r['exact'])

    def test_rule5_moved(self):
        r = resolve(CodeRef('golan_fw', 'src/a.c', r'^int f\('), self.trees(self.C))
        self.assertEqual(r['line'], 3)
        self.assertEqual(r['url'], 'https://git-nbu.nvidia.com/r/plugins/gitiles/golan_fw/+/%s/src/a.c#2' % self.A)
        self.assertEqual((r['exact'], r['moved']), (False, (2, None)))
        self.assertTrue(r['why'].startswith('same code at %s' % self.A[:10]), r['why'])
        self.assertEqual(html(r), '<a href="%s"><code>a.c:3</code></a>' % r['url'])

    def test_no_server_copy(self):
        r = resolve(CodeRef('golan_fw', 'src/a.c', r'^int k\(', end=r'^\}'), self.trees(self.E))
        self.assertEqual((r['line'], r['end']), (13, 15))
        self.assertIsNone(r['url'])
        self.assertTrue(r['why'].startswith('local commit %s' % self.E[:10]), r['why'])
        self.assertEqual(html(r), '<code>a.c:13-15</code>')

    def test_rule3_patchset(self):
        r = resolve(CodeRef('golan_fw', 'src/a.c', r'return 2;'), self.trees(self.R, changes=[{'change': 1234, 'ps': 2}]))
        self.assertEqual(r['line'], 11)
        self.assertEqual(r['url'], 'https://git-nbu.nvidia.com/r/c/golan_fw/+/1234/2/src/a.c#11')
        self.assertTrue(r['exact'])
        self.assertEqual(html(r), '<a href="%s"><code>a.c:11</code></a>' % r['url'])

    def test_rule4_same_lines(self):
        r = resolve(CodeRef('golan_fw', 'src/a.c', r'^int f\(', end=r'^\}'), self.trees(self.D))
        self.assertEqual((r['line'], r['end']), (2, 7))
        self.assertEqual(r['url'], 'https://git-nbu.nvidia.com/r/plugins/gitiles/golan_fw/+/%s/src/a.c#2' % self.A)
        self.assertEqual((r['exact'], r['moved']), (False, None))

    def test_patch_applied(self):
        r = resolve(CodeRef('golan_fw', 'src/a.c', r'^int f\('), self.trees(self.A, patch=self.patch))
        self.assertEqual(r['line'], 3)
        self.assertEqual((r['exact'], r['moved']), (False, (2, None)))
        r = resolve(CodeRef('golan_fw', 'src/a.c', r'^int added;'), self.trees(self.A, patch=self.patch))
        self.assertIsNone(r['url'])
        self.assertIn('run.diff', r['why'])
        bad = os.path.join(self.tmp, 'bad.diff')
        with open(bad, 'w') as f:
            f.write('--- a/src/a.c\n+++ b/src/a.c\n@@ -1,2 +1,3 @@\n /* nothing like this */\n+x\n int nope;\n')
        with self.assertRaisesRegex(CodeRefError, 'does not apply'):
            resolve(CodeRef('golan_fw', 'src/a.c', r'^int f\('), self.trees(self.A, patch=bad))
        # a patch that does not touch the file leaves it, and its link, as the commit has them
        r = resolve(CodeRef('golan_fw', 'src/b.c', r'^int b'), self.trees(self.A, patch=self.patch))
        self.assertTrue(r['exact'])

    def test_cache_is_per_tree(self):
        self.assertTrue(any(k[0] == 'blob' for k in coderefs._cache))


if __name__ == '__main__':
    unittest.main()
