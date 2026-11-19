"""The language files (web/lang/<code>.json), for every script that needs a page's texts.

One flat file per language, the same keys in each (CI checks that: scripts/check-language.py). A page marks
text by key (data-t="home.ai.title"); the page generator writes the default language into the markup so the
page reads right before any script runs, and /lib/lang.js carries all languages to the browser, where the
switch changes the page without a reload.

Uses only Python's standard library (serve-web.py imports this), and works on the system python3 3.9.
"""
import glob
import json
import os
import re

import kit_country

CODE = kit_country.CODE
DEFAULT = kit_country.LANG
KEY = r"[a-z0-9][a-z0-9_.-]*"
PLACEHOLDER = re.compile(r"\{([a-z]+)\}")


def lang_dir(web=None):
    return os.path.join(web or os.path.join(CODE, "web"), "lang")


def load(web=None):
    """{language code: {key: text}}, the default language first."""
    texts = {}
    for path in sorted(glob.glob(os.path.join(lang_dir(web), "*.json"))):
        with open(path, encoding="utf-8") as f:
            texts[os.path.basename(path)[:-5]] = json.load(f)
    return dict(sorted(texts.items(), key=lambda kv: kv[0] != DEFAULT))


def t(texts, key, lang=None, params=None):
    """The text for `key` in `lang`, else in the default language, else the key itself.
    A parameter may itself be a text per language ({"uk": ..., "en": ...})."""
    lang = lang or DEFAULT
    s = (texts.get(lang) or {}).get(key) or (texts.get(DEFAULT) or {}).get(key) or key
    for name, v in (params or {}).items():
        if isinstance(v, dict):
            v = v.get(lang) or v.get(DEFAULT) or ""
        s = s.replace("{" + name + "}", str(v))
    return s


def pages_script(web=None):
    """JavaScript for /lib/lang.js: every language's texts as window.KIT_LANG, then the layer itself."""
    data = {"default": DEFAULT, "texts": load(web)}
    layer = os.path.join(web or os.path.join(CODE, "web"), "lib", "language.js")
    with open(layer, encoding="utf-8") as f:
        return "window.KIT_LANG = " + json.dumps(data, ensure_ascii=False) + ";\n" + f.read()


# An element marked data-t="key" (and maybe data-p='{"count": 3}') gets the text between its tags;
# data-t-attr="placeholder:key;aria-label:key" sets attributes.
_ELEMENT = re.compile(r'(<([a-z0-9]+)\b[^>]*?\sdata-t="(' + KEY + r')"[^>]*>)(.*?)(</\2>)', re.S)
_ATTRS = re.compile(r'<[a-z0-9]+\b[^>]*?\sdata-t-attr="([^"]+)"[^>]*>')


def _params(tag):
    m = re.search(r"\sdata-p='([^']*)'", tag)
    return json.loads(m.group(1)) if m else {}


def fill(page, texts, lang=None):
    """The page with every marked element's text written in `lang` (the default language)."""
    import html

    def element(m):
        return m.group(1) + html.escape(t(texts, m.group(3), lang, _params(m.group(1))), quote=False) + m.group(5)

    def attrs(m):
        tag = m.group(0)
        for pair in m.group(1).split(";"):
            name, _, key = pair.partition(":")
            value = html.escape(t(texts, key, lang, _params(tag)), quote=True)
            if re.search(r"\s" + re.escape(name) + r'="', tag):
                tag = re.sub(r"(\s" + re.escape(name) + r'=")[^"]*"', lambda a: a.group(1) + value + '"', tag, count=1)
            else:
                tag = tag[:-1] + ' %s="%s">' % (name, value)
        return tag

    return _ATTRS.sub(attrs, _ELEMENT.sub(element, page))
