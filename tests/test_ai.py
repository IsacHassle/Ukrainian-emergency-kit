"""Seam 1, the AI for Ukraine: From sources, Quick answer and Save battery driven over HTTP against the stand-in AI
and the tiny Libraries (one Ukrainian, one English)."""
import json
import os
import unittest
import urllib.request

from servedkit import ServedKit
from standins import ANSWER


def post_lines(kit, path, payload):
    req = urllib.request.Request(kit.url + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return [json.loads(l) for l in r.read().decode("utf-8").splitlines() if l.strip()]


def ask(kit, text, earlier=None):
    msgs = ([{"role": "user", "content": earlier}, {"role": "assistant", "content": "ok"}] if earlier else [])
    return post_lines(kit, "/ai-api/books-chat", {"messages": msgs + [{"role": "user", "content": text}]})


PLAN = None


class FromSourcesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kit = ServedKit()
        cls.kit.start()
        global PLAN
        PLAN = cls.kit.ai.plan_reply

    @classmethod
    def tearDownClass(cls):
        cls.kit.stop()

    def test_sources_come_from_the_ukrainian_and_the_english_library(self):
        lines = ask(self.kit, "Як зупинити кровотечу?")
        sources = lines[0]["sources"]
        libs = {s["title"]: s for s in sources if s.get("href")}
        self.assertIn("Зупинка кровотечі", libs)   # a Ukrainian title, found in the Ukrainian Library
        self.assertIn("/content/wikipedia_uk_medicine_test_2026-01/", libs["Зупинка кровотечі"]["href"])
        self.assertEqual(libs["Зупинка кровотечі"]["library"], "WikiMed (українська)")
        self.assertIn("Tourniquet", libs)           # an English title, found in the English Library
        self.assertIn("/content/wikipedia_en_medicine_test_2026-01/", libs["Tourniquet"]["href"])
        self.assertEqual(libs["Tourniquet"]["library"], "WikiMed")

    def test_a_ukrainian_title_is_found_by_suggestion_when_the_library_has_no_full_text_index(self):
        self.kit.ai.plan_reply = "SEARCH: кровотеча\nUKRAINIAN: Зупинка кровоте\nENGLISH: NONE"   # not an exact title
        try:
            sources = ask(self.kit, "Що робити при кровотечі?")[0]["sources"]
        finally:
            self.kit.ai.plan_reply = PLAN
        self.assertIn("Зупинка кровотечі", [s["title"] for s in sources])

    def test_sources_line_comes_first_then_the_streamed_answer(self):
        lines = ask(self.kit, "Як зупинити кровотечу?")
        self.assertEqual(list(lines[0]), ["sources"])
        self.assertTrue(all("sources" not in l for l in lines[1:]))
        self.assertEqual("".join(l.get("message", {}).get("content", "") for l in lines[1:]), ANSWER)

    def test_the_official_guide_comes_before_library_articles(self):
        titles = [s["title"] for s in ask(self.kit, "Як зупинити кровотечу?")[0]["sources"]]
        self.assertTrue(titles[0].endswith(".pdf"))
        self.assertFalse(any(t.endswith(".pdf") for t in titles[titles.index("Tourniquet"):]))

    def test_the_planning_call_asks_for_titles_in_both_languages(self):
        before = len(self.kit.ai.chat_requests)
        ask(self.kit, "Як зупинити кровотечу?")
        plan = [r for r in self.kit.ai.chat_requests[before:] if r.get("stream") is False][0]
        system = plan["messages"][0]["content"]
        self.assertIn("UKRAINIAN:", system)
        self.assertIn("ENGLISH:", system)

    def test_it_still_answers_from_library_articles_when_the_book_index_app_is_closed(self):
        kit = ServedKit()
        kit.start()
        try:
            kit.ai._anythingllm.stop()   # AnythingLLM is not running
            lines = ask(kit, "Як зупинити кровотечу?")
        finally:
            kit.stop()
        titles = [s["title"] for s in lines[0]["sources"]]
        self.assertIn("Зупинка кровотечі", titles)
        self.assertIn("Tourniquet", titles)
        self.assertFalse(any(t.endswith(".pdf") for t in titles))
        self.assertEqual("".join(l.get("message", {}).get("content", "") for l in lines[1:]), ANSWER)

    def test_nothing_about_a_question_is_written_to_disk_or_logs(self):
        kit = ServedKit()
        kit.start()
        try:
            def tree():
                out = {}
                for root, _, files in os.walk(kit.tmp):
                    for f in files:
                        p = os.path.join(root, f)
                        out[p] = (os.lstat(p).st_size, os.lstat(p).st_mtime)
                return out
            before = tree()
            secret = "Мій син Тарас отруївся газом у Ковелі"
            ask(kit, secret)
            post_lines(kit, "/ai-api/chat", {"model": "emergency", "messages": [{"role": "user", "content": secret}]})
            self.assertEqual(tree(), before)
            for root, _, files in os.walk(kit.tmp):   # no file anywhere holds the question
                for f in files:
                    p = os.path.join(root, f)
                    if not os.path.islink(p):
                        with open(p, "rb") as fh:
                            self.assertNotIn("Тарас".encode(), fh.read(), f)
            kit._proc.terminate()   # the web server's own log (stderr) holds nothing either
            self.assertNotIn("Тарас".encode(), kit._proc.stderr.read())
        finally:
            kit.stop()

    def test_only_the_kits_own_models_and_workspace_are_used(self):
        before = len(self.kit.ai.chat_requests)
        ask(self.kit, "Як зупинити кровотечу?")
        models = {r["model"] for r in self.kit.ai.chat_requests[before:]}
        self.assertEqual(models, {"emergency"})
        self.assertEqual(set(self.kit.ai.searched_workspaces), {"emergency-kit"})


if __name__ == "__main__":
    unittest.main()
