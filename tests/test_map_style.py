"""The basemap style (web/map/style.json): Ukraine's recognised borders, no military areas, labels in one language.

Checked as data, because the style is data; how it looks on the real map is checked by eye on the development
Mac (ticket 08's screenshots), and the language switch is driven in headless Chrome by test_map_page.py.
"""
import json
import os
import unittest

from servedkit import REPO

with open(os.path.join(REPO, "web", "map", "style.json"), encoding="utf-8") as f:
    STYLE = json.load(f)
LAYERS = {l["id"]: l for l in STYLE["layers"]}
UK = ["coalesce", ["get", "name:uk"], ["get", "name"]]   # the Ukrainian page: Ukrainian name, else the local one


class StyleTest(unittest.TestCase):
    def test_two_sources_the_world_overview_and_the_country_area(self):
        self.assertEqual(sorted(STYLE["sources"]), ["area", "world"])
        self.assertNotIn("sweden", json.dumps(STYLE).lower())
        self.assertEqual({l["source"] for l in STYLE["layers"] if "source" in l}, {"area", "world"})

    def test_crimea_is_drawn_as_ukraine(self):
        # The Russian-claimed "state border" across Crimea is flagged disputed in the tiles. It must not be
        # drawn as a country border: it is restyled as an ordinary oblast line.
        for src in ("world", "area"):
            self.assertEqual(LAYERS["boundaries_country-" + src]["filter"],
                             ["all", ["<=", "kind_detail", 2], ["!=", "disputed", True]])
            self.assertEqual(LAYERS["boundaries-" + src]["filter"],
                             ["any", [">", "kind_detail", 2], ["all", ["<=", "kind_detail", 2], ["==", "disputed", True]]])

    def test_nothing_military_is_drawn(self):
        text = json.dumps(STYLE)
        self.assertNotIn("military", text)
        self.assertNotIn("naval_base", text)

    def test_every_name_label_is_one_language_with_the_local_name_as_fallback(self):
        text = json.dumps(STYLE)
        self.assertNotIn("name:sv", text)
        named = [l for l in STYLE["layers"] if "name" in json.dumps(l.get("layout", {}).get("text-field", ""))]
        self.assertGreater(len(named), 20)
        for l in named:
            field = l["layout"]["text-field"]
            if l["id"].startswith("places_region"):   # low zooms show the region's short code
                self.assertEqual(field, ["step", ["zoom"], ["coalesce", ["get", "ref:en"], ["get", "ref"]], 6, UK], l["id"])
            else:
                self.assertEqual(field, UK, l["id"])
        ids = {l["id"] for l in named}
        for kind in ("places_country", "places_locality", "roads_labels_minor", "roads_labels_major", "pois",
                     "water_label_ocean", "water_label_lakes", "earth_label_islands", "water_waterway_label"):
            self.assertIn(kind + "-area", ids)
        # house numbers and road shields are not names
        self.assertEqual(LAYERS["address_label-area"]["layout"]["text-field"], ["get", "addr_housenumber"])
        self.assertEqual(LAYERS["roads_shields-area"]["layout"]["text-field"], ["get", "shield_text"])


if __name__ == "__main__":
    unittest.main()
