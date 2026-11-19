"""The country config (config/country.json): checked as CI checks it, and followed through the served kit.

A kit with a different country config (made here from the real one: other names, numbers, models and Book
index workspace) must show those facts on the pages and use them in the AI requests, and none of Sweden's.
"""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.request

from servedkit import REPO, ServedKit
from standins import ANSWER

CHECK = os.path.join(REPO, "scripts", "check-country.py")


def check(config):
    """Runs the validator on a config (a dict); returns (exit code, output)."""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "country.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False)
        run = subprocess.run([sys.executable, CHECK, path], capture_output=True, text=True)
        return run.returncode, run.stdout + run.stderr


def real():
    with open(os.path.join(REPO, "config", "country.json"), encoding="utf-8") as f:
        return json.load(f)


def testland(c):
    """Another country: nothing in it is shared with Ukraine's facts."""
    c = copy.deepcopy(c)
    c["country"] = "testland"
    c["kit_name"] = {"uk": "Testlådan", "en": "Testkit"}
    c["kit_description"] = {"uk": "Testbeskrivning."}
    c["ai"]["models"] = {"main": "alpha", "small": "alpha-small"}
    c["ai"]["workspace"] = "ws-alpha"
    c["ai"]["answer_language"] = "Testish"
    c["ai"]["authorities"] = "the Testland authorities (TL1, TL2)"
    c["ai"]["example_source"] = "TL1 - Stop bleeding"
    c["emergency_numbers"] = [
        {"number": "999", "primary": True, "label": {"uk": "nödläge", "en": "emergency"}, "print_label": {"uk": "nödläge", "en": "emergency"}},
        {"number": "7000", "label": {"uk": "testråd", "en": "test advice"}, "print_label": {"uk": "testrådgivning", "en": "test advice line"}},
    ]
    c["radio"] = {"label": {"uk": "Radio Test"}, "print_label": {"uk": "Testradion"}}
    c["official_guides"]["folder"] = "Testguides"
    c["official_guides"]["print_pages"] = ["TL1 - Stop bleeding"]
    c["official_guides"]["sources"] = [{"id": "TL1", "label": {"uk": "TL1 · Testråd"}}]
    c["emergency_topics"] = [{"id": "bleeding", "wikimed": {"uk": "Bleeding", "en": "Bleeding"}, "label": {"uk": "Testblödning", "en": "Test bleeding"},
                              "official_guide": {"uk": "TL1 - Stop bleeding"}, "first": 1}]
    c["checklist"]["additions"] = [{"uk": "Ett testföremål"}]
    c["map"]["shortcuts"] = [{"label": {"uk": "Testby"}, "center": [1.5, 2.5], "zoom": 9}]
    c["map"]["overview_label"] = {"uk": "Testland"}
    c["checklist"]["official_lists"] = [{"id": "home", "heading": {"uk": "Hemma"}, "guide": {"uk": "TL1 - Home"},
                                         "section": {"uk": "Home"}, "start": {"uk": "Have:"}, "until": {"uk": "End"}}]
    return c


def get(kit, path):
    with urllib.request.urlopen(kit.url + path, timeout=10) as r:
        return r.read().decode("utf-8")


def post(kit, path, payload):
    req = urllib.request.Request(kit.url + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return [json.loads(l) for l in r.read().decode("utf-8").splitlines() if l.strip()]


class ConfigIsValidTest(unittest.TestCase):
    def test_the_real_config_is_valid(self):
        code, out = check(real())
        self.assertEqual(code, 0, out)

    def test_a_missing_part_is_refused_and_named(self):
        c = real()
        del c["ai"]["workspace"]
        code, out = check(c)
        self.assertNotEqual(code, 0)
        self.assertIn("ai.workspace", out)

    def test_text_missing_in_the_default_language_is_refused(self):
        c = real()
        c["kit_name"] = {"en": "Emergency Kit"}
        code, out = check(c)
        self.assertNotEqual(code, 0)
        self.assertIn("kit_name", out)

    def test_a_kit_name_without_english_is_refused(self):
        c = real()
        c["kit_name"] = {"uk": "Тривожна валіза"}
        code, out = check(c)
        self.assertNotEqual(code, 0)
        self.assertIn("kit_name", out)

    def test_an_emergency_number_label_without_english_is_refused(self):
        c = real()
        c["emergency_numbers"][1]["label"] = {"uk": "поліція"}
        code, out = check(c)
        self.assertNotEqual(code, 0)
        self.assertIn("emergency_numbers[1].label", out)

    def test_a_map_shape_that_is_not_a_closed_polygon_is_refused(self):
        c = real()
        c["map"]["shape"] = "config/country.json"
        code, out = check(c)
        self.assertNotEqual(code, 0)
        self.assertIn("map.shape", out)

    def test_a_workspace_address_that_is_not_made_from_its_name_is_refused(self):
        c = real()
        c["ai"]["workspace_name"] = "Emergency kits"   # AnythingLLM would make "emergency-kits"
        code, out = check(c)
        self.assertNotEqual(code, 0)
        self.assertIn("ai.workspace", out)

    def test_two_models_with_one_name_are_refused(self):
        c = real()
        c["ai"]["models"]["small"] = c["ai"]["models"]["main"]
        code, out = check(c)
        self.assertNotEqual(code, 0)

    def test_an_emergency_topic_without_an_id_is_refused(self):
        c = real()
        del c["emergency_topics"][0]["id"]
        code, out = check(c)
        self.assertNotEqual(code, 0)
        self.assertIn("emergency_topics", out)


class OtherCountryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kit = ServedKit(country=testland)
        cls.kit.start()

    @classmethod
    def tearDownClass(cls):
        cls.kit.stop()

    def test_start_page_shows_the_config_s_name_numbers_and_topics(self):
        page = get(self.kit, "/")
        self.assertIn("<title>Testlådan</title>", page)
        self.assertIn("<h1 data-kit>Testlådan</h1>", page)
        self.assertIn("Телефонуйте 999", page)
        self.assertIn("testråd", page)
        self.assertIn("Radio Test", page)
        self.assertIn("Testblödning", page)
        self.assertIn("TL1 · Testråd", page)   # the Official Guides, grouped by the config's sources
        self.assertIn("las/?f=docs/Testguides/TL1%20-%20Stop%20bleeding.md", page)   # the topic opens its guide
        for ukraine in ("<title>Тривожна", "Телефонуйте 112", "пожежно-рятувальна", "Українське радіо", "Джгут"):
            self.assertNotIn(ukraine, page)

    def test_pages_get_the_config_from_the_web_server(self):
        script = get(self.kit, "/lib/country.js")
        first = script.splitlines()[0]   # window.COUNTRY = {...};
        facts = json.loads(first[first.index("{"):first.rindex("}") + 1])
        self.assertEqual(facts["kit_name"]["uk"], "Testlådan")
        self.assertEqual(facts["ai"]["models"], {"main": "alpha", "small": "alpha-small"})
        self.assertEqual(facts["emergency_numbers"][0]["number"], "999")
        self.assertEqual(facts["map"]["shortcuts"][0]["label"]["uk"], "Testby")
        self.assertEqual(facts["checklist"]["additions"], [{"uk": "Ett testföremål"}])
        self.assertNotIn("ready_gov", facts)   # build-time facts do not go to Visitor devices

    def test_status_reports_the_config_s_models_and_workspace(self):
        data = json.loads(get(self.kit, "/ai-api/status"))
        self.assertEqual(data["models"], ["alpha", "alpha-small"])
        self.assertTrue(data["books"])   # the stand-in knows only the workspace "ws-alpha"

    def test_the_chat_takes_the_config_s_models_only(self):
        lines = post(self.kit, "/ai-api/chat", {"model": "alpha-small", "messages": [{"role": "user", "content": "A cut"}]})
        self.assertEqual("".join(l.get("message", {}).get("content", "") for l in lines), ANSWER)
        with self.assertRaises(urllib.error.HTTPError) as refused:
            post(self.kit, "/ai-api/chat", {"model": "emergency", "messages": [{"role": "user", "content": "A cut"}]})
        self.assertEqual(refused.exception.code, 400)

    def test_from_sources_uses_the_config_in_the_ai_request(self):
        before = len(self.kit.ai.chat_requests)
        lines = post(self.kit, "/ai-api/books-chat", {"messages": [{"role": "user", "content": "How do I stop bleeding?"}]})
        self.assertIn("sources", lines[0])
        asked = self.kit.ai.chat_requests[before:]
        self.assertTrue(asked)
        self.assertEqual({r["model"] for r in asked}, {"alpha"})
        answer = [r for r in asked if r.get("stream")][0]
        # The instructions file (config/AI-PROMPT.txt) is the country's own text; the part the engine adds is checked.
        system = answer["messages"][0]["content"].split("EXCERPTS FOR THIS QUESTION", 1)[1]
        self.assertIn("the Testland authorities (TL1, TL2)", system)
        self.assertIn("into a Testish answer", system)
        self.assertIn("TL1 - Stop bleeding", system)
        self.assertNotIn("1177", system)
        self.assertNotIn("Swedish", system)
        self.assertIn("ws-alpha", self.kit.ai.searched_workspaces)
        self.assertEqual(set(self.kit.ai.searched_workspaces), {"ws-alpha"})

    def test_the_web_app_manifest_carries_the_config_s_name(self):
        manifest = json.loads(get(self.kit, "/manifest.webmanifest"))
        self.assertEqual(manifest["name"], "Testlådan")
        self.assertEqual(manifest["short_name"], "Testlådan")
        self.assertEqual(manifest["lang"], "uk")
        self.assertEqual(manifest["description"], "Testbeskrivning.")


def shell(kit_dir, config, snippet):
    """Runs a bash snippet that has sourced scripts/country.sh, as the install scripts do."""
    env = dict(os.environ, KIT=kit_dir)
    if config:
        env["EK_COUNTRY"] = config
    run = subprocess.run(["bash", "-c", '. "$KIT/scripts/country.sh"; ' + snippet], env=env, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    return run.stdout.strip()


class ShellScriptsReadTheConfigTest(unittest.TestCase):
    """The install and start scripts get their facts from scripts/country.sh. Their steps need a Mac, Ollama
    and the internet, so what is tested is what they would be told."""

    def test_ukraine_s_facts_are_what_the_scripts_are_told(self):
        self.assertEqual(shell(REPO, None, "country ai.models.main"), "emergency")
        self.assertEqual(shell(REPO, None, "country ai.models.small"), "emergency-small")
        self.assertEqual(shell(REPO, None, "country ai.base_models.main"), "gemma4:26b")
        self.assertEqual(shell(REPO, None, "country ai.base_models.small"), "gemma4:e4b")
        self.assertEqual(shell(REPO, None, "country ai.workspace"), "emergency-kit")
        self.assertEqual(shell(REPO, None, "country ai.workspace_name"), "Emergency Kit")
        self.assertEqual(shell(REPO, None, "country map.pmtiles"), "ukraine")
        self.assertEqual(shell(REPO, None, "country map.shape"), "config/map-area.geojson")
        self.assertEqual(shell(REPO, None, "country map.max_zoom"), "15")
        self.assertEqual(shell(REPO, None, "country map.search_release_repo"), "IsacHassle/Swedish-doomsdaykit")
        self.assertEqual(shell(REPO, None, "country kit_name"), "Тривожна валіза")
        self.assertEqual(shell(REPO, None, "country ai.check.expect"), "112")

    def test_another_config_changes_what_the_scripts_are_told(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "country.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(testland(real()), f, ensure_ascii=False)
            self.assertEqual(shell(REPO, path, "country ai.models.main"), "alpha")
            self.assertEqual(shell(REPO, path, "country ai.workspace"), "ws-alpha")
            self.assertEqual(shell(REPO, path, "country kit_name"), "Testlådan")
            self.assertEqual(shell(REPO, path, "country map.regions.0.slug"), "ukraine")   # unchanged in testland


if __name__ == "__main__":
    unittest.main()
