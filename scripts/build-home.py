#!/usr/bin/env python3
"""Builds web/index.html, the kit's start page.

It asks the running Kiwix server (port 8090) which libraries are installed,
checks that every emergency link really opens, and writes one page with:
search across all libraries, the AI page and the map, emergency topics, key
PDF books, all libraries, and the country's emergency numbers. Run by share-library.sh on start.
Every country fact comes from config/country.json (scripts/kit_country.py).
"""
import html
import json
import os
import re
import urllib.request

import kit_country

KIWIX_PORT = os.environ.get("EK_KIWIX", "localhost:8090").rpartition(":")[2]   # the Library server (tests choose it)
KIWIX = "http://localhost:" + KIWIX_PORT
HOME = os.environ.get("EK_KIT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the kit folder
WEB = os.environ.get("EK_WEB") or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
DOCS = os.path.join(HOME, "documents")

# Everything about the country comes from the country config (config/country.json): the Emergency Topics
# (label, article, Official Guide), the Books, the Library groups, the emergency numbers.
# Emergency topic articles are looked up in the encyclopedia Libraries the AI also uses, in order.
C = kit_country.COUNTRY
text = kit_country.text
TOPICS = C["emergency_topics"]
# Where an Official Guide on the same thing is saved (scripts/fetch-swedish-pages.py), the button opens
# that guide in the default language, with the encyclopedia article one tap away.
OFFICIAL = {t["article"]: text(t["official_guide"]) for t in TOPICS if t.get("official_guide")}
OFFICIAL_DIR = C["official_guides"]["folder"]
# The emergency topics shown straight away; the rest are one tap away under "More".
FIRST = [t["article"] for t in sorted((t for t in TOPICS if t.get("first")), key=lambda t: t["first"])]
EMERGENCY = [(text(t["label"]), t["label"].get("en", text(t["label"])), t["article"]) for t in TOPICS]
ENCYCLOPEDIAS = [l["prefix"] for l in C["ai"]["libraries"] if l["kind"] == "encyclopedia"]

# (label, description, path under documents/)
BOOKS = [(text(b["label"]), text(b["description"]), b["path"]) for b in C["books"]]

# Library groups: (heading, [(book name prefix, short description)])
GROUPS = [(text(g["heading"]), [(l["prefix"], text(l["description"])) for l in g["libraries"]]) for g in C["library_groups"]]

ADVICE_ORDER = [s["id"] for s in C["official_guides"]["sources"]]
ADVICE_NAMES = {s["id"]: text(s["label"]) for s in C["official_guides"]["sources"]}
ADVICE_COUNT = 0


def official_page(stem):
    """(link to the reader page, authority) for a saved Official Guide, or (None, None)."""
    if not stem or not os.path.exists(os.path.join(DOCS, OFFICIAL_DIR, stem + ".md")):
        return (None, None)
    rel = "docs/" + OFFICIAL_DIR + "/" + stem + ".md"
    return ("las/?f=" + urllib.request.quote(rel), stem.split(" - ", 1)[0])


PRIMARY = next((n for n in C["emergency_numbers"] if n.get("primary")), C["emergency_numbers"][0])


def numbers_html():
    """The other emergency numbers and the radio station, as one line under the main number."""
    parts = [html.escape(n["number"]).replace(" ", "&nbsp;") + " " + html.escape(text(n["label"]))
             for n in C["emergency_numbers"] if n is not PRIMARY]
    return " · ".join(parts + [html.escape(text(C["radio"]["label"]))])


def kiwix_ok(path):
    try:
        req = urllib.request.Request(KIWIX + path, method="HEAD")
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
    swe = [b["name"] for b in books if b["lang"] == C["search_languages"]["country"]]

    med_books = [b for b in (by_prefix(p) for p in ENCYCLOPEDIAS) if b]
    emergency = []
    for sv, en, art in EMERGENCY:
        for b in med_books:
            path = f"/content/{b['name']}/{art}"
            if kiwix_ok(path):
                emergency.append((sv, en, f"/viewer#{b['name']}/{art}", official_page(OFFICIAL.get(art))))
                break

    # The Official Guides, grouped by authority.
    advice = {}
    folder = os.path.join(DOCS, OFFICIAL_DIR)
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if name.endswith(".md") and " - " in name:
            src, title = name[:-3].split(" - ", 1)
            advice.setdefault(src, []).append((title, official_page(name[:-3])))
    advice_html = "".join(
        f'<h3>{html.escape(ADVICE_NAMES.get(src, src))}</h3><ul class="list cols">'
        + "".join(f'<li><a href="{href}">{html.escape(t)}</a></li>' for t, href in items) + "</ul>"
        for src, items in sorted(advice.items(), key=lambda kv: ADVICE_ORDER.index(kv[0]) if kv[0] in ADVICE_ORDER else 99))
    advice_count = sum(len(v) for v in advice.values())

    books_html = []
    for label, desc, rel in BOOKS:
        if os.path.exists(os.path.join(DOCS, rel)):
            href = "docs/" + "/".join(urllib.request.quote(p) for p in rel.split("/"))
            books_html.append(f'<li><a href="{href}">{html.escape(label)}</a><small>{html.escape(desc)}</small></li>')

    groups_html = []
    shown = set()
    for heading, items in GROUPS:
        rows = []
        for prefix, desc in items:
            b = by_prefix(prefix)
            if not b:
                continue
            shown.add(b["name"])
            rows.append(f'<li><a data-k="/viewer#{b["name"]}">{html.escape(b["title"])}</a><small>{html.escape(desc)}</small></li>')
        if rows:
            groups_html.append(f'<h3>{html.escape(heading)}</h3><ul class="list rows">{"".join(rows)}</ul>')
    extra = [b for b in books if b["name"] not in shown]
    if extra:
        rows = "".join(f'<li><a data-k="/viewer#{b["name"]}">{html.escape(b["title"])}</a><small>{html.escape(b["name"])}</small></li>' for b in extra)
        groups_html.append(f'<h3>Övrigt</h3><ul class="list rows">{rows}</ul>')

    def topic(sv, en, k, sv_href, sv_src):
        if sv_href:
            return f'<li><a href="{sv_href}">{html.escape(sv)}</a><small>{html.escape(sv_src)}</small></li>'
        return f'<li><a data-k="{html.escape(k)}">{html.escape(sv)}</a><small>engelska</small></li>'
    first = [e for e in emergency if e[2].rsplit("/", 1)[-1] in FIRST]
    first.sort(key=lambda e: FIRST.index(e[2].rsplit("/", 1)[-1]))
    rest = [e for e in emergency if e not in first]
    emergency_html = "".join(topic(sv, en, k, *svp) for sv, en, k, svp in first)
    more_html = "".join(topic(sv, en, k, *svp) for sv, en, k, svp in rest)

    page = TEMPLATE
    for key, val in {
        "%EMERGENCY%": emergency_html or "<li>Starta Krislådan så att biblioteken är igång.</li>",
        "%MORE%": more_html,
        "%MORECOUNT%": str(len(rest)),
        "%ADVICECOUNT%": str(advice_count),
        "%ADVICE%": advice_html or "<p>Kör installationen för att hämta myndigheternas råd.</p>",
        "%BOOKS%": "".join(books_html),
        "%GROUPS%": "".join(groups_html) or "<p>Inga bibliotek hittades. Kör share-library.sh.</p>",
        "%KITNAME%": html.escape(kit_country.kit_name()),
        "%LANG%": kit_country.LANG,
        "%LOCALE%": kit_country.LOCALE,
        "%PRIMARY%": html.escape(PRIMARY["number"]),
        "%NUMBERS%": numbers_html(),
        "%ENG%": json.dumps(eng),
        "%SWE%": json.dumps(swe),
        "%COUNT%": str(len(books)),
        "%LIBPORT%": KIWIX_PORT,
    }.items():
        page = page.replace(key, val)
    os.makedirs(WEB, exist_ok=True)
    with open(os.path.join(WEB, "index.html"), "w") as f:
        f.write(page)
    print(f"Start page built: {len(books)} libraries, {len(emergency)} emergency topics, {len(books_html)} books.")


TEMPLATE = r"""<!doctype html>
<html lang="%LANG%">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%KITNAME%</title>
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
  <h1>%KITNAME%</h1>
  <p class="meta">Fungerar utan internet · %COUNT% bibliotek · <span id="clock"></span></p>

  <p class="emergency"><strong>Livsfara? Ring %PRIMARY%.</strong><span>%NUMBERS%</span></p>
  <p class="notice" id="battery" hidden></p>

  <div class="primary">
    <a class="big dark" href="ai/"><b>Fråga AI</b><span>Fråga på svenska om skador, sjukdom, vatten, mat och värme. Svaret bygger på krislådans böcker.</span><i>→</i></a>
    <a class="big" href="map/"><b>Karta</b><span>Hela Sverige, utan internet. Sök adress och hitta närmaste sjukhus, apotek och vatten.</span><i>→</i></a>
  </div>
  <p class="where"><a href="map/?gps=1">Var är jag? →</a><small>Din position på kartan, med USB GPS-mottagare eller mobilen</small></p>

  <section>
    <h2>Akut</h2>
    <ul class="list cols">%EMERGENCY%</ul>
    <details class="inline"><summary>+ Fler akuta ämnen (%MORECOUNT%)</summary><ul class="list cols">%MORE%</ul></details>
  </section>

  <section>
    <h2>Sök i biblioteken</h2>
    <form class="search" id="search">
      <input type="search" id="q" placeholder="Sök, helst på engelska" autocomplete="off" aria-label="Sök i biblioteken">
      <button type="submit">Sök</button>
      <button type="button" class="plain" id="sv">På svenska</button>
    </form>
  </section>

  <div class="later">
    <details class="more"><summary><b>Myndigheternas råd</b><span>%ADVICECOUNT% sidor från 1177, MCF och Livsmedelsverket</span></summary>
      <div class="inner">%ADVICE%</div></details>
    <details class="more"><summary><b>Böcker</b><span>De viktigaste som PDF</span></summary>
      <div class="inner"><ul class="list rows">%BOOKS%<li><a href="docs/">Alla dokument</a><small>Hela samlingen</small></li></ul></div></details>
    <details class="more"><summary><b>Alla bibliotek</b><span>%COUNT% st</span></summary>
      <div class="inner">%GROUPS%</div></details>
    <details class="more"><summary><b>Förbered dig</b><span>Skriv ut, checklista, mobilens GPS</span></summary>
      <div class="inner"><ul class="list rows">
        <li><a href="skriv-ut/">Skriv ut</a><small>Första hjälpen, varningar, vatten och värme på papper. Gör det medan det finns ström.</small></li>
        <li><a href="checklista/">Checklista</a><small>Har du det du behöver för en vecka hemma?</small></li>
        <li><a href="mobil/">Mobilens GPS</a><small>Ställ in en mobil så att den kan visa din position.</small></li>
      </ul></div></details>
  </div>

  <footer class="kit">Kontrollera en gång i månaden med Kontrollera Krislåda.command · Bibliotek från Kiwix · Karta © OpenStreetMap · Råd från 1177, MCF och Livsmedelsverket</footer>
</main>
<script>
  const KIWIX = 'http://' + (location.hostname || 'localhost') + ':%LIBPORT%';   // the libraries are always plain http
  const ENG = %ENG%, SWE = %SWE%;
  document.querySelectorAll('[data-k]').forEach(a => a.href = KIWIX + a.dataset.k);
  const go = books => {
    const q = document.getElementById('q').value.trim();
    if (!q || !books.length) return;
    location.href = KIWIX + '/search?pattern=' + encodeURIComponent(q) + books.map(b => '&books.name=' + encodeURIComponent(b)).join('');
  };
  document.getElementById('search').addEventListener('submit', e => { e.preventDefault(); go(ENG); });
  document.getElementById('sv').addEventListener('click', () => go(SWE.length ? SWE : ENG));
  const clock = () => { document.getElementById('clock').textContent = new Date().toLocaleString('%LOCALE%', { dateStyle: 'medium', timeStyle: 'short' }); };
  clock(); setInterval(clock, 30000);
  const battery = () => fetch('/ai-api/status').then(r => r.json()).then(s => {
    const b = s.battery, el = document.getElementById('battery');
    if (b && b.on_battery) {
      el.hidden = false;
      el.textContent = `Datorn går på batteri (${b.percent} %). Spara ström: sänk ljusstyrkan, stäng andra appar och välj Spara batteri i AI:n.`;
    } else el.hidden = true;
  }).catch(() => {});
  battery(); setInterval(battery, 60000);
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
