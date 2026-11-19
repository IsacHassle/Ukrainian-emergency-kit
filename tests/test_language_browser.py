"""The УКР | ENG switch in headless Chrome (Seam 1): both languages, surviving a reload, and a browser whose
storage throws. Skipped the same way as the other browser tests when Chrome or the test tools are missing."""
import os
import subprocess
import unittest

from servedkit import REPO, ServedKit
from test_served_kit_browser import REQUIRED, find_chrome, why_skip


@unittest.skipIf(why_skip() and not REQUIRED, why_skip())
class SwitchTest(unittest.TestCase):
    def test_the_switch_in_chrome(self):
        self.assertIsNone(why_skip())
        kit = ServedKit()
        try:
            kit.start()
            env = dict(os.environ, EK_TEST_URL=kit.url, EK_CHROME=find_chrome())
            run = subprocess.run(["node", os.path.join(REPO, "tests", "browser", "language.js")], env=env, cwd=REPO,
                                 capture_output=True, text=True, timeout=120)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertEqual(run.stdout.count("ok - "), 9, run.stdout)
        finally:
            kit.stop()


if __name__ == "__main__":
    unittest.main()
