#!/usr/bin/env python3
"""Builds the offline search for the map, for the country in config/country.json, from OpenStreetMap.

Input:  maps/osm/<region>-latest.osm.pbf  (the full-detail region, download.geofabrik.de)
Output: web/map/data/places.json         towns, villages, neighbourhoods and services
                                         (hospitals, pharmacies, police, water, food, fuel...)
                                         used by every search and by the "nearest" buttons
        web/map/data/letters/<a-z0-9>.json   streets, addresses, farms and landmarks,
                                         split by first letter so a phone only loads one small file

Needs osmium (brew install osmium-tool) and Python 3. Takes a few minutes.
Run:  python3 scripts/build-map-index.py
"""
import gzip
import json
import math
import os
import subprocess
import sys
import tempfile
import time
import unicodedata
from collections import defaultdict

import kit_country

KIT = os.environ.get("KIT_DIR") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGION = next(r for r in kit_country.COUNTRY["map"]["regions"] if r["detail"] == "full")   # the Geofabrik extract
OSM = os.path.join(KIT, "maps", "osm", REGION["slug"] + "-latest.osm.pbf")
OUT = os.path.join(KIT, "web", "map", "data")

# What a place is called in the search results, and which tags make something a service or a landmark:
# all from the country config (map.labels), the same words the map page uses to rank and zoom.
LABELS = kit_country.COUNTRY["map"]["labels"]
PLACE = LABELS["place"]
BASE_PLACES = set(LABELS["base_places"])   # always loaded
STREET = LABELS["street"]
pair = lambda table: {tuple(k.split("=", 1)): v for k, v in table.items()}
SERVICE = pair(LABELS["service"])    # (key, value) -> label; always loaded, used by the "nearest" buttons
LANDMARK = pair(LABELS["landmark"])  # named places that help find your way; loaded per letter
STATION = LANDMARK.get(("railway", "station"))
TOWN_TYPES = LABELS["town_types"]    # cities and towns: they name the area of what is near them
CITY = TOWN_TYPES[0]                 # a city needs no area name
HOOD_TYPES = [t for t in LABELS["area_types"] if t not in TOWN_TYPES]   # neighbourhoods and villages
ROADS = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential",
         "living_street", "pedestrian", "road"}
NAME_TAGS = kit_country.COUNTRY["map"]["name_tags"]   # the first one that is set names the place
TAGS = sorted(set(NAME_TAGS) | {"name"}) + ["place", "highway", "amenity", "shop", "railway", "public_transport", "leisure",
        "natural", "tourism", "aeroway", "addr:street", "addr:place", "addr:housenumber", "addr:city"]


def norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return "".join(c if c.isalnum() else " " for c in s).split()


def letter(s):
    w = norm(s)
    c = w[0][0] if w else "_"
    return c if c.isascii() and c.isalnum() else "_"


def km(a, b):
    return math.hypot((a[0] - b[0]) * 111.3 * math.cos(math.radians(a[1])), (a[1] - b[1]) * 110.6)


def centre(g):
    t, c = g["type"], g["coordinates"]
    if t == "Point":
        return c
    pts = c if t == "LineString" else c[0] if t == "Polygon" else c[0][0] if t == "MultiPolygon" else c[0]
    if t == "LineString":
        return pts[len(pts) // 2]
    return [sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)]


def export(work, pbf, *filters):
    """osmium tags-filter + export, yielding (tags, [lon, lat]) for each object."""
    sub = os.path.join(work, "part.osm.pbf")
    out = os.path.join(work, "part.geojsonseq")
    cfg = os.path.join(work, "cfg.json")
    json.dump({"attributes": {}, "linear_tags": True, "area_tags": True, "include_tags": TAGS}, open(cfg, "w"))
    subprocess.run(["osmium", "tags-filter", pbf, *filters, "-o", sub, "--overwrite"], check=True)
    subprocess.run(["osmium", "export", sub, "-c", cfg, "-f", "geojsonseq", "-o", out, "--overwrite"], check=True)
    with open(out) as fh:
        for line in fh:
            f = json.loads(line.lstrip("\x1e"))
            yield f["properties"], centre(f["geometry"])


def main():
    if not os.path.exists(OSM):
        sys.exit(f"Missing {OSM}. Download https://download.geofabrik.de/{REGION['geofabrik']}-latest.osm.pbf there first.")
    t0 = time.time()
    work = tempfile.mkdtemp(prefix="kit-map-")
    base, per_letter = [], defaultdict(list)          # [name, type, lon, lat]
    places = []                                        # for area names

    # 1. Places.
    for tags, (lon, lat) in export(work, OSM, "n/place"):
        name = next((tags[t] for t in NAME_TAGS if tags.get(t)), None)
        typ = PLACE.get(tags.get("place"))
        if not name or not typ:
            continue
        e = [name, typ, round(lon, 5), round(lat, 5)]
        (base if typ in BASE_PLACES else per_letter[letter(name)]).append(e)
        places.append((lon, lat, name, typ))
    print(f"places: {len(places)} ({time.time() - t0:.0f}s)", flush=True)

    # 2. Services and landmarks.
    filters = sorted({f"nwr/{k}={v}" for k, v in list(SERVICE) + list(LANDMARK)})
    for tags, (lon, lat) in export(work, OSM, *filters):
        label = next((SERVICE[(k, tags[k])] for k in ("amenity", "shop") if (k, tags.get(k)) in SERVICE), None)
        name = next((tags[t] for t in NAME_TAGS if tags.get(t)), None)
        if label:
            base.append([name or label, label, round(lon, 5), round(lat, 5)])
            continue
        label = next((LANDMARK[(k, v)] for k, v in tags.items() if (k, v) in LANDMARK), None)
        if label and name:
            per_letter[letter(name)].append([name, label, round(lon, 5), round(lat, 5)])
    print(f"services and landmarks done ({time.time() - t0:.0f}s)", flush=True)

    # 3. Streets: one entry per street per area (pieces within 1.5 km are the same street).
    pieces = defaultdict(list)
    for tags, (lon, lat) in export(work, OSM, "w/highway=" + ",".join(sorted(ROADS))):
        name = tags.get("name")
        if name and tags.get("highway") in ROADS:
            pieces[name].append((lon, lat))
    streets = 0
    for name, pts in pieces.items():
        grid = {}
        for p in pts:
            key = (round(p[0] / 0.025), round(p[1] / 0.0135))   # about 1.5 km cells
            grid.setdefault(key, []).append(p)
        for cell in grid.values():
            cx, cy = sum(p[0] for p in cell) / len(cell), sum(p[1] for p in cell) / len(cell)
            mid = min(cell, key=lambda p: km(p, (cx, cy)))
            per_letter[letter(name)].append([name, STREET, round(mid[0], 5), round(mid[1], 5)])
            streets += 1
    print(f"streets: {streets} ({time.time() - t0:.0f}s)", flush=True)

    # 4. Addresses, grouped by street (or by village, for addresses without a street).
    addresses = defaultdict(lambda: defaultdict(dict))   # letter -> street -> key -> [num, lon, lat, city]
    count = 0
    for tags, (lon, lat) in export(work, OSM, "nwr/addr:housenumber"):
        street = tags.get("addr:street") or tags.get("addr:place")
        num = tags.get("addr:housenumber")
        if not street or not num:
            continue
        city = tags.get("addr:city") or ""
        for n in str(num).replace(";", ",").split(","):
            n = n.strip()
            if n:
                key = (n.upper().replace(" ", ""), city, round(lon, 3), round(lat, 3))
                if key not in addresses[letter(street)][street]:
                    addresses[letter(street)][street][key] = [n, round(lon, 5), round(lat, 5), city]
                    count += 1
    print(f"addresses: {count} ({time.time() - t0:.0f}s)", flush=True)

    # 5. Area names ("Huvudsta, Solna") so places with the same name can be told apart.
    def grid_of(items, cell):
        g = defaultdict(list)
        for it in items:
            g[(int(it[0] / cell), int(it[1] / cell))].append(it)
        return g
    hoods = grid_of([p for p in places if p[3] in HOOD_TYPES], 0.05)
    towns = grid_of([p for p in places if p[3] in TOWN_TYPES], 0.25)

    def nearest(g, cell, lon, lat, limit):
        best, bd = None, limit
        gx, gy = int(lon / cell), int(lat / cell)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for p in g.get((gx + dx, gy + dy), ()):
                    d = km((lon, lat), p)
                    if d < bd:
                        best, bd = p[2], d
        return best

    def area(name, lon, lat):
        parts = []
        for p in (nearest(hoods, 0.05, lon, lat, 3.0), nearest(towns, 0.25, lon, lat, 15.0)):
            if p and p != name and p not in parts:
                parts.append(p)
        return ", ".join(parts)

    def pack(items):
        seen, out = set(), []
        for name, typ, lon, lat in items:
            key = (name, typ, round(lon, 2 if typ in (STREET, STATION) else 3), round(lat, 2 if typ in (STREET, STATION) else 3))
            if key not in seen and any(ch.isalpha() for ch in name):
                seen.add(key)
                out.append([name, typ, lon, lat, "" if typ == CITY else area(name, lon, lat)])
        types = sorted({e[1] for e in out})
        areas = sorted({e[4] for e in out})
        ti, ai = {t: i for i, t in enumerate(types)}, {a: i for i, a in enumerate(areas)}
        return {"types": types, "areas": areas, "items": [[e[0], ti[e[1]], e[2], e[3], ai[e[4]]] for e in out]}

    def write(path, obj):
        data = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "wb").write(data)
        open(path + ".gz", "wb").write(gzip.compress(data, 9))
        return len(data)

    size = write(os.path.join(OUT, "places.json"), pack(base))
    print(f"places.json: {len(base)} names, {size // 1024} KB", flush=True)
    for name in ("addresses.json", "addresses.json.gz"):   # replaced by the per-letter files
        if os.path.exists(os.path.join(OUT, name)):
            os.remove(os.path.join(OUT, name))
    total = 0
    for ch in sorted(set(per_letter) | set(addresses)):
        obj = pack(per_letter.get(ch, []))
        cities = sorted({a[3] for st in addresses[ch].values() for a in st.values()})
        ci = {c: i for i, c in enumerate(cities)}
        obj["cities"] = cities
        obj["addresses"] = {st: sorted(([a[0], a[1], a[2], ci[a[3]]] for a in v.values()), key=lambda a: (len(a[0]), a[0]))
                            for st, v in addresses[ch].items()}
        total += write(os.path.join(OUT, "letters", f"{ch}.json"), obj)
    print(f"letter files: {total // 1024 // 1024} MB in total ({time.time() - t0:.0f}s)")
    subprocess.run(["rm", "-rf", work])


if __name__ == "__main__":
    main()
