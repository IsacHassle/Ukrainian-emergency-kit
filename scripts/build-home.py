#!/usr/bin/env python3
"""Builds web/index.html, the kit's start page.

It asks the running Kiwix server (port 8090) which libraries are installed,
checks that every emergency link really opens, and writes one page with:
search across all libraries, the AI page and the map, emergency topics, key
PDF books, all libraries, and the country's emergency numbers. Run by share-library.sh on start.
The page's own texts are keys in web/lang/*.json (scripts/kit_lang.py): written here in the default language,
switched in the browser by lib/language.js. Texts from the country config come out in every language.
Every country fact comes from config/country.json (scripts/kit_country.py).
"""
import html
import json
import os
import re
import urllib.parse
import urllib.request

import kit_country
import kit_lang

KIWIX_PORT = os.environ.get("EK_KIWIX", "localhost:8090").rpartition(":")[2]   # the Library server (tests choose it)
KIWIX = "http://localhost:" + KIWIX_PORT
HOME = os.environ.get("EK_KIT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the kit folder
WEB = os.environ.get("EK_WEB") or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
DOCS = os.path.join(HOME, "documents")

# Everything about the country comes from the country config (config/country.json): the Emergency Topics
# (label, article, Official Guide), the Books, the Library groups, the emergency numbers.
# Each Emergency Topic names its WikiMed article in every language ("wikimed": {"uk": ..., "en": ...}); a link
# opens the article in the page language (Ukrainian WikiMed on УКР, English WikiMed on ENG). A topic's Official
# Guide ("official_guide", saved by the guide saver) opens first when it has one.
C = kit_country.COUNTRY
text = kit_country.text
TEXTS = kit_lang.load(WEB)   # the language files: every text the page itself says is a key in them
TOPICS = C["emergency_topics"]
# A topic's Official Guides ("official_guide": {"uk": [names], "en": [names]}, names as in config/pages.txt) are the
# ones the guide saver (scripts/fetch-pages.py) saved: the first one that is saved opens first, in the reader, with the
# encyclopedia article one tap away. Each page language has its own guides: the English page never opens a Ukrainian one.
OFFICIAL = {t["id"]: {code: ([n] if isinstance(n, str) else n) for code, n in (t.get("official_guide") or {}).items()} for t in TOPICS}
OFFICIAL_DIR = C["official_guides"]["folder"]
# The emergency topics shown straight away; the rest (a country may have more) are one tap away under "More".
FIRST = [t["id"] for t in sorted((t for t in TOPICS if t.get("first")), key=lambda t: t["first"])]
# The WikiMed Library of each language, by the start of its name (the newest version is the one installed).
WIKIMED = {l["language"]: l["prefix"] for l in C["ai"]["libraries"] if l["kind"] == "encyclopedia" and "medicine" in l["prefix"]}

# (label, description, path under documents/)
BOOKS = [(b["label"], b["description"], b["path"]) for b in C["books"]]

# Library groups: (heading, [(book name prefix, short description)])
GROUPS = [(g["heading"], [(l["prefix"], l["description"]) for l in g["libraries"]]) for g in C["library_groups"]]

ADVICE_ORDER = [s["id"] for s in C["official_guides"]["sources"]]
ADVICE_NAMES = {s["id"]: s["label"] for s in C["official_guides"]["sources"]}


def saved(code, stem):
    """(address, source) of a saved Official Guide in a language, or None. The default language's guides are in the
    guides folder, another language's in a subfolder named by its code (as scripts/fetch-pages.py saves them).
    A text opens in the reader, a PDF opens as itself."""
    sub = "" if code == kit_country.LANG else code + "/"
    for ext in (".md", ".pdf"):
        if os.path.exists(os.path.join(DOCS, OFFICIAL_DIR, *(sub + stem + ext).split("/"))):
            rel = "docs/" + "/".join(urllib.request.quote(p) for p in (OFFICIAL_DIR + "/" + sub + stem + ext).split("/"))
            return (("read/?f=" + rel) if ext == ".md" else rel, stem.split(" - ", 1)[0])
    return None


def saved_guides(code):
    """Every saved guide of a language, [(source, title, address)], in file name order."""
    folder = os.path.join(DOCS, OFFICIAL_DIR, *([] if code == kit_country.LANG else [code]))
    out = []
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        stem, ext = os.path.splitext(name)
        if ext in (".md", ".pdf") and " - " in stem:
            source, title = stem.split(" - ", 1)
            out.append((source, title, saved(code, stem)[0]))
    return out


def both(value):
    """A text from the country config in every language the kit has, as spans the page language picks from
    (CSS in lib/kit.css), so it switches without a script. A language without its own text shows the default."""
    langs = list(TEXTS)
    return "".join(f'<span data-l="{code}">{html.escape(text(value, code))}</span>' for code in langs)


# How a language is named in "home.urgent.<language>": the note on a topic that opens an article in the other language.
LANGUAGE_WORD = {"uk": "ukrainian", "en": "english"}

PRIMARY = next((n for n in C["emergency_numbers"] if n.get("primary")), C["emergency_numbers"][0])


def numbers_html():
    """The other emergency numbers and the radio station, as one line under the main number."""
    parts = [html.escape(n["number"]).replace(" ", "&nbsp;") + " " + both(n["label"])
             for n in C["emergency_numbers"] if n is not PRIMARY]
    return " · ".join(parts + [both(C["radio"]["label"])])


def jattr(data):
    """JSON for a single-quoted HTML attribute (data-p='...'): non-ASCII and quotes escaped the JSON way."""
    return json.dumps(data, ensure_ascii=True).replace("'", "\\u0027")


def kiwix_ok(path):
    try:
        req = urllib.request.Request(KIWIX + urllib.parse.quote(path, safe="/()"), method="HEAD")
        return urllib.request.urlopen(req, timeout=5).status in (200, 302)
    except Exception:
        return False


def catalog():
    try:
        x = urllib.request.urlopen(KIWIX + "/catalog/v2/entries?count=500", timeout=10).read().decode()
    except Exception:
        return []
    books = []
    for e in re.findall(r"<entry>(.*?)</entry>", x, re.S):
        name = re.search(r'href="/content/([^"/]+)', e)
        lang = re.search(r"<language>(.*?)</language>", e)
        title = re.search(r"<title>(.*?)</title>", e, re.S)
        if name:
            books.append({"name": name.group(1), "lang": lang.group(1) if lang else "",
                          "title": html.unescape(title.group(1)) if title else name.group(1)})
    return books


def main():
    books = catalog()
    by_prefix = lambda p: next((b for b in books if b["name"].startswith(p)), None)
    eng = [b["name"] for b in books if b["lang"] == C["search_languages"]["main"]]
    local = [b["name"] for b in books if b["lang"] == C["search_languages"]["country"]]

    # Each topic's article in each language's WikiMed Library, checked so that a renamed article drops out quietly.
    # A language without its article opens the other language's, and the link says so.
    emergency = []
    for t in TOPICS:
        found = {}
        for code, prefix in WIKIMED.items():
            book = by_prefix(prefix)
            path = t["wikimed"].get(code)
            if book and path and kiwix_ok(f"/content/{book['name']}/{path}"):
                found[code] = f"/viewer#{book['name']}/{urllib.parse.quote(path, safe='()')}"
        guides = {code: [g for g in map(lambda n: saved(code, n), OFFICIAL[t["id"]].get(code, [])) if g] for code in TEXTS}
        emergency.append((t, found, guides))

    # The Official Guides of each language, grouped by authority.
    advice_html, advice_counts = "", {}
    for code in TEXTS:
        advice = {}
        for src, title, href in saved_guides(code):
            advice.setdefault(src, []).append((title, href))
        advice_counts[code] = sum(len(v) for v in advice.values())
        body = "".join(
            f'<h3>{both(ADVICE_NAMES[src]) if src in ADVICE_NAMES else html.escape(src)}</h3><ul class="list cols">'
            + "".join(f'<li><a href="{href}">{html.escape(t)}</a></li>' for t, href in items) + "</ul>"
            for src, items in sorted(advice.items(), key=lambda kv: ADVICE_ORDER.index(kv[0]) if kv[0] in ADVICE_ORDER else 99))
        empty = '<p data-t="home.guides.empty"></p>'
        advice_html += f'<div data-l="{code}">{body or empty}</div>'
    advice_summary = "".join(f'<span data-l="{code}" data-t="home.guides.summary" data-p=\'{{"count": {n}}}\'></span>'
                             for code, n in advice_counts.items())

    books_html = []
    for label, desc, rel in BOOKS:
        if os.path.exists(os.path.join(DOCS, rel)):
            href = "docs/" + "/".join(urllib.request.quote(p) for p in rel.split("/"))
            books_html.append(f'<li><a href="{href}">{both(label)}</a><small>{both(desc)}</small></li>')

    groups_html = []
    shown = set()
    for heading, items in GROUPS:
        rows = []
        for prefix, desc in items:
            b = by_prefix(prefix)
            if not b:
                continue
            shown.add(b["name"])
            rows.append(f'<li><a data-k="/viewer#{b["name"]}">{html.escape(b["title"])}</a><small>{both(desc)}</small></li>')
        if rows:
            groups_html.append(f'<h3>{both(heading)}</h3><ul class="list rows">{"".join(rows)}</ul>')
    extra = [b for b in books if b["name"] not in shown]
    if extra:
        rows = "".join(f'<li><a data-k="/viewer#{b["name"]}">{html.escape(b["title"])}</a><small>{html.escape(b["name"])}</small></li>' for b in extra)
        groups_html.append(f'<h3 data-t="home.libraries.other"></h3><ul class="list rows">{rows}</ul>')

    def topic(code, t, found, guides):
        """The topic as one list item for a page language, or "" when this language has neither a guide nor an article.
        With a saved guide the item opens it first and names its source; any other saved guide of that language is one
        tap away, then the encyclopedia article. Without one it opens the article, the other language's if need be."""
        if not guides and not found:
            return ""
        own = found.get(code)
        article = own or next(iter(found.values()), None)
        note = ""
        if article and not own:   # an article in the other language: say so
            other = next(c for c in TEXTS if c in found)
            note = f'<small data-t="home.urgent.{LANGUAGE_WORD[other]}"></small>'
        label = both(t["label"])
        if guides:
            (href, source), more = guides[0], guides[1:]
            # One note under the topic: the guide's source, any other guide, then the article. It may wrap, so a
            # topic with several guides stays inside its column.
            parts = [html.escape(source)] + [f'<a href="{h}">{html.escape(s)}</a>' for h, s in more]
            if article:
                parts.append(f'<a data-k="{html.escape(article)}"><span data-t="home.urgent.article"></span></a>')
            return f'<li data-l="{code}"><a href="{href}">{label}</a><small class="links">{" · ".join(parts)}</small>{note}</li>'
        return f'<li data-l="{code}"><a data-k="{html.escape(article)}">{label}</a>{note}</li>'

    first = [e for e in emergency if e[0]["id"] in FIRST]
    first.sort(key=lambda e: FIRST.index(e[0]["id"]))
    rest = [e for e in emergency if e not in first]
    emergency_html, more_section = "", ""
    for code in TEXTS:
        shown = "".join(topic(code, t, found, guides[code]) for t, found, guides in first)
        more = [topic(code, t, found, guides[code]) for t, found, guides in rest]
        more = [m for m in more if m]
        emergency_html += shown or f'<li data-l="{code}" data-t="home.urgent.empty"></li>'
        if more:
            more_section += (f'<details class="inline" data-l="{code}"><summary data-t="home.urgent.more" data-p=\'{{"count": {len(more)}}}\'></summary>'
                             f'<ul class="list cols">{"".join(more)}</ul></details>')
    emergency_count = sum(1 for t, found, guides in emergency if found or any(guides.values()))

    page = TEMPLATE
    for key, val in {
        "%EMERGENCY%": emergency_html,
        "%MORE%": more_section,
        "%ADVICESUMMARY%": advice_summary,
        "%ADVICE%": advice_html,
        "%BOOKS%": "".join(books_html),
        "%GROUPS%": "".join(groups_html) or '<p data-t="home.libraries.none"></p>',
        "%KITNAME%": html.escape(kit_country.kit_name()),
        "%PLACE%": jattr({"place": C["map"]["overview_label"]}),
        "%LANG%": kit_country.LANG,
        "%PRIMARY%": html.escape(PRIMARY["number"]),
        "%NUMBERS%": numbers_html(),
        "%ENG%": json.dumps(eng),
        "%LOCAL%": json.dumps(local),
        "%COUNT%": str(len(books)),
        "%LIBPORT%": KIWIX_PORT,
    }.items():
        page = page.replace(key, val)
    page = kit_lang.fill(page, TEXTS)   # the texts the page says itself, in the default language
    os.makedirs(WEB, exist_ok=True)
    with open(os.path.join(WEB, "index.html"), "w") as f:
        f.write(page)
    print(f"Start page built: {len(books)} libraries, {emergency_count} emergency topics, {len(books_html)} books.")


TEMPLATE = r"""<!doctype html>
<html lang="%LANG%" data-title="{kit}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%KITNAME%</title>
<script src="/lib/country.js"></script>
<script src="/lib/lang.js"></script>
<link rel="manifest" href="/manifest.webmanifest">
<link rel="apple-touch-icon" href="/icon-180.png">
<meta name="apple-mobile-web-app-title" content="%KITNAME%">
<meta name="apple-mobile-web-app-capable" content="yes">
<link rel="icon" href="/icon-180.png">
<link rel="stylesheet" href="lib/kit.css">
<style>
  .primary { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 26px; }
  .big { position: relative; display: block; padding: 18px 20px 20px; border: 1px solid var(--muted); border-radius: 12px;
         text-decoration: none; color: var(--fg); background: var(--bg); transition: border-color .15s, transform .15s; }
  .big:hover { border-color: var(--fg); transform: translateY(-1px); }
  .big b { display: block; font-size: 23px; font-weight: 650; letter-spacing: -.01em; }
  .big span { display: block; margin-top: 6px; color: var(--muted); font-size: 15px; line-height: 1.45; max-width: 36ch; }
  .big i { position: absolute; top: 17px; right: 20px; font-style: normal; font-size: 22px; color: var(--muted); }
  .big.dark { background: var(--fg); color: var(--bg); border-color: var(--fg); }
  .big.dark span, .big.dark i { color: var(--bg); opacity: .72; }
  .where { margin: 10px 0 0; font-size: 15px; }
  .where a { text-decoration: none; } .where a:hover { text-decoration: underline; }
  .where small { margin-left: 6px; }
  ul.list small.links { white-space: normal; text-align: right; }
  form.search { display: flex; gap: 8px; }
  form.search input { flex: 1; min-width: 0; }
  details.more { border-top: 1px solid var(--line); }
  details.more:last-of-type { border-bottom: 1px solid var(--line); }
  details.more > summary { list-style: none; cursor: pointer; padding: 14px 0; display: flex; justify-content: space-between; gap: 12px; }
  details.more > summary::-webkit-details-marker { display: none; }
  details.more > summary b { font-weight: 600; }
  details.more > summary span { color: var(--muted); font-size: 14px; margin-left: auto; }
  details.more > summary::after { content: "+"; color: var(--muted); width: 14px; text-align: right; }
  details.more[open] > summary::after { content: "–"; }
  details.more > .inner { padding: 0 0 22px; }
  details.inline > summary { list-style: none; cursor: pointer; color: var(--muted); font-size: 14px; padding: 10px 0 0; }
  details.inline > summary::-webkit-details-marker { display: none; }
  details.inline[open] > summary { padding-bottom: 6px; }
  .later { margin-top: 48px; }
  @media (max-width: 560px) {
    .primary { grid-template-columns: 1fr; gap: 10px; margin-top: 20px; }
    .big { padding: 16px 18px; } .big b { font-size: 21px; }
    .where small { display: block; margin: 2px 0 0; }
    form.search { flex-wrap: wrap; }
    form.search input { flex-basis: 100%; }
    details.more > summary span { display: none; }
  }
</style>
</head>
<body>
<main class="page">
  <h1 data-kit>%KITNAME%</h1>
  <p class="meta"><span data-t="home.meta.offline"></span> · <span data-t="home.meta.libraries" data-p='{"count": %COUNT%}'></span> · <span id="clock"></span></p>

  <p class="emergency"><strong data-t="home.emergency.call" data-p='{"number": "%PRIMARY%"}'></strong><span>%NUMBERS%</span></p>
  <p class="notice" id="battery" hidden></p>

  <div class="primary">
    <a class="big dark" href="ai/"><b data-t="home.ai.title"></b><span data-t="home.ai.text"></span><i>→</i></a>
    <a class="big" href="map/"><b data-t="home.map.title"></b><span data-t="home.map.text" data-p='%PLACE%'></span><i>→</i></a>
  </div>
  <p class="where"><a href="map/?gps=1" data-t="home.where.link"></a><small data-t="home.where.text"></small></p>

  <section>
    <h2 data-t="home.urgent.heading"></h2>
    <ul class="list cols">%EMERGENCY%</ul>
    %MORE%
  </section>

  <section>
    <h2 data-t="home.search.heading"></h2>
    <form class="search" id="search">
      <input type="search" id="q" data-t-attr="placeholder:home.search.placeholder;aria-label:home.search.label" autocomplete="off">
      <button type="submit" data-t="home.search.button"></button>
      <button type="button" class="plain" id="local" data-t="home.search.local"></button>
    </form>
  </section>

  <div class="later">
    <details class="more"><summary><b data-t="home.guides.title"></b>%ADVICESUMMARY%</summary>
      <div class="inner">%ADVICE%</div></details>
    <details class="more"><summary><b data-t="home.books.title"></b><span data-t="home.books.summary"></span></summary>
      <div class="inner"><ul class="list rows">%BOOKS%<li><a href="docs/" data-t="home.books.all"></a><small data-t="home.books.allnote"></small></li></ul></div></details>
    <details class="more"><summary><b data-t="home.libraries.title"></b><span data-t="home.libraries.summary" data-p='{"count": %COUNT%}'></span></summary>
      <div class="inner">%GROUPS%</div></details>
    <details class="more"><summary><b data-t="home.prepare.title"></b><span data-t="home.prepare.summary"></span></summary>
      <div class="inner"><ul class="list rows">
        <li><a href="print/" data-t="home.prepare.print.title"></a><small data-t="home.prepare.print.text"></small></li>
        <li><a href="checklist/" data-t="home.prepare.checklist.title"></a><small data-t="home.prepare.checklist.text"></small></li>
      </ul></div></details>
  </div>

  <footer class="kit" data-t="home.footer"></footer>
</main>
<script>
  const KIWIX = 'http://' + (location.hostname || 'localhost') + ':%LIBPORT%';   // the libraries are always plain http
  const ENG = %ENG%, LOCAL = %LOCAL%;
  document.querySelectorAll('[data-k]').forEach(a => a.href = KIWIX + a.dataset.k);
  const go = books => {
    const q = document.getElementById('q').value.trim();
    if (!q || !books.length) return;
    location.href = KIWIX + '/search?pattern=' + encodeURIComponent(q) + books.map(b => '&books.name=' + encodeURIComponent(b)).join('');
  };
  document.getElementById('search').addEventListener('submit', e => { e.preventDefault(); go(ENG); });
  document.getElementById('local').addEventListener('click', () => go(LOCAL.length ? LOCAL : ENG));
  const clock = () => { document.getElementById('clock').textContent = new Date().toLocaleString(KIT.locale, { dateStyle: 'medium', timeStyle: 'short' }); };
  clock(); setInterval(clock, 30000);
  let onBattery = null;   // the battery notice is written by this script, so it is redrawn when the language changes
  const showBattery = () => {
    const el = document.getElementById('battery');
    el.hidden = !onBattery;
    if (onBattery) el.textContent = KIT.t('home.battery', { percent: onBattery.percent });
  };
  const battery = () => fetch('/ai-api/status').then(r => r.json()).then(s => {
    onBattery = s.battery && s.battery.on_battery ? s.battery : null;
    showBattery();
  }).catch(() => {});
  battery(); setInterval(battery, 60000);
  KIT.onChange(() => { clock(); showBattery(); });
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
