#!/usr/bin/env python3
"""Checks the language files and the pages' use of them; CI runs it on every push.

- web/lang/<code>.json files are flat {key: text} with the same keys in every language, no empty text,
  and the same {placeholders} in every language's text of a key;
- every key a page uses exists in every language. A page uses a key as data-t="key",
  data-t-attr="attribute:key;...", or KIT.t('key') in its script (the pages in web/, and the start page
  generator scripts/build-home.py).

Prints each problem on its own line and exits non-zero if there is any.
Usage: python3 scripts/check-language.py [repo folder]
"""
import glob
import json
import os
import re
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = r"[a-z0-9][a-z0-9_.-]*"
PLACEHOLDER = re.compile(r"\{([a-z]+)\}")
problems = []


def bad(where, why):
    problems.append(f"{where}: {why}")


def used_keys(text):
    for m in re.finditer(r'\sdata-t="(' + KEY + ')"', text):
        yield m.group(1)
    for m in re.finditer(r'\sdata-t-attr="([^"]+)"', text):
        for pair in m.group(1).split(";"):
            yield pair.partition(":")[2]
    for m in re.finditer(r"\bKIT\.t\(\s*['\"`]([^'\"`]+)['\"`]", text):
        yield m.group(1)


def main():
    texts = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "web", "lang", "*.json"))):
        code = os.path.basename(path)[:-5]
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            bad(path, f"cannot be read as JSON ({e})")
            continue
        if not isinstance(data, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in data.items()):
            bad(path, "must be one flat object of key: text")
            continue
        texts[code] = data
        # Sorted keys give each page's texts their own place in the file, so work on different pages
        # merges without touching the same lines.
        if list(data) != sorted(data):
            bad(path, "keys must be in alphabetical order (sort them with: python3 -c \"import json,sys; "
                      "p=sys.argv[1]; d=json.load(open(p)); json.dump(dict(sorted(d.items())), open(p,'w'), "
                      "ensure_ascii=False, indent=1)\" <file>)")
    if len(texts) < 2:
        bad("web/lang", "needs at least two language files")

    # The same keys everywhere.
    every = set().union(*texts.values()) if texts else set()
    for code, data in texts.items():
        for key in sorted(every - set(data)):
            others = [c for c in texts if key in texts[c]]
            bad(f"web/lang/{code}.json", f"missing key {key} (it is in {', '.join(others)})")
        for key, value in data.items():
            if not re.fullmatch(KEY, key):
                bad(f"web/lang/{code}.json", f"key {key} must be lower case words joined by dots")
            if not value.strip():
                bad(f"web/lang/{code}.json", f"key {key} has no text")
    # The same placeholders in each key's texts.
    for key in sorted(every):
        found = {c: sorted(PLACEHOLDER.findall(d[key])) for c, d in texts.items() if key in d}
        if len({tuple(v) for v in found.values()}) > 1:
            bad(key, "the languages use different {placeholders}: " + "; ".join(f"{c} {v}" for c, v in found.items()))

    # Every key a page uses.
    pages = [p for p in glob.glob(os.path.join(ROOT, "web", "**", "*.html"), recursive=True)
             if "/map/lib/" not in p and "/docs/" not in p]
    pages.append(os.path.join(ROOT, "scripts", "build-home.py"))
    for path in pages:
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as f:
            body = f.read()
        for key in sorted(set(used_keys(body))):
            if key not in every:
                bad(os.path.relpath(path, ROOT), f"uses key {key}, which is in no language file")

    for p in problems:
        print(p)
    if problems:
        sys.exit(f"{len(problems)} problem(s) in the language files")
    print(f"language files ok: {len(texts)} languages, {len(every)} keys")


main()
