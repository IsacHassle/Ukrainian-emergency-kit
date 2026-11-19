"""The map search's matching rules (ticket 09): transliteration, normalising, street types, query parsing and
ranking, run in node against the same table the Python builder is checked with (tests/kit/search-cases.json)."""
import json
import os
import subprocess
import sys
import unittest

from servedkit import REPO, ServedKit
from test_served_kit_browser import REQUIRED, find_chrome, why_skip

sys.path.insert(0, os.path.join(REPO, "scripts"))


class SearchRulesTest(unittest.TestCase):
    def test_the_matching_rules(self):
        run = subprocess.run(["node", os.path.join(REPO, "tests", "browser", "search-rules.js")],
                             capture_output=True, text=True, cwd=REPO, timeout=60)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


class BuilderRulesTest(unittest.TestCase):
    """The build script uses a Python copy of the rules. It must agree with the page on every case, or a street
    is stored in one letter file and looked for in another."""

    def test_the_python_copy_agrees_with_the_table(self):
        import kit_translit as t
        with open(os.path.join(REPO, "tests", "kit", "search-cases.json"), encoding="utf-8") as f:
            cases = json.load(f)
        for name, fn in (("translit", t.translit), ("translit_ru", t.translit_ru), ("norm", t.norm),
                         ("strip_type", t.strip_type), ("letter", t.letter_of)):
            for given, want in cases[name]:
                self.assertEqual(fn(given), want, name + " " + given)


def load_builder():
    import importlib.util
    spec = importlib.util.spec_from_file_location("build_map_index", os.path.join(REPO, "scripts", "build-map-index.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class BuilderTest(unittest.TestCase):
    """What the build decides, without running osmium: which name is shown, which are only keys, which crossings
    count, how the release file is laid out."""

    @classmethod
    def setUpClass(cls):
        cls.b = load_builder()

    def test_a_russian_name_is_never_the_shown_name(self):
        b = self.b
        self.assertEqual(b.shown_name({"name": "Евпатория", "name:uk": "Євпаторія", "name:ru": "Евпатория"}), "Євпаторія")
        self.assertEqual(b.shown_name({"name": "Київ", "name:ru": "Киев"}), "Київ")
        self.assertEqual(b.shown_name({"name": "улица Ленина"}), None)
        self.assertEqual(b.shown_name({"name": "улица Ленина", "name:en": "Lenin Street"}), "Lenin Street")
        self.assertEqual(b.shown_name({"name": "Первомайская"}), None)
        self.assertEqual(b.shown_name({"name": "Bălți", "name:ru": "Бельцы"}), "Bălți")

    def test_russian_and_older_names_are_keys_not_shown(self):
        b = self.b
        tags = {"name": "Київ", "name:uk": "Київ", "name:en": "Kyiv", "name:ru": "Киев", "old_name": "Kiev"}
        self.assertEqual(b.english_name(tags, "Київ"), "")   # Kyiv is what the page transliterates anyway
        self.assertEqual(b.other_names(tags, "Київ", ""), "Киев|Kiev")
        tags["name:en"] = "Kiev City"
        self.assertEqual(b.english_name(tags, "Київ"), "Kiev City")

    def test_regions_are_found_whole_or_as_sub_regions(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            for n in ("ukraine-261117.osm.pbf", "ukraine-261118.osm.pbf", "poland-podkarpackie-261118.osm.pbf",
                      "poland-lubelskie-261118.osm.pbf", "moldova-latest.osm.pbf", "moldova-261101.osm.pbf"):
                open(os.path.join(d, n), "w").close()
            names = lambda slug: [os.path.basename(f) for f in self.b.find_extracts(d, slug)]
            self.assertEqual(names("ukraine"), ["ukraine-261118.osm.pbf"])
            self.assertEqual(names("poland"), ["poland-lubelskie-261118.osm.pbf", "poland-podkarpackie-261118.osm.pbf"])
            self.assertEqual(names("moldova"), ["moldova-261101.osm.pbf"])   # a dated file beats "latest"
            self.assertEqual(names("romania"), [])

    def test_border_control_objects_become_one_site_per_crossing(self):
        objs = [(22.9526, 49.7995, {}), (22.9527, 49.7996, {}), (22.9508, 49.8002, {}), (24.0, 48.0, {})]
        sites = self.b.group_crossings(objs)
        self.assertEqual([len(t) for _, _, t in sites], [3, 1])

    def test_a_crossing_counts_only_at_the_border_to_a_neighbour(self):
        square = lambda x, y, w: self.b.Outline([[(x, y), (x + w, y), (x + w, y + w), (x, y + w)]])
        outlines = {"ukraine": square(0, 0, 2), "poland": square(2, 0, 2), "belarus_like": square(0, 2, 2)}
        full = [{"slug": "ukraine"}]
        near_pl = self.b.at_land_border(1.99, 1.0, {k: outlines[k] for k in ("ukraine", "poland")}, full)
        self.assertTrue(near_pl)                                                        # at the Polish border
        self.assertFalse(self.b.at_land_border(1.0, 1.0, {k: outlines[k] for k in ("ukraine", "poland")}, full))   # inland
        # the other side of Ukraine is not a region of the country config: not counted
        self.assertFalse(self.b.at_land_border(1.0, 1.99, {k: outlines[k] for k in ("ukraine", "poland")}, full))

    def test_the_release_file_holds_the_gzipped_files_the_installer_expects(self):
        import gzip
        import tarfile
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            files = {"places.json": {"types": ["city"], "areas": [""], "items": [["Київ", 0, 30.5, 50.4, 0]]},
                     "letters/k.json": {"types": [], "areas": [], "items": [], "cities": [], "addresses": {}}}
            self.b.write(files, os.path.join(d, "data"), os.path.join(d, "rel"))
            with tarfile.open(os.path.join(d, "rel", "map-search.tar.gz")) as tar:
                self.assertEqual(tar.getnames(), ["letters/k.json.gz", "places.json.gz"])
                tar.extractall(os.path.join(d, "kit"))
            data = json.load(gzip.open(os.path.join(d, "kit", "places.json.gz")))
            self.assertEqual(data["items"][0][0], "Київ")   # get-maps.sh looks for places.json.gz after unpacking
            self.assertEqual(sorted(os.listdir(os.path.join(d, "data", "letters"))), ["k.json.gz"])


class ConfigKindsTest(unittest.TestCase):
    def test_every_kind_the_build_can_write_has_a_name_in_both_languages(self):
        with open(os.path.join(REPO, "config", "country.json"), encoding="utf-8") as f:
            labels = json.load(f)["map"]["labels"]
        kinds = set(labels["place"].values()) | set(labels["service"].values()) | set(labels["landmark"].values())
        kinds |= {labels["street"], labels["address"], labels["border_crossing"]}
        for lang in ("uk", "en"):
            with open(os.path.join(REPO, "web", "lang", lang + ".json"), encoding="utf-8") as f:
                texts = json.load(f)
            for kind in kinds:
                self.assertIn("map.type." + kind, texts, lang + " " + kind)


@unittest.skipIf(why_skip() and not REQUIRED, why_skip())
class SearchInTheBrowserTest(unittest.TestCase):
    def test_searching_the_map_page(self):
        kit = ServedKit(tiles=True)
        try:
            kit.start()
            env = dict(os.environ, EK_TEST_URL=kit.url, EK_CHROME=find_chrome())
            run = subprocess.run(["node", os.path.join(REPO, "tests", "browser", "search.js")], env=env, cwd=REPO,
                                 capture_output=True, text=True, timeout=240)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("ok - no result shows a Russian name", run.stdout)
        finally:
            kit.stop()


if __name__ == "__main__":
    unittest.main()
