"""Parse one utopx log: records, commands (LOG_OP), the functions they target, and their dumps."""
import re

ANSI = re.compile(r'\x1b\[[0-9;]*m')
REC = re.compile(r'^(\S+\.(?:cpp|h|c|hpp):\d+)\s+\(([^)]*)\)\s+(\d\d:\d\d:\d\d\.\d+)\s+\[(\w)\]\s+(\S+)\s+:\s?(.*)$')
OPRE = re.compile(r'^([A-Z_0-9]+(?: [A-Z_0-9]+)*)\s*:\s*\[G\]\[VHCA=(0x[0-9a-f]+):GVMI=(0x[0-9a-f]+):PORT=\w+:DBDF=([\w:.]+):HIX=\w+\]\s*(.*)$')
NOISE = re.compile('|'.join([
    r'Generating target vhca', r'Generating resources', r'Generating operation', r'service thread', r'Generation attempt',
    r'Manually generating', r'UpdateDB is done', r'Sending cmdif doorbell', r'Updating operation', r'Cloning the operation',
    r'Updating WRAPPER', r'wait for barrier', r'Checking vhca validity', r' current vhca ', r'Starting streams', r'Stopping streams',
    r'Executing operation', r'Executing [A-Z_]+\.\.\.', r'Post Executing', r'Verify [A-Z_]+ operation', r'Printing Log drop',
    r'PORT\.cpp', r'HcaCapsManager', r'InitHcaCapStage', r'Set done to all caps', r'updating VHCA=', r'Ver done',
    r'Initializing device', r'CmdQueue PA', r'Initializing bit cleared', r'DmaDesc\.cpp', r'Generating op ', r'Updating [A-Z_]+\.\.\.',
    r'orig Mac', r'Add expected event', r'Moving to test stage', r'DROP :', r'targetType:', r'exec vhca:', r'Performing Command on',
    r'setting first time hca cap', r'Setting cap ', r'UpdateAfterFirst', r'done BuildRequ', r'Starting Scenario', r'trust level',
    r'HISTOGRAM', r'IsMsixEn',
]))
NUMRE = r'input_num_entries=(0x[0-9a-f]+?)(?=embedded|\s|$)'  # LOG_OP glues the next field on: ...=0x3c73cembedded_function=0x0
DUMPSKIP = re.compile(r'^\s*(SLOT|INPUT|OUTPUT)\b|sw_owner_id|^\s*$')


def squeeze(s):
    return re.sub(r' {2,}', ' ', s.strip())


def secs(t):
    h, m, s = t.split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)


class Log:
    def __init__(self, path):
        self.path = path
        self.lines = [None]
        self.rec = {}
        self.owner = [None]
        self.tabs = {}          # record line -> seconds since the first midnight; keeps counting across midnight
        cur, prev, day = None, None, 0
        with open(path, encoding='utf-8', errors='replace') as f:
            for n, raw in enumerate(f, 1):
                t = ANSI.sub('', raw.rstrip('\n'))
                self.lines.append(t)
                m = REC.match(t)
                if m:
                    cur = m.group(2)
                    self.rec[n] = m.groups()
                    sec = secs(m.group(3))
                    if prev is not None and sec < prev - 43200:
                        day += 1
                    prev = sec
                    self.tabs[n] = sec + 86400 * day
                self.owner.append(cur)
        self.ops = []
        for n, r in self.rec.items():
            if r[4] != 'LOG_OP':
                continue
            m = OPRE.match(r[5])
            if m:
                self.ops.append(dict(n=n, thr=r[1], time=r[2], t=self.tabs[n], opcode=m.group(1), vhca=m.group(2),
                                     gvmi=m.group(3), dbdf=m.group(4), rest=m.group(5)))
        types = {}
        for r in self.rec.values():
            for v, ty in re.findall(r'VHCA=(0x[0-9a-f]+):GVMI=\w+:TYPE=(\w+)', r[5]):
                types.setdefault(v, ty)
        gen = {}
        for o in self.ops:
            gen.setdefault(o['vhca'], (o['gvmi'], o['dbdf']))
        self.fn = {}
        for v, (g, d) in gen.items():
            self.fn[v] = 'PSF' if types.get(v) == 'PSF' else 'PF%d' % int(d.rsplit('.', 1)[1], 16)
        self.fn_info = {self.fn[v]: dict(vhca=v, gvmi=g, dbdf=d) for v, (g, d) in gen.items()}
        others = sorted(set(types) - set(gen))   # the checker's copies of the functions; a log may have none
        self.checker = re.compile(r'VHCA=(%s)\b' % '|'.join(others)) if others else None
        for o in self.ops:
            o['fn'] = self.fn[o['vhca']]

    def is_checker(self, text):
        """True for a line about a checker copy of a function (utopx's second model); pages show the generator copy."""
        return bool(self.checker and self.checker.search(text))

    def first(self, rx, after=0):
        """The first line after `after` that matches, or None."""
        c = re.compile(rx)
        return next((n for n in range(after + 1, len(self.lines)) if c.search(self.lines[n])), None)

    def get_op(self, opcode, fn, nth=0, rest=None, after=0):
        """The nth command of that opcode sent by that function (after a line), or None."""
        hits = [o for o in self.ops if o['opcode'] == opcode and o['fn'] == fn and o['n'] > after
                and (rest is None or re.search(rest, o['rest']))]
        return hits[nth] if len(hits) > nth else None

    def is_debug(self):
        """A walkthrough needs a debug-level log (debug_conf.xml): it shows the command dumps (LOG_KEY_CMDIF)."""
        return any(r[4] == 'LOG_KEY_CMDIF' for r in self.rec.values())

    def verdict(self):
        """How the run ended: the PASSED/FAILED line, the test status, the MAIN_FATAL line and the FATAL/UFATAL records."""
        st = self.first(r'Test-status is \d+')
        return dict(passed=self.first(r'\[TEST PASSED\]'), failed=self.first(r'\[TEST FAILED\]'),
                    status=(st, int(re.search(r'Test-status is (\d+)', self.lines[st]).group(1))) if st else None,
                    main_fatal=self.first(r'MAIN_FATAL:'),
                    fatal=[n for n, r in sorted(self.rec.items()) if r[4] == 'FATAL'],
                    ufatal=[n for n, r in sorted(self.rec.items()) if r[4] == 'UFATAL'])

    def find(self, rx, after=0, nth=0):
        hits = [n for n in range(after + 1, len(self.lines)) if re.search(rx, self.lines[n])]
        return hits[nth]

    def findall(self, rx):
        return [n for n in range(1, len(self.lines)) if re.search(rx, self.lines[n])]

    def op(self, opcode, fn, nth=0, rest=None):
        hits = [o for o in self.ops if o['opcode'] == opcode and o['fn'] == fn and (rest is None or re.search(rest, o['rest']))]
        return hits[nth]

    def threads(self, o):
        kind, suf = o['thr'].split(':', 1)
        return {o['thr']} if kind == 'TST' else {'GEN:' + suf, 'EXE:' + suf, 'VER:' + suf}

    def op_lines(self, o):
        thr, ths = o['thr'], self.threads(o)
        start = o['n']
        for k in range(o['n'] - 1, max(0, o['n'] - 6000), -1):
            if self.owner[k] == thr:
                start = k
        end = o['n']
        for k in range(o['n'], min(len(self.lines), o['n'] + 30000)):
            if self.owner[k] in ths:
                end = k
                r = self.rec.get(k)
                if r and 'Ver done' in r[5] and r[1] in ths:
                    break
        return [k for k in range(start, end + 1) if self.owner[k] in ths]

    def keep(self, k, fields=None, keep=()):
        t = self.lines[k]
        if any(re.search(p, t) for p in keep):
            return True
        if k in self.rec:
            return bool(self.rec[k][5].strip()) and not (self.is_checker(t) or NOISE.search(t))
        if DUMPSKIP.search(t):
            return False
        s = t.strip()
        if s.startswith('--------') or fields is None:
            return True
        return s.split(':', 1)[0].strip() in fields
