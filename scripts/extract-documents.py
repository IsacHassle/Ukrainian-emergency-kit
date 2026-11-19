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
"""
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


def archive(prefix):
    found = sorted(glob.glob(os.path.join(LIB, prefix + "_*.zim")))
    return Archive(found[-1]) if found else None


def entries(z):
    for i in range(z.all_entry_count):
        e = z.get_entry_by_id(i)
        if not e.is_redirect:
            yield e, e.get_item()


def save(path, data):
    if isinstance(data, bytes):
        digest = hashlib.sha256(data).digest()
        if digest in SEEN:          # the same book under another name or in another collection
            return 0
        SEEN.add(digest)
    if os.path.exists(path):
        return 0
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb" if isinstance(data, bytes) else "w") as f:
        f.write(data)
    return 1


def safe(name):
    return re.sub(r'[/:\\]', '-', name).strip()


def pdf_collections(mixed=False):
    cfg = json.load(open(os.path.join(KIT, "config", "document-names.json")))
    for prefix, folder in cfg["folders"].items():
        if (prefix == MIXED) != mixed:
            continue
        z = archive(prefix)
        if not z:
            print(f"  {folder}: biblioteket är inte hämtat, hoppar över")
            continue
        names, n = cfg["names"].get(prefix, {}), 0
        for e, it in entries(z):
            if it.mimetype == "application/pdf":
                rel = names.get(e.path) or os.path.join(folder, safe(os.path.basename(e.path)))
                n += save(os.path.join(OUT, rel), bytes(it.content))
        print(f"  {folder}: {n} nya")


def nhs_medicines():
    z = archive("nhs.uk_en_medicines")
    if not z:
        print("  NHS Medicines: biblioteket är inte hämtat, hoppar över")
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
    print(f"  NHS Medicines: {n} nya")


if __name__ == "__main__":
    print("Plockar ut böckerna ur biblioteken:")
    pdf_collections()
    nhs_medicines()
    pdf_collections(mixed=True)
