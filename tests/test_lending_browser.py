"""The phone page and the lending switch in headless Chrome: the Kit Mac sees and uses the switch, a Visitor
device does not and is told why a Lent position is refused (both languages). Skipped like the other browser
tests when Chrome or the test tools are missing."""
import os
import subprocess
import unittest

from servedkit import REPO, ServedKit
from test_served_kit_browser import REQUIRED, find_chrome, why_skip


def run_page(kit, role):
    env = dict(os.environ, EK_TEST_URL=kit.url, EK_CHROME=find_chrome(), EK_TEST_ROLE=role)
    return subprocess.run(["node", os.path.join(REPO, "tests", "browser", "lending.js")], env=env, cwd=REPO,
                          capture_output=True, text=True, timeout=120)


@unittest.skipIf(why_skip() and not REQUIRED, why_skip())
class LendingBrowserTest(unittest.TestCase):
    def test_the_kit_mac_page(self):
        self.assertIsNone(why_skip())
        kit = ServedKit()
        try:
            kit.start()
            run = run_page(kit, "mac")
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertEqual(run.stdout.count("ok - "), 4, run.stdout)
        finally:
            kit.stop()

    def test_a_visitor_device_page(self):
        self.assertIsNone(why_skip())
        kit = ServedKit(peer="192.168.1.50")
        try:
            kit.start()
            run = run_page(kit, "visitor")
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertEqual(run.stdout.count("ok - "), 4, run.stdout)
        finally:
            kit.stop()


if __name__ == "__main__":
    unittest.main()
