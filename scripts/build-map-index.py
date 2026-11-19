#!/usr/bin/env python3
"""Builds the offline map search for the country in config/country.json, from OpenStreetMap.

Input:  Geofabrik extracts (download.geofabrik.de) for the regions in the country config (map.regions), found by
        their slug in --osm-dir: <slug>-<YYMMDD>.osm.pbf (or -latest). A region may be given as sub-regions
        instead (poland-podkarpackie-<date>.osm.pbf and so on); the whole file wins when both exist.
        The outlines (<slug>.poly, from the same site) are fetched next to them when missing.
Output: <out>/places.json.gz         towns, villages, services and border crossings: always loaded
        <out>/letters/<a-z0-9_>.json.gz   streets, addresses and landmarks, split by the first letter of the
                                     transliterated name (so a phone loads one small file)
        <release>/map-search.tar.gz  the same files in one archive: the release file scripts/get-maps.sh fetches

What goes in (the matching rules are in scripts/kit_translit.py and web/map/search.js):
  - full-detail regions: every named place, service and landmark, every street, every address, inside the map shape
  - border-strip regions: cities and towns inside the map shape
  - border crossings (barrier=border_control) from every region, grouped by site, only those at the land border
    between a full-detail region (map.regions) and another region
Names: what is shown is Ukrainian (name:uk, else name when it is not Russian) or the local name; the English name
is name:en, or the page transliterates the Ukrainian one. Russian and older names (name:ru, old_name, ...) are
only stored as search keys. A way or place whose only name is Russian is left out (counted in the log).

Needs osmium (brew install osmium-tool) and Python 3 (standard library only). Takes some minutes.
Run:  python3 scripts/build-map-index.py --osm-dir ~/.cache/emergency-kit-build/geofabrik --out /some/folder
"""
import argparse
import gzip
import io
import json
import math
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit_country  # noqa: E402
import kit_translit as T  # noqa: E402

KIT = os.environ.get("KIT_DIR") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAP = kit_country.COUNTRY["map"]
LABELS = MAP["labels"]
PLACE = LABELS["place"]                  # place=* value -> kind
BASE_PLACES = set(LABELS["base_places"])  # kinds in places.json (always loaded)
STREET, CROSSING, SHELTER = LABELS["street"], LABELS["border_crossing"], LABELS["shelter"]
UNNAMED_CROSSING = LABELS["unnamed_crossing"]   # how a crossing with no name is called (after it: the nearest place)
pair = lambda table: {tuple(k.split("=", 1)): v for k, v in table.items()}
SERVICE = pair(LABELS["service"])        # (key, value) -> kind; always loaded
LANDMARK = pair(LABELS["landmark"])      # named places that help find your way; loaded per letter
TOWN_KINDS = set(LABELS["town_types"])   # cities and towns name the area of what is near them
HOOD_KINDS = set(LABELS["area_types"]) - TOWN_KINDS
NAME_TAGS = MAP["name_tags"]             # every one is a search key; the first two are what is shown
ROADS = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential",
         "living_street", "pedestrian", "road"}
GROUP_KM = 2.0        # border control objects closer than this are one crossing
NEAR_BORDER_KM = 5.0  # a crossing must be this close to the border between a full-detail region and another one
TAGS = sorted(set(NAME_TAGS) | {"name", "name:uk", "name:en"}) + [
    "place", "highway", "amenity", "shop", "railway", "public_transport", "leisure", "natural", "tourism",
    "aeroway", "barrier", "addr:street", "addr:place", "addr:housenumber", "addr:city",
    "healthcare", "emergency", "man_made", "drinking_water", "access", "military", "landuse", "building", "office",
    "operator", "operator:type", "bunker_type", "shelter_type"]

# ---------- nearest help: what counts, and what must never be indexed ----------
# Shelters: the OpenStreetMap tags for a civil shelter. The first four are the spec's tags; the rest are what
# mappers really use in Ukraine (notes/10-nearest-help.md). Picnic and bus stop shelters, dugouts of partisans
# and every other bunker kind are not in the list, so they are never found.
SHELTER_TAGS = {
    "shelter_type": {"bomb_shelter", "bomb", "air_raid", "civil_defence", "nuclear", "radioactive_shelter"},
    "bunker_type": {"bomb_shelter", "air_raid_shelter", "\u0430ir-raid shelter", "civil_shelter"},   # one has a Cyrillic a
    "amenity": {"air_raid_shelter", "bomb_shelter"},
    "emergency": {"air_raid_shelter"},
    "building": {"air_raid_shelter", "bomb_shelters"},
}
MILITARY_KEYS = ("military",)
MILITARY_VALUE = {("landuse", "military"), ("building", "military"), ("office", "military"), ("access", "military"),
                  ("operator:type", "military")}
# Words that mark a name or an operator as military, in the languages the country's names come in (the config,
# map.labels.military_words, patterns: short words are written as whole words, \\b...\\b).
NEVER = "(?!)"   # a pattern that matches nothing, for a country with no words in a list
MILITARY_WORDS = re.compile("|".join(LABELS["military_words"]) or NEVER, re.I)
NAME_AND_OPERATOR = ("name", "name:uk", "name:en", "name:ru", "operator", "official_name", "short_name")


def shelter_group(tags):
    """'bunker_type=civil_shelter' and so on: the shelter tag an object carries, or None."""
    for key, values in SHELTER_TAGS.items():
        if tags.get(key) in values:
            return key + "=" + tags[key]
    return None


def is_military(tags, civil_shelter=False):
    """Anything military is left out of the index. The one exception: a civil shelter tag wins over
    military=bunker, because that is how most civil shelters were tagged under the old bunker scheme."""
    for key in MILITARY_KEYS:
        if tags.get(key) and not (civil_shelter and tags[key] == "bunker"):
            return True
    if any(tags.get(k) == v for k, v in MILITARY_VALUE):
        return True
    return any(MILITARY_WORDS.search(tags.get(k) or "") for k in NAME_AND_OPERATOR)


def service_kind(tags):
    """The nearest-help (or service) kind of an object, or None when it is not one or must not be indexed."""
    shelter = shelter_group(tags)
    if is_military(tags, civil_shelter=bool(shelter)):
        return None
    if shelter:
        return SHELTER
    if tags.get("drinking_water") == "no":
        return None
    kind = None
    for key in ("amenity", "shop", "healthcare", "emergency", "man_made", "natural"):
        kind = SERVICE.get((key, tags.get(key)))
        if kind:
            break
    if not kind:
        return None
    # springs and wells count only where the mapper says the water is drinkable; private fuel is not for anyone
    if tags.get("natural") == "spring" or tags.get("man_made") == "water_well":
        if tags.get("drinking_water") != "yes" and not tags.get("amenity"):
            return None
    if kind == "fuel" and tags.get("access") in ("private", "no", "customers"):
        return None
    return kind

# What marks a name as written in the other language, the one the country does not want shown (config,
# map.labels.other_language; for Ukraine it is Russian): letters the country's language does not have, street
# types spelled the other language's way, and its adjective endings.
OTHER = LABELS["other_language"]
RU_LETTERS = re.compile("[%s]" % (OTHER["letters"] + OTHER["letters"].upper()) if OTHER["letters"] else NEVER)
RU_TYPES = set(OTHER["street_types"])
RU_ENDINGS = tuple(OTHER["endings"])


def looks_russian(s, endings=False):
    if RU_LETTERS.search(s):
        return True
    w = s.lower().split()
    if w and (w[0].rstrip(".") in RU_TYPES or w[-1].rstrip(".") in RU_TYPES):
        return True
    return endings and bool(w) and w[-1].endswith(RU_ENDINGS) and cyrillic(w[-1])


def cyrillic(s):
    return any("Ѐ" <= c <= "ӿ" for c in s)


def shown_name(tags):
    """The name to show: Ukrainian, or the local name when it is not Russian, else the English name; None if none."""
    uk = tags.get("name:uk")
    if uk and not RU_LETTERS.search(uk):   # name:uk is sometimes a Russian name by mistake
        return uk
    name = tags.get("name")
    if name and not looks_russian(name, endings=True):
        return name
    en = tags.get("name:en")
    if en and not cyrillic(en):
        return en
    return None


def english_name(tags, shown):
    en = tags.get("name:en")
    if not en or cyrillic(en) or en.strip().lower() == T.translit(shown).strip().lower():
        return ""
    return en


def other_names(tags, shown, en, limit=6):
    """The other names the entry can be found under, '|' joined (never shown)."""
    seen = {T.norm(shown), T.norm(T.translit(shown)), T.norm(en)}
    out = []
    for tag in NAME_TAGS:
        if tag in ("name:uk", "name:en"):
            continue
        for v in (tags.get(tag) or "").split(";"):
            v = v.strip()
            k = T.norm(v)
            if v and k and k not in seen and T.norm(T.translit(v)) not in seen:
                seen.add(k)
                out.append(v)
    return "|".join(out[:limit])


def distance_km(a, b):
    return math.hypot((a[0] - b[0]) * 111.3 * math.cos(math.radians(a[1])), (a[1] - b[1]) * 110.6)


def centre(g):
    t, c = g["type"], g["coordinates"]
    if t == "Point":
        return c
    if t == "LineString":
        return c[len(c) // 2]
    pts = c[0] if t == "Polygon" else c[0][0] if t == "MultiPolygon" else c[0]
    return [sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)]


# ---------- outlines ----------
class Outline:
    """A polygon (or several) from a GeoJSON shape or a Geofabrik .poly file: inside test and nearness to its edge."""

    def __init__(self, rings):
        self.edges = defaultdict(list)   # latitude band (0.1 degree) -> edges crossing it
        self.all = []
        for r in rings:
            for (x1, y1), (x2, y2) in zip(r, r[1:] + r[:1]):
                self.all.append((x1, y1, x2, y2))
                for band in range(math.floor(min(y1, y2) * 10), math.floor(max(y1, y2) * 10) + 1):
                    self.edges[band].append((x1, y1, x2, y2))

    @classmethod
    def from_geojson(cls, path):
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        geoms = [f["geometry"] for f in d["features"]] if d["type"] == "FeatureCollection" else [d.get("geometry", d)]
        rings = []
        for g in geoms:
            for poly in (g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]):
                rings.append([tuple(p[:2]) for p in poly[0]])   # outer ring only
        return cls(rings)

    @classmethod
    def from_poly(cls, path):
        """Geofabrik .poly: a name line, then rings (a name line, coordinate lines, END), then END."""
        rings, ring, hole = [], None, False
        lines = open(path, encoding="utf-8").read().splitlines()[1:]
        for line in lines:
            line = line.strip()
            if ring is None:
                if line and line != "END":
                    hole, ring = line.startswith("!"), []
            elif line == "END":
                if not hole and ring:
                    rings.append(ring)
                ring = None
            elif line:
                x, y = line.split()[:2]
                ring.append((float(x), float(y)))
        return cls(rings)

    def contains(self, lon, lat):
        inside = False
        for x1, y1, x2, y2 in self.edges.get(math.floor(lat * 10), ()):
            if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
                inside = not inside
        return inside

    def near(self, lon, lat, limit_km):
        """True when inside, or within limit_km of an edge."""
        if self.contains(lon, lat):
            return True
        k = math.cos(math.radians(lat))
        for x1, y1, x2, y2 in self.all:
            dx, dy = (x2 - x1) * k, y2 - y1
            ln = dx * dx + dy * dy
            t = 0 if not ln else max(0, min(1, (((lon - x1) * k) * dx + (lat - y1) * dy) / ln))
            if math.hypot((lon - x1) * k - t * dx, (lat - y1) - t * dy) * 111 <= limit_km:
                return True
        return False


# ---------- reading the extracts ----------
def find_extracts(osm_dir, slug):
    """The files for a region: the whole country if present, else its sub-regions (newest of each)."""
    pat = re.compile(re.escape(slug) + r"(?P<sub>(?:-[a-z]+)*)-(?P<date>\d{6}|latest)\.osm\.pbf$")
    best = {}
    for name in os.listdir(osm_dir):
        m = pat.match(name)
        if m:
            key = m.group("sub")
            rank = (m.group("date") != "latest", m.group("date"))
            if key not in best or rank > best[key][0]:
                best[key] = (rank, os.path.join(osm_dir, name))
    return [best[""][1]] if "" in best else [v[1] for _, v in sorted(best.items())]


def export(work, pbf, filters, geometry):
    """osmium tags-filter + export, yielding (tags, [lon, lat]) for each object."""
    sub, out, cfg = (os.path.join(work, n) for n in ("part.osm.pbf", "part.geojsonseq", "cfg.json"))
    with open(cfg, "w") as f:
        json.dump({"attributes": {}, "linear_tags": True, "area_tags": True, "include_tags": TAGS,
                   "geometry_types": geometry}, f)
    subprocess.run(["osmium", "tags-filter", pbf, *filters, "-o", sub, "--overwrite"], check=True)
    subprocess.run(["osmium", "export", sub, "-c", cfg, "-f", "geojsonseq", "-o", out, "--overwrite"], check=True)
    with open(out, encoding="utf-8") as fh:
        for line in fh:
            line = line.lstrip("\x1e").strip()
            if not line:
                continue
            f = json.loads(line)
            yield f["properties"], centre(f["geometry"])


def fetch_poly(geofabrik, dest):
    if not os.path.exists(dest):
        print("fetching the outline of " + geofabrik, flush=True)
        urllib.request.urlretrieve("https://download.geofabrik.de/%s.poly" % geofabrik, dest + ".part")
        os.replace(dest + ".part", dest)


class Grid:
    """Nearest named point within a limit, by cells of `cell` degrees."""

    def __init__(self, pts, cell):
        self.cell, self.g = cell, defaultdict(list)
        for p in pts:
            self.g[(int(p[0] / cell), int(p[1] / cell))].append(p)

    def nearest(self, lon, lat, limit):
        best, bd = None, limit
        gx, gy = int(lon / self.cell), int(lat / self.cell)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for p in self.g.get((gx + dx, gy + dy), ()):
                    d = distance_km((lon, lat), p)
                    if d < bd:
                        best, bd = p[2], d
        return best


def group_crossings(objs, limit=GROUP_KM):
    """Group border control objects that lie within `limit` km of each other (single linkage)."""
    parent = list(range(len(objs)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    grid = defaultdict(list)
    for i, (lon, lat, _) in enumerate(objs):
        grid[(int(lon / 0.05), int(lat / 0.05))].append(i)
    for i, (lon, lat, _) in enumerate(objs):
        gx, gy = int(lon / 0.05), int(lat / 0.05)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in grid.get((gx + dx, gy + dy), ()):
                    if j > i and distance_km((lon, lat), objs[j][:2]) <= limit:
                        parent[find(j)] = find(i)
    groups = defaultdict(list)
    for i in range(len(objs)):
        groups[find(i)].append(i)
    sites = []
    for idx in groups.values():
        lon = sum(objs[i][0] for i in idx) / len(idx)
        lat = sum(objs[i][1] for i in idx) / len(idx)
        sites.append((lon, lat, [objs[i][2] for i in idx]))
    return sorted(sites, key=lambda s: (s[0], s[1]))


def at_land_border(lon, lat, outlines, full):
    """Within NEAR_BORDER_KM of the border between a full-detail country and another region's country."""
    near = {slug: o.near(lon, lat, NEAR_BORDER_KM) for slug, o in outlines.items()}
    return any(near[f["slug"]] and any(v for s, v in near.items() if s != f["slug"]) for f in full)


def crossing_object(tags):
    """A border control object that may become a crossing: nothing military (a post inside a military area is not one)."""
    return None if is_military(tags) else tags


def near_closed_border(lon, lat, closed, limit_km):
    """True when a crossing lies in, or within limit_km of, an area whose border Ukraine keeps closed. The post on
    the Ukrainian side stands a little outside the area's edge, so nearness counts."""
    return any(o.near(lon, lat, limit_km) for o in closed)


def load_closed_areas(osm_dir, work):
    """The outlines named in map.closed_border_areas, cut from the region's extract (a relation by its tag)."""
    out = []
    for area in MAP.get("closed_border_areas", []):
        files = find_extracts(osm_dir, area["region"])
        if not files:
            sys.exit("Missing the %s extract for the closed area %s" % (area["region"], area["name"]))
        sub, gj = os.path.join(work, "closed.osm.pbf"), os.path.join(work, "closed.geojson")
        subprocess.run(["osmium", "tags-filter", files[0], "r/" + area["relation"], "-o", sub, "--overwrite"], check=True)
        subprocess.run(["osmium", "export", sub, "-f", "geojson", "-o", gj, "--overwrite"], check=True)
        with open(gj, encoding="utf-8") as f:
            data = json.load(f)
        data["features"] = [x for x in data["features"] if x["geometry"]["type"] in ("Polygon", "MultiPolygon")]
        if not data["features"]:
            sys.exit("No outline for the closed area %s (%s) in %s" % (area["name"], area["relation"], files[0]))
        with open(gj, "w", encoding="utf-8") as f:
            json.dump(data, f)
        out.append((area["near_km"], Outline.from_geojson(gj)))
    return out


def build(osm_dir, poly_dir, work):
    t0 = time.time()
    regions = MAP["regions"]
    shape = Outline.from_geojson(os.path.join(KIT, MAP["shape"]))
    closed = load_closed_areas(osm_dir, work)
    full = [r for r in regions if r["detail"] == "full"]
    outlines = {}
    for r in regions:
        dest = os.path.join(poly_dir, r["slug"] + ".poly")
        fetch_poly(r["geofabrik"], dest)
        outlines[r["slug"]] = Outline.from_poly(dest)

    def log(msg):
        print("%s (%ds)" % (msg, time.time() - t0), flush=True)
    stats = Counter()
    shelters = Counter()                        # shelters found, by the tag they carry

    base, per_letter = [], defaultdict(list)    # entries: [name, kind, lon, lat, keys, en]
    place_nodes = []                            # (lon, lat, name, kind) for area names
    crossings = []                              # (lon, lat, tags)
    streets_raw = defaultdict(list)             # shown name -> [(lon, lat)]
    street_meta = {}                            # shown name -> (keys set, en)
    ru2uk = defaultdict(Counter)                # normalised Russian street name -> Ukrainian names
    raw_addresses = []                          # (street, number, lon, lat, city)

    for region in regions:
        files = find_extracts(osm_dir, region["slug"])
        if not files:
            sys.exit("Missing %s-<date>.osm.pbf in %s. Download it from https://download.geofabrik.de/%s-latest.osm.pbf"
                     % (region["slug"], osm_dir, region["geofabrik"]))
        is_full = region["detail"] == "full"
        for pbf in files:
            log("reading " + os.path.basename(pbf))
            # 1. Places. Border-strip regions give only cities and towns.
            for tags, (lon, lat) in export(work, pbf, ["n/place"], ["point"]):
                kind = PLACE.get(tags.get("place"))
                if not kind:
                    continue
                shown = shown_name(tags)
                if not shown:
                    stats["place dropped (no name, or Russian only)"] += 1
                    continue
                place_nodes.append((lon, lat, shown, kind))
                if not shape.contains(lon, lat) or (not is_full and kind not in TOWN_KINDS):
                    continue
                en = english_name(tags, shown)
                if not is_full and not en and cyrillic(shown):
                    en = tags.get("name") or ""   # a neighbour's town: English is its local name
                e = [shown, kind, round(lon, 5), round(lat, 5), other_names(tags, shown, en), en]
                (base if kind in BASE_PLACES else per_letter[T.letter_of(shown)]).append(e)
            # 2. Border control objects (grouped below).
            for tags, (lon, lat) in export(work, pbf, ["nwr/barrier=border_control", "nwr/amenity=border_control"],
                                           ["point", "polygon"]):
                if crossing_object(tags) is None:
                    stats["border object left out as military"] += 1
                    continue
                crossings.append((lon, lat, dict(tags, _full=is_full)))
            if not is_full:
                continue
            # 3. Services and landmarks.
            filters = sorted({"nwr/%s=%s" % kv for kv in list(SERVICE) + list(LANDMARK)}
                             | {"nwr/%s=%s" % (k, v) for k, vs in SHELTER_TAGS.items() for v in vs})
            for tags, (lon, lat) in export(work, pbf, filters, ["point", "polygon"]):
                if not shape.contains(lon, lat):
                    continue
                kind = service_kind(tags)
                if kind is None and is_military(tags, civil_shelter=bool(shelter_group(tags))):
                    stats["left out as military"] += 1
                    continue   # nothing military is indexed, not even as a landmark
                shown = shown_name(tags) or ""
                en = english_name(tags, shown) if shown else ""
                keys = other_names(tags, shown, en) if shown else ""
                if kind:   # a service without a name is shown by its kind
                    if kind == SHELTER:
                        shelters[shelter_group(tags)] += 1
                    base.append([shown, kind, round(lon, 5), round(lat, 5), keys, en])
                    continue
                kind = next((LANDMARK[(k, v)] for k, v in tags.items() if (k, v) in LANDMARK), None)
                if kind and shown:
                    per_letter[T.letter_of(shown)].append([shown, kind, round(lon, 5), round(lat, 5), keys, en])
            log("services and landmarks")
            # 4. Streets, collected by name. The Russian form of each name is remembered for addresses.
            for tags, (lon, lat) in export(work, pbf, ["w/highway=" + ",".join(sorted(ROADS))], ["linestring"]):
                if tags.get("highway") not in ROADS or not (tags.get("name") or tags.get("name:uk")):
                    continue
                if not shape.contains(lon, lat):
                    continue
                shown = shown_name(tags)
                if not shown:
                    stats["street dropped (Russian name only)"] += 1
                    continue
                streets_raw[shown].append((lon, lat))
                keys, en = street_meta.setdefault(shown, (set(), ""))
                for v in other_names(tags, shown, english_name(tags, shown)).split("|"):
                    if v and len(keys) < 6:
                        keys.add(v)
                if not en:
                    street_meta[shown] = (keys, english_name(tags, shown))
                ru = [tags.get("name:ru")] + ([tags.get("name")] if looks_russian(tags.get("name") or "", endings=True) else [])
                for r in ru:
                    if r and r != shown:
                        ru2uk[T.norm(T.strip_type(r))][shown] += 1
            log("streets")
            # 5. Addresses.
            for tags, (lon, lat) in export(work, pbf, ["nwr/addr:housenumber"], ["point", "polygon"]):
                street = tags.get("addr:street") or tags.get("addr:place")
                num = tags.get("addr:housenumber")
                if street and num and shape.contains(lon, lat):
                    raw_addresses.append((street, num, lon, lat, tags.get("addr:city") or ""))
            log("addresses read: %d" % len(raw_addresses))

    hoods = Grid([p for p in place_nodes if p[3] in HOOD_KINDS], 0.05)
    towns = Grid([p for p in place_nodes if p[3] in TOWN_KINDS], 0.25)

    def area(name, lon, lat):
        """"Neighbourhood, Town": the nearest neighbourhood within 3 km and the nearest town within 15 km."""
        parts = []
        for p in (hoods.nearest(lon, lat, 3.0), towns.nearest(lon, lat, 15.0)):
            if p and p != name and p not in parts:
                parts.append(p)
        return ", ".join(parts)

    # Border crossings: one entry per site, only where a full-detail region meets another region.
    sites, kept = group_crossings(crossings), 0
    for lon, lat, objs in sites:
        if not shape.contains(lon, lat) or not at_land_border(lon, lat, outlines, full):
            stats["crossing site dropped (not at the border to a neighbour)"] += 1
            continue
        if any(near_closed_border(lon, lat, [o], km_) for km_, o in closed):
            stats["crossing site dropped (on a closed stretch: Transnistria)"] += 1
            continue
        names, ens, others = Counter(), Counter(), Counter()
        # A site on the border has objects on both sides (Shehyni and Medyka, and the Ukraine extract holds both).
        # The Ukrainian side is the one mapped with a Cyrillic `name`: it names the site, and the other side's
        # names stay as search keys.
        ours = [t for t in objs if cyrillic(t.get("name", ""))] or [t for t in objs if t["_full"]] or objs
        for tags in objs:
            s = shown_name(tags)
            if s and tags in ours:
                names[s] += 1
            if tags.get("name:en") and not cyrillic(tags["name:en"]) and tags in ours:
                ens[tags["name:en"]] += 1
            for v in other_names(tags, s or "", "").split("|") + ([s] if s else []):
                if v:
                    others[v] += 1
        near_place = towns.nearest(lon, lat, 30.0) or hoods.nearest(lon, lat, 30.0) or ""
        if names:
            shown = names.most_common(1)[0][0]
            en = ens.most_common(1)[0][0] if ens else ""
            if en.strip().lower() == T.translit(shown).strip().lower():
                en = ""
        else:   # unnamed: named after the nearest place
            shown, en = UNNAMED_CROSSING["name"] + near_place, UNNAMED_CROSSING["en"] + T.translit(near_place)
        keys = "|".join(v for v, _ in others.most_common(6) if T.norm(v) != T.norm(shown))
        base.append([shown, CROSSING, round(lon, 5), round(lat, 5), keys, en])
        kept += 1
    log("border crossings: %d sites, %d kept" % (len(sites), kept))

    # Streets: one entry per name per 1.5 km cell.
    for name, pts in streets_raw.items():
        keys, en = street_meta[name]
        grid = {}
        for p in pts:
            grid.setdefault((round(p[0] / 0.025), round(p[1] / 0.0135)), []).append(p)
        for cell in grid.values():
            cx, cy = sum(p[0] for p in cell) / len(cell), sum(p[1] for p in cell) / len(cell)
            mid = min(cell, key=lambda p: distance_km(p, (cx, cy)))
            per_letter[T.letter_of(name)].append([name, STREET, round(mid[0], 5), round(mid[1], 5), "|".join(sorted(keys)), en])
    log("street entries")

    # Addresses by street name. A Russian street name becomes the Ukrainian name of the street with that Russian
    # name, or the address is left out. Without addr:city the area name comes from the nearest places.
    resolve = {k: c.most_common(1)[0][0] for k, c in ru2uk.items()}
    addresses = defaultdict(lambda: defaultdict(dict))   # letter -> street -> key -> [num, lon, lat, city]
    cell_area, count = {}, 0
    for street, num, lon, lat, city in raw_addresses:
        if looks_russian(street):
            street = resolve.get(T.norm(T.strip_type(street)))
            if not street:
                stats["address dropped (Russian street name, no Ukrainian name known)"] += 1
                continue
        if city and looks_russian(city, endings=True):
            city = ""
        if not city:
            ck = (round(lon / 0.01), round(lat / 0.01))   # worked out once per 1 km cell
            if ck not in cell_area:
                cell_area[ck] = area("", ck[0] * 0.01, ck[1] * 0.01)
            city = cell_area[ck]
        for n in re.split(r"[;,]", str(num)):
            n = n.strip()
            if n:
                key = (re.sub(r"[\s-]+", "", n.upper()), city, round(lon, 3), round(lat, 3))
                bucket = addresses[T.letter_of(street)][street]
                if key not in bucket:
                    bucket[key] = [n, round(lon, 5), round(lat, 5), city]
                    count += 1
    log("addresses: %d" % count)

    def pack(items):
        seen, out = set(), []
        for name, kind, lon, lat, keys, en in items:
            fine = 2 if kind == STREET else 3
            key = (name, kind, round(lon, fine), round(lat, fine))
            if key in seen or (name and not any(ch.isalpha() for ch in name)):
                continue
            seen.add(key)
            out.append((name, kind, lon, lat, "" if kind == "city" else area(name, lon, lat), keys, en))
        out.sort(key=lambda e: (e[1], e[0], e[2], e[3]))
        kinds = sorted({e[1] for e in out})
        areas = sorted({e[4] for e in out})
        ki, ai = {k: i for i, k in enumerate(kinds)}, {a: i for i, a in enumerate(areas)}
        rows = []
        for name, kind, lon, lat, ar, keys, en in out:
            row = [name, ki[kind], lon, lat, ai[ar], keys, en]
            while row[-1] == "":
                row.pop()
            rows.append(row)
        return {"types": kinds, "areas": areas, "items": rows}

    files = {"places.json": pack(base)}
    kinds = Counter(files["places.json"]["types"][row[1]] for row in files["places.json"]["items"])
    for kind in sorted(set(SERVICE.values()) | {SHELTER, CROSSING}):
        print("  nearest help, %s: %d" % (kind, kinds[kind]))
    for tag, n in sorted(shelters.items()):
        print("  shelter objects by tag, %s: %d" % (tag, n))
    for ch in sorted(set(per_letter) | set(addresses)):
        obj = pack(per_letter.get(ch, []))
        cities = sorted({a[3] for st in addresses[ch].values() for a in st.values()})
        ci = {c: i for i, c in enumerate(cities)}
        obj["cities"] = cities
        obj["addresses"] = {st: sorted(([a[0], a[1], a[2], ci[a[3]]] for a in v.values()), key=lambda a: (len(a[0]), a[0]))
                            for st, v in sorted(addresses[ch].items())}
        files["letters/%s.json" % ch] = obj
    for what, n in sorted(stats.items()):
        print("  %s: %d" % (what, n))
    return files


def write(files, out, release):
    sizes = {}
    os.makedirs(os.path.join(out, "letters"), exist_ok=True)
    for old in os.listdir(os.path.join(out, "letters")):
        os.remove(os.path.join(out, "letters", old))   # letters from an earlier build must not linger
    for name, obj in files.items():
        data = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode()
        gz = gzip.compress(data, 9, mtime=0)
        with open(os.path.join(out, name + ".gz"), "wb") as f:
            f.write(gz)
        sizes[name] = (len(data), len(gz))
    if release:
        os.makedirs(release, exist_ok=True)
        path = os.path.join(release, "map-search.tar.gz")
        with tarfile.open(path + ".part", "w:gz", format=tarfile.GNU_FORMAT) as tar:
            for name in sorted(files):
                with open(os.path.join(out, name + ".gz"), "rb") as f:
                    data = f.read()
                info = tarfile.TarInfo(name + ".gz")
                info.size, info.mtime, info.mode = len(data), 0, 0o644
                tar.addfile(info, io.BytesIO(data))
        os.replace(path + ".part", path)
        print("%s: %.1f MB" % (path, os.path.getsize(path) / 1e6))
    raw, gz = sum(s[0] for s in sizes.values()), sum(s[1] for s in sizes.values())
    big = max(sizes.items(), key=lambda kv: kv[1][1])
    print("%d files, %.1f MB raw, %.1f MB gzipped; places.json %.1f MB raw / %.1f MB gz; largest %s %.1f MB raw / %.1f MB gz"
          % (len(sizes), raw / 1e6, gz / 1e6, sizes["places.json"][0] / 1e6, sizes["places.json"][1] / 1e6,
             big[0], big[1][0] / 1e6, big[1][1] / 1e6))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--osm-dir", default=os.environ.get("EK_OSM_DIR") or os.path.join(KIT, "maps", "osm"))
    ap.add_argument("--poly-dir", help="where <slug>.poly outlines are kept (default: next to the extracts)")
    ap.add_argument("--out", default=os.path.join(KIT, "web", "map", "data"))
    ap.add_argument("--release", help="also write map-search.tar.gz into this folder")
    a = ap.parse_args()
    if not os.path.isdir(a.osm_dir):
        sys.exit("Missing %s. Put the Geofabrik extracts there (download.geofabrik.de)." % a.osm_dir)
    poly = a.poly_dir or a.osm_dir
    os.makedirs(poly, exist_ok=True)
    work = tempfile.mkdtemp(prefix="kit-map-")
    try:
        write(build(a.osm_dir, poly, work), a.out, a.release)
    finally:
        subprocess.run(["rm", "-rf", work])


if __name__ == "__main__":
    main()
