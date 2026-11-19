"""The guide saver (Seam 2, the install pipeline): scripts/fetch-pages.py run against stand-in copies of the
authorities' websites, and the files it leaves in the kit folder.

The fixture pages in tests/internet copy each site's real structure (menus, scripts, share buttons, the article
container the research found per site). The tests run with http_proxy pointing at the stand-in, so nothing here
reaches the internet, and the real country config's per-site rules are the ones under test.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from servedkit import REPO
from standins import StandInInternet

SAVER = os.path.join(REPO, "scripts", "fetch-pages.py")
FOLDER = "Official Guides"

SIRENS = "http://dovidka.info/advices/shho-robyty-koly-pochuly-syreny/"
BLEEDING = "http://dovidka.info/articles/yak-zupynytu-krovotechu/"
BLEEDING_EN = "http://dovidka.info/en/articles/tactical-medicine-how-to-stop-bleeding/"
MOZ = "http://moz.gov.ua/uk/moz-nagadue-bazovi-pravila-domedichnoi-dopomogi"
PHC = "http://phc.org.ua/news/yak-znezaraziti-vodu-ta-profilaktika-zakhvoryuvan-scho-peredayutsya-cherez-vodu"
MINES = "http://redcross.org.ua/mines/"
BURNS = "http://redcross.org.ua/wp-content/uploads/2026/06/13_опіки.pdf"
DSNS = "http://bezpeka.dsns.gov.ua/materials/bezpeka-v-umovakh-viyny"

LIST = """
uk | %s | dovidka.info - Що робити, коли почули сирени
uk | %s | dovidka.info - Тактична медицина, як зупинити кровотечу
en | %s | dovidka.info - Tactical medicine, how to stop bleeding
uk | %s | МОЗ - МОЗ нагадує, базові правила домедичної допомоги
uk | %s | ЦГЗ - Як знезаразити воду
uk | %s | Червоний Хрест - Мінна небезпека
uk | %s | Червоний Хрест - Пожежі та опіки, перша допомога
uk | %s | ДСНС - Безпека в умовах війни
""" % (SIRENS, BLEEDING, BLEEDING_EN, MOZ, PHC, MINES, BURNS, DSNS)

UK = ["dovidka.info - Що робити, коли почули сирени.md", "dovidka.info - Тактична медицина, як зупинити кровотечу.md",
      "МОЗ - МОЗ нагадує, базові правила домедичної допомоги.md", "ЦГЗ - Як знезаразити воду.md",
      "Червоний Хрест - Мінна небезпека.md", "Червоний Хрест - Пожежі та опіки, перша допомога.pdf"]


def internet():
    net = StandInInternet()
    net.page(SIRENS, "dovidka-advice.html")
    net.page(BLEEDING, "dovidka-article.html")
    net.page(BLEEDING_EN, "dovidka-article-en.html")
    net.page(MOZ, "moz.html")
    net.page(PHC, "phc.html")
    net.page(MINES, "redcross.html")
    net.page(BURNS, "leaflet.pdf")
    net.refuse(DSNS)
    return net.start()


class Saver:
    """Runs the guide saver in a fresh kit folder with a given list; `run()` returns (exit code, output)."""

    def __init__(self, net, list_text=LIST):
        self.net = net
        self.tmp = tempfile.mkdtemp(prefix="ek-guides-")
        self.kit = os.path.join(self.tmp, "kit")
        self.list = os.path.join(self.tmp, "pages.txt")
        with open(self.list, "w", encoding="utf-8") as f:
            f.write(list_text)

    def run(self, *args, **env):
        e = dict(os.environ, EK_KIT=self.kit, EK_PAGES=self.list, **self.net.env())
        e.update(env)
        run = subprocess.run([sys.executable, SAVER] + list(args), env=e, capture_output=True, text=True, timeout=120)
        return run.returncode, run.stdout + run.stderr

    def path(self, *parts):
        return os.path.join(self.kit, "documents", FOLDER, *parts)

    def read(self, *parts):
        with open(self.path(*parts), encoding="utf-8") as f:
            return f.read()

    def files(self, *parts):
        return sorted(os.listdir(self.path(*parts)))

    def close(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class SaverTestCase(unittest.TestCase):
    def setUp(self):
        self.net = internet()
        self.saver = Saver(self.net)
        self.addCleanup(self.net.stop)
        self.addCleanup(self.saver.close)


class SavedTextTest(SaverTestCase):
    def setUp(self):
        super().setUp()
        self.code, self.out = self.saver.run()

    def test_each_guide_is_saved_as_text_named_after_its_source(self):
        self.assertEqual(self.code, 0, self.out)
        for name in UK:
            self.assertIn(name, self.saver.files(), name)

    def test_a_dovidka_advice_page_without_an_article_element_keeps_only_the_advice(self):
        t = self.saver.read(UK[0])
        self.assertTrue(t.startswith("# Що робити, коли почули сирени\n"), t[:80])   # the site's name is cut from the title
        self.assertIn("**Сигнал повітряної тривоги «Увага всім»** лунає", t)
        self.assertIn("\n- Негайно йдіть в укриття.\n- Візьміть тривожну валізу.\n", t)
        for noise in ("Пошук по сайту", "Підписатися", "ACCEPT ALL", "youtube", "Головна", "Поради"):
            self.assertNotIn(noise, t)

    def test_a_dovidka_article_keeps_its_structure(self):
        t = self.saver.read(UK[1])
        self.assertTrue(t.startswith("# Тактична медицина: як зупинити кровотечу\n"), t[:80])
        self.assertIn("Сильна кровотеча вбиває за кілька хвилин. Діяти треба одразу.", t)   # a no-break space is a plain space
        self.assertIn("\n## Як зупинити сильну кровотечу\n", t)   # the page's own title sits below the guide's
        self.assertIn("\n### Джгут\n", t)
        self.assertIn("\n#### Що ще\n", t)
        self.assertIn("\n1. Накладіть джгут на **10 см** вище рани.\n", t)
        self.assertIn("\n  - Запишіть час.\n", t)
        self.assertIn("\n3. Не знімайте джгут.\n", t)
        self.assertIn("| Крок | Дія |", t)
        self.assertIn("| 1 | Подзвоніть 103 |", t)
        for noise in ("Поділитися", "TRACKER-NOISE", "Всі права", "Головна"):
            self.assertNotIn(noise, t)

    def test_the_ministry_of_health_page_keeps_the_article_container_only(self):
        t = self.saver.read(UK[2])
        self.assertTrue(t.startswith("# МОЗ нагадує: базові правила домедичної допомоги\n"), t[:80])
        self.assertIn("за номером «103» для виклику", t)
        self.assertIn("Підготовлений – значить захищений!", t)
        for noise in ("Читайте також", "Міністерство охорони", "Новини"):
            self.assertNotIn(noise, t)

    def test_the_public_health_center_page_keeps_the_news_content_only(self):
        t = self.saver.read(UK[3])
        self.assertTrue(t.startswith("# Як знезаразити воду та профілактика захворювань\n"), t[:90])   # the site's name is cut
        self.assertIn("**Кип’ятіння**. Це найбільш надійний спосіб.", t)
        self.assertIn("*Водоканал повідомляє про зупинку насосних станцій.*", t)
        for noise in ("Поділитися", "Про нас", "9 січня"):
            self.assertNotIn(noise, t)

    def test_the_red_cross_page_keeps_the_page_builder_content_only(self):
        t = self.saver.read(UK[4])
        self.assertTrue(t.startswith("# Мінна небезпека\n"), t[:60])
        self.assertIn("МІННА НЕБЕЗПЕКА", t)
        self.assertIn("зателефонуйте **101**", t)
        self.assertNotIn("COOKIE-NOISE", t)
        self.assertNotIn("Головна", t)

    def test_each_text_says_where_it_came_from_and_when_in_its_language(self):
        t = self.saver.read(UK[2])
        self.assertRegex(t, r"\nДжерело: МОЗ, %s\. Збережено \d{4}-\d\d-\d\d для читання без інтернету\.\n" % re.escape(MOZ))
        e = self.saver.read("en", "dovidka.info - Tactical medicine, how to stop bleeding.md")
        self.assertRegex(e, r"\nSource: dovidka\.info, %s\. Saved \d{4}-\d\d-\d\d for reading offline\.\n" % re.escape(BLEEDING_EN))

    def test_a_pdf_is_saved_as_the_pdf_itself(self):
        with open(self.saver.path(UK[5]), "rb") as f:
            got = f.read()
        with open(os.path.join(REPO, "tests", "internet", "leaflet.pdf"), "rb") as f:
            self.assertEqual(got, f.read())

    def test_the_cyrillic_in_a_pdf_address_is_percent_encoded_for_the_request(self):
        sent = [r[2] for r in self.net.requests if r[2].endswith(".pdf")]   # the stand-in decodes what it receives
        self.assertEqual(sent, ["/wp-content/uploads/2026/06/13_опіки.pdf"])

    def test_english_guides_are_saved_apart_from_the_ukrainian_ones(self):
        self.assertEqual(self.saver.files("en"), ["dovidka.info - Tactical medicine, how to stop bleeding.md"])
        self.assertNotIn("en", [f for f in self.saver.files() if f.endswith(".md")])
        self.assertTrue(self.saver.read("en", self.saver.files("en")[0]).startswith("# Tactical medicine: how to stop bleeding\n"))

    def test_the_manifest_marks_only_ukrainian_guides_for_the_ai_index(self):
        m = json.loads(self.saver.read("saved.json"))
        self.assertRegex(m["saved"], r"^\d{4}-\d\d-\d\d$")
        by = {g["file"]: g for g in m["guides"]}
        self.assertEqual(sorted(by), sorted(UK + ["en/dovidka.info - Tactical medicine, how to stop bleeding.md"]))
        self.assertTrue(by[UK[2]]["index"])
        self.assertTrue(by[UK[5]]["index"])
        en = by["en/dovidka.info - Tactical medicine, how to stop bleeding.md"]
        self.assertFalse(en["index"])
        self.assertEqual((en["language"], en["source"], en["url"]), ("en", "dovidka.info", BLEEDING_EN))


class RefusedTest(SaverTestCase):
    def test_an_optional_source_that_refuses_is_skipped_and_reported_and_everything_else_is_saved(self):
        code, out = self.saver.run()
        self.assertEqual(code, 0, out)   # a refusal from the State Emergency Service must not fail the install
        self.assertEqual(len(self.saver.files()) - 2, 6)   # saved.json, en/, and six guides; no ДСНС file
        self.assertFalse([f for f in self.saver.files() if f.startswith("ДСНС")])
        self.assertIn(DSNS, out)
        self.assertRegex(out, r"(?i)skipped")
        self.assertRegex(out, r"saved 7")   # six Ukrainian and one English
        self.assertNotIn("ДСНС - Безпека в умовах війни", [g["name"] for g in json.loads(self.saver.read("saved.json"))["guides"]])

    def test_a_required_source_that_is_gone_is_reported_failed_and_the_rest_is_still_saved(self):
        self.net.add(MOZ, 404, b"nothing here", "text/html")
        code, out = self.saver.run()
        self.assertEqual(code, 1, out)
        self.assertIn(MOZ, out)
        self.assertRegex(out, r"(?i)failed")
        self.assertNotIn(UK[2], self.saver.files())
        self.assertIn(UK[3], self.saver.files())

    def test_an_optional_source_that_answers_is_saved(self):
        # Inside Ukraine the State Emergency Service answers; its article is saved like the others.
        self.net.page(DSNS, "dovidka-article.html")
        code, out = self.saver.run()
        self.assertEqual(code, 0, out)
        self.assertIn("ДСНС - Безпека в умовах війни.md", self.saver.files())

    def test_a_page_with_no_article_in_it_is_not_saved_as_an_empty_guide(self):
        self.net.add(SIRENS, 200, b"<html><title>x</title><body><nav>Menu</nav><p>No article here</p></body></html>")
        code, out = self.saver.run()
        self.assertEqual(code, 1, out)
        self.assertNotIn(UK[0], self.saver.files())
        self.assertIn(SIRENS, out)


class UpdateTest(SaverTestCase):
    def test_saved_guides_are_not_fetched_again_unless_asked(self):
        self.saver.run()
        before = len(self.net.requests)
        code, out = self.saver.run()
        self.assertEqual(code, 0, out)
        asked = [r for r in self.net.requests[before:] if r[1] != "bezpeka.dsns.gov.ua"]
        self.assertEqual(asked, [])   # only the optional source that has nothing saved is tried again
        self.assertRegex(out, r"already there 7")
        code, out = self.saver.run("--refresh")
        self.assertEqual(code, 0, out)
        self.assertGreaterEqual(len(self.net.requests), before + 7)

    def test_a_failed_refresh_keeps_the_copy_already_saved(self):
        self.saver.run()
        old = self.saver.read(UK[2])
        self.net.add(MOZ, 404, b"gone", "text/html")
        code, out = self.saver.run("--refresh")
        self.assertEqual(code, 1, out)
        self.assertEqual(self.saver.read(UK[2]), old)

    def test_requests_are_polite_a_generic_client_name_and_a_pause_between(self):
        self.saver.run(EK_FETCH_PAUSE="0.15")
        agents = {r[3].get("User-Agent") for r in self.net.requests}
        self.assertEqual(len(agents), 1)
        agent = agents.pop()
        self.assertIn("EmergencyKit", agent)
        for private in (os.path.expanduser("~"), os.environ.get("USER", "-"), "@"):
            self.assertNotIn(private, agent)
        times = [r[4] for r in self.net.requests]
        gaps = [b - a for a, b in zip(times, times[1:])]
        self.assertGreaterEqual(min(gaps), 0.14)


class GuideListTest(unittest.TestCase):
    """The real list, config/pages.txt, against the real country config."""

    def text(self):
        with open(os.path.join(REPO, "config", "pages.txt"), encoding="utf-8") as f:
            return f.read()

    def lines(self):
        with open(os.path.join(REPO, "config", "pages.txt"), encoding="utf-8") as f:
            return [[p.strip() for p in l.split("#")[0].split("|")] for l in f if l.split("#")[0].strip()]

    def test_every_line_is_a_language_an_address_and_a_name_that_starts_with_a_source(self):
        with open(os.path.join(REPO, "config", "country.json"), encoding="utf-8") as f:
            ids = {s["id"] for s in json.load(f)["official_guides"]["sources"]}
        lines = self.lines()
        self.assertGreater(len(lines), 40)
        for lang, url, name in lines:
            self.assertIn(lang, ("uk", "en"), url)
            self.assertTrue(url.startswith("https://"), url)
            self.assertIn(name.split(" - ", 1)[0], ids, name)
        names = [(l, n) for l, _, n in lines]
        self.assertEqual(len(names), len(set(names)))

    def test_the_list_covers_the_sources_the_spec_names_and_the_handbook_in_both_languages(self):
        text = self.text()
        for host in ("dovidka.info", "moz.gov.ua", "phc.org.ua", "redcross.org.ua", "dsns.gov.ua"):
            self.assertIn("//" + host, text.replace("//bezpeka.", "//"))
        self.assertIn("todolist_war_ua_extended_web.pdf", text)
        self.assertIn("war-during-war-brochure-in-english-2024.pdf", text)

    def test_no_unofficial_mirror_is_in_the_list(self):
        text = self.text()
        for mirror in ("optum", "scribd"):
            self.assertNotIn(mirror, text)

    def test_every_ukrainian_topic_of_the_ticket_is_covered_by_a_ukrainian_guide(self):
        names = " ".join(n for l, _, n in self.lines() if l == "uk")
        for word in ("сирени", "Укриття", "Росіяни обстрілюють", "У зоні бойових дій", "Мінна безпека", "Блекаут",
                     "Як очистити воду", "кишковим інфекціям", "радіаційної аварії", "домедичної допомоги"):
            self.assertIn(word, names)


if __name__ == "__main__":
    unittest.main()
