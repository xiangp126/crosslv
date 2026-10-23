"""The step the engine adds when a run fails: what utopx dropped right before, the FATAL, and how the run ended."""
import collections
import re

from .model import Step


def fatal_summary(L):
    """Where the run stopped: dict(line, where, func, msg) from its MAIN_FATAL line (or its first FATAL record);
    None when the log has neither."""
    v = L.verdict()
    n = v['main_fatal']
    if n is None:
        if not v['fatal']:
            return None
        n = v['fatal'][0]
        r = L.rec[n]
        return dict(line=n, where=r[0], func=None, msg=r[5].split(' DETAILS:')[0].strip())
    text = L.lines[n]
    m = re.search(r'MAIN_FATAL: (\S+?:\d+), in Func (\w+)\.\s*"?(.*)$', text)
    if not m:
        return dict(line=n, where=None, func=None, msg=text.split('MAIN_FATAL:', 1)[1].strip())
    msg = re.split(r' DETAILS:|"', m.group(3), 1)[0].strip()
    return dict(line=n, where=m.group(1), func=m.group(2), msg=msg)


def failed(v):
    return bool(v['failed'] or v['main_fatal'] or v['fatal'] or (v['status'] and v['status'][1] != 0))


def failure_step(L, steps):
    """The last step of a failed run, or None when the run passed. It joins the flow of the last step before the failure."""
    v = L.verdict()
    if not failed(v):
        return None
    fs = fatal_summary(L)
    ends = [n for n in [v['main_fatal'], v['failed'], v['status'][0] if v['status'] else None] + v['fatal'] + v['ufatal'] if n]
    stop = min(ends)
    shown = {k for st in steps for k in st.lines + st.context}
    # what utopx dropped after its last command: "Operation failed <op>" records, and why the last one had no target
    last_op = max((o['n'] for o in L.ops if o['n'] < stop), default=0)
    dropped = [k for k in range(last_op + 1, stop) if k in L.rec and re.search(r'Operation failed [A-Z_]+', L.rec[k][5])]
    why = []
    if dropped:
        name = re.search(r'Operation failed ([A-Z_]+)', L.lines[dropped[-1]]).group(1)
        gen = max((k for k in range(last_op + 1, dropped[-1]) if ('Generating op %s ' % name) in (L.lines[k] + ' ')), default=None)
        if gen:
            why = [k for k in range(gen, dropped[-1]) if k in L.rec and L.rec[k][4] == 'DROP']
    end = [k for k in range(stop, len(L.lines)) if k in L.rec and (
        L.rec[k][4] in ('FATAL', 'UFATAL') or re.search(r'Test failed|Test-status is \d+|\[TEST FAILED\]', L.rec[k][5]))]
    lines = [k for k in dropped + why + end if k not in shown]
    if not lines:
        return None
    marks, notes = [], {}
    n = 0
    if dropped:
        n += 1
        c = collections.Counter(re.search(r'Operation failed ([A-Z_]+)', L.lines[k]).group(1) for k in dropped)
        sent = sum(1 for o in L.ops if dropped[0] < o['n'] < stop)
        marks.append((r'Operation failed [A-Z_]+', n))
        notes[n] = ('After its last command (L%s) utopx tries %s and drops each one%s (<code class="logsrc">%s</code>).' % (
            f'{last_op:,}', ', '.join('%s%s' % (op, '' if x == 1 else ' ×%d' % x) for op, x in c.items()),
            ': none is sent' if not sent else '', L.rec[dropped[0]][0]))
    if why:
        n += 1
        marks.append((r"couldn.t find target vhca for [A-Z_]+|no legal Intersection|can not execute_cmd_target_type", n))
        notes[n] = 'Why %s is dropped: utopx finds no function it may send the command to.' % name
    if fs:
        n += 1
        marks.append((re.escape(fs['msg']) if fs['msg'] else r'FATAL', n))
        notes[n] = '<b>FATAL%s</b>%s: "%s". The run stops here.' % (
            ' in %s' % fs['func'] if fs['func'] else '', ' (<code class="logsrc">%s</code>)' % fs['where'] if fs['where'] else '', fs['msg'])
        if v['main_fatal'] and v['main_fatal'] in lines:
            n += 1
            marks.append((r'MAIN_FATAL: \S+', n))
            notes[n] = 'utopx reports it as the run\'s MAIN_FATAL.'
    if v['status'] or v['failed']:
        n += 1
        marks += [(r'Test-status is \d+', n), (r'\[TEST FAILED\]', n), (r'Test failed', n)]
        notes[n] = 'The run ends with test status %s: TEST FAILED.' % (v['status'][1] if v['status'] else '?')
    before = [st for st in steps if st.lines[0] < lines[0]]
    flow = before[-1].flow if before else (steps[0].flow if steps else 1)
    prev = before[-1].choreo if before else {}
    title = 'The run stops: %s' % (fs['msg'] if fs and fs['msg'] else 'test status %s' % (v['status'][1] if v['status'] else '?'))
    st = Step('run-fails', flow, title, lines, marks, notes)
    st.choreo = {k: x for k, x in prev.items() if k not in ('passed', 'cmds', 'scene')}
    st.choreo.update(cmds=[], banner='fail')
    st.caption = 'The run stops%s%s: "%s". Test status %s.' % (
        ' at %s' % fs['where'] if fs and fs['where'] else '', ' in %s' % fs['func'] if fs and fs['func'] else '',
        fs['msg'] if fs else 'FAILED', v['status'][1] if v['status'] else '?')
    return st
