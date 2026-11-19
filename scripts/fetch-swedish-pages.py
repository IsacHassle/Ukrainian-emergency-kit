#!/usr/bin/env python3
"""Sparar svenska myndigheters råd (MCF, 1177, Livsmedelsverket, Krisinformation) som text i
documents/<mappen i landets konfiguration>/, så att de går att läsa utan internet och AI:n kan svara ur dem.

Sidorna står i config/swedish-pages.txt. Varje sida hämtas från myndighetens egen webbplats.
Sidor som redan är sparade hoppas över; kör med --uppdatera för att hämta om allt.

Run with the kit's Python (made by scripts/get-tools.sh):
    tools/venv/bin/python scripts/fetch-swedish-pages.py [--uppdatera]
"""
import datetime
import os
import re
import sys
import urllib.parse
import urllib.request

from bs4 import BeautifulSoup
from markdownify import markdownify

import kit_country

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUIDES = kit_country.COUNTRY["official_guides"]   # where they are saved and which sites they come from (country config)
OUT = os.path.join(KIT, "documents", GUIDES["folder"])
SOURCES = {s["host"]: s["id"] for s in GUIDES["sources"]}
REFRESH = "--uppdatera" in sys.argv
DROP = ("nav, header, footer, aside, script, style, noscript, form, button, svg, img, picture, figure, iframe, video, "
        "[role=navigation], [aria-label=Brödsmulor], .breadcrumb, .breadcrumbs, .c-breadcrumbs, .share, .c-share, "
        ".cookie, .feedback, .c-feedback, .print, .related, .c-related")


def page(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh) " + kit_country.slug() + "/1.0"})
    html = urllib.request.urlopen(req, timeout=30).read()
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    title = " ".join(h1.get_text(" ").split()) if h1 else (soup.title.get_text().strip() if soup.title else url)
    main = soup.find("main") or soup.find("article") or soup.body
    for tag in main.select(DROP):
        tag.decompose()
    md = markdownify(str(main), heading_style="ATX", strip=["a"])
    # Videos cannot be played offline: drop what only refers to them, and empty headings.
    lines, prev = [], None
    for line in md.split("\n"):
        t = line.strip()
        if re.fullmatch(r"#+", t) or t.startswith("Video:") or re.match(r"Filmen (visar|handlar)", t):
            continue
        if t and t == prev:
            continue
        lines.append(line)
        prev = t or prev
    md = "\n".join(lines)
    md = re.sub(r"[ \t]+\n", "\n", md)
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    return title, md


def main():
    os.makedirs(OUT, exist_ok=True)
    urls = [l.split("#")[0].strip() for l in open(os.path.join(KIT, "config", "swedish-pages.txt"))]
    urls = [u for u in urls if u.startswith("http")]
    got = skipped = failed = 0
    done = {}
    for name in os.listdir(OUT):   # remember which address each saved file came from
        try:
            first = open(os.path.join(OUT, name)).read(600)
            m = re.search(r"Källa: [^,]+, (\S+)\.", first)
            if m:
                done[m.group(1)] = name
        except OSError:
            pass
    today = datetime.date.today().isoformat()
    for url in urls:
        if url in done and not REFRESH:
            skipped += 1
            continue
        src = SOURCES.get(urllib.parse.urlparse(url).netloc, urllib.parse.urlparse(url).netloc)
        try:
            title, md = page(url)
        except Exception as e:   # one page failing must not stop the rest
            print(f"  Kunde inte hämta {url} ({e.__class__.__name__})")
            failed += 1
            continue
        if len(md) < 200:
            print(f"  Nästan tom sida, hoppar över: {url}")
            failed += 1
            continue
        name = re.sub(r"\s+", " ", re.sub(r'[/:\\?"]', "-", f"{src} - {title}")).strip()[:150] + ".md"
        if url in done and done[url] != name:
            os.remove(os.path.join(OUT, done[url]))
        with open(os.path.join(OUT, name), "w") as f:
            f.write(f"# {title}\n\nKälla: {src}, {url}. Sparad {today} för läsning utan internet.\n\n{md}\n")
        got += 1
    print(f"  Svenska myndigheter: {got} sparade, {skipped} fanns redan, {failed} gick inte att hämta")


if __name__ == "__main__":
    main()
