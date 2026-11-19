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
