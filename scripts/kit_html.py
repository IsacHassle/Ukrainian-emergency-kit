"""Turns an authority's web page into the kit's Markdown (what the reader and the AI index read).

`to_markdown(html, containers)` keeps only the text inside the first container that the page has (a container is
`tag` or `tag.class`, from the Official Guide source in the country config), with headings, lists, tables, bold and
italics, and drops everything around it: menus, forms, scripts, share buttons, videos, images. `page_title(html,
suffixes)` is the page's <title> without the site's name.

Uses only Python's standard library, so it runs on the system python3 3.9 and in CI without extra packages. The
parser is tolerant: a page with a stray or missing end tag still gives its text, because an end tag closes the
nearest open tag of that name and whatever was opened inside it.
"""
import html
import re
from html.parser import HTMLParser

# Elements whose content is never part of a guide.
DROP = {"script", "style", "noscript", "svg", "nav", "form", "button", "iframe", "figure", "header", "footer",
        "aside", "picture", "video", "audio", "select", "template", "head", "dialog", "canvas", "map", "object", "embed"}
# Class names (any part of a class) that mark page furniture inside an article.
DROP_CLASS = re.compile(r"breadcrumb|cookie|share|social|print-link|related|comments|pagination|newsletter|subscribe", re.I)
VOID = {"br", "hr", "img", "input", "meta", "link", "area", "base", "col", "source", "track", "wbr", "param"}
BLOCK = {"p", "div", "section", "article", "main", "blockquote", "pre", "ul", "ol", "li", "table", "tr", "dl", "dt", "dd",
         "h1", "h2", "h3", "h4", "h5", "h6", "address", "details", "summary", "fieldset", "tbody", "thead", "tfoot", "center"}
HEADING = {"h1": 2, "h2": 3, "h3": 4, "h4": 5, "h5": 6, "h6": 6}   # the guide's own title is the h1 line, so these start at ##
EMPHASIS = {"b": "**", "strong": "**", "i": "*", "em": "*"}


def _matches(container, tag, attrs):
    want_tag, _, want_class = container.partition(".")
    if tag != want_tag:
        return False
    return not want_class or want_class in (dict(attrs).get("class") or "").split()


class _Converter(HTMLParser):
    def __init__(self, container):
        super().__init__(convert_charrefs=True)
        self.container = container
        self.stack = []        # [tag, dropped, is_container_root]
        self.inside = False    # inside the container
        self.done = False      # the container is closed
        self.lines = []
        self.buf = []          # inline text of the line being written
        self.prefix = ""       # what starts the next line: "## ", "- ", "1. "
        self.lists = []        # open lists: ["ul"|"ol", item number]
        self.marks = []        # (tag, index in buf) of open bold/italic
        self.row = None        # cells of the table row being read
        self.cell = None
        self.header_row = False
        self.found = False

    # ---- output ----
    def flush(self):
        text = re.sub(r"\s+", " ", "".join(self.buf)).strip()   # \s also covers no-break and line separator spaces
        if self.prefix.startswith("#"):
            text = text.replace("*", "")   # a heading is bold already
        self.buf = []
        self.marks = []
        if text:
            self.lines.append(self.prefix + text)
        self.prefix = ""
        return bool(text)

    def blank(self):
        if self.lines and self.lines[-1] != "":
            self.lines.append("")

    def dropping(self):
        return any(entry[1] for entry in self.stack)

    # ---- parser callbacks ----
    def handle_starttag(self, tag, attrs):
        if self.done:
            return
        if tag in VOID:
            if self.inside and not self.dropping():
                if tag == "br":
                    if self.cell is not None:
                        self.buf.append(" ")
                    else:
                        self.flush()
                elif tag == "hr":
                    self.flush()
            return
        root = False
        if not self.inside:
            if _matches(self.container, tag, attrs):
                self.inside = root = self.found = True
            self.stack.append([tag, False, root])
            return
        classes = dict(attrs).get("class") or ""
        # A nested <article> is a list of other posts (a "latest news" block), never part of this guide.
        dropped = tag in DROP or tag == "article" or bool(DROP_CLASS.search(classes)) or "hidden" in dict(attrs) or dict(attrs).get("aria-hidden") == "true"
        self.stack.append([tag, dropped, False])
        if dropped or self.dropping():
            return
        if tag in HEADING:
            self.flush()
            self.blank()
            self.prefix = "#" * HEADING[tag] + " "
        elif tag in ("ul", "ol"):
            self.flush()
            start = dict(attrs).get("start") or "1"
            self.lists.append([tag, int(start) if start.isdigit() else 1])
        elif tag == "li":
            self.flush()
            if self.lists:
                kind, number = self.lists[-1]
                self.prefix = "  " * (len(self.lists) - 1) + ("- " if kind == "ul" else "%d. " % number)
                self.lists[-1][1] += 1
            else:
                self.prefix = "- "
        elif tag == "table":
            self.flush()
            self.blank()
        elif tag == "tr":
            self.row = []
            self.header_row = False
        elif tag in ("td", "th"):
            self.cell = []
            self.header_row = self.header_row or tag == "th"
        elif tag in EMPHASIS:
            self.marks.append((tag, len(self.cell if self.cell is not None else self.buf)))
        elif tag in BLOCK and self.cell is None:
            self.flush()
            if tag not in ("div", "section", "article", "main", "summary"):
                self.blank()

    def handle_endtag(self, tag):
        if self.done or tag in VOID:
            return
        names = [e[0] for e in self.stack]
        if tag not in names:
            return
        while True:
            entry = self.stack.pop()
            self._close(entry)
            if entry[0] == tag:
                break
            if self.done:
                return

    def _close(self, entry):
        tag, dropped, root = entry
        if root:
            self.flush()
            self.inside = False
            self.done = True
            return
        if not self.inside or dropped or self.dropping():
            return
        if tag in EMPHASIS:
            target = self.cell if self.cell is not None else self.buf
            for i in range(len(self.marks) - 1, -1, -1):
                if self.marks[i][0] == tag:
                    start = self.marks.pop(i)[1]
                    inner = "".join(target[start:])
                    del target[start:]
                    core = inner.strip()
                    if core and not core.startswith(EMPHASIS[tag]):   # nested bold in bold would double the marks
                        lead = inner[:len(inner) - len(inner.lstrip())]
                        tail = inner[len(inner.rstrip()):]
                        target.append(lead + EMPHASIS[tag] + core + EMPHASIS[tag] + tail)
                    else:
                        target.append(inner)
                    break
        elif tag in ("td", "th"):
            if self.row is not None and self.cell is not None:
                text = re.sub(r"\s+", " ", "".join(self.cell)).strip().replace("|", "/")
                self.row.append(text)
            self.cell = None
        elif tag == "tr":
            if self.row and any(self.row):
                self.lines.append("| " + " | ".join(self.row) + " |")
                if self.header_row:
                    self.lines.append("|" + "---|" * len(self.row))
            self.row = None
        elif tag in HEADING:
            self.flush()
            self.blank()
        elif tag in ("ul", "ol"):
            self.flush()
            if self.lists:
                self.lists.pop()
            if not self.lists:
                self.blank()
        elif tag == "li":
            self.flush()
        elif tag == "table":
            self.blank()
        elif tag in BLOCK and self.cell is None:
            self.flush()
            if tag not in ("div", "section", "article", "main", "summary"):
                self.blank()

    def handle_data(self, data):
        if self.inside and not self.done and not self.dropping():
            (self.cell if self.cell is not None else self.buf).append(data)


def to_markdown(page, containers):
    """The Markdown of the page's article, or None when the page has none of the containers."""
    for container in containers:
        parser = _Converter(container)
        parser.feed(page)
        parser.close()
        parser.flush()
        if parser.found:
            lines = []
            for line in parser.lines:
                if line == "" and (not lines or lines[-1] == ""):
                    continue
                if line and lines and line == lines[-1] and not line.startswith(("|", "-")):
                    continue   # a heading or line written twice in a row
                lines.append(line)
            text = "\n".join(lines).strip()
            if text:
                return text
    return None


def page_title(page, suffixes=()):
    """The text of <title> with the site's name cut off ("Shelter - Dovidka.info" -> "Shelter"), or ""."""
    m = re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
    title = re.sub(r"\s+", " ", html.unescape(m.group(1))).strip() if m else ""
    for suffix in suffixes:
        if title.endswith(suffix):
            title = title[:-len(suffix)].strip()
    return title
