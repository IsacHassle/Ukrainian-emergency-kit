"""The map search's matching rules (ticket 09): transliteration, normalising, street types, query parsing and
ranking, run in node against the same table the Python builder is checked with (tests/kit/search-cases.json)."""
import json
import os
import subprocess
import sys
import unittest

from servedkit import REPO

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


if __name__ == "__main__":
    unittest.main()
