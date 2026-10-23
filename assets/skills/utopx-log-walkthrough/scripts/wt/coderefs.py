"""Source lines a story cites, found by their code in the trees the run used, and linked to the same file on the server.

A story names a line by an anchor (a regex on the code), never by its number: CodeRef(repo, path, anchor) is looked up in
the file as the run's commit has it (git show; with the run's uncommitted patch applied when the run info names one), so
the number is right for that tree. The link goes to a commit the server has whose copy of the file is identical:

  1. the run's commit, when a remote-tracking ref contains it (gitiles);
  2. the newest commit under it that a remote-tracking ref contains, when the file has not changed in between (gitiles);
  3. a gerrit patchset the run info lists, when its copy of the file is identical (gerrit's file view when the patchset
     changes the file, gitiles at the patchset's commit otherwise).

When none has the identical file, the link goes to a server copy that has the same cited lines, marked exact=False:
at the same numbers (rule 4), or at other numbers (rule 5, moved = the server copy's numbers; the label keeps the run's).
Otherwise the result has no url, and why says so. A cited line that cannot be found is an error (CodeRefError), never a
guessed number.
"""
import os
import re
import subprocess
import tempfile

GITILES = 'https://git-nbu.nvidia.com/r/plugins/gitiles/'
GERRIT_C = 'https://git-nbu.nvidia.com/r/c/'
PROJECTS = {'golan_fw': 'golan_fw', 'utopx': 'fw_ver/utopx'}

_cache = {}


class CodeRefError(Exception):
    """A cited line that cannot be found as the run's tree has it."""


class CodeRef:
    """repo: 'golan_fw' or 'utopx'; path: inside the repo; anchor: regex on one line of the file; end: regex for the
    range's last line (searched from the anchor line on) or a line count; within: regex for the first line of the C/C++
    function (or block) the anchor is in, which ends at the next line that is a lone '}' at column 0; nth: which match of
    the anchor (0-based). Without nth, an anchor that matches more than one line is an error."""

    def __init__(self, repo, path, anchor, end=None, within=None, nth=None):
        self.repo, self.path, self.anchor, self.end, self.within, self.nth = repo, path, anchor, end, within, nth

    def __repr__(self):
        opt = ''.join(', %s=%r' % (k, getattr(self, k)) for k in ('end', 'within', 'nth') if getattr(self, k) is not None)
        return 'CodeRef(%r, %r, %r%s)' % (self.repo, self.path, self.anchor, opt)


def _run(args, cwd=None, data=None, env=None, timeout=60):
    r = subprocess.run(args, cwd=cwd, input=data, capture_output=True, env=env, timeout=timeout)
    return r.returncode, r.stdout, r.stderr.decode('utf-8', 'replace').strip()


def _git(tree, *args):
    """stdout of a git command in a tree, as bytes; CodeRefError when it fails."""
    rc, out, err = _run(['git', '-C', tree] + list(args))
    if rc:
        raise CodeRefError('git %s in %s: %s' % (' '.join(args), tree, (err.splitlines() or ['failed'])[-1]))
    return out


def _memo(key, fn):
    if key not in _cache:
        _cache[key] = fn()
    return _cache[key]


def _commit(tree, rev):
    if not os.path.isdir(tree):
        raise CodeRefError('no tree %s' % tree)
    return _memo(('commit', tree, rev), lambda: _git(tree, 'rev-parse', '--verify', '--quiet', rev + '^{commit}').decode().strip())


def _blob(tree, commit, path):
    """The blob id of a file at a commit, or None when the commit has no such file."""
    def get():
        rc, out, _ = _run(['git', '-C', tree, 'rev-parse', '--verify', '--quiet', '%s:%s' % (commit, path)])
        return out.decode().strip() if rc == 0 else None
    return _memo(('blob', tree, commit, path), get)


def _content(tree, commit, path, patch=None):
    """The file as bytes at a commit, with the patch applied when one is given and touches the file."""
    def get():
        if _blob(tree, commit, path) is None:
            raise CodeRefError('%s has no %s at %s' % (tree, path, commit[:10]))
        data = _git(tree, 'show', '%s:%s' % (commit, path))
        if not patch:
            return data
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, path)
            os.makedirs(os.path.dirname(f), exist_ok=True)
            with open(f, 'wb') as out:
                out.write(data)
            rc, _, err = _run(['git', 'apply', '--include=' + path, os.path.abspath(patch)], cwd=d,
                              env=dict(os.environ, GIT_CEILING_DIRECTORIES=d))
            if rc:
                raise CodeRefError('patch %s does not apply to %s at %s: %s' % (patch, path, commit[:10], err))
            with open(f, 'rb') as inp:
                return inp.read()
    return _memo(('content', tree, commit, path, patch), get)


def _hash(data):
    rc, out, err = _run(['git', 'hash-object', '--stdin'], data=data)
    if rc:
        raise CodeRefError('git hash-object: %s' % err)
    return out.decode().strip()


def _lines(data):
    return data.decode('utf-8', 'replace').split('\n')


def _on_server(tree, commit):
    """True when a remote-tracking ref contains the commit."""
    return _memo(('server', tree, commit), lambda: not _git(tree, 'rev-list', '-n', '1', commit, '--not', '--remotes').strip())


def _parent(tree, commit):
    rc, out, _ = _run(['git', '-C', tree, 'rev-parse', '--verify', '--quiet', commit + '^1'])
    return out.decode().strip() if rc == 0 else None


def _modified(tree, commit, path):
    """True when the commit changes the file against its first parent."""
    return bool(_git(tree, 'diff-tree', '--no-commit-id', '--name-only', '-r', commit, '--', path).strip())


def _patchset(tree, change, ps):
    """The commit of a gerrit patchset when it is in the local repository: a local refs/changes ref, else asked from the
    server with git ls-remote (one ref, BatchMode ssh). None when it cannot be found or is not fetched."""
    ref = 'refs/changes/%02d/%d/%d' % (int(change) % 100, int(change), int(ps))

    def get():
        rc, out, _ = _run(['git', '-C', tree, 'rev-parse', '--verify', '--quiet', ref + '^{commit}'])
        if rc == 0:
            return out.decode().strip()
        env = {k: v for k, v in os.environ.items() if k != 'DISPLAY'}
        env.update(GIT_SSH_COMMAND='ssh -o BatchMode=yes -o ConnectTimeout=10', GIT_TERMINAL_PROMPT='0')
        try:
            rc, out, _ = _run(['git', '-C', tree, 'ls-remote', 'origin', ref], env=env, timeout=40)
        except subprocess.TimeoutExpired:
            return None
        sha = out.decode().split()[0] if rc == 0 and out.strip() else None
        if sha and _run(['git', '-C', tree, 'cat-file', '-e', sha + '^{commit}'])[0] == 0:
            return sha
        return None
    return _memo(('patchset', tree, change, ps), get)


def _span(lines, ref, where):
    """(line, end) of a CodeRef in a file's lines, 1-based; CodeRefError when the anchor is missing or ambiguous."""
    lo, hi = 1, len(lines)
    if ref.within:
        wrx = re.compile(ref.within)
        lo = next((i for i, s in enumerate(lines, 1) if wrx.search(s)), None)
        if lo is None:
            raise CodeRefError('%s: block %r not found in %s' % (where, ref.within, ref.path))
        hi = next((i for i in range(lo + 1, len(lines) + 1) if lines[i - 1].rstrip() == '}'), len(lines))
    rx = re.compile(ref.anchor)
    hits = [i for i in range(lo, hi + 1) if rx.search(lines[i - 1])]
    if not hits:
        raise CodeRefError('%s: anchor %r not found in %s%s' % (where, ref.anchor, ref.path,
                                                                ' inside %r' % ref.within if ref.within else ''))
    if ref.nth is None and len(hits) > 1:
        raise CodeRefError('%s: anchor %r matches %d lines of %s (%s); give nth' % (
            where, ref.anchor, len(hits), ref.path, ', '.join(str(h) for h in hits[:8])))
    if ref.nth is not None and ref.nth >= len(hits):
        raise CodeRefError('%s: anchor %r matches %d lines of %s, nth=%d' % (where, ref.anchor, len(hits), ref.path, ref.nth))
    line = hits[ref.nth or 0]
    end = None
    if isinstance(ref.end, int):
        end = line + ref.end - 1
        if end > len(lines):
            raise CodeRefError('%s: %s has no line %d' % (where, ref.path, end))
    elif ref.end is not None:
        erx = re.compile(ref.end)
        end = next((i for i in range(line, len(lines) + 1) if erx.search(lines[i - 1])), None)
        if end is None:
            raise CodeRefError('%s: end %r not found after line %d of %s' % (where, ref.end, line, ref.path))
    return line, (end if end != line else None)


def _gitiles(repo, commit, path, line):
    return '%s%s/+/%s/%s#%d' % (GITILES, PROJECTS[repo], commit, path, line)


def _link(ref, t, tree, commit, blob, line, end, lines):
    """(url, exact, moved, why) for the resolved line, by the rules in the module docstring."""
    repo, path = ref.repo, ref.path
    candidates = []                     # (server commit, url pattern) for rules 4 and 5
    c = commit
    for _ in range(500):                # rules 1 and 2: down the first parents while the file stays the same
        same = _blob(tree, c, path) == blob
        if _on_server(tree, c):
            if same:
                return _gitiles(repo, c, path, line), True, None, None
            candidates.append((c, _gitiles(repo, c, path, 0).replace('#0', '#%d')))
            break
        if not same:
            # the file changed in a local commit: keep walking to the newest server commit, only as a rule-4 candidate
            p = c
            while p and not _on_server(tree, p):
                p = _parent(tree, p)
            if p:
                candidates.append((p, _gitiles(repo, p, path, 0).replace('#0', '#%d')))
            break
        c = _parent(tree, c)
        if c is None:
            break
    for ch in t.get('changes', []):     # rule 3: the patchsets the run info lists
        sha = _commit(tree, ch['commit']) if ch.get('commit') else _patchset(tree, ch['change'], ch['ps'])
        if not sha:
            continue
        gerrit = '%s%s/+/%d/%d/%s#%%d' % (GERRIT_C, PROJECTS[repo], int(ch['change']), int(ch['ps']), path)
        if _modified(tree, sha, path):
            if _blob(tree, sha, path) == blob:
                return gerrit % line, True, None, None
            candidates.append((sha, gerrit))
            continue
        # the patchset leaves the file as its parent has it: link the newest server commit with that copy
        p, pblob = sha, _blob(tree, sha, path)
        while p and not _on_server(tree, p) and _blob(tree, p, path) == pblob:
            p = _parent(tree, p)
        at = p if p and _on_server(tree, p) and _blob(tree, p, path) == pblob else sha
        if pblob == blob:
            return _gitiles(repo, at, path, line), True, None, None
        candidates.append((at, _gitiles(repo, at, path, 0).replace('#0', '#%d')))
    want = lines[line - 1:(end or line)]
    spans = []
    for sha, url in candidates:         # rules 4 and 5: the same cited lines in a server copy
        if _blob(tree, sha, path) is None:
            continue
        other = _lines(_content(tree, sha, path))
        try:
            oline, oend = _span(other, ref, sha[:10])
        except CodeRefError:
            continue
        if other[oline - 1:(oend or oline)] == want:
            spans.append((oline, oend, sha, url))
    for oline, oend, sha, url in sorted(spans, key=lambda x: (x[0], x[1]) != (line, end)):
        if (oline, oend) == (line, end):
            return url % line, False, None, 'same lines at %s; the file differs elsewhere' % sha[:10]
        return url % oline, False, (oline, oend), 'same code at %s, lines %d%s there' % (
            sha[:10], oline, '-%d' % oend if oend else '')
    why = 'local commit %s%s: no commit on the server has this file as the run used it' % (
        commit[:10], ' with %s' % os.path.basename(t['patch']) if t.get('patch') else '')
    return None, False, None, why


def resolve(ref, trees):
    """Find a CodeRef in the run's tree. trees: {'golan_fw': {'path': ..., 'commit': ..., 'changes': [{'change': N,
    'ps': P, 'commit': the patchset's commit, optional, saves a git ls-remote}], 'patch': optional diff the run's tree
    had on top}, 'utopx': {...}}. Returns dict(repo, path, line, end,
    text, commit, url, exact, moved, why): exact is True when the linked copy of the file is the run's; moved is the
    linked copy's (line, end) when the cited lines sit elsewhere there. Raises CodeRefError when the line cannot be found."""
    t = trees.get(ref.repo) if trees else None
    if not t or not t.get('path') or not t.get('commit'):
        raise CodeRefError('the run info has no %s tree (path and commit)' % ref.repo)
    tree = t['path']
    try:
        commit = _commit(tree, t['commit'])
    except CodeRefError:
        raise CodeRefError('%s has no commit %s' % (tree, t['commit']))
    patch = t.get('patch')
    if patch and not os.path.exists(patch):
        raise CodeRefError('no patch file %s' % patch)
    data = _content(tree, commit, ref.path, patch)
    lines = _lines(data)
    line, end = _span(lines, ref, '%s %s' % (ref.repo, commit[:10]))
    blob = _blob(tree, commit, ref.path) if data == _content(tree, commit, ref.path) else _hash(data)
    url, exact, moved, why = _link(ref, t, tree, commit, blob, line, end, lines)
    return dict(repo=ref.repo, path=ref.path, line=line, end=end, text=lines[line - 1].strip(), commit=commit,
                url=url, exact=exact, moved=moved, why=why)


def resolve_all(refs, trees):
    """{name: result} for a story's CODEREFS, and a list of 'name: error' for the ones that cannot be found."""
    got, errors = {}, []
    for name, ref in refs.items():
        try:
            got[name] = resolve(ref, trees)
        except CodeRefError as e:
            errors.append('%s: %s' % (name, e))
    return got, errors


def label(res):
    """'page_supplier_func.c:322-327'."""
    return '%s:%d%s' % (os.path.basename(res['path']), res['line'], '-%d' % res['end'] if res.get('end') else '')


def html(res):
    """The label as code, linked when there is a URL."""
    lab = '<code>%s</code>' % label(res)
    return '<a href="%s">%s</a>' % (res['url'], lab) if res.get('url') else lab


PLACE = re.compile(r'\[\[(ref|tree|crefs-note):?([\w.-]*)\]\]')
NOTE = (' <b>Source lines</b> (a file and its line numbers) are the lines in the trees the run used; a link opens '
        'them on the server, with a dotted underline when the run\'s commit is local and the link opens the same code in a '
        'server copy.')


def fill(page, refs, trees):
    """Replace a page's placeholders: [[ref:name]] with the resolved, linked source line, [[tree:repo]] with the run's
    commit, [[crefs-note]] with the line explaining source links (only when the page has one). Returns (page, errors,
    notes): errors are references that cannot be found, notes say what could not be resolved for want of a tree."""
    errors, notes, done = [], set(), {}

    def esc(s):
        return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

    def one(m):
        kind, name = m.groups()
        if kind == 'crefs-note':
            return m.group(0)
        if kind == 'tree':
            t = (trees or {}).get(name)
            if not t or not t.get('commit'):
                notes.add('the run info has no %s tree' % name)
                return 'the run\'s %s tree (not recorded)' % name
            return '<code>%s</code>' % t['commit'][:10]
        ref = refs.get(name)
        if ref is None:
            errors.append('%s: no such code reference in the story' % name)
            return '<code class="cref unresolved">%s</code>' % esc(name)
        if not (trees or {}).get(ref.repo):
            notes.add('the run info has no %s tree: source lines show the file only' % ref.repo)
            return '<code class="cref">%s</code>' % os.path.basename(ref.path)
        if name not in done:
            try:
                done[name] = resolve(ref, trees)
            except CodeRefError as e:
                done[name] = e
        r = done[name]
        if isinstance(r, CodeRefError):
            errors.append('%s: %s' % (name, r))
            return '<code class="cref unresolved">%s:?</code>' % os.path.basename(ref.path)
        if not r['url']:
            return '<code class="cref" title="%s">%s</code>' % (esc(r['why']), label(r))
        if r['exact']:
            title = '%s %s, the commit the run used' % (r['repo'], r['commit'][:10])
            return '<a class="cref" href="%s" title="%s"><code>%s</code></a>' % (r['url'], esc(title), label(r))
        title = 'The run used %s %s, a local commit; the link opens the %s' % (r['repo'], r['commit'][:10], r['why'])
        return '<a class="cref approx" href="%s" title="%s"><code>%s</code></a>' % (r['url'], esc(title), label(r))

    page = PLACE.sub(one, page)
    page = page.replace('[[crefs-note]]', NOTE if 'class="cref' in page else '')
    return page, errors, sorted(notes)
