# Write a test workspace: long.md, about as heavy as the real ledgers (540 KB, thousands of lines,
# tables, code, many headings), with a link to src/sample.cpp#L79 and one to other.md in the middle,
# tables whose first column holds 7-digit change numbers, and one heading too long for one line of the
# sidebar (section 43); src/sample.cpp, the code file the first link opens; and other.md. other.md links to
# lines of repo/pinned.cpp as of the commit in repo/ (?v=<commit>): line 20, moved to 23 since by 3 lines
# added at the top, and line 40, changed since (neither edit committed); and to anchors.md#run-25 (an <a id>
# in a table row) and anchors.md#run-log (a heading), which anchors.md has far down its page.
# Always the same content, so measurements compare across runs: the commit too, made with a fixed author,
# date and no user git config.
#   python3 make_sample.py <workspace dir>
import os
import shutil
import subprocess
import sys

ws = sys.argv[1]
os.makedirs(os.path.join(ws, 'src'), exist_ok=True)

with open(os.path.join(ws, 'src', 'sample.cpp'), 'w') as f:
    for n in range(1, 201):
        f.write('// line %d\n' % n if n != 79 else 'int line_79_is_here = 79;  // the link target\n')

para = ('第 {n} 段：PSF 回归里这一步把 VHCA 的页还给 FW，再查 `CmdTeardownHca.cpp` 的返回值。'
        'The teardown path frees the ICM pages of every function before the next seed; '
        'when one is missed the run stops at the FATAL line in the log. ') * 3
out = ['# 测试文档', '', '这份文档由 tools/make_sample.py 生成，用来测预览。', '']
for s in range(1, 86):
    title = '## %d. 第 %d 节' % (s, s)
    if s == 43:
        title += '：这一节的标题故意写得很长，目录里要折成几行显示，不能截成一行'
    out += [title, '']
    for p in range(6):
        out += [para.format(n=s * 10 + p), '']
    out += ['| Change | 内容 | 状态 |', '|---|---|---|']
    for r in range(8):
        out.append('| [%d](https://example.invalid/r/%d) | `[Test Bug] <EMU> sat-PF emu-manager delegation, '
                   'seed %d` 这一行故意写长，让第二列需要换行 | ✅ 10-%02d merged |' % (1459000 + s * 8 + r, 1459000 + s * 8 + r, 900000 + r, r % 28 + 1))
    out += ['', '```diff', '@@ -10,6 +10,7 @@ void Teardown()', ' {', '-    FreePages(vhca);',
            '+    FreePages(vhca, /*all*/ true);', '+    WaitForReturn(vhca);', ' }', '```', '']
    for p in range(3):
        out += ['- 列表第 %d 项：%s' % (p, para.format(n=p)[:120])]
    out.append('')
    if s == 42:
        out += ['链接测试：[sample.cpp:79 FATAL : VHCA does not return pages](src/sample.cpp#L79)，'
                '另一份文档 [other.md](other.md)', '']

with open(os.path.join(ws, 'long.md'), 'w') as f:
    f.write('\n'.join(out) + '\n')

repo = os.path.join(ws, 'repo')
shutil.rmtree(repo, ignore_errors=True)
os.makedirs(repo)
env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1', GIT_AUTHOR_NAME='make_sample',
           GIT_AUTHOR_EMAIL='make_sample@example.invalid', GIT_AUTHOR_DATE='2026-10-22T12:00:00Z',
           GIT_COMMITTER_NAME='make_sample', GIT_COMMITTER_EMAIL='make_sample@example.invalid',
           GIT_COMMITTER_DATE='2026-10-22T12:00:00Z')
def git(*args):
    return subprocess.run(['git'] + list(args), cwd=repo, env=env, check=True, capture_output=True, text=True).stdout.strip()
def write_pinned(lines):
    with open(os.path.join(repo, 'pinned.cpp'), 'w') as f:
        f.write('\n'.join(lines) + '\n')
pinned = ['// pinned line %d' % n for n in range(1, 61)]
pinned[19] = 'int cited_20 = 20;  // moved to line 23 by the lines added at the top'
pinned[39] = 'int cited_40 = 40;  // changed after the commit'
write_pinned(pinned)
git('init', '-q')
git('add', 'pinned.cpp')
git('commit', '-q', '-m', 'pinned.cpp')
commit = git('rev-parse', '--short=10', 'HEAD')
write_pinned(['// added after the commit'] * 3 + pinned[:39] + ['int cited_40 = 41;  // changed after the commit'] + pinned[40:])

with open(os.path.join(ws, 'other.md'), 'w') as f:
    f.write('# 另一份文档\n\n从 long.md 的链接打开，应该在新 tab 里。\n\n'
            '带 commit 的源码行链接：[pinned.cpp:20](repo/pinned.cpp?v=%s#L20)（之后上面加了 3 行），'
            '[pinned.cpp:40](repo/pinned.cpp?v=%s#L40)（之后这一行改了）。\n\n'
            '别的文件里的锚点：[Run log #25](anchors.md#run-25)（表格行里的 `<a id>`），'
            '[Run log](anchors.md#run-log)（标题）。\n' % (commit, commit))

anchors = ['# 锚点测试', '', '本页的锚点：[Run log #25](#run-25)（表格行里的 `<a id>`），[Run log](#run-log)（标题）。', '']
for s in range(1, 31):
    if s == 16:
        anchors += ['## Run log', '', '| # | 结果 |', '|---|---|']
        anchors += ['| <a id="run-%d"></a>%d | 第 %d 次，%s |' % (n, n, n, 'PASS' if n % 4 else 'FAIL：VHCA does not return pages')
                    for n in range(1, 61)]
        anchors.append('')
    anchors += ['## %d. 第 %d 节' % (s, s), '']
    for p in range(3):
        anchors += [para.format(n=s * 10 + p), '']
with open(os.path.join(ws, 'anchors.md'), 'w') as f:
    f.write('\n'.join(anchors) + '\n')
print('%s: long.md %d KB, %d lines; other.md; src/sample.cpp; repo/pinned.cpp at %s; anchors.md'
      % (ws, os.path.getsize(os.path.join(ws, 'long.md')) // 1024, len(out), commit))
