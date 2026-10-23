"""Stories: one package per feature. A story decides which steps a page has and what each step says."""
import importlib

NAMES = ('psf',)


def pick(L, name=None):
    """(story module, None), or (None, why no story fits the log)."""
    why = []
    for n in ([name] if name else NAMES):
        try:
            story = importlib.import_module('stories.' + n)
        except ImportError:
            return None, 'no story named %s (stories: %s)' % (n, ', '.join(NAMES))
        reason = story.match(L)
        if reason is None:
            return story, None
        why.append('%s: %s' % (n, reason))
    return None, '; '.join(why)
