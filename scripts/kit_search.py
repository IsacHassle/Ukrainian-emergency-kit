"""Finds what the AI reads before it answers in "From sources" (the AI page's books mode).

Two places are searched at the same time:
  - The kit's books, embedded in AnythingLLM (the Book index workspace named in the country config): the
    Official Guides, the brochure, the medical, water, food and knot books, NHS Medicines and Ready.gov.
  - The big medical libraries in Kiwix, which are too big to embed: the Libraries named in the country
    config (for Sweden WikiMed, MDWiki and MedlinePlus).
    The libraries are in English, so the AI first turns the question into English article titles;
    Kiwix finds the articles in a tenth of a second, and their most useful sections are passed on.

Either place may be missing (AnythingLLM not open, Kiwix not started): the other still works.
Uses only Python's standard library, like serve-web.py.
"""
import html
import html.parser
import json
import os
import re
import threading
import urllib.error
import urllib.parse
import urllib.request

import kit_country

KIT = os.environ.get("EK_KIT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the kit folder


def address(env, default):
    """(host, port) of a helper app. The defaults are where the apps normally listen; the tests point
    them at stand-ins (EK_OLLAMA, EK_ANYTHINGLLM, EK_KIWIX = "host:port") so they never meet a running kit."""
    host, _, port = (os.environ.get(env) or default).rpartition(":")
    return host, int(port)


OLLAMA_ADDR = address("EK_OLLAMA", "127.0.0.1:11434")
ANYTHINGLLM_ADDR = address("EK_ANYTHINGLLM", "127.0.0.1:3001")
KIWIX_ADDR = address("EK_KIWIX", "127.0.0.1:8090")   # the Library server

KEY_FILE = os.path.join(KIT, "tools", "anythingllm-api-key")
ANYTHINGLLM = "http://%s:%d/api" % ANYTHINGLLM_ADDR
KIWIX = "http://%s:%d" % KIWIX_ADDR
OLLAMA = "http://%s:%d" % OLLAMA_ADDR
WORKSPACE = kit_country.workspace()
MODEL = kit_country.models()["main"]
OPTIONS = {"num_ctx": 16384}   # room for the instructions, the excerpts and the conversation

# Kiwix libraries searched (from the country config), by the start of their file name. The "encyclopedia"
# ones use Wikipedia's article titles. (Sweden leaves CDC's library out: it is travel advice by country, too noisy.)
_LIBS = kit_country.COUNTRY["ai"]["libraries"]
# Only the English Libraries for now: the planning call returns English titles. Looking up Ukrainian titles in
# the Ukrainian Libraries is a later step.
WIKIS = [(l["prefix"], l["label"]) for l in _LIBS if l["kind"] == "encyclopedia" and l["language"] == "en"]
PLAIN = [(l["prefix"], l["label"]) for l in _LIBS if l["kind"] == "plain" and l["language"] == "en"]

PLAN_PROMPT = (
    "You prepare two searches for an offline crisis kit. Reply with exactly two lines and nothing else.\n"
    "SEARCH: the user's latest question rewritten so it stands on its own (bring in what an earlier question "
    "was about), in the user's own language.\n"
    "TERMS: 1 to 3 English encyclopedia article titles for a medical library (Wikipedia's medical articles and "
    "MedlinePlus), separated by semicolons. Use the shortest common title, for example: Burn (not Burn treatment), "
    "Hypothermia, Bleeding, Laceration, Tick-borne encephalitis, Water purification, Carbon monoxide poisoning, "
    "Ibuprofen. Name conditions, injuries or medicines, not whole fields (not Pediatrics). Write TERMS: NONE if the question is not about health, illness, injuries, medicines, poisoning, "
    "or safe drinking water and food.")

_lock = threading.Lock()
_key = None


def _request(url, body=None, headers=None, timeout=10):
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json"} if data else {}
    h.update(headers or {})
    return urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h), timeout=timeout)


# ---------- the kit's books (AnythingLLM) ----------

def _api_key(renew=False):
    """AnythingLLM's search needs a key. The kit makes one the first time and keeps it in tools/."""
    global _key
    with _lock:
        if _key and not renew:
            return _key
        if not renew and os.path.exists(KEY_FILE):
            _key = open(KEY_FILE).read().strip()
            if _key:
                return _key
        made = json.load(_request(ANYTHINGLLM + "/system/generate-api-key", {"name": kit_country.kit_name()}))
        _key = made["apiKey"]["secret"]
        fd = os.open(KEY_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(_key)
        return _key


def book_passages(query, top=6):
    """The passages in the kit's books that best match the question: [{"title", "text"}]."""
    found = None
    for renew in (False, True):
        try:
            resp = _request(f"{ANYTHINGLLM}/v1/workspace/{WORKSPACE}/vector-search", {"query": query[:2000], "topN": top},
                            {"Authorization": "Bearer " + _api_key(renew)}, timeout=60)
            found = json.load(resp).get("results", [])
            break
        except urllib.error.HTTPError as e:
            if e.code not in (401, 403):
                return []
        except (OSError, ValueError, KeyError, TypeError):
            return []
    out, seen = [], set()
    for r in found or []:
        text = re.sub(r"<document_metadata>.*?</document_metadata>\s*", "", r.get("text") or "", flags=re.S).strip()
        if text and text not in seen:
            seen.add(text)
            out.append({"title": (r.get("metadata") or {}).get("title") or "", "text": text})
    return out


# ---------- one quick call to the AI ----------

def plan(question, earlier=""):
    """(the question as a stand-alone search, English article titles or [] if it is not a health question)."""
    ask = (f"Earlier question: {earlier}\n" if earlier else "") + f"Latest question: {question}"
    body = {"model": MODEL, "stream": False, "think": False, "keep_alive": "30m",
            "messages": [{"role": "system", "content": PLAN_PROMPT}, {"role": "user", "content": ask[:3000]}],
            "options": dict(OPTIONS, temperature=0, num_predict=120)}
    try:
        reply = json.load(_request(OLLAMA + "/api/chat", body, timeout=180))["message"]["content"]
    except (OSError, ValueError, KeyError, TypeError):
        return question, []
    search, terms = question, []
    for line in reply.splitlines():
        m = re.match(r"\W*(SEARCH|TERMS)\W*:\s*(.*)", line, re.I)
        if not m:
            continue
        if m.group(1).upper() == "SEARCH":
            search = m.group(2).strip() or question
            continue
        for t in re.split(r"[;,]", m.group(2)):
            t = t.strip().strip("\"'.*").strip()
            if t and t.upper() != "NONE" and len(t) <= 60 and t not in terms:
                terms.append(t)
    return search, terms[:3]


# ---------- the big libraries (Kiwix) ----------

def _libraries():
    """The open Kiwix libraries we search: {content name: label}, newest version of each."""
    xml = _request(KIWIX + "/catalog/v2/entries?count=500", timeout=5).read().decode("utf-8", "ignore")
    newest = {}
    for name in re.findall(r'href="/content/([^"/]+)"', xml):
        for prefix, _ in WIKIS + PLAIN:
            if name.startswith(prefix + "_") and name > newest.get(prefix, ""):
                newest[prefix] = name
    return newest


def _search(books, pattern, n=8):
    query = [("books.name", b) for b in books] + [("pattern", pattern), ("format", "xml"), ("pageLength", str(n))]
    xml = _request(KIWIX + "/search?" + urllib.parse.urlencode(query), timeout=10).read().decode("utf-8", "ignore")
    hits = []
    for item in re.findall(r"<item>(.*?)</item>", xml, re.S):
        title, link = re.search(r"<title>(.*?)</title>", item, re.S), re.search(r"<link>(.*?)</link>", item, re.S)
        if title and link:
            hits.append((html.unescape(title.group(1)).strip(), html.unescape(link.group(1)).strip()))
    return hits


VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class _Text(html.parser.HTMLParser):
    """An article as plain text, by main section: [{"head", "subs", "paras"}]. The opening is section 0."""
    SKIP = {"head", "title", "script", "style", "nav", "header", "footer", "aside", "table", "sup", "figure",
            "noscript", "form", "button", "svg", "select", "iframe"}
    JUNK = {"usa-banner", "hide-offscreen", "breadcrumbs", "page-url", "print-only", "hatnote", "navbox", "reflist",
            "references", "mw-references-wrap", "infobox", "thumb", "gallery", "toc", "sidebar", "section-button",
            "noprint", "mw-editsection"}   # exact class or id names: menus, banners, reference lists
    BLOCKS = {"p", "li", "dd", "dt", "blockquote", "h1", "h2", "h3", "h4"}
    END = re.compile(r"^(references|see also|external links|further reading|notes|sources|bibliography|"
                     r"related (medlineplus )?(health topics|information)|review date|learn how to cite)", re.I)

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.buf, self.tag, self.sub, self.done = [], None, None, False
        self.skip_tag, self.skip_depth = None, 0
        self.sections = [{"head": "", "subs": [], "paras": []}]

    def handle_starttag(self, tag, attrs):
        if self.skip_tag:
            self.skip_depth += tag == self.skip_tag
            return
        a = dict(attrs)
        names = set(f"{a.get('class') or ''} {a.get('id') or ''}".split())
        if tag not in VOID and (tag in self.SKIP or (tag not in ("html", "body", "main") and names & self.JUNK)):
            self.flush()
            self.skip_tag, self.skip_depth = tag, 1
        elif tag in self.BLOCKS:
            self.flush()
            self.tag = tag

    def handle_endtag(self, tag):
        if self.skip_tag:
            if tag == self.skip_tag:
                self.skip_depth -= 1
                if self.skip_depth == 0:
                    self.skip_tag = None
            return
        if tag in self.BLOCKS:
            self.flush()
            self.tag = None

    def handle_data(self, data):
        if not self.skip_tag and not self.done:
            self.buf.append(data)

    def flush(self):
        text = re.sub(r"\s+", " ", "".join(self.buf)).strip()
        self.buf = []
        if not text or self.done:
            return
        if self.tag in ("h2", "h3", "h4") and self.END.match(text):
            self.done = True
        elif self.tag == "h2":
            self.sections.append({"head": text, "subs": [], "paras": []})
            self.sub = None
        elif self.tag in ("h3", "h4"):
            self.sections[-1]["subs"].append(text)
            self.sub = text
        elif self.tag != "h1" and len(text) > 25:
            self.sections[-1]["paras"].append(f"{self.sub}: {text}" if self.sub else text)
            self.sub = None


HIGH = re.compile(r"first aid|treatment|management|what to do|do not|home care|self.care|rewarming|"
                  r"when to (call|contact|see)", re.I)
MID = re.compile(r"symptom|signs|emergency|prevention|diagnosis", re.I)


def _excerpt(path, terms, limit=2400):
    """The opening of an article plus its most useful sections (first aid, treatment ...), as text."""
    p = _Text()
    p.feed(_request(KIWIX + path, timeout=10).read().decode("utf-8", "ignore"))
    p.flush()
    lead = " ".join(p.sections[0]["paras"])[:700]
    words = {w.lower() for t in terms for w in re.findall(r"[A-Za-z]{4,}", t)}
    scored = []
    for i, s in enumerate(p.sections[1:], 1):
        if not s["paras"]:
            continue
        names = " ".join([s["head"]] + s["subs"])
        score = 5 * bool(HIGH.search(names)) + 2 * bool(MID.search(names)) \
            + sum(w in (names + " " + s["paras"][0]).lower() for w in words)
        scored.append((-score, i, s["head"], " ".join(s["paras"])))
    out, used = ([lead] if lead else []), len(lead)
    for _, _, head, text in sorted(scored)[:3]:
        room = limit - used
        if room < 200:
            break
        piece = f"{head}: {text}"[:min(1100, room)]
        out.append(piece)
        used += len(piece)
    return "\n".join(out)


def _title_of(path):
    return urllib.parse.unquote(path.rstrip("/").split("/")[-1]).replace("_", " ")


def _book_of(link):
    parts = link.split("/")
    return parts[2] if len(parts) > 2 else ""


def library_articles(terms, limit=3):
    """Up to `limit` articles from Kiwix for the search terms: [{"title", "library", "href", "text"}]."""
    if not terms:
        return []
    try:
        libs = _libraries()
    except (OSError, ValueError):
        return []
    label = {libs[p]: name for p, name in WIKIS + PLAIN if p in libs}
    wikis = [libs[p] for p, _ in WIKIS if p in libs]
    plain = [libs[p] for p, _ in PLAIN if p in libs]
    picked, seen = [], set()

    def take(title, path):
        key = re.sub(r"[^a-z0-9]", "", title.lower())
        if key in seen or len(picked) >= limit:
            return False
        try:
            text = _excerpt(path, terms)
        except (OSError, ValueError):
            return False
        if len(text) < 200:
            return False
        seen.add(key)
        picked.append({"title": title, "library": label.get(_book_of(path), "Kiwix"), "href": path, "text": text})
        return True

    for n, term in enumerate(terms):
        # The encyclopedia article with this title (WikiMed first, then MDWiki), else one whose title has every word.
        got = False
        for book in wikis:
            path = f"/content/{book}/" + urllib.parse.quote((term[:1].upper() + term[1:]).replace(" ", "_"))
            try:
                final = urllib.parse.urlsplit(_request(KIWIX + path, timeout=5).geturl()).path   # follows redirects
            except (OSError, ValueError):
                continue
            got = take(_title_of(final), final)
            break
        if not got and wikis:
            try:
                hits = _search(wikis, term, 5)
            except (OSError, ValueError):
                hits = []
            words = term.lower().split()
            for title, link in hits:
                if all(w in title.lower() for w in words) and take(title, link):
                    break
        # For the main term, also the plain-language page (MedlinePlus often has a "First aid" section).
        if n == 0 and plain:
            try:
                hits = _search(plain, term)
            except (OSError, ValueError):
                hits = []
            hits = [h for h in hits if not re.search(r"multiple languages|series|spanish|español", h[0], re.I)
                    and not re.search(r"/(presentations|languages|lab-tests|genetics)/", h[1])]
            words = re.findall(r"[a-z]{4,}", term.lower()) or [term.lower()]
            hits = [h for h in hits if any(w in h[0].lower() for w in words)]   # the title must be about the term
            hits.sort(key=lambda h: term.lower() not in h[0].lower())          # titles naming all of it first
            for title, link in hits[:3]:
                if take(re.split(r"\s*[:|]\s*", title)[0], link):
                    break
    return picked


# ---------- together ----------

def gather(question, earlier=""):
    """Searches both places. Returns (book passages, library articles)."""
    out = {}

    def books(query):
        out["books"] = book_passages(query)

    jobs = []
    if not earlier:   # a first question can search the books while the AI picks the article titles
        jobs.append(threading.Thread(target=books, args=(question,), daemon=True))
        jobs[-1].start()
    search, terms = plan(question, earlier)
    if earlier:       # a follow-up ("and for a child?") searches with the rewritten, stand-alone question
        jobs.append(threading.Thread(target=books, args=(search,), daemon=True))
        jobs[-1].start()
    out["libs"] = library_articles(terms)
    for j in jobs:
        j.join(120)
    return out.get("books", []), out.get("libs", [])


def system_prompt(base, passages, articles):
    """The AI's instructions plus what was found, numbered so the answer can name its sources."""
    if not passages and not articles:
        return base + ("\n\nEXCERPTS FOR THIS QUESTION\nNothing in the kit's books or libraries matched this question. "
                       "Say so briefly, then answer carefully from what you know.")
    parts, n = [], 0
    for p in passages:
        n += 1
        name = re.sub(r"\.(pdf|md|txt)$", "", p["title"], flags=re.I)
        parts.append(f"[{n}] {name} (the kit's books)\n{p['text']}")
    for a in articles:
        n += 1
        parts.append(f"[{n}] {a['library']}: {a['title']}\n{a['text']}")
    ai = kit_country.COUNTRY["ai"]
    return base + (
        "\n\nEXCERPTS FOR THIS QUESTION\n"
        "Found in the kit's books and libraries for this question. Base your answer on them where they fit, "
        + ai["authorities"] + " first. Name the sources "
        "you used, only from the list below and by the name shown there (for example \"" + ai["example_source"] + "\" "
        "or \"WikiMed: Hypothermia\"); never name a source that is not below. "
        "The library excerpts are in English: translate what you use, and never mix English into a " + ai["answer_language"] + " answer. "
        "If the excerpts do not cover the question, say so and answer carefully.\n\n" + "\n\n".join(parts))
