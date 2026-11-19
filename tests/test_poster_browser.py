"""The Keeper's poster in headless Chrome: both QR codes read back (a decoder, jsQR, stands in for the phone's
camera), the password goes nowhere, and the poster prints on one A4 page. Skipped like the other browser tests
when Chrome or the test tools are missing. Set EK_POSTER_SAMPLE=<file.pdf> to also save a sample poster."""
import os
import subprocess
import unittest

from servedkit import REPO, ServedKit
from test_served_kit_browser import REQUIRED, find_chrome, why_skip


@unittest.skipIf(why_skip() and not REQUIRED, why_skip())
class PosterBrowserTest(unittest.TestCase):
    def test_the_poster_in_chrome(self):
        self.assertIsNone(why_skip())
        kit = ServedKit()
        try:
            kit.start()
            env = dict(os.environ, EK_TEST_URL=kit.url, EK_CHROME=find_chrome())
            run = subprocess.run(["node", os.path.join(REPO, "tests", "browser", "poster.js")], env=env, cwd=REPO,
                                 capture_output=True, text=True, timeout=120)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertEqual(run.stdout.count("ok - "), 7, run.stdout)
        finally:
            kit.stop()


if __name__ == "__main__":
    unittest.main()
