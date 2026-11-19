"""The country config (config/country.json), for every script that needs a country's facts.

Kit name, default language, emergency numbers, AI model names and Book index workspace, map regions and
labels, the Libraries the AI looks up, Emergency Topics and checklist additions all live in that one file
(ADR 0002), so no script or page has a country written into it. EK_COUNTRY points at another file; the tests
use that to run the kit as another country.

Uses only Python's standard library (serve-web.py imports this), and works on the system python3 3.9.
"""
import json
import os

CODE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # where the code and its config are
PATH = os.environ.get("EK_COUNTRY") or os.path.join(CODE, "config", "country.json")

with open(PATH, encoding="utf-8") as _f:
    COUNTRY = json.load(_f)

LANG = COUNTRY["default_language"]

# What a Visitor device's pages may read (served as /lib/country.js). Everything else is for the scripts
# that build the kit or the start page, and stays on the Kit Mac.
PAGE_KEYS = ("country", "default_language", "kit_name", "emergency_numbers", "radio", "checklist")


def text(value, lang=None):
    """A text from the config in `lang`, else in the default language. Plain strings pass through."""
    if isinstance(value, dict):
        return value.get(lang or LANG) or value.get(LANG) or ""
    return value or ""


def kit_name(lang=None):
    return text(COUNTRY["kit_name"], lang)


def models():
    """{"main": name, "small": name}: the AI models, as Ollama knows them."""
    return COUNTRY["ai"]["models"]


def workspace():
    return COUNTRY["ai"]["workspace"]


def for_pages():
    """The part of the config that the pages need, as one dict."""
    out = {k: COUNTRY[k] for k in PAGE_KEYS if k in COUNTRY}
    out["ai"] = {"models": COUNTRY["ai"]["models"]}
    out["official_guides"] = {k: COUNTRY["official_guides"][k] for k in ("folder", "print_pages")}
    m = COUNTRY["map"]
    out["map"] = {k: m[k] for k in ("center", "zoom", "overview_label", "shortcuts", "zoom_by_type",
                                    "search_priority", "nearest") if k in m}
    out["map"]["labels"] = {k: m["labels"][k] for k in ("street", "address", "approximate_prefix", "area_types")}
    return out


def pages_script():
    """JavaScript that gives a page the config as window.COUNTRY, and fills in the kit name."""
    return "window.COUNTRY = " + json.dumps(for_pages(), ensure_ascii=False) + ";\n" + PAGE_HELPERS


# Loaded first by every page: text(), the kit name in the title, and elements marked data-kit.
PAGE_HELPERS = r"""(() => {
  const C = window.COUNTRY;
  const lang = () => (document.documentElement.lang || C.default_language);
  // A text from the config in the page's language, else in the default language.
  C.text = v => (v && typeof v === 'object') ? (v[lang()] || v[C.default_language] || '') : (v || '');
  C.kit = () => C.text(C.kit_name);
  C.primaryNumber = () => (C.emergency_numbers.find(n => n.primary) || C.emergency_numbers[0]).number;
  addEventListener('DOMContentLoaded', () => {
    document.title = document.title.split('{kit}').join(C.kit());
    document.querySelectorAll('[data-kit]').forEach(el => { el.textContent = C.kit(); });
    document.querySelectorAll('[data-kit-attr]').forEach(el => {
      const [a, v] = el.dataset.kitAttr.split('=');
      el.setAttribute(a, v.split('{kit}').join(C.kit()));
    });
    document.querySelectorAll('[data-number]').forEach(el => { el.textContent = C.primaryNumber(); });
  });
})();
"""
