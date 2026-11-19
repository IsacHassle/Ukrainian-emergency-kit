"""Story 79: the engine takes another country's config and texts. The kit is served with a second country, Testland
(its own language "tl", its own config, its own AI instruction files and its own language files), and followed end
to end: the start page, every other page, the numbers, the topics, the AI page's wording and what the AI is
told. Nothing Ukrainian is left: no Cyrillic letters and no word Ukraine or Ukrainian."""
import json
import os
import re
import shutil
import tempfile
import unittest
import urllib.request

from servedkit import REPO, ServedKit
from standins import ANSWER
from test_country_config import post, real, testland

CYRILLIC = re.compile("[Ѐ-ӿ]")
PAGES = ("/", "/ai/", "/map/", "/checklist/", "/print/", "/phone/", "/read/", "/poster/")

PROMPT = ('You are the offline assistant in the kit "Testkit". Answer in Testish or English. '
          "Call 999 in an emergency. The Testland authorities (TL1, TL2) come first.\n")
PLAN_PROMPT = ("You prepare searches for an offline kit in Testland. Reply with exactly three lines.\n"
               "SEARCH: the question as a stand-alone search.\nTESTISH: 1 to 3 article titles in Testish.\n"
               "ENGLISH: 1 to 3 English article titles.\n")


def in_testish(node):
    """The config with every text per language keyed "tl" instead of "uk" (Testland's own language)."""
    if isinstance(node, dict):
        return {("tl" if k == "uk" else k): in_testish(v) for k, v in node.items()}
    if isinstance(node, list):
        return [in_testish(v) for v in node]
    return node


def plain(text):
    return text.replace("Ukrainian", "Testish").replace("Ukraine", "Testland")


def testish_texts(node):
    """Every text per language in `node`: the Testish one is "Testish " and the English text, the English one plain."""
    if isinstance(node, dict):
        if "tl" in node and "en" in node:
            return {"tl": "Testish " + plain(node["en"]), "en": plain(node["en"])}
        return {k: testish_texts(v) for k, v in node.items()}
    if isinstance(node, list):
        return [testish_texts(v) for v in node]
    return node


def second_country(files):
    def make(c):
        c = in_testish(testland(c))
        c["default_language"], c["locale"] = "tl", "tl-TL"
        c["repo"] = "testland/testkit"
        for l in c["ai"]["library_languages"] + c["ai"]["libraries"]:
            if l.get("code", l.get("language")) == "uk":
                l.update({"code": "tl", "name": "Testish", "plan_label": "TESTISH"} if "code" in l else {"language": "tl"})
        c["map"] = testish_texts(c["map"])
        c["ai"]["answer_languages"] = [{"name": "Testish", "alphabet": "a-z", "letters": "", "words": []}]
        c["ai"]["prompt_file"], c["ai"]["plan_prompt_file"] = files["prompt"], files["plan"]
        c["ai"]["answer_language"] = "Testish"
        c["map"]["labels"]["military_words"] = ["army"]
        c["map"]["labels"]["other_language"] = {"letters": "", "street_types": [], "endings": []}
        c["map"]["labels"]["unnamed_crossing"] = {"name": "Crossing, ", "en": "Crossing, "}
        c["map"]["street_types"] = ["street", "st"]
        c["map"]["shortcuts"] = [{"label": {"tl": "Testby", "en": "Testtown"}, "center": [1.5, 2.5], "zoom": 9}]
        c["map"]["overview_label"] = {"tl": "Testland", "en": "Testland"}
        c["official_guides"]["print_skip"] = ["^Important information", "^https?://"]
        c["official_guides"]["print_drop_lines"] = ["^#[^\\s#]"]
        for part in ("books", "library_groups"):
            c[part] = testish_texts(c[part])
        c["emergency_topics"][0]["label"] = {"tl": "Testblödning", "en": "Test bleeding"}
        return c
    return make


def language_files(web):
    """Testland's language files: every key of the real English file, as Testish text and as plain English, with
    no word of the real country in it."""
    with open(os.path.join(REPO, "web", "lang", "en.json"), encoding="utf-8") as f:
        en = json.load(f)
    tl = {k: "Testish " + plain(v) for k, v in en.items()}
    en = {k: plain(v) for k, v in en.items()}
    en["home.urgent.in.tl"], tl["home.urgent.in.tl"] = "in Testish", "in Testish"
    en.pop("home.urgent.in.uk"), tl.pop("home.urgent.in.uk")
    en["lang.name"], tl["lang.name"] = "English", "Testish"
    folder = os.path.join(web, "lang")
    shutil.rmtree(folder)
    os.makedirs(folder)
    for code, d in (("tl", tl), ("en", en)):
        with open(os.path.join(folder, code + ".json"), "w", encoding="utf-8") as f:
            json.dump(dict(sorted(d.items())), f, ensure_ascii=False, indent=1)


class SecondCountryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files_dir = tempfile.mkdtemp(prefix="ek-testland-")
        files = {"prompt": os.path.join(cls.files_dir, "AI-PROMPT.txt"), "plan": os.path.join(cls.files_dir, "AI-PLAN-PROMPT.txt")}
        for path, text in ((files["prompt"], PROMPT), (files["plan"], PLAN_PROMPT)):
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        cls.kit = ServedKit(country=second_country(files), web_hook=language_files)
        for book in cls.kit.library.catalog:   # Testland's Library in its own language
            book["title"] = plain(book["title"]) if book["language"] != "ukr" else "Testish medicine (test)"
        cls.kit.start()

    @classmethod
    def tearDownClass(cls):
        cls.kit.stop()
        shutil.rmtree(cls.files_dir, ignore_errors=True)

    def get(self, path):
        with urllib.request.urlopen(self.kit.url + path, timeout=10) as r:
            return r.read().decode("utf-8")

    def assert_nothing_ukrainian(self, text, where):
        self.assertIsNone(CYRILLIC.search(text), "%s has Cyrillic: %r" % (where, text[CYRILLIC.search(text).start() - 40:][:90] if CYRILLIC.search(text) else ""))
        self.assertNotRegex(text, r"Ukrain", where)

    def test_the_start_page_shows_testland_in_its_own_language(self):
        page = self.get("/")
        self.assertIn("<title>Testlådan</title>", page)
        self.assertIn('lang="tl"', page)
        self.assertIn("999", page)
        self.assertIn("Testblödning", page)
        self.assertIn("TL1 · Testråd", page)
        self.assertIn("Testish ", page)   # the page's own texts come from the Testish language file

    def test_no_page_has_anything_ukrainian_left(self):
        for path in PAGES + ("/lib/country.js", "/lib/lang.js", "/manifest.webmanifest"):
            self.assert_nothing_ukrainian(self.get(path), path)

    def test_the_two_languages_are_testish_and_english(self):
        data = self.get("/lib/lang.js")
        first = data.splitlines()[0]
        langs = json.loads(first[first.index("{"):first.rindex("}") + 1])
        self.assertEqual(langs["default"], "tl")
        self.assertEqual(sorted(langs["texts"]), ["en", "tl"])

    def test_the_numbers_come_from_the_config(self):
        script = self.get("/lib/country.js")
        facts = json.loads(script.splitlines()[0][len("window.COUNTRY = "):-1])
        self.assertEqual([n["number"] for n in facts["emergency_numbers"]], ["999", "7000"])
        self.assertEqual(facts["emergency_numbers"][0]["label"]["tl"], "nödläge")
        self.assertEqual(facts["map"]["street_types"], ["street", "st"])

    def test_what_the_ai_is_told_is_testland_s_own(self):
        before = len(self.kit.ai.chat_requests)
        self.kit.ai.plan_reply = "SEARCH: stop bleeding\nTESTISH: Bleeding\nENGLISH: Tourniquet"
        lines = post(self.kit, "/ai-api/books-chat", {"messages": [{"role": "user", "content": "How do I stop bleeding?"}]})
        self.assertIn("sources", lines[0])
        asked = self.kit.ai.chat_requests[before:]
        plan = [r for r in asked if not r.get("stream")][0]["messages"][0]["content"]
        self.assertEqual(plan.strip(), PLAN_PROMPT.strip())   # the planning instructions are the country's file
        answer = [r for r in asked if r.get("stream")][0]["messages"][0]["content"]
        self.assert_nothing_ukrainian(answer, "the AI's instructions")
        self.assertTrue(answer.startswith(PROMPT.strip()))
        self.assertIn("The excerpts are in Testish or in English", answer)
        self.assertIn("a question in Testish gets an answer in Testish", answer)
        self.assertIn("Testish if it is unclear", answer)
        self.assertIn("TL1 - Stop bleeding", answer)

    def test_the_ai_answers_through_the_chat(self):
        lines = post(self.kit, "/ai-api/chat", {"model": "alpha", "messages": [{"role": "user", "content": "A cut"}]})
        self.assertEqual("".join(l.get("message", {}).get("content", "") for l in lines), ANSWER)


if __name__ == "__main__":
    unittest.main()
