"""Emergency Topics on the start page (Seam 1): each opens WikiMed in the page language, Ukrainian WikiMed
on УКР and English WikiMed on ENG, and the config names exactly the topics the spec lists.
The test Library has a Ukrainian and an English WikiMed with only a few of the real articles."""
import json
import os
import re
import unittest
import urllib.parse
import urllib.request

from servedkit import REPO, ServedKit
from test_country_config import check, real

UK = "wikipedia_uk_medicine_test_2026-01"
EN = "wikipedia_en_medicine_test_2026-01"
IDS = ["bleeding", "blast", "crush", "cpr", "burns", "shock", "hypothermia", "co", "mines", "radiation"]


def viewer(book, path):
    return "/viewer#%s/%s" % (book, urllib.parse.quote(path))


def item(page, label, lang="uk"):
    """The <li> of the topic whose Ukrainian label is `label`, as written for a page language, or None.
    Every topic is written once per language (<li data-l="uk"> and <li data-l="en">); a language that has
    neither a guide nor an article for it has none."""
    for m in re.finditer(r'<li data-l="%s">.*?</li>' % lang, page):
        if label in m.group(0) or (lang == "en" and label in LABEL_EN and LABEL_EN[label] in m.group(0)):
            return m.group(0)
    return None


LABEL_EN = {"Сильна кровотеча, джгут": "Severe bleeding, tourniquet", "Серцево-легенева реанімація": "CPR",
            "Вибухова травма": "Blast injury", "Переохолодження": "Hypothermia", "Опіки": "Burns"}


class TopicConfigTest(unittest.TestCase):
    def test_the_config_has_the_ten_topics_in_order_each_with_both_articles(self):
        topics = real()["emergency_topics"]
        self.assertEqual([t["id"] for t in topics], IDS)
        for t in topics:
            self.assertTrue(t["wikimed"]["uk"] and t["wikimed"]["en"], t["id"])
            self.assertTrue(t["label"]["uk"] and t["label"]["en"], t["id"])

    def test_a_topic_without_its_wikimed_article_is_refused(self):
        c = real()
        del c["emergency_topics"][0]["wikimed"]["en"]
        code, out = check(c)
        self.assertNotEqual(code, 0)
        self.assertIn("emergency_topics[0].wikimed", out)


class StartPageTopicsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kit = ServedKit()
        cls.kit.start()
        with urllib.request.urlopen(cls.kit.url + "/", timeout=10) as r:
            cls.page = r.read().decode("utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.kit.stop()

    def test_a_topic_without_a_saved_guide_opens_the_article_in_each_page_language(self):
        li = item(self.page, "Серцево-легенева реанімація")
        self.assertIn('data-k="%s"' % viewer(UK, "Серцево-легенева_реанімація"), li)
        self.assertNotIn("read/?f=", li)
        self.assertNotIn("data-t=", li)   # nothing to explain: the article exists in this language

    def test_a_topic_with_one_language_only_opens_that_article_in_both_and_says_so(self):
        li = item(self.page, "Вибухова травма")
        self.assertIn('data-k="%s"' % viewer(EN, "Blast_injury"), li)
        self.assertIn('data-t="home.urgent.in.en"', li)
        en = item(self.page, "Вибухова травма", "en")
        self.assertIn('data-k="%s"' % viewer(EN, "Blast_injury"), en)
        self.assertNotIn("home.urgent.in.en", en)

    def test_a_topic_whose_articles_and_guides_are_in_none_is_left_out_of_both_pages(self):
        self.assertIsNone(item(self.page, "Радіація"))
        self.assertIsNone(item(self.page, "Радіація", "en"))

    def test_all_shown_topics_are_in_one_list_with_no_more_section(self):
        self.assertNotIn('class="inline"', self.page)


@unittest.skipUnless(os.path.isdir(os.path.expanduser("~/.cache/emergency-kit-build/zim")),
                     "the real WikiMed files are not in ~/.cache/emergency-kit-build/zim")
class RealLibraryTest(unittest.TestCase):
    def test_every_topic_article_exists_in_the_real_wikimed(self):
        # Needs libzim: EK_LIBZIM_PYTHON names a Python that has it (the kit's tools/venv/bin/python).
        import subprocess
        import sys
        run = subprocess.run([os.environ.get("EK_LIBZIM_PYTHON", sys.executable), os.path.join(REPO, "scripts", "check-topics.py")],
                             capture_output=True, text=True)
        if run.returncode == 3:
            self.skipTest(run.stdout.strip())
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


if __name__ == "__main__":
    unittest.main()
