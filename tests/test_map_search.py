"""The map search's matching rules (ticket 09): transliteration, normalising, street types, query parsing and
ranking, run in node against the same table the Python builder is checked with (tests/kit/search-cases.json)."""
import os
import subprocess
import unittest

from servedkit import REPO


class SearchRulesTest(unittest.TestCase):
    def test_the_matching_rules(self):
        run = subprocess.run(["node", os.path.join(REPO, "tests", "browser", "search-rules.js")],
                             capture_output=True, text=True, cwd=REPO, timeout=60)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


if __name__ == "__main__":
    unittest.main()
