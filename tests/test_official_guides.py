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
import urllib.request

from servedkit import REPO, ServedKit
from standins import StandInInternet
from test_emergency_topics import EN as LIB_EN, UK as LIB_UK, item, viewer

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

    def test_a_server_that_stumbles_is_asked_again(self):
        self.net.stumble(MOZ, 2)
        code, out = self.saver.run()
        self.assertEqual(code, 0, out)
        self.assertIn(UK[2], self.saver.files())
        self.assertEqual(len([r for r in self.net.requests if r[2].endswith("domedichnoi-dopomogi")]), 3)

    def test_a_page_that_is_gone_is_not_asked_again(self):
        self.net.add(MOZ, 404, b"gone", "text/html")
        self.saver.run()
        self.assertEqual(len([r for r in self.net.requests if r[2].endswith("domedichnoi-dopomogi")]), 1)

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


class LinkCheckTest(SaverTestCase):
    """The weekly link check reads the same list: gone is a problem, refused is only a note, moved is a warning."""

    def check(self):
        run = subprocess.run([sys.executable, os.path.join(REPO, "scripts", "check-links.py"), "--guides"],
                             env=dict(os.environ, EK_PAGES=self.saver.list, **self.net.env()), capture_output=True, text=True, timeout=120)
        return run.returncode, run.stdout + run.stderr

    def test_all_answering_and_the_optional_source_refusing_passes_and_says_refused(self):
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertRegex(out, r"(?i)refused.*%s" % re.escape(DSNS))
        self.assertNotIn("PROBLEM", out)
        self.assertNotIn("WARNING", out)

    def test_a_guide_that_is_gone_is_a_problem(self):
        self.net.add(PHC, 404, b"nothing", "text/html")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertRegex(out, r"PROBLEM.*%s" % re.escape(PHC))

    def test_an_optional_guide_that_is_gone_is_only_a_warning(self):
        self.net.add(DSNS, 404, b"nothing", "text/html")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertRegex(out, r"WARNING.*%s" % re.escape(DSNS))

    def test_a_guide_that_redirects_to_another_page_is_a_warning(self):
        self.net.redirect(MOZ, "http://moz.gov.ua/uk/news")
        self.net.page("http://moz.gov.ua/uk/news", "moz.html")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertRegex(out, r"WARNING.*%s" % re.escape(MOZ))

    def test_a_required_source_that_refuses_is_a_warning_not_a_problem(self):
        self.net.refuse(MOZ)
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertRegex(out, r"WARNING.*%s" % re.escape(MOZ))


def read(kit, path="/"):
    with urllib.request.urlopen(kit.url + path, timeout=10) as r:
        return r.read().decode("utf-8")


def blocks(page, tag, lang):
    return re.findall(r'<%s data-l="%s"[^>]*>.*?</%s>' % (tag, lang, tag), page, re.S)


class StartPageGuidesTest(unittest.TestCase):
    """The start page over a test kit with a few saved guides (tests/servedkit.py): Emergency Topics open their
    Official Guide first, in the page's language, then the article; the list of guides follows the page language."""

    @classmethod
    def setUpClass(cls):
        cls.kit = ServedKit()
        cls.kit.start()
        cls.page = read(cls.kit)

    @classmethod
    def tearDownClass(cls):
        cls.kit.stop()

    def li(self, label, lang):
        return item(self.page, label, lang)

    def test_a_topic_opens_its_ukrainian_guide_in_the_reader_first_then_the_article(self):
        li = self.li("Сильна кровотеча, джгут", "uk")
        self.assertIn('href="las/?f=docs/Official%20Guides/dovidka.info%20-%20%D0%A2%D0%B0%D0%BA%D1%82%D0%B8%D1%87%D0%BD%D0%B0', li)
        self.assertLess(li.index("las/?f="), li.index("data-k="))
        self.assertIn("dovidka.info</small>", li)   # it names its source
        self.assertIn('data-t="home.urgent.article"', li)
        self.assertIn(viewer(LIB_UK, "Зупинка_кровотечі"), li)

    def test_the_english_page_opens_the_english_guide_and_never_a_ukrainian_one(self):
        li = self.li("Сильна кровотеча, джгут", "en")
        self.assertIn('href="las/?f=docs/Official%20Guides/en/dovidka.info%20-%20Tactical%20medicine', li)
        self.assertIn(viewer(LIB_EN, "Bleeding"), li)
        for page_li in blocks(self.page, "li", "en"):
            self.assertNotIn("%D0%", re.sub(r"data-k=\"[^\"]*\"", "", page_li), page_li)   # no Cyrillic address in a guide link

    def test_a_topic_with_no_english_guide_opens_the_english_article_only(self):
        self.assertIsNone(self.li("Переохолодження", "en"))   # no English guide and no article in the test Library
        li = self.li("Серцево-легенева реанімація", "en")
        self.assertIn("Rescue%20is%20in%20our%20hands", li)   # CPR has an English guide, then the article
        self.assertIn(viewer(LIB_EN, "Cardiopulmonary_resuscitation"), li)

    def test_when_the_first_guide_is_not_saved_the_next_one_opens(self):
        li = self.li("Переохолодження", "uk")   # the Public Health Center page is not saved, the Red Cross leaflet is
        self.assertIn('href="docs/Official%20Guides/%D0%A7%D0%B5%D1%80%D0%B2%D0%BE%D0%BD%D0%B8%D0%B9%20%D0%A5%D1%80%D0%B5%D1%81%D1%82%20-', li)
        self.assertIn(".pdf", li)   # a PDF opens as the PDF, not in the reader
        self.assertNotIn("las/?f=", li)

    def test_the_start_page_never_writes_a_python_tuple_as_an_address(self):
        self.assertNotIn('href="(', self.page)
        self.assertNotIn("None", self.page)
        for href in re.findall(r'href="([^"]*)"', self.page):
            self.assertNotIn("%27", href)

    def test_the_list_of_official_guides_follows_the_page_language(self):
        uk = " ".join(blocks(self.page, "div", "uk"))
        en = " ".join(blocks(self.page, "div", "en"))
        self.assertIn("Як надати допомогу пораненому", uk)
        self.assertIn("Переохолодження, перша допомога", uk)
        self.assertNotIn("Tactical medicine", uk)
        self.assertIn("Tactical medicine, how to stop bleeding", en)
        self.assertIn("Rescue is in our hands", en)
        self.assertNotIn("Як надати", en)
        self.assertNotIn("Переохолодження", en)
        self.assertIn('href="las/?f=docs/Official%20Guides/en/', en)
        self.assertIn('href="docs/Official%20Guides/%D0%A7', uk)   # the PDF

    def test_the_summary_counts_the_guides_of_each_language(self):
        self.assertRegex(self.page, r'<span data-l="uk" data-t="home.guides.summary" data-p=\'\{"count": 3\}\'>')
        self.assertRegex(self.page, r'<span data-l="en" data-t="home.guides.summary" data-p=\'\{"count": 2\}\'>')

    def test_the_sources_are_headed_with_their_name_in_each_language(self):
        self.assertIn("dovidka.info · Укриття, війна, перша допомога", self.page)
        self.assertIn("dovidka.info · Shelter, war, first aid", self.page)


class ReaderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kit = ServedKit()
        cls.kit.start()

    @classmethod
    def tearDownClass(cls):
        cls.kit.stop()

    def test_the_reader_page_has_no_swedish_and_its_texts_are_keys(self):
        page = read(self.kit, "/las/")
        for swedish in ("Läs ", "Fråga AI", "Skriv ut", "Laddar", "Okänt", "hittades inte"):
            self.assertNotIn(swedish, page)
        self.assertIn('data-t="reader.', page)

    def test_a_saved_guide_in_either_language_is_served_for_the_reader(self):
        uk = read(self.kit, "/docs/Official%20Guides/dovidka.info%20-%20%D0%A2%D0%B0%D0%BA%D1%82%D0%B8%D1%87%D0%BD%D0%B0%20%D0%BC%D0%B5%D0%B4%D0%B8%D1%86%D0%B8%D0%BD%D0%B0%2C%20%D1%8F%D0%BA%20%D0%B7%D1%83%D0%BF%D0%B8%D0%BD%D0%B8%D1%82%D0%B8%20%D0%BA%D1%80%D0%BE%D0%B2%D0%BE%D1%82%D0%B5%D1%87%D1%83.md")
        self.assertIn("Натисніть на рану.", uk)
        en = read(self.kit, "/docs/Official%20Guides/en/dovidka.info%20-%20Tactical%20medicine%2C%20how%20to%20stop%20bleeding.md")
        self.assertIn("Press on the wound.", en)


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


class TopicGuidesConfigTest(unittest.TestCase):
    """Which Official Guide each Emergency Topic opens (the user's decisions: the English page never opens a
    Ukrainian guide)."""

    def config(self):
        with open(os.path.join(REPO, "config", "country.json"), encoding="utf-8") as f:
            return json.load(f)

    def check(self, config, with_list=True):
        with tempfile.TemporaryDirectory() as d:
            if with_list:
                shutil.copy(os.path.join(REPO, "config", "pages.txt"), d)
            path = os.path.join(d, "country.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False)
            run = subprocess.run([sys.executable, os.path.join(REPO, "scripts", "check-country.py"), path], capture_output=True, text=True)
            return run.returncode, run.stdout + run.stderr

    def test_the_real_config_and_list_agree(self):
        code, out = self.check(self.config())
        self.assertEqual(code, 0, out)

    def test_a_guide_name_that_is_not_in_the_list_is_refused_and_named(self):
        c = self.config()
        c["emergency_topics"][0]["official_guide"]["uk"] = ["dovidka.info - Немає такої сторінки"]
        code, out = self.check(c)
        self.assertNotEqual(code, 0)
        self.assertIn("emergency_topics[0].official_guide.uk", out)

    def test_an_english_topic_names_only_english_guides(self):
        lang = {}
        with open(os.path.join(REPO, "config", "pages.txt"), encoding="utf-8") as f:
            for l in f:
                parts = [x.strip() for x in l.split("#")[0].split("|")]
                if len(parts) == 3:
                    lang[parts[2]] = parts[0]
        for t in self.config()["emergency_topics"]:
            for code, names in t.get("official_guide", {}).items():
                for n in names:
                    self.assertEqual(lang[n], code, "%s opens %s on the %s page" % (t["id"], n, code))

    def test_the_topics_open_these_guides(self):
        got = {t["id"]: t.get("official_guide", {}) for t in self.config()["emergency_topics"]}
        self.assertEqual(got["hypothermia"].get("en"), None)   # no English guide exists: English WikiMed only
        self.assertEqual(got["mines"]["en"][0], "dovidka.info - A guide to handling the threat of mining")
        self.assertEqual(got["mines"]["uk"][0], "dovidka.info - Мінна безпека")
        self.assertEqual(got["co"]["en"], ["dovidka.info - Blackout"])
        self.assertEqual(got["bleeding"]["uk"][0], "dovidka.info - Тактична медицина, як зупинити кровотечу")
        self.assertEqual(got["cpr"]["uk"][0], "Червоний Хрест - Перша допомога, довідник для населення")
        self.assertEqual(set(got), {"bleeding", "blast", "crush", "cpr", "burns", "shock", "hypothermia", "co", "mines", "radiation"})


if __name__ == "__main__":
    unittest.main()
