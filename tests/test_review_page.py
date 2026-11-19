"""The review page (/review/): every Ukrainian text beside its English one, for the native-speaker review.

Seam 1: driven over HTTP and in headless Chrome. The page is not linked from any menu, and it must keep
listing every key as later tickets add more (the tests read the language files and the country config as they
are, never a fixed list).
"""
import glob
import json
import os
import subprocess
import unittest
import urllib.request

from servedkit import REPO, ServedKit
from test_served_kit_browser import REQUIRED, find_chrome, why_skip


def texts_in_config(node, path=""):
    """The path of every {uk, en} pair in the country config."""
    if isinstance(node, dict):
        if isinstance(node.get("uk"), str) and isinstance(node.get("en"), str):
            yield path
            return
        for k, v in node.items():
            yield from texts_in_config(v, path + "/" + k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from texts_in_config(v, "%s/%d" % (path, i))


def get(kit, path):
    with urllib.request.urlopen(kit.url + path, timeout=10) as r:
        return r.read().decode("utf-8")


class ReviewPageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kit = ServedKit()
        cls.kit.start()
        cls.data = json.loads(get(cls.kit, "/review/data.json"))
        cls.page = get(cls.kit, "/review/")

    @classmethod
    def tearDownClass(cls):
        cls.kit.stop()

    def test_every_language_file_key_is_listed_with_both_texts(self):
        files = {}
        for code in ("uk", "en"):
            with open(os.path.join(REPO, "web", "lang", code + ".json"), encoding="utf-8") as f:
                files[code] = json.load(f)
        listed = {row["key"]: row for row in self.data["keys"]}
        self.assertEqual(set(listed), set(files["uk"]))
        for key in files["uk"]:
            self.assertEqual(listed[key]["uk"], files["uk"][key], key)
            self.assertEqual(listed[key]["en"], files["en"][key], key)

    def test_every_config_text_is_listed_with_both_texts(self):
        with open(os.path.join(REPO, "config", "country.json"), encoding="utf-8") as f:
            paths = set(texts_in_config(json.load(f)))
        listed = {row["path"] for row in self.data["config"]}
        self.assertEqual(listed, paths)
        self.assertIn("/kit_name", listed)
        self.assertTrue(any(p.startswith("/emergency_topics/") for p in listed))
        self.assertTrue(all(row["uk"] and row["en"] for row in self.data["config"]))

    def test_the_page_is_english_only_and_loads_the_list(self):
        self.assertIn('<html lang="en"', self.page)
        self.assertIn("/review/data.json", self.page)
        self.assertNotIn("/lib/lang.js", self.page)

    def test_the_page_is_not_linked_from_any_page_or_menu(self):
        pages = [p for p in glob.glob(os.path.join(REPO, "web", "**", "*.html"), recursive=True)
                 if os.sep + "review" + os.sep not in p]
        pages.append(os.path.join(REPO, "scripts", "build-home.py"))
        for path in pages:
            with open(path, encoding="utf-8") as f:
                self.assertNotIn("review/", f.read(), path)
        self.assertNotIn("review", get(self.kit, "/").lower())

    @unittest.skipIf(why_skip() and not REQUIRED, why_skip())
    def test_the_page_shows_every_key_and_config_text_in_chrome(self):
        env = dict(os.environ, EK_TEST_URL=self.kit.url, EK_CHROME=find_chrome(),
                   EK_TEST_KEYS=json.dumps([r["key"] for r in self.data["keys"]]),
                   EK_TEST_CONFIG=str(len(self.data["config"])))
        run = subprocess.run(["node", os.path.join(REPO, "tests", "browser", "review.js")], env=env, cwd=REPO,
                             capture_output=True, text=True, timeout=120)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual(run.stdout.count("ok - "), 3, run.stdout)


if __name__ == "__main__":
    unittest.main()
