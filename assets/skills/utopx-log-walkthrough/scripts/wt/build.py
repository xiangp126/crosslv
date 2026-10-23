"""build: one debug log -> a walkthrough page (fragment for the Artifact tool, optional standalone copy)."""
import re
import sys

from .coderefs import fill
from .failure import failure_step
from .log import Log
from .page import page
from .render import transitions_of
from .runinfo import load


def write_page(frag, out, standalone=None):
    ids = set(re.findall(r'id="([^"]+)"', frag))
    for ref in set(re.findall(r'href="#([^"]+)"', frag)):
        if ref not in ids:
            raise SystemExit('dangling link #' + ref)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(frag)
    if standalone:
        head, body = frag.split('<div class="wrap">', 1)
        with open(standalone, 'w', encoding='utf-8') as f:
            f.write('<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, '
                    'initial-scale=1, viewport-fit=cover">\n%s</head>\n<body><div class="wrap">%s</body></html>\n' % (head, body))


def main(args):
    import stories
    L = Log(args.log)
    if not L.is_debug():
        print('%s is not a debug log: it has no command dumps (LOG_KEY_CMDIF records). Run utopx again with '
              '--xml_conf_file debug_conf.xml.' % args.log, file=sys.stderr)
        return 2
    L.info = load(L, args.run_info)
    story, why = stories.pick(L, args.story)
    if story is None:
        print('no story fits %s: %s' % (args.log, why), file=sys.stderr)
        return 2
    steps, facts = story.build_steps(L)
    fs = failure_step(L, steps)
    if fs:
        steps.append(fs)
    frag = page(L, story, steps, facts, transitions_of(L))
    frag, errors, notes = fill(frag, getattr(story, 'CODEREFS', {}), L.info.get('trees'))
    for n in notes:
        print('source lines:', n)
    if errors or (args.strict and notes):
        for e in errors:
            print('source line not found:', e, file=sys.stderr)
        if args.strict and notes:
            print('--strict: every source line must be resolved from the trees in the run info', file=sys.stderr)
        return 1
    write_page(frag, args.out, args.standalone)
    print('steps', len(steps), 'bytes', len(frag.encode('utf-8')))
    for name, reason in facts.get('skipped', []):
        print('left out', name + ':', reason)
    print('run facts from', ', '.join(L.info['sources']))
    return 0
