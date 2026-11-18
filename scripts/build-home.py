#!/usr/bin/env python3
"""Builds web/index.html, the crisis kit start page.

It asks the running Kiwix server (port 8090) which libraries are installed,
checks that every emergency link really opens, and writes one page with:
search across all libraries, the AI page and the map, emergency topics, key
PDF books, all libraries, and the Swedish emergency numbers. Run by share-library.sh on start.
"""
import html
import json
import os
import re
import urllib.request

KIWIX = "http://localhost:8090"
HOME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the kit folder
WEB = os.path.join(HOME, "web")
DOCS = os.path.join(HOME, "documents")

# (Swedish, English, article). Articles are looked up in WikiMed, then MDWiki.
# Where a Swedish authority page on the same thing is saved (scripts/fetch-swedish-pages.py),
# the button opens that page in Swedish, with the English article one tap away.
SWEDISH = {
    'Cardiopulmonary_resuscitation': '1177 - Hjärt-lungräddning',
    'Bleeding': '1177 - Stoppa en blödning',
    'Tourniquet': 'MCF - Stoppa en blödning',
    'Choking': '1177 - Om någon sätter i halsen',
    'Shock_(circulatory)': '1177 - Chock',
    'Burn': '1177 - Brännskador',
    'Frostbite': '1177 - Köldskador – förfrysning',
    'Heat_stroke': '1177 - Värmeslag',
    'Anaphylaxis': '1177 - Allergisk chock – anafylaxi',
    'Head_injury': '1177 - Hjärnskakning',
    'Wound': '1177 - Behandling av stora sår',
    'Carbon_monoxide_poisoning': '1177 - Inandning av skadlig gas',
    'Poisoning': '1177 - Förgiftning',
    'Drowning': '1177 - Drunkningsolyckor',
    'Snakebite': '1177 - Huggormsbett',
    'Tick-borne_encephalitis': '1177 - Fästingbett',
    'Potassium_iodide': 'MCF - Varning kring Sveriges kärnkraftverk',
}
SV_DIR = "library/Svenska myndigheter"
# The emergency topics shown straight away; the rest are one tap away under "Fler".
FIRST = ["Cardiopulmonary_resuscitation", "Bleeding", "Choking", "Shock_(circulatory)", "Burn",
         "Hypothermia", "Anaphylaxis", "Poisoning", "Carbon_monoxide_poisoning"]
EMERGENCY = [
    ("Hjärt-lungräddning", "CPR", "Cardiopulmonary_resuscitation"),
    ("Kraftig blödning", "Severe bleeding", "Bleeding"),
    ("Tryckförband, tourniquet", "Tourniquet", "Tourniquet"),
    ("Luftvägsstopp", "Choking", "Choking"),
    ("Chock", "Shock", "Shock_(circulatory)"),
    ("Brännskada", "Burn", "Burn"),
    ("Nedkylning", "Hypothermia", "Hypothermia"),
    ("Förfrysning", "Frostbite", "Frostbite"),
    ("Värmeslag", "Heat stroke", "Heat_stroke"),
    ("Allergisk chock", "Anaphylaxis", "Anaphylaxis"),
    ("Hjärtinfarkt", "Heart attack", "Myocardial_infarction"),
    ("Stroke", "Stroke", "Stroke"),
    ("Benbrott", "Fracture", "Bone_fracture"),
    ("Huvudskada", "Head injury", "Head_injury"),
    ("Sår", "Wounds", "Wound"),
    ("Blodförgiftning", "Sepsis", "Sepsis"),
    ("Uttorkning, diarré", "Dehydration", "Oral_rehydration_therapy"),
    ("Kolmonoxid (aggregat, kaminer)", "Carbon monoxide", "Carbon_monoxide_poisoning"),
    ("Förgiftning", "Poisoning", "Poisoning"),
    ("Svampförgiftning", "Mushroom poisoning", "Mushroom_poisoning"),
    ("Kramper", "Seizure", "Epileptic_seizure"),
    ("Lågt blodsocker", "Hypoglycemia", "Hypoglycemia"),
    ("Astma", "Asthma", "Asthma"),
    ("Drunkning", "Drowning", "Drowning"),
    ("Förlossning", "Childbirth", "Childbirth"),
    ("Huggormsbett", "Snakebite", "Snakebite"),
    ("Fästingar, TBE", "Tick-borne encephalitis", "Tick-borne_encephalitis"),
    ("Strålning, jodtabletter", "Radiation, iodine", "Potassium_iodide"),
    ("Panikångest", "Panic attack", "Panic_attack"),
]

# (label, description, path under documents/)
BOOKS = [
    ("Om krisen eller kriget kommer", "Myndighetens råd, på svenska", "Om-krisen-eller-kriget-kommer.pdf"),
    ("In case of crisis or war", "The same brochure in English", "In-case-of-crisis-or-war.pdf"),
    ("Where There Is No Doctor", "The classic village health care handbook", "library/Medical Library/Where there is no Doctor.pdf"),
    ("First Aid (Field Manual)", "Step-by-step first aid, US Army", "library/Military Medicine/First Aid (Field Manual).pdf"),
    ("Survival and Austere Medicine", "Medicine when there is no hospital", "library/Medical Library/Survival and Austere Medicine.pdf"),
    ("Family Guide to Emergency Health Care", "Care at home for the family", "library/Military Medicine/Family Guide to Emergency Health Care.pdf"),
    ("Emergency Childbirth", "Delivering a baby without a hospital", "library/Military Medicine/Emergency Childbirth.pdf"),
    ("Where There Is No Dentist", "Tooth pain, infections, extractions", "library/Medical Library/Where There is No Dentist.pdf"),
    ("Purifying Water During an Emergency", "Making water safe to drink", "library/Water Treatment/Purifying Water During an Emergency.pdf"),
    ("Bandaging and Splinting", "Dressings, slings and splints", "library/Military Medicine/Bandaging and Splinting.pdf"),
]

# Library groups: (heading, [(book name prefix, short Swedish description)])
GROUPS = [
    ("Sjukvård", [
        ("wikipedia_en_medicine", "Alla medicinska Wikipedia-artiklar, med bilder"),
        ("mdwiki_en", "Granskat medicinskt uppslagsverk"),
        ("zimgit-medicine", "Böcker: akutsjukvård, Where There Is No Doctor"),
        ("irp.fas.org_en_military-medicine", "Fältsjukvård, trauma, blödning"),
        ("medlineplus", "Sjukdomar och läkemedel, lättläst"),
        ("nhs.uk_en_medicines", "Läkemedel: vad de är till för, biverkningar"),
        ("wwwnc.cdc.gov", "Smittsamma sjukdomar och utbrott"),
    ]),
    ("Vatten, mat och skydd", [
        ("zimgit-water", "Rena vatten: koka, filtrera, kemiskt"),
        ("zimgit-food-preparation", "Förvara och laga mat utan el"),
        ("zimgit-post-disaster", "Skydd, sanitet, återuppbyggnad"),
        ("solar.lowtechmagazine", "Värme och matlagning utan el"),
        ("www.ready.gov", "Beredskap för olika katastrofer"),
        ("cd3wdproject", "Lågteknik: odling, vatten, energi, bygg"),
        ("appropedia", "Hållbar självförsörjning, praktiska projekt"),
        ("cooking.stackexchange", "Frågor och svar om matlagning"),
        ("gardening.stackexchange", "Frågor och svar om odling"),
        ("outdoors.stackexchange", "Friluftsliv, skydd, värme"),
        ("zimgit-knots", "Knopar och surrningar"),
    ]),
    ("Laga och kommunicera", [
        ("ifixit", "Reparationsguider för allt"),
        ("mechanics.stackexchange", "Bilreparationer"),
        ("diy.stackexchange", "Hus: värme, vatten, el"),
        ("ham.stackexchange", "Amatörradio och nödkommunikation"),
    ]),
    ("Allmän kunskap", [
        ("wikipedia_sv_all", "Svenska Wikipedia, med bilder"),
        ("wikipedia_en_all", "English Wikipedia, text only"),
    ]),
]


ADVICE_ORDER = ["1177", "MCF", "Livsmedelsverket", "Krisinformation"]
ADVICE_NAMES = {"1177": "1177 · Första hjälpen och skador", "MCF": "MCF · Hemberedskap, varningar, skyddsrum, brand",
                "Livsmedelsverket": "Livsmedelsverket · Vatten och mat", "Krisinformation": "Krisinformation.se"}
ADVICE_COUNT = 0


def swedish_page(stem):
    """(link to the reader page, authority) for a saved Swedish page, or (None, None)."""
    if not stem or not os.path.exists(os.path.join(DOCS, SV_DIR, stem + ".md")):
        return (None, None)
    rel = "docs/" + SV_DIR + "/" + stem + ".md"
    return ("las/?f=" + urllib.request.quote(rel), stem.split(" - ", 1)[0])


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
    eng = [b["name"] for b in books if b["lang"] == "eng"]
    swe = [b["name"] for b in books if b["lang"] == "swe"]

    med_books = [b for b in (by_prefix("wikipedia_en_medicine"), by_prefix("mdwiki_en")) if b]
    emergency = []
    for sv, en, art in EMERGENCY:
        for b in med_books:
            path = f"/content/{b['name']}/{art}"
            if kiwix_ok(path):
                emergency.append((sv, en, f"/viewer#{b['name']}/{art}", swedish_page(SWEDISH.get(art))))
                break

    # Swedish authorities' advice, grouped by authority.
    advice = {}
    folder = os.path.join(DOCS, SV_DIR)
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if name.endswith(".md") and " - " in name:
            src, title = name[:-3].split(" - ", 1)
            advice.setdefault(src, []).append((title, swedish_page(name[:-3])))
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
        "%ENG%": json.dumps(eng),
        "%SWE%": json.dumps(swe),
        "%COUNT%": str(len(books)),
    }.items():
        page = page.replace(key, val)
    os.makedirs(WEB, exist_ok=True)
    with open(os.path.join(WEB, "index.html"), "w") as f:
        f.write(page)
    print(f"Start page built: {len(books)} libraries, {len(emergency)} emergency topics, {len(books_html)} books.")


TEMPLATE = r"""<!doctype html>
<html lang="sv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Krislåda</title>
<link rel="manifest" href="/manifest.webmanifest">
<link rel="apple-touch-icon" href="/icon-180.png">
<meta name="apple-mobile-web-app-title" content="Krislåda">
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
  <h1>Krislåda</h1>
  <p class="meta">Fungerar utan internet · %COUNT% bibliotek · <span id="clock"></span></p>

  <p class="emergency"><strong>Livsfara? Ring 112.</strong><span>1177 sjukvårdsråd · 113&nbsp;13 information vid kris · 114&nbsp;14 polisen · Radio P4</span></p>
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
  const KIWIX = 'http://' + (location.hostname || 'localhost') + ':8090';   // the libraries are always plain http
  const ENG = %ENG%, SWE = %SWE%;
  document.querySelectorAll('[data-k]').forEach(a => a.href = KIWIX + a.dataset.k);
  const go = books => {
    const q = document.getElementById('q').value.trim();
    if (!q || !books.length) return;
    location.href = KIWIX + '/search?pattern=' + encodeURIComponent(q) + books.map(b => '&books.name=' + encodeURIComponent(b)).join('');
  };
  document.getElementById('search').addEventListener('submit', e => { e.preventDefault(); go(ENG); });
  document.getElementById('sv').addEventListener('click', () => go(SWE.length ? SWE : ENG));
  const clock = () => { document.getElementById('clock').textContent = new Date().toLocaleString('sv-SE', { dateStyle: 'medium', timeStyle: 'short' }); };
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
