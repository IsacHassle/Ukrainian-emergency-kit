"""The country config (config/country.json), for every script that needs a country's facts.

Kit name, default language, emergency numbers, AI model names and Book index workspace, map regions and
labels, the Libraries the AI looks up, Emergency Topics and checklist additions all live in that one file
(ADR 0002), so no script or page has a country written into it. EK_COUNTRY points at another file; the tests
use that to run the kit as another country.

Uses only Python's standard library (serve-web.py imports this), and works on the system python3 3.9.
"""
import json
import os
import unicodedata

CODE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # where the code and its config are
PATH = os.environ.get("EK_COUNTRY") or os.path.join(CODE, "config", "country.json")

with open(PATH, encoding="utf-8") as _f:
    COUNTRY = json.load(_f)

LANG = COUNTRY["default_language"]
LOCALE = COUNTRY["locale"]   # for dates and times, like sv-SE

# What a Visitor device's pages may read (served as /lib/country.js). Everything else is for the scripts
# that build the kit or the start page, and stays on the Kit Mac.
PAGE_KEYS = ("country", "default_language", "locale", "kit_name", "emergency_numbers", "radio", "checklist")


def text(value, lang=None):
    """A text from the config in `lang`, else in the default language. Plain strings pass through."""
    if isinstance(value, dict):
        return value.get(lang or LANG) or value.get(LANG) or ""
    return value or ""


def kit_name(lang=None):
    return text(COUNTRY["kit_name"], lang)


def slug():
    """The kit's name in plain letters, for file names ("Krislåda" -> "Krislada")."""
    plain = unicodedata.normalize("NFKD", kit_name()).encode("ascii", "ignore").decode()
    return "".join(ch for ch in plain if ch.isalnum()) or "kit"


def manifest(template):
    """The web app manifest (the static file is a template with {kit}, {description} and {lang})."""
    return (template.replace("{kit}", json.dumps(kit_name())[1:-1])
            .replace("{description}", json.dumps(text(COUNTRY["kit_description"]))[1:-1])
            .replace("{lang}", LANG))


def models():
    """{"main": name, "small": name}: the AI models, as Ollama knows them."""
    return COUNTRY["ai"]["models"]


def workspace():
    return COUNTRY["ai"]["workspace"]


def for_pages():
    """The part of the config that the pages need, as one dict."""
    out = {k: COUNTRY[k] for k in PAGE_KEYS if k in COUNTRY}
    out["slug"] = slug()
    out["ai"] = {"models": COUNTRY["ai"]["models"], "workspace_name": COUNTRY["ai"]["workspace_name"]}
    out["official_guides"] = {k: COUNTRY["official_guides"][k] for k in ("folder", "print_pages", "print_skip", "print_drop_lines")}
    m = COUNTRY["map"]
    out["map"] = {k: m[k] for k in ("pmtiles", "center", "zoom", "overview_label", "shortcuts", "zoom_by_type",
                                    "search_priority", "nearest") if k in m}
    out["map"]["labels"] = {k: m["labels"][k] for k in ("street", "address", "approximate_prefix", "approximate", "area_types")}
    return out


def pages_script():
    """JavaScript that gives a page the config as window.COUNTRY, and fills in the kit name."""
    return "window.COUNTRY = " + json.dumps(for_pages(), ensure_ascii=False) + ";\n" + PAGE_HELPERS


# Loaded first by every page: text(), the kit name in the title, and elements marked data-kit, data-number
# and data-country. Follows the page language (lang.js sets <html lang>, and says "kitlang" when it changes).
PAGE_HELPERS = r"""(() => {
  const C = window.COUNTRY;
  const lang = () => (document.documentElement.lang || C.default_language);
  // A text from the config in the page's language, else in the default language.
  C.text = v => (v && typeof v === 'object') ? (v[lang()] || v[C.default_language] || '') : (v || '');
  C.kit = () => C.text(C.kit_name);
  C.primaryNumber = () => (C.emergency_numbers.find(n => n.primary) || C.emergency_numbers[0]).number;
  // The title keeps its template ("Checklist · {kit}") so the kit's name can change with the language.
  function apply() {
    const root = document.documentElement;
    if (!root.dataset.title) root.dataset.title = document.title;
    document.title = root.dataset.title.split('{kit}').join(C.kit());
    document.querySelectorAll('[data-kit]').forEach(el => { el.textContent = C.kit(); });
    document.querySelectorAll('[data-kit-attr]').forEach(el => {
      const [a, v] = el.dataset.kitAttr.split('=');
      el.setAttribute(a, v.split('{kit}').join(C.kit()));
    });
    // Any other fact by its path in the config: <span data-country="ai.models.main"></span>.
    document.querySelectorAll('[data-country]').forEach(el => {
      el.textContent = C.text(el.dataset.country.split('.').reduce((o, k) => (o == null ? o : o[k]), C));
    });
    document.querySelectorAll('[data-number]').forEach(el => { el.textContent = C.primaryNumber(); });
  }
  addEventListener('DOMContentLoaded', apply);
  addEventListener('kitlang', apply);
})();
"""
