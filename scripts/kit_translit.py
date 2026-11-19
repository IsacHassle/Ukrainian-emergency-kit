"""The map search's matching rules in Python, for the build script (scripts/build-map-index.py).

web/map/search.js has the same rules for the page. Both are checked against tests/kit/search-cases.json: the
letter file a street is written to here must be the one the page asks for. Stdlib only, Python 3.9 compatible.
"""
import re
import unicodedata

import kit_country

ANY = {"а": "a", "б": "b", "в": "v", "г": "h", "ґ": "g", "д": "d", "е": "e", "є": "ie", "ж": "zh", "з": "z", "и": "y",
       "і": "i", "ї": "i", "й": "i", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s",
       "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch", "ю": "iu", "я": "ia"}
START = {"є": "ye", "ї": "yi", "й": "y", "ю": "yu", "я": "ya"}   # at the start of a word
DROP = {"ь", "'", "’", "ʼ", "`", "′"}
RU = {"а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i", "й": "y",
      "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
      "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya"}
FOLD = {"і": "и", "ї": "и", "ы": "и", "є": "е", "э": "е", "ё": "е", "ґ": "г", "й": "и"}
# Street types in the country's languages (config, map.street_types), lower case without the dot. The two letter
# tables above (Ukrainian and Russian to Latin) stay in code: they are rules of those scripts, and the tests
# (tests/kit/search-cases.json) hold them equal to the page's copy in web/map/search.js.
TYPES = set(kit_country.COUNTRY["map"]["street_types"])


def _is_letter(ch):
    return unicodedata.category(ch)[0] in "LN"


def translit(s):
    """Ukrainian to Latin, the national system (KMU resolution 55 of 2010)."""
    out, at_start, cs, i = [], True, list(s), 0
    while i < len(cs):
        j, ch = i, cs[i]
        lo = ch.lower()
        up = ch != lo
        if lo in DROP:
            at_start = False
            i += 1
            continue
        if lo == "з" and i + 1 < len(cs) and cs[i + 1].lower() == "г":
            r = "zgh"
            i += 1
        elif lo in ANY:
            r = START[lo] if (at_start and lo in START) else ANY[lo]
        else:
            out.append(ch)
            at_start = not _is_letter(ch)
            i += 1
            continue
        if up:
            nx = cs[i + 1] if i + 1 < len(cs) else None
            prev_up = j > 0 and cs[j - 1] != cs[j - 1].lower()
            next_up = bool(nx) and nx != nx.lower()
            r = r.upper() if (len(r) > 1 and (prev_up or next_up)) else r[0].upper() + r[1:]
        out.append(r)
        at_start = False
        i += 1
    return "".join(out)


def translit_ru(s):
    """Russian to Latin, only to match older spellings (Kiev, Kharkov). Never shown."""
    out = []
    for ch in s:
        lo = ch.lower()
        r = RU.get(lo)
        if r is None:
            out.append(ch)
        else:
            out.append(r if ch == lo else (r[0].upper() + r[1:] if r else ""))
    return "".join(out)


def norm(s):
    """The form names and queries are compared in (the same as norm() in web/map/search.js)."""
    s = unicodedata.normalize("NFD", str(s).lower())
    s = re.sub("[̀-ͯ'’ʼ`′ьъ]", "", s)
    s = "".join(FOLD.get(c, c) for c in s)
    return re.sub(r"[\W_]+", " ", s).strip()


def strip_type(s):
    w = s.split()
    is_type = lambda x: x.lower().rstrip(".") in TYPES
    if len(w) > 1 and is_type(w[0]):
        return " ".join(w[1:])
    if len(w) > 1 and is_type(w[-1]):
        return " ".join(w[:-1])
    return s.strip()


def letter_of(s):
    """The letter file a name is stored in."""
    s = strip_type(s)
    s = re.sub("[ёэ]", "е", s, flags=re.I)
    s = re.sub("ы", "и", s, flags=re.I)
    s = re.sub("ъ", "", s, flags=re.I)
    c = norm(translit(s))[:1]
    return c if c and c.isascii() and c.isalnum() else "_"
