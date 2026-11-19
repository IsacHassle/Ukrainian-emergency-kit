"""The language layer: the key check CI runs (Seam 3) and the texts the served kit gives (Seam 1).

Pages mark text by key; web/lang/uk.json and web/lang/en.json hold the texts. The check fails when a key is in
one file only, or a page uses a key that is in neither, or a text's {placeholders} differ between languages.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.request

from servedkit import REPO, ServedKit

CHECK = os.path.join(REPO, "scripts", "check-language.py")


def run_check(root):
    run = subprocess.run([sys.executable, CHECK, root], capture_output=True, text=True)
    return run.returncode, run.stdout + run.stderr


class KeyCheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ek-lang-")
        shutil.copytree(os.path.join(REPO, "web", "lang"), os.path.join(self.tmp, "web", "lang"))
        os.makedirs(os.path.join(self.tmp, "scripts"))
        shutil.copy(os.path.join(REPO, "scripts", "build-home.py"), os.path.join(self.tmp, "scripts"))
        os.makedirs(os.path.join(self.tmp, "web", "page"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def texts(self, lang):
        path = os.path.join(self.tmp, "web", "lang", lang + ".json")
        with open(path, encoding="utf-8") as f:
            return path, json.load(f)

    def save(self, path, data):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)

    def test_the_real_language_files_and_pages_pass(self):
        code, out = run_check(REPO)
        self.assertEqual(code, 0, out)

    def test_a_key_in_one_language_only_fails_and_is_named(self):
        path, en = self.texts("en")
        del en["home.ai.title"]
        self.save(path, en)
        code, out = run_check(self.tmp)
        self.assertNotEqual(code, 0)
        self.assertIn("home.ai.title", out)

    def test_keys_out_of_alphabetical_order_fail(self):
        # Sorted keys put each page's new texts in their own place in the file, so tickets built side
        # by side merge without touching the same lines.
        path, en = self.texts("en")
        keys = sorted(en)
        self.save(path, {k: en[k] for k in [keys[-1]] + keys[:-1]})
        code, out = run_check(self.tmp)
        self.assertNotEqual(code, 0)
        self.assertIn("alphabetical", out)

    def test_a_page_using_a_key_that_exists_in_neither_fails(self):
        with open(os.path.join(self.tmp, "web", "page", "index.html"), "w", encoding="utf-8") as f:
            f.write('<p data-t="nowhere.at.all"></p><script>KIT.t("also.missing")</script>')
        code, out = run_check(self.tmp)
        self.assertNotEqual(code, 0)
        self.assertIn("nowhere.at.all", out)
        self.assertIn("also.missing", out)

    def test_a_placeholder_missing_in_one_language_fails(self):
        path, en = self.texts("en")
        en["home.meta.libraries"] = "libraries"   # the Ukrainian text has {count}
        self.save(path, en)
        code, out = run_check(self.tmp)
        self.assertNotEqual(code, 0)
        self.assertIn("home.meta.libraries", out)


def get(kit, path):
    with urllib.request.urlopen(kit.url + path, timeout=10) as r:
        return r.read().decode("utf-8")


SWEDISH = ("Krislåda", "Fungerar utan", "Livsfara", "Fråga AI", "Sök i biblioteken", "Myndigheternas", "Böcker",
           "Förbered dig", "Alla bibliotek", "Skriv ut", "På svenska", "Hela ")


class ServedTextsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kit = ServedKit()
        cls.kit.start()

    @classmethod
    def tearDownClass(cls):
        cls.kit.stop()

    def test_the_server_gives_pages_both_languages_and_the_default(self):
        script = get(self.kit, "/lib/lang.js")
        first = script.splitlines()[0]   # window.KIT_LANG = {...};
        data = json.loads(first[first.index("{"):first.rindex("}") + 1])
        self.assertEqual(data["default"], "uk")
        self.assertEqual(sorted(data["texts"]), ["en", "uk"])
        self.assertEqual(data["texts"]["uk"]["home.ai.title"], "Запитати ШІ")
        self.assertEqual(data["texts"]["en"]["home.ai.title"], "Ask the AI")
        self.assertEqual(set(data["texts"]["uk"]), set(data["texts"]["en"]))

    def test_the_start_page_reads_in_ukrainian_by_default_with_no_swedish(self):
        page = get(self.kit, "/")
        self.assertIn('<html lang="uk"', page)
        self.assertIn("<title>Тривожна валіза</title>", page)
        self.assertIn("<h1 data-kit>Тривожна валіза</h1>", page)
        self.assertIn("Запитати ШІ", page)
        self.assertIn("Загроза життю? Телефонуйте 112.", page)
        for swedish in SWEDISH:
            self.assertNotIn(swedish, page)

    def test_the_start_page_marks_its_texts_by_key_and_carries_the_config_texts_in_both_languages(self):
        page = get(self.kit, "/")
        self.assertIn('data-t="home.ai.title"', page)
        self.assertIn('<span data-l="en">police</span>', page)   # from the country config, hidden until the page switches
        self.assertIn("Ukraine", page)   # the map card's {place}, a text per language

    def test_emergency_numbers_come_from_the_country_config_in_both_languages(self):
        page = get(self.kit, "/")
        for number in ("101", "102", "103", "104"):
            self.assertIn(number, page)
        self.assertIn("поліція", page)
        self.assertIn("police", page)
        self.assertIn("пожежно-рятувальна служба", page)

    def test_every_page_loads_the_language_layer_with_one_line(self):
        for path in ("/", "/ai/", "/map/", "/checklist/", "/print/", "/phone/", "/read/"):
            page = get(self.kit, path)
            self.assertEqual(page.count('src="/lib/lang.js"'), 1, path)
            # the language layer sets <html lang> itself; no page writes a language into its markup (any country)
            self.assertTrue(page.split("<html", 1)[1].startswith(' lang="uk"') or page.split("<html", 1)[1].startswith(">"), path)


if __name__ == "__main__":
    unittest.main()
