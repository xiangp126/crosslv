#!/usr/bin/env python3
"""Build, check and compare walkthrough pages made from one utopx debug log.

  walkthrough.py build LOG --out FRAG.html [--standalone PAGE.html] [--run-info J] [--context C] [--story NAME] [--strict]
  walkthrough.py check PAGE.html [--log LOG]
  walkthrough.py golden OLD.html NEW.html [--rename old=new ...]
"""
import argparse
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main(argv=None):
    ap = argparse.ArgumentParser(prog='walkthrough.py', description='utopx log walkthrough pages')
    sub = ap.add_subparsers(dest='cmd', required=True)

    b = sub.add_parser('build', help='build a page from a debug log')
    b.add_argument('log')
    b.add_argument('--out', required=True, help='the page fragment to publish with the Artifact tool')
    b.add_argument('--standalone', help='also write a complete HTML file (the local copy)')
    b.add_argument('--run-info', help='JSON with the run facts the log does not carry')
    b.add_argument('--context', help='JSON with the page title and the context sentences (slots)')
    b.add_argument('--story', help='story name; default: the story whose match() accepts the log')
    b.add_argument('--strict', action='store_true', help='fail on any unresolved code reference or run fact')

    c = sub.add_parser('check', help='check a built page')
    c.add_argument('page')
    c.add_argument('--log', help='the log the page was built from: compare every shown line with it')

    g = sub.add_parser('golden', help='compare the visible text and the data of two pages')
    g.add_argument('old')
    g.add_argument('new')
    g.add_argument('--rename', action='append', default=[], metavar='OLD=NEW',
                   help='choreography key renamed between the two pages')

    a = ap.parse_args(argv)
    if a.cmd == 'golden':
        from wt import golden
        return golden.main(a)
    if a.cmd == 'check':
        from wt import checks
        return checks.main(a)
    if a.cmd == 'build':
        from wt import build
        return build.main(a)
    return 2


if __name__ == '__main__':
    sys.exit(main())
