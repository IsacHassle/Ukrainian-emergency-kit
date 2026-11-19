"""Seam 1, the served kit: the web server runs against the small test kit, with stand-ins for the
Library server and the AI, and is driven over HTTP the way Visitor devices use it.

Run everything with:  python3 -m unittest discover -s tests
"""
import json
import unittest
import urllib.request

from servedkit import ServedKit
from standins import ANSWER


def get(kit, path):
    with urllib.request.urlopen(kit.url + path, timeout=10) as r:
        return r.status, r.read()


def post_lines(kit, path, payload):
    req = urllib.request.Request(kit.url + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return [json.loads(l) for l in r.read().decode("utf-8").splitlines() if l.strip()]


class ServedKitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kit = ServedKit()
        cls.kit.start()

    @classmethod
    def tearDownClass(cls):
        cls.kit.stop()

    def test_start_page_loads_and_lists_the_test_libraries(self):
        status, body = get(self.kit, "/")
        page = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("<title>", page)
        self.assertIn("Сильна кровотеча, джгут", page)   # an emergency topic found in the test Library

    def test_status_reports_ai_engine_book_index_and_libraries(self):
        status, body = get(self.kit, "/ai-api/status")
        data = json.loads(body)
        self.assertEqual(status, 200)
        self.assertTrue(data["ollama"])
        self.assertTrue(data["books"])
        self.assertTrue(data["libraries"])
        self.assertIn("emergency", data["models"])
        self.assertNotIn("crisis", data["models"])   # the Swedish kit's model is never this kit's
        self.assertEqual(data["library_port"], self.kit.library_port)

    def test_quick_answer_streams_from_the_stand_in_ai(self):
        lines = post_lines(self.kit, "/ai-api/chat", {"model": "emergency", "messages": [{"role": "user", "content": "A cut"}]})
        text = "".join(l.get("message", {}).get("content", "") for l in lines)
        self.assertEqual(text, ANSWER)
        self.assertTrue(lines[-1]["done"])

    def test_from_sources_sends_sources_line_first_then_the_answer(self):
        lines = post_lines(self.kit, "/ai-api/books-chat", {"messages": [{"role": "user", "content": "How do I stop bleeding?"}]})
        titles = [s["title"] for s in lines[0]["sources"]]
        self.assertIn("First Aid (Field Manual).pdf", titles)   # from the test Books
        self.assertIn("Tourniquet", titles)                      # from the test Library
        text = "".join(l.get("message", {}).get("content", "") for l in lines[1:])
        self.assertEqual(text, ANSWER)

    def test_map_search_file_is_served(self):
        status, body = get(self.kit, "/map/data/places.json")
        names = [item[0] for item in json.loads(body)["items"]]
        self.assertIn("Київ", names)


if __name__ == "__main__":
    unittest.main()
