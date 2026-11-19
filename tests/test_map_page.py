"""The map page in headless Chrome, in both languages (ticket 08). Search, nearest and Lent positions are other
tickets: their logic is untouched here, only the texts moved into the language files."""
import os
import subprocess
import unittest

from servedkit import REPO, ServedKit
from test_served_kit_browser import REQUIRED, find_chrome, why_skip


@unittest.skipIf(why_skip() and not REQUIRED, why_skip())
class MapPageTest(unittest.TestCase):
    def test_the_map_page_in_both_languages(self):
        self.assertIsNone(why_skip())
        with_map, without = ServedKit(tiles=True), ServedKit()
        try:
            with_map.start()
            without.start()
            env = dict(os.environ, EK_TEST_URL=with_map.url, EK_TEST_URL_NOMAP=without.url, EK_CHROME=find_chrome())
            run = subprocess.run(["node", os.path.join(REPO, "tests", "browser", "map.js")], env=env, cwd=REPO,
                                 capture_output=True, text=True, timeout=240)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertGreaterEqual(run.stdout.count("ok - "), 4, run.stdout)
        finally:
            with_map.stop()
            without.stop()


if __name__ == "__main__":
    unittest.main()
