// Where the lines a link cites as of a commit are now. [VHCA.cpp:5149](../src/hca/VHCA.cpp?v=6faa4de858#L5149)
// cites line 5149 of VHCA.cpp as of commit 6faa4de858; since then the worktree may have moved to another commit or
// been edited. git diff between that commit and the file in the worktree tells where the line is now.
'use strict';
const { execFile } = require('child_process');
const fs = require('fs');
const path = require('path');

// git <args> run in <dir>: what it prints; rejects when git fails
function git(dir, args) {
    return new Promise((resolve, reject) => execFile('git', args, { cwd: dir, maxBuffer: Infinity },
        (error, out) => error ? reject(error) : resolve(out)));
}

// git runs in the file's folder, or in the nearest folder above it that still exists
function existingDir(file) {
    let dir = path.dirname(file);
    while (!fs.existsSync(dir)) {
        dir = path.dirname(dir);
    }
    return dir;
}

// Where the old lines from..to (counted from 1) are in the new file, from the hunks of `git diff -U0`: { start, end,
// changed }, or null when the diff adds the whole file. A hunk @@ -a,b +c,d @@ takes out old lines a..a+b-1 and puts
// new lines c..c+d-1 in their place; with b 0 it takes out none and puts its lines after old line a; with d 0 it puts
// none, and its place is the line that now follows, c+1. A line no hunk touches moves by the lines put in and taken
// out above it. When a hunk changes or deletes a cited line, or puts lines between them, changed is true and
// start..end are the lines in their place now: a cited line that a hunk took out is replaced by that hunk's new lines,
// so the range starts at its first or ends at its last; end < start when nothing at all is in their place.
function mapLines(diff, from, to) {
    if (/^new file mode /m.test(diff)) {
        return null;
    }
    let start, end, changed = false, shiftFrom = 0, shiftTo = 0;
    for (const [, a, b = '1', c, d = '1'] of diff.matchAll(/^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@/gm)) {
        const removed = Number(b), added = Number(d);
        // the old lines the hunk takes out are lo..hi-1 (with none, it goes in just before old line lo); the new
        // lines it puts in are first..last
        const lo = removed > 0 ? Number(a) : Number(a) + 1, hi = lo + removed;
        const first = added > 0 ? Number(c) : Number(c) + 1, last = first + added - 1;
        if (hi <= from) {
            shiftFrom += added - removed;
        }
        if (hi <= to) {
            shiftTo += added - removed;
        }
        if (hi > from && lo <= to) {
            changed = true;
            if (removed > 0 && lo <= from) {
                start = first;
            }
            if (removed > 0 && to < hi) {
                end = last;
            }
        }
    }
    return { start: start ?? from + shiftFrom, end: end ?? to + shiftTo, changed };
}

// Lines from..to of <file> as of <commit>, in the worktree file now (edits not committed included): { sha, start,
// end, changed } as mapLines has them, sha the commit in full; { sha, gone: true } when the file is no longer in the
// worktree; null when the repository the file is in has no such commit, or the commit has no such file.
async function locate(file, commit, from, to) {
    const dir = existingDir(file);
    const sha = (await git(dir, ['rev-parse', '--verify', '--quiet', commit + '^{commit}']).catch(() => '')).trim();
    if (!sha) {
        return null;
    }
    if (!fs.existsSync(file)) {
        return { sha, gone: true };
    }
    const lines = mapLines(await git(dir, ['diff', '--no-color', '--no-ext-diff', '-U0', sha, '--', path.relative(dir, file)]), from, to);
    return lines && { sha, ...lines };
}

// The text of <file> as of <commit>
function fileAt(file, commit) {
    const dir = existingDir(file);
    return git(dir, ['show', commit + ':./' + path.relative(dir, file)]);
}

module.exports = { locate, fileAt };
