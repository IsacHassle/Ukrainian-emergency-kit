#!/usr/bin/env python3
"""The guide saver: saves the Official Guides (config/pages.txt) into documents/<official_guides.folder>/, so they
can be read without internet in the reader and, the Ukrainian ones, searched by the AI.

Text pages become Markdown named after their source ("МОЗ - Що робити у разі радіаційної аварії.md"), PDFs are
saved as the PDF itself. Guides in the country's own language go in the folder, guides in any other language in a
subfolder named by the language code ("en/"), which the AI index leaves out. A saved.json beside them lists what
was saved, from where, when, and whether it is marked for the AI index.

Optional sources (the State Emergency Service, which refuses requests from outside Ukraine) are skipped quietly
when they refuse, and reported. A guide already saved is not fetched again; --refresh fetches everything again,
and a copy that cannot be refreshed stays as it was. The saver pauses between requests and sends a generic
client name.

Exit code: 0 when everything that is not optional was saved, 1 when some guide could not be fetched.

Uses only Python's standard library (the system python3 3.9 is enough):
    python3 scripts/fetch-pages.py [--refresh]
"""
import datetime
import json
import os
import sys

import kit_country
import kit_guides
import kit_html

KIT = os.environ.get("EK_KIT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDER = kit_country.COUNTRY["official_guides"]["folder"]
OUT = os.path.join(KIT, "documents", FOLDER)
REFRESH = "--refresh" in sys.argv

# What a saved text says about itself, in the guide's language: "Source: <source>, <address>. Saved <date> ...".
SOURCE_LINE = {
    "uk": "Джерело: {source}, {url}. Збережено {date} для читання без інтернету.",
    "en": "Source: {source}, {url}. Saved {date} for reading offline.",
}
MIN_TEXT = 120   # a page that gives less text than this is a menu or an error page, not a guide


def say(uk, en):
    """One line with both languages, as the other scripts print."""
    print(f"{uk} / {en}", flush=True)


def save(path, data):
    """Writes through a temporary file, so a failed write never leaves half a guide (or loses the old copy)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".part", "wb") as f:
        f.write(data)
    os.replace(path + ".part", path)


def text_guide(guide, result, today):
    """The Markdown of a fetched page, or None with a reason."""
    source = kit_guides.source_of(guide.url) or {}
    page = result.body.decode("utf-8", "replace")
    body = kit_html.to_markdown(page, source.get("container") or ["article", "main"])
    if body is None:
        return None, "no article on the page"
    if len(body) < MIN_TEXT:
        return None, "almost no text"
    title = kit_html.page_title(page, source.get("title_suffix") or ()) or guide.name.split(" - ", 1)[1]
    # Many pages repeat their title as the first heading of the article: the saved text has it once.
    first, _, rest = body.partition("\n")
    if first.lstrip("#").strip().replace("\u201c", '"').replace("\u201d", '"') == title.replace("\u201c", '"').replace("\u201d", '"'):
        body = rest.strip() or body
    line = SOURCE_LINE.get(guide.language, SOURCE_LINE["en"]).format(source=guide.source_id, url=guide.url, date=today)
    return f"# {title}\n\n{line}\n\n{body}\n".encode("utf-8"), ""


def main():
    guides = kit_guides.read_list()
    today = datetime.date.today().isoformat()
    counts = {"saved": 0, "there": 0, "skipped": 0, "failed": 0}
    saved = []
    for guide in guides:
        sub = kit_guides.language_folder(guide.language)
        file = (sub + "/" if sub else "") + guide.name + (".pdf" if guide.is_pdf else ".md")
        path = os.path.join(OUT, *file.split("/"))
        entry = {"name": guide.name, "file": file, "url": guide.url, "language": guide.language,
                 "source": guide.source_id, "index": kit_guides.indexed(guide.language)}
        if os.path.exists(path) and not REFRESH:
            counts["there"] += 1
            saved.append(entry)
            continue
        result = kit_guides.fetch(guide.url)
        data, why = None, result.detail
        if result.state == "ok":
            if guide.is_pdf:
                data = result.body if result.body.startswith(b"%PDF") else None
                why = "not a PDF"
            else:
                data, why = text_guide(guide, result, today)
        if data is None:
            # An optional source that does not give its page, for any reason from outside Ukraine (a refusal, a reset
            # connection, a timeout), is skipped: the install must not fail because of it.
            if kit_guides.optional(guide.url) and result.state in ("refused", "error"):
                counts["skipped"] += 1
                say(f"Пропущено (сайт не відповідає з цієї країни): {guide.url}",
                    f"Skipped (the site does not answer from here): {guide.url}")
            else:
                counts["failed"] += 1
                say(f"Не вдалося зберегти: {guide.url} ({why})", f"Failed to save: {guide.url} ({why})")
            if os.path.exists(path):   # a refresh that fails keeps the copy already saved
                saved.append(entry)
            continue
        save(path, data)
        counts["saved"] += 1
        saved.append(entry)
    save(os.path.join(OUT, "saved.json"), json.dumps({"saved": today, "guides": saved}, ensure_ascii=False, indent=1).encode("utf-8"))
    say("Офіційні посібники: збережено {saved}, уже були {there}, пропущено {skipped}, не вдалося {failed}".format(**counts),
        "Official Guides: saved {saved}, already there {there}, skipped {skipped}, failed {failed}".format(**counts))
    return 1 if counts["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
