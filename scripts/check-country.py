#!/usr/bin/env python3
"""Checks a country config (default config/country.json); CI runs it on every push.

Prints each problem on its own line, with the path of the part that is wrong, and exits non-zero if
there is any. Usage: python3 scripts/check-country.py [path]
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kit_say import die, say  # noqa: E402

PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                                         "config", "country.json")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # map.shape is a path from here
problems = []


def bad(where, why):
    problems.append(f"{where}: {why}")


def get(where, obj, key, kind):
    """obj[key] if it is there and of the right type, else records a problem and returns None."""
    if not isinstance(obj, dict) or key not in obj:
        bad(f"{where}.{key}".lstrip("."), "missing")
        return None
    v = obj[key]
    if not isinstance(v, kind) or (kind is str and not v.strip()) or (kind in (list, dict) and not v):
        bad(f"{where}.{key}".lstrip("."), f"must be a non-empty {kind.__name__}")
        return None
    return v


def texts(where, v, lang, also=()):
    """A text per language, with the default language always there (and the languages in `also`)."""
    if not isinstance(v, dict) or not all(isinstance(k, str) and isinstance(t, str) for k, t in v.items()):
        bad(where, "must be a text per language, like {\"uk\": \"...\", \"en\": \"...\"}")
        return
    for code in (lang,) + tuple(also):
        if not v.get(code, "").strip():
            bad(where, f"has no text in {code}" + (" (the default language)" if code == lang else ""))


def point(where, v):
    if not (isinstance(v, list) and len(v) == 2 and all(isinstance(n, (int, float)) for n in v)
            and -180 <= v[0] <= 180 and -90 <= v[1] <= 90):
        bad(where, "must be [longitude, latitude]")


def check_shape(path):
    """The map's shape (map.shape, a path from the repo folder): a GeoJSON file with one valid Polygon."""
    if not path:
        return
    full = os.path.join(ROOT, path)
    try:
        with open(full, encoding="utf-8") as f:
            g = json.load(f)
    except (OSError, ValueError) as e:
        return bad("map.shape", f"{path} cannot be read as JSON ({e})")
    geoms = [x.get("geometry") for x in g.get("features", [])] if g.get("type") == "FeatureCollection" else [g.get("geometry") if g.get("type") == "Feature" else g]
    if len(geoms) != 1 or not isinstance(geoms[0], dict) or geoms[0].get("type") != "Polygon":
        return bad("map.shape", f"{path} must hold exactly one Polygon")
    for ring in geoms[0].get("coordinates") or [[]]:
        if len(ring) < 4 or ring[0] != ring[-1] or not all(isinstance(p, list) and len(p) == 2 and -180 <= p[0] <= 180 and -90 <= p[1] <= 90 for p in ring):
            return bad("map.shape", f"{path} has a ring that is not closed or has coordinates outside the world")


def main():
    try:
        with open(PATH, encoding="utf-8") as f:
            c = json.load(f)
    except (OSError, ValueError) as e:
        die(f"{PATH}: не читається як JSON ({e})", f"{PATH}: cannot be read as JSON ({e})")
    if not isinstance(c, dict):
        die(f"{PATH}: має бути об'єктом JSON", f"{PATH}: must be a JSON object")

    get("", c, "country", str)
    lang = get("", c, "default_language", str)
    if lang is None:
        lang = "uk"
    elif not re.fullmatch(r"[a-z]{2,3}", lang):
        bad("default_language", "must be a language code like uk")
    get("", c, "locale", str)
    texts("kit_description", get("", c, "kit_description", dict), lang)
    texts("kit_name", get("", c, "kit_name", dict), lang, also=("en",))   # the name in both languages

    # The AI.
    ai = get("", c, "ai", dict) or {}
    models = get("ai", ai, "models", dict) or {}
    names = [get("ai.models", models, k, str) for k in ("main", "small")]
    if None not in names and len(set(names)) != 2:
        bad("ai.models", "main and small must have different names")
    bases = get("ai", ai, "base_models", dict) or {}
    for k in ("main", "small"):
        get("ai.base_models", bases, k, str)
    for k in ("workspace", "workspace_name", "answer_language", "authorities", "example_source"):
        get("ai", ai, k, str)
    # AnythingLLM makes a workspace's address from its name, so the two must agree.
    if isinstance(ai.get("workspace"), str) and isinstance(ai.get("workspace_name"), str) \
            and re.sub(r"[^a-z0-9]+", "-", ai["workspace_name"].lower()).strip("-") != ai["workspace"]:
        bad("ai.workspace", "must be what AnythingLLM makes of ai.workspace_name (lower case, dashes between words)")
    chk = get("ai", ai, "check", dict) or {}
    for k in ("question", "expect"):
        get("ai.check", chk, k, str)
    libs = get("ai", ai, "libraries", list) or []
    for i, lib in enumerate(libs):
        w = f"ai.libraries[{i}]"
        for k in ("prefix", "label", "language"):
            get(w, lib, k, str)
        if isinstance(lib, dict) and lib.get("kind") not in ("encyclopedia", "plain"):
            bad(w + ".kind", "must be encyclopedia or plain")

    # The AI's instruction files, the languages of the Libraries and the languages a question may come in.
    for k in ("prompt_file", "plan_prompt_file"):
        f = get("ai", ai, k, str)
        if f and not os.path.isfile(f if os.path.isabs(f) else os.path.join(ROOT, f)):
            bad(f"ai.{k}", f"{f} is not a file")
    plan_text = ""
    f = ai.get("plan_prompt_file")
    if isinstance(f, str) and os.path.isfile(f if os.path.isabs(f) else os.path.join(ROOT, f)):
        with open(f if os.path.isabs(f) else os.path.join(ROOT, f), encoding="utf-8") as fh:
            plan_text = fh.read()
    if plan_text and "SEARCH:" not in plan_text:
        bad("ai.plan_prompt_file", "must ask for a line starting SEARCH:")
    codes = set()
    for i, l in enumerate(get("ai", ai, "library_languages", list) or []):
        w = f"ai.library_languages[{i}]"
        for k in ("code", "name", "plan_label"):
            get(w, l, k, str)
        if isinstance(l, dict) and isinstance(l.get("code"), str):
            codes.add(l["code"])
        if isinstance(l, dict) and isinstance(l.get("plan_label"), str) and plan_text and l["plan_label"] + ":" not in plan_text:
            bad(w + ".plan_label", f"{l['plan_label']}: is not a line the plan prompt asks for")
    for i, lib in enumerate(libs):
        if isinstance(lib, dict) and lib.get("language") not in codes:
            bad(f"ai.libraries[{i}].language", "is not one of ai.library_languages")
    for i, l in enumerate(get("ai", ai, "answer_languages", list) or []):
        w = f"ai.answer_languages[{i}]"
        get(w, l, "name", str)
        get(w, l, "alphabet", str)
        if not isinstance(l, dict) or not isinstance(l.get("letters"), str) or not isinstance(l.get("words"), list):
            bad(w, "needs letters (a string, may be empty) and words (a list)")
    sw = get("ai", ai, "section_words", dict) or {}
    for k in ("high", "mid"):
        get("ai.section_words", sw, k, list)
    get("", c, "repo", str)
    if isinstance(c.get("repo"), str) and not re.fullmatch(r"[\w.-]+/[\w.-]+", c["repo"]):
        bad("repo", "must look like owner/name")

    # Emergency numbers.
    nums = get("", c, "emergency_numbers", list) or []
    for i, n in enumerate(nums):
        w = f"emergency_numbers[{i}]"
        get(w, n, "number", str)
        texts(w + ".label", n.get("label") if isinstance(n, dict) else None, lang, also=("en",))
        texts(w + ".print_label", n.get("print_label") if isinstance(n, dict) else None, lang, also=("en",))
    if sum(1 for n in nums if isinstance(n, dict) and n.get("primary")) != 1:
        bad("emergency_numbers", "exactly one number must be marked primary")
    radio = get("", c, "radio", dict) or {}
    texts("radio.label", radio.get("label"), lang)
    texts("radio.print_label", radio.get("print_label"), lang)

    # Official Guides.
    og = get("", c, "official_guides", dict) or {}
    get("official_guides", og, "folder", str)
    for i, s in enumerate(get("official_guides", og, "sources", list) or []):
        get(f"official_guides.sources[{i}]", s, "id", str)
        get(f"official_guides.sources[{i}]", s, "host", str)
        for pattern in (s.get("cut_from") or []) if isinstance(s, dict) else []:
            try:
                re.compile(pattern)
            except (re.error, TypeError):
                bad(f"official_guides.sources[{i}].cut_from", f"{pattern!r} is not a valid pattern")
        texts(f"official_guides.sources[{i}].name", s.get("name") if isinstance(s, dict) else None, lang, also=("en",))
        texts(f"official_guides.sources[{i}].label", s.get("label") if isinstance(s, dict) else None, lang)
        if isinstance(s, dict):
            if "optional" in s and not isinstance(s["optional"], bool):
                bad(f"official_guides.sources[{i}].optional", "must be true or false")
            cont = s.get("container", [])
            if not isinstance(cont, list) or not all(isinstance(x, str) and x for x in cont):
                bad(f"official_guides.sources[{i}].container", "must be a list of selectors like \"article\" or \"div.post\"")
    printed = get("official_guides", og, "print_pages", dict) or {}
    for code, names in printed.items():
        if not isinstance(names, list) or not all(isinstance(p, str) and " - " in p for p in names):
            bad(f"official_guides.print_pages.{code}", "must be a list of saved guides' names like \"Source - Title\"")
    if lang not in printed:
        bad("official_guides.print_pages", f"needs a list for the default language ({lang})")
    for key in ("print_skip", "print_drop_lines"):
        for i, p in enumerate(get("official_guides", og, key, list) or []):
            try:
                re.compile(p)
            except (re.error, TypeError):
                bad(f"official_guides.{key}[{i}]", "must be a regular expression")

    # The guide list beside the config (config/pages.txt), when there is one: (language, name) of every line.
    listed = None
    pages = os.path.join(os.path.dirname(os.path.abspath(PATH)), "pages.txt")
    if os.path.exists(pages):
        listed = set()
        ids = {s.get("id") for s in og.get("sources", []) if isinstance(s, dict)}
        with open(pages, encoding="utf-8") as f:
            for number, line in enumerate(f, 1):
                line = line.split("#", 1)[0].strip()
                if not line:
                    continue
                parts = [x.strip() for x in line.split("|")]
                if len(parts) != 3 or not parts[1].startswith("http") or " - " not in parts[2]:
                    bad(f"pages.txt:{number}", "must be `language | address | Source - Title`")
                    continue
                listed.add((parts[0], parts[2]))
                if parts[2].split(" - ", 1)[0] not in ids:
                    bad(f"pages.txt:{number}", f"{parts[2].split(' - ', 1)[0]!r} is not a source in official_guides.sources")

    if listed is not None:
        for code, names in printed.items():
            for n in names if isinstance(names, list) else []:
                if (code, n) not in listed:
                    bad(f"official_guides.print_pages.{code}", f"{n!r} is not in pages.txt for {code}")

    # Emergency Topics.
    topics = get("", c, "emergency_topics", list) or []
    seen = set()
    for i, t in enumerate(topics):
        w = f"emergency_topics[{i}]"
        tid = get(w, t, "id", str)
        if tid in seen:
            bad(w + ".id", f"{tid} is listed twice")
        seen.add(tid)
        # The article in each language's WikiMed Library. Official Guides come first when a topic has one.
        wm = get(w, t, "wikimed", dict) or {}
        for code in (lang, "en"):
            get(w + ".wikimed", wm, code, str)
        texts(w + ".label", t.get("label") if isinstance(t, dict) else None, lang)
        guide = t.get("official_guide") if isinstance(t, dict) else None
        if guide is not None:
            if not isinstance(guide, dict) or not guide:
                bad(w + ".official_guide", "must be {\"uk\": [guide names], \"en\": [...]}, a language per key")
                guide = {}
            for code, names in guide.items():
                names = [names] if isinstance(names, str) else names
                if not isinstance(names, list) or not all(isinstance(n, str) and " - " in n for n in names):
                    bad(f"{w}.official_guide.{code}", "must be saved guides' names like \"Source - Title\" (one, or a list)")
                    continue
                for n in names:   # a name has to be in the list the saver reads, in that language
                    if listed is not None and (code, n) not in listed:
                        bad(f"{w}.official_guide.{code}", f"{n!r} is not in pages.txt for {code}")

    # Start page lists.
    for i, b in enumerate(get("", c, "books", list) or []):
        get(f"books[{i}]", b, "path", str)
        texts(f"books[{i}].label", b.get("label") if isinstance(b, dict) else None, lang)
        texts(f"books[{i}].description", b.get("description") if isinstance(b, dict) else None, lang)
    for i, g in enumerate(get("", c, "library_groups", list) or []):
        texts(f"library_groups[{i}].heading", g.get("heading") if isinstance(g, dict) else None, lang)
        for j, lib in enumerate(get(f"library_groups[{i}]", g, "libraries", list) or []):
            get(f"library_groups[{i}].libraries[{j}]", lib, "prefix", str)
            texts(f"library_groups[{i}].libraries[{j}].description", lib.get("description") if isinstance(lib, dict) else None, lang)
    sl = get("", c, "search_languages", dict) or {}
    for k in ("main", "country"):
        get("search_languages", sl, k, str)

    # Checklist.
    cl = get("", c, "checklist", dict) or {}
    # Each list is read from a saved Official Guide: the section, the line that starts the list and the line it ends before.
    for i, ol in enumerate(get("checklist", cl, "official_lists", list) or []):
        where = f"checklist.official_lists[{i}]"
        get(where, ol, "id", str)
        for k in ("heading", "guide", "section", "start", "until"):
            texts(f"{where}.{k}", ol.get(k) if isinstance(ol, dict) else None, lang)
    for i, a in enumerate(get("checklist", cl, "additions", list) or []):
        texts(f"checklist.additions[{i}]", a, lang)

    # The map.
    m = get("", c, "map", dict) or {}
    regions = get("map", m, "regions", list) or []
    for i, r in enumerate(regions):
        w = f"map.regions[{i}]"
        get(w, r, "geofabrik", str)
        get(w, r, "slug", str)
        if isinstance(r, dict) and r.get("detail") not in ("full", "border"):
            bad(w + ".detail", "must be full or border")
    if regions and not any(isinstance(r, dict) and r.get("detail") == "full" for r in regions):
        bad("map.regions", "at least one region must be full detail")
    get("map", m, "pmtiles", str)
    check_shape(get("map", m, "shape", str))
    for k in ("max_zoom", "world_max_zoom"):
        if not isinstance(m.get(k), int) or isinstance(m.get(k), bool) or not 0 <= m[k] <= 22:
            bad(f"map.{k}", "must be a whole number from 0 to 22")
    point("map.center", m.get("center"))
    if not isinstance(m.get("zoom"), (int, float)):
        bad("map.zoom", "must be a number")
    texts("map.overview_label", m.get("overview_label"), lang)
    for i, s in enumerate(m.get("shortcuts") or []):
        texts(f"map.shortcuts[{i}].label", s.get("label"), lang)
        point(f"map.shortcuts[{i}].center", s.get("center"))
    tags = get("map", m, "name_tags", list)
    if tags is not None and not all(isinstance(t, str) for t in tags):
        bad("map.name_tags", "must be a list of tag names")
    lab = get("map", m, "labels", dict) or {}
    for k in ("place", "service", "landmark"):
        get("map.labels", lab, k, dict)
    for k in ("street", "address", "border_crossing", "shelter"):
        get("map.labels", lab, k, str)
    for k in ("base_places", "area_types", "town_types"):
        get("map.labels", lab, k, list)
    # Words that mark a name as military, the other language whose names are left out, and the street types the search strips.
    for where, v in (("map.labels.military_words", lab.get("military_words")), ("map.street_types", m.get("street_types"))):
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            bad(where, "must be a list of words (may be empty)")
    for w in lab.get("military_words") or []:
        try:
            re.compile(w)
        except re.error as e:
            bad("map.labels.military_words", f"{w!r} is not a valid pattern ({e})")
    other = lab.get("other_language")
    if not isinstance(other, dict) or not isinstance(other.get("letters"), str) \
            or not all(isinstance(other.get(k), list) for k in ("street_types", "endings")):
        bad("map.labels.other_language", "needs letters (a string), street_types and endings (lists), all may be empty")
    elif not isinstance(other.get("words", []), list):
        bad("map.labels.other_language.words", "must be a list of whole words")
    crossing = get("map.labels", lab, "unnamed_crossing", dict) or {}
    for k in ("name", "en"):
        get("map.labels.unnamed_crossing", crossing, k, str)
    for k in ("zoom_by_type", "search_priority"):
        get("map", m, k, dict)
    for i, n in enumerate(get("map", m, "nearest", list) or []):
        texts(f"map.nearest[{i}].label", n.get("label") if isinstance(n, dict) else None, lang)
        get(f"map.nearest[{i}]", n, "types", list)
    for i, a in enumerate(m.get("no_help_areas") or []):   # where nearest help is not listed (optional)
        for k in ("name", "region", "relation"):
            get(f"map.no_help_areas[{i}]", a, k, str)
    for i, n in enumerate(m.get("nearest") or []):
        if isinstance(n, dict) and "reach_km" in n and not (isinstance(n["reach_km"], (int, float)) and n["reach_km"] > 0):
            bad(f"map.nearest[{i}].reach_km", "must be a number above 0 (how far the list reaches)")
    for i, a in enumerate(get("map", m, "closed_border_areas", list) or []):
        for k in ("name", "region", "relation"):
            get(f"map.closed_border_areas[{i}]", a, k, str)
        if not isinstance(a.get("near_km"), (int, float)):
            bad(f"map.closed_border_areas[{i}].near_km", "must be a number")

    for p in problems:
        print(p)
    if problems:
        die(f"{PATH}: проблем {len(problems)}", f"{PATH}: {len(problems)} problem(s)")
    say(f"{PATH}: усе гаразд", f"{PATH}: ok")


main()
