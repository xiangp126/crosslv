"""A step of a walkthrough: the log lines it shows, the marks on them, the numbered notes, and what the stage does."""


class Skip(Exception):
    """A step builder raises it when the log does not have what the step shows; the step is left out."""


class Step:
    def __init__(self, sid, flow, title, lines, marks, notes, slide=None, raw_cap=140, caption='',
                 choreo=None, attachments=None, context=None, context_marks=None, context_label='Earlier in the log'):
        self.sid, self.flow, self.title = sid, flow, title
        self.lines = sorted(set(lines))
        self.marks = marks      # (regex on the whitespace-squeezed line, note number[, set of line numbers])
        self.notes = notes      # note number -> html
        self.slide = slide or []
        self.raw_cap = raw_cap
        self.caption = caption                       # the sentence under the stage
        self.choreo = choreo or {}                   # what the stage shows; see references/story-api.md
        self.attachments = list(attachments or [])   # html blocks shown after the log lines
        self.context = list(context or [])           # earlier log lines shown above the step's own lines
        self.context_marks = context_marks or []
        self.context_label = context_label
