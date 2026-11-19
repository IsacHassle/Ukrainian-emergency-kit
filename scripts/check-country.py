#!/usr/bin/env python3
"""Checks a country config (default config/country.json); CI runs it on every push.

Prints each problem on its own line, with the path of the part that is wrong, and exits non-zero if
there is any. Usage: python3 scripts/check-country.py [path]
"""
import json
import os
import re
import sys

PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                                         "config", "country.json")
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


def texts(where, v, lang):
    """A text per language, with the default language always there."""
    if not isinstance(v, dict) or not all(isinstance(k, str) and isinstance(t, str) for k, t in v.items()):
        bad(where, "must be a text per language, like {\"sv\": \"...\"}")
    elif not v.get(lang, "").strip():
        bad(where, f"has no text in the default language ({lang})")


def point(where, v):
    if not (isinstance(v, list) and len(v) == 2 and all(isinstance(n, (int, float)) for n in v)
            and -180 <= v[0] <= 180 and -90 <= v[1] <= 90):
        bad(where, "must be [longitude, latitude]")


def main():
    try:
        with open(PATH, encoding="utf-8") as f:
            c = json.load(f)
    except (OSError, ValueError) as e:
        sys.exit(f"{PATH}: cannot be read as JSON ({e})")
    if not isinstance(c, dict):
        sys.exit(f"{PATH}: must be a JSON object")

    get("", c, "country", str)
    lang = get("", c, "default_language", str)
    if lang is None:
        lang = "sv"
    elif not re.fullmatch(r"[a-z]{2,3}", lang):
        bad("default_language", "must be a language code like uk")
    get("", c, "locale", str)
    texts("kit_description", get("", c, "kit_description", dict), lang)
    texts("kit_name", get("", c, "kit_name", dict), lang)

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

    # Emergency numbers.
    nums = get("", c, "emergency_numbers", list) or []
    for i, n in enumerate(nums):
        w = f"emergency_numbers[{i}]"
        get(w, n, "number", str)
        texts(w + ".label", n.get("label") if isinstance(n, dict) else None, lang)
        texts(w + ".print_label", n.get("print_label") if isinstance(n, dict) else None, lang)
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
        texts(f"official_guides.sources[{i}].label", s.get("label") if isinstance(s, dict) else None, lang)
    pages = get("official_guides", og, "print_pages", list) or []
    if not all(isinstance(p, str) and " - " in p for p in pages):
        bad("official_guides.print_pages", "each must be a saved guide's name like \"Source - Title\"")

    # Emergency Topics.
    topics = get("", c, "emergency_topics", list) or []
    seen = set()
    for i, t in enumerate(topics):
        w = f"emergency_topics[{i}]"
        art = get(w, t, "article", str)
        if art in seen:
            bad(w + ".article", f"{art} is listed twice")
        seen.add(art)
        texts(w + ".label", t.get("label") if isinstance(t, dict) else None, lang)
        guide = t.get("official_guide") if isinstance(t, dict) else None
        if guide is not None:
            texts(w + ".official_guide", guide, lang)

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
    ol = get("checklist", cl, "official_list", dict) or {}
    for k in ("guide", "section", "source_prefix"):
        get("checklist.official_list", ol, k, str)
    texts("checklist.official_list.heading", ol.get("heading"), lang)
    for i, a in enumerate(get("checklist", cl, "additions", list) or []):
        texts(f"checklist.additions[{i}]", a, lang)

    # Ready.gov.
    rg = get("", c, "ready_gov", dict) or {}
    get("ready_gov", rg, "note", str)
    pat = get("ready_gov", rg, "skip_pattern", str)
    if pat:
        try:
            re.compile(pat)
        except re.error as e:
            bad("ready_gov.skip_pattern", f"is not a valid pattern ({e})")

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
    get("map", m, "search_release_repo", str)
    bbox = get("map", m, "bbox", list)
    if bbox is not None:
        if not (len(bbox) == 4 and all(isinstance(n, (int, float)) for n in bbox)
                and bbox[0] < bbox[2] and bbox[1] < bbox[3]):
            bad("map.bbox", "must be [west, south, east, north] with west < east and south < north")
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
    for k in ("street", "address", "approximate_prefix", "approximate"):
        get("map.labels", lab, k, str)
    for k in ("base_places", "area_types", "town_types"):
        get("map.labels", lab, k, list)
    for k in ("zoom_by_type", "search_priority"):
        get("map", m, k, dict)
    for i, n in enumerate(get("map", m, "nearest", list) or []):
        texts(f"map.nearest[{i}].label", n.get("label") if isinstance(n, dict) else None, lang)
        get(f"map.nearest[{i}]", n, "types", list)

    for p in problems:
        print(p)
    if problems:
        sys.exit(f"{PATH}: {len(problems)} problem(s)")
    print(f"{PATH}: ok")


main()
