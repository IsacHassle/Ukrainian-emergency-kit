#!/usr/bin/env python3
"""Takes the books out of the offline libraries into documents/library/, so the AI can read
them and people can open them as PDFs:

  Medical Library, Military Medicine, Water Treatment, Food for Preppers, Knots, Post Disaster
      PDFs from the Kiwix "zimgit" collections, named by title (config/document-names.json)
  NHS Medicines      every page of the NHS Medicines A to Z, as text

Many books are in more than one collection (Post Disaster repeats most of the others). Each book is
kept once, in its most specific collection: the collections are read with Post Disaster last, and a
PDF identical to one already taken is skipped. Fewer copies also means the AI gets different
passages instead of the same one twice.

Run with the kit's Python (made by scripts/get-tools.sh):
    tools/venv/bin/python scripts/extract-documents.py
Safe to re-run: files that already exist are left alone.

Update takes only the Libraries that have a newer version:
    tools/venv/bin/python scripts/extract-documents.py --update zimgit-water_en nhs.uk_en_medicines
Those Libraries are read again, a Book that is new is added and a Book that changed replaces its old copy (the Book
index then takes in only those, scripts/embed-documents.sh). Books of other Libraries are not read or touched.
"""
import sys
import glob
import hashlib
import json
import os
import re

from bs4 import BeautifulSoup
from libzim.reader import Archive

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(KIT, "library")
OUT = os.path.join(KIT, "documents", "library")
MIXED = "zimgit-post-disaster_en"   # repeats books from the other collections, so it is read last
SEEN = set()                        # every PDF taken so far, by content
ONLY = None                         # with --update: the Libraries (by name without version) to read again
CHANGED = 0                         # Books that replaced an older copy


def archive(prefix):
    found = sorted(glob.glob(os.path.join(LIB, prefix + "_*.zim")))
    return Archive(found[-1]) if found else None


def entries(z):
    for i in range(z.all_entry_count):
        e = z.get_entry_by_id(i)
        if not e.is_redirect:
            yield e, e.get_item()


def wanted(prefix):
    return ONLY is None or prefix in ONLY


def save(path, data):
    global CHANGED
    if isinstance(data, bytes):
        digest = hashlib.sha256(data).digest()
        if digest in SEEN:          # the same book under another name or in another collection (or unchanged)
            return 0
        SEEN.add(digest)
    if os.path.exists(path):
        if ONLY is None:
            return 0
        if not isinstance(data, bytes):   # a text Book: leave it when it says the same
            with open(path, encoding="utf-8") as f:
                if f.read() == data:
                    return 0
        CHANGED += 1                # an older copy of this Book: replaced
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb" if isinstance(data, bytes) else "w", **({} if isinstance(data, bytes) else {"encoding": "utf-8"})) as f:
        f.write(data)
    return 1


def safe(name):
    return re.sub(r'[/:\\]', '-', name).strip()


def pdf_collections(mixed=False):
    cfg = json.load(open(os.path.join(KIT, "config", "document-names.json")))
    for prefix, folder in cfg["folders"].items():
        if (prefix == MIXED) != mixed or not wanted(prefix):
            continue
        z = archive(prefix)
        if not z:
            print(f"  {folder}: бібліотеку не завантажено, пропускаю / the Library is not downloaded, skipping")
            continue
        names, n = cfg["names"].get(prefix, {}), 0
        for e, it in entries(z):
            if it.mimetype == "application/pdf":
                rel = names.get(e.path) or os.path.join(folder, safe(os.path.basename(e.path)))
                n += save(os.path.join(OUT, rel), bytes(it.content))
        print(f"  {folder}: нових {n} / {n} new")


def nhs_medicines():
    if not wanted("nhs.uk_en_medicines"):
        return
    z = archive("nhs.uk_en_medicines")
    if not z:
        print("  NHS Medicines: бібліотеку не завантажено, пропускаю / the Library is not downloaded, skipping")
        return
    n = 0
    for e, it in entries(z):
        if not it.mimetype.startswith("text/html") or not re.match(r"www\.nhs\.uk/medicines/.+/$", e.path):
            continue
        soup = BeautifulSoup(bytes(it.content), "html.parser")
        raw = soup.title.get_text() if soup.title else e.title   # the page title, not its heading (that adds brand names)
        title = re.sub(r"\s*-\s*NHS\s*$", "", " ".join(raw.split())).replace("\u2019", "'").strip()
        main = soup.find("main") or soup.body
        for tag in main.select("nav, script, style, form, footer, aside, .nhsuk-review-date, .nhsuk-breadcrumb"):
            tag.decompose()
        text = re.sub(r"\n{3,}", "\n\n", main.get_text("\n")).strip()
        if len(text) > 200:
            name = re.sub(r"\s+", " ", re.sub(r"[/:\\]", "", title)).strip().rstrip(".")
            n += save(os.path.join(OUT, "NHS Medicines", name + ".md"),
                      f"# {title}\n\nSource: NHS Medicines A to Z (nhs.uk), offline copy.\n\n{text}\n")
    print(f"  NHS Medicines: нових {n} / {n} new")


def known_books():
    """The PDFs already in documents/library, so that a Book of a Library read again is not taken twice when an
    unchanged Library holds the same PDF."""
    for base, _, names in os.walk(OUT):
        for n in names:
            if n.endswith(".pdf"):
                with open(os.path.join(base, n), "rb") as f:
                    SEEN.add(hashlib.sha256(f.read()).digest())


if __name__ == "__main__":
    if "--update" in sys.argv:
        ONLY = set(sys.argv[sys.argv.index("--update") + 1:])
        known_books()
    print("Видобуваю книги з бібліотек / Taking the Books out of the Libraries:")
    pdf_collections()
    nhs_medicines()
    pdf_collections(mixed=True)
    if ONLY is not None:
        print(f"  змінених книг: {CHANGED} / changed Books: {CHANGED}")
