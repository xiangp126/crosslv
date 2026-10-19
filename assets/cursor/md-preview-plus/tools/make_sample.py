# Write a test workspace: long.md, about as heavy as the real ledgers (540 KB, thousands of lines,
# tables, code, many headings), with a link to src/sample.cpp#L79 and one to other.md in the middle and
# tables whose first column holds 7-digit change numbers; src/sample.cpp, the code file the first link
# opens; and other.md.
# Always the same content, so measurements compare across runs.
#   python3 make_sample.py <workspace dir>
import os
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
    out += ['## %d. 第 %d 节' % (s, s), '']
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
with open(os.path.join(ws, 'other.md'), 'w') as f:
    f.write('# 另一份文档\n\n从 long.md 的链接打开，应该在新 tab 里。\n')
print('%s: long.md %d KB, %d lines; other.md; src/sample.cpp' % (ws, os.path.getsize(os.path.join(ws, 'long.md')) // 1024, len(out)))
