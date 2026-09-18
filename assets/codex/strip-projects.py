#!/usr/bin/env python3
"""git clean filter for assets/codex/config.toml.

Codex appends a [projects."<path>"] entry every time you trust a new directory, and
~/.codex/config.toml is a symlink into this repo — so those entries land in version
control. They leak the local directory layout (ticket numbers, project names, home
paths) and are pure per-machine runtime state: nothing else in the repo reads them.

This filter drops them on the way into git. The working file is untouched, Codex keeps
writing to it freely, and a fresh clone simply starts with no trusted directories —
which is the correct default anyway.

Registered via .gitattributes + `git config filter.codexcfg.clean`; see assets/codex/README.md.
"""
import re
import sys

SECTION = re.compile(r'^\[')
PROJECTS = re.compile(r'^\[projects\.')

def main():
    out, skipping = [], False
    for line in sys.stdin.read().splitlines(True):
        if PROJECTS.match(line):
            skipping = True
            continue
        if skipping:
            # a new, non-projects section ends the skip; blank/keys in between are dropped
            if SECTION.match(line):
                skipping = False
            else:
                continue
        out.append(line)

    # collapse the blank-line run left where the projects block used to be
    text = re.sub(r'\n{3,}', '\n\n', ''.join(out))
    sys.stdout.write(text)

if __name__ == '__main__':
    main()
