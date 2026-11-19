"""Seam 1 in headless Chrome: the start page and the AI page, driven as a Visitor device drives them.

Needs Chrome (or Chromium) and the test tools (`npm ci` in the repo folder). Without them the tests are
skipped with a message, so the harness still runs on a Mac that has neither. Set EK_CHROME to a Chrome
program to use a specific one. EK_REQUIRE_BROWSER=1 (CI) turns the skip into a failure.
"""
import os
import shutil
import subprocess
import unittest

from servedkit import REPO, ServedKit
from standins import ANSWER

CANDIDATES = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/Applications/Chromium.app/Contents/MacOS/Chromium",
              "google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]


def find_chrome():
    for c in [os.environ.get("EK_CHROME")] + CANDIDATES:
        if c and (os.path.isfile(c) or shutil.which(c)):
            return shutil.which(c) or c
    return None


def why_skip():
    if not find_chrome():
        return "headless browser tests skipped: Chrome not found (install Chrome or set EK_CHROME)"
    if not shutil.which("node"):
        return "headless browser tests skipped: Node.js not found"
    if not os.path.isdir(os.path.join(REPO, "node_modules", "puppeteer-core")):
        return "headless browser tests skipped: run `npm ci` in the repo folder first"
    return None


REQUIRED = bool(os.environ.get("EK_REQUIRE_BROWSER"))   # set in CI: a missing Chrome is a failure there


@unittest.skipIf(why_skip() and not REQUIRED, why_skip())
class BrowserTest(unittest.TestCase):
    def test_start_page_and_ai_page_work_in_chrome(self):
        self.assertIsNone(why_skip())
        kit = ServedKit()
        try:
            kit.start()
            env = dict(os.environ, EK_TEST_URL=kit.url, EK_CHROME=find_chrome(), EK_TEST_ANSWER=ANSWER)
            run = subprocess.run(["node", os.path.join(REPO, "tests", "browser", "run.js")], env=env, cwd=REPO,
                                 capture_output=True, text=True, timeout=120)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertEqual(run.stdout.count("ok - "), 3, run.stdout)
        finally:
            kit.stop()


    def test_pages_follow_another_countrys_config_in_chrome(self):
        import json
        from test_country_config import testland
        self.assertIsNone(why_skip())
        kit = ServedKit(country=testland)
        try:
            kit.start()
            expect = {"kit": "Testlådan", "models": ["alpha", "alpha-small"], "number": "999",
                      "checklist": "Ett testföremål", "shortcut": "Testby"}
            env = dict(os.environ, EK_TEST_URL=kit.url, EK_CHROME=find_chrome(), EK_TEST_ANSWER=ANSWER,
                       EK_TEST_EXPECT=json.dumps(expect))
            run = subprocess.run(["node", os.path.join(REPO, "tests", "browser", "run.js")], env=env, cwd=REPO,
                                 capture_output=True, text=True, timeout=120)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertEqual(run.stdout.count("ok - "), 8, run.stdout)
            # the AI page's quick mode asked the stand-in for the config's model, nothing else
            self.assertEqual({r["model"] for r in kit.ai.chat_requests}, {"alpha"})
        finally:
            kit.stop()


if __name__ == "__main__":
    unittest.main()
