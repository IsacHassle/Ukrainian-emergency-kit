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


class FromSourcesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kit = ServedKit()
        cls.kit.start()

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


if __name__ == "__main__":
    unittest.main()
