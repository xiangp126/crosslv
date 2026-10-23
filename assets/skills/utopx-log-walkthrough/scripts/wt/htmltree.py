"""A small HTML tree for reading pages back: enough for the checks and the golden comparison."""
from html.parser import HTMLParser

VOID = {'br', 'img', 'hr', 'meta', 'link', 'input', 'wbr', 'col', 'source', 'path', 'circle', 'rect', 'line',
        'polyline', 'polygon', 'stop', 'use'}
BLOCK = {'div', 'p', 'li', 'tr', 'h1', 'h2', 'h3', 'h4', 'header', 'footer', 'section', 'article', 'summary',
         'details', 'dt', 'dd', 'table', 'thead', 'tbody', 'ul', 'ol', 'dl', 'figcaption', 'text', 'title'}


class Node:
    def __init__(self, tag, attrs, parent=None):
        self.tag, self.attrs, self.parent, self.kids = tag, dict(attrs), parent, []

    def cls(self):
        return (self.attrs.get('class') or '').split()

    def walk(self):
        for k in self.kids:
            if isinstance(k, Node):
                yield k
                yield from k.walk()

    def find_all(self, pred):
        return [n for n in self.walk() if pred(n)]

    def first(self, pred):
        return next((n for n in self.walk() if pred(n)), None)

    def text(self, titles=False):
        """Visible text; block elements start a new line. With titles, tooltip text is added in brackets."""
        out = []
        for k in self.kids:
            if isinstance(k, str):
                out.append(k)
            elif k.tag in ('script', 'style'):
                continue
            else:
                if k.tag in BLOCK:
                    out.append('\n')
                if titles and k.attrs.get('title'):
                    out.append(' [%s] ' % k.attrs['title'])
                out.append(k.text(titles))
                if k.tag in BLOCK:
                    out.append('\n')
        return ''.join(out)


class _Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node('root', [])
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs, self.cur)
        self.cur.kids.append(n)
        if tag not in VOID:
            self.cur = n

    def handle_startendtag(self, tag, attrs):
        self.cur.kids.append(Node(tag, attrs, self.cur))

    def handle_endtag(self, tag):
        n = self.cur
        while n is not self.root and n.tag != tag:
            n = n.parent
        if n is not self.root:
            self.cur = n.parent

    def handle_data(self, data):
        self.cur.kids.append(data)


def parse(page):
    t = _Tree()
    t.feed(page)
    t.close()
    return t.root
