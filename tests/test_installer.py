"""The installer (Seam 2): install.sh run on a copy of the repo in a temporary folder, with stand-in downloads
(tests/installkit.py). Nothing is installed on the real Mac."""
import os
import re
import unittest

from installkit import InstallKit


def lines(text):
    return [l for l in text.splitlines() if l.strip()]


class Refusals(unittest.TestCase):
    def tearDown(self):
        self.kit.stop()

    def test_refuses_a_mac_without_apple_silicon(self):
        self.kit = InstallKit(uname_m="x86_64", ai=False)
        r = self.kit.install()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Apple", r.stdout)
        self.assertRegex(r.stdout, r"Потрібен Mac з чипом Apple.* / .*needs a Mac with an Apple chip")
        self.assertFalse(os.path.exists(self.kit.path("tools")), "nothing is downloaded before the refusal")

    def test_refuses_below_55_gb_free(self):
        self.kit = InstallKit(free_gb=54, ai=False)
        r = self.kit.install()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("54", r.stdout)
        self.assertIn("55", r.stdout)
        self.assertFalse(os.path.exists(self.kit.path("tools")))

    def test_accepts_exactly_55_gb(self):
        self.kit = InstallKit(free_gb=55, uname_m="x86_64", ai=False)   # past the space check, stopped by the chip
        r = self.kit.install()
        self.assertNotIn("Вільно", r.stdout)


NO_WORDS = re.compile(r"^(GET|OK)\s")   # status lines of the Library download that carry only a file name


def bilingual(testcase, text):
    for line in lines(text):
        if NO_WORDS.match(line) or line.startswith("  "):   # indented: a tool's own output
            continue
        testcase.assertIn(" / ", line, "a message in one language only: " + line)


class FullInstall(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kit = InstallKit()
        cls.result = cls.kit.install()

    @classmethod
    def tearDownClass(cls):
        cls.kit.stop()

    def test_it_succeeds_and_every_message_has_both_languages(self):
        self.assertEqual(self.result.returncode, 0, self.result.stdout + self.result.stderr)
        bilingual(self, self.result.stdout)
        self.assertIn("Готово / Done", self.result.stdout)

    def test_the_kit_folder_is_complete(self):
        kit = self.kit
        self.assertTrue(os.access(kit.path("tools", "kiwix-tools", "kiwix-serve"), os.X_OK))
        self.assertTrue(os.access(kit.path("tools", "pmtiles"), os.X_OK))
        self.assertTrue(os.path.exists(kit.path("tools", "venv", "bin", "python")))
        with open(kit.path("config", "libraries.txt"), encoding="utf-8") as f:
            wanted = [l.split("#")[0].split()[0] for l in f if l.split("#")[0].strip()]
        have = sorted(os.listdir(kit.path("library")))
        self.assertEqual(have, sorted(os.path.basename(u) for u in wanted))
        for name in ("world", "ukraine"):
            with open(kit.path("maps", name + ".pmtiles"), "rb") as f:
                self.assertEqual(f.read(7), b"PMTiles")
        self.assertTrue(os.path.exists(kit.path("web", "map", "data", "places.json.gz")))
        self.assertTrue(os.path.exists(kit.path("documents", "Official Guides", "saved.json")))
        self.assertTrue(os.path.exists(kit.path("documents", "Тривожна валіза - посібник.md")))
        self.assertTrue(os.path.exists(kit.path("documents", "Emergency Kit - guide.md")))

    def test_it_never_leaves_part_files(self):
        for folder in ("library", "maps", "installers"):
            self.assertEqual([n for n in os.listdir(self.kit.path(folder)) if n.endswith(".part")], [])

    def test_the_desktop_shortcut_is_named_after_the_kit(self):
        link = os.path.join(self.kit.home, "Desktop", "Тривожна валіза")
        self.assertTrue(os.path.islink(link))
        self.assertEqual(os.path.realpath(link), os.path.realpath(self.kit.kit))

    def test_the_app_installers_are_kept_for_kit_drives(self):
        for app in ("Ollama", "AnythingLLM"):
            self.assertGreater(os.path.getsize(self.kit.path("installers", app + ".dmg")), 0)
            self.assertTrue(os.path.isdir(os.path.join(self.kit.apps, app + ".app")), "installed into the apps folder")

    def test_the_ai_uses_the_kits_own_names_and_never_the_swedish_kits(self):
        calls = "\n".join(self.kit.calls())
        self.assertIn("ollama create emergency ", calls)
        self.assertIn("ollama create emergency-small ", calls)
        sent = repr(self.kit.ai.setup_posts)
        self.assertIn("/api/workspace/emergency-kit/update", sent)
        for text in (calls, sent):
            self.assertNotIn("crisis", text)

    def test_the_book_index_got_the_books_of_this_kit_only(self):
        self.assertGreater(len(self.kit.ai.uploads), 0)
        self.assertEqual(list(self.kit.ai.embedded), ["emergency-kit"])


class Resume(unittest.TestCase):
    def test_running_it_again_downloads_nothing_it_already_has(self):
        kit = InstallKit()
        try:
            self.assertEqual(kit.install().returncode, 0)
            before = kit.calls()
            again = kit.install()
            self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
            new = kit.calls()[len(before):]
            self.assertEqual([c for c in new if c.endswith((".zim", ".dmg", ".tar.gz", ".zip"))], [])
            self.assertIn("вже є / already there", again.stdout)
        finally:
            kit.stop()


class WithoutTheAI(unittest.TestCase):
    def test_no_ai_installs_no_apps_and_asks_for_less_space(self):
        kit = InstallKit(free_gb=30, ai=False)
        try:
            r = kit.install("--no-ai")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(os.listdir(kit.apps), [])
            self.assertFalse(os.path.exists(kit.path("installers", "Ollama.dmg")))
            bilingual(self, r.stdout)
        finally:
            kit.stop()


class Start(unittest.TestCase):
    def test_start_without_libraries_says_to_install_first_in_both_languages(self):
        kit = InstallKit(ai=False)
        try:
            r = kit.run("scripts/share-library.sh")
            self.assertNotEqual(r.returncode, 0)
            self.assertRegex(r.stdout, r"Спершу встановіть валізу.* / No Libraries found")
        finally:
            kit.stop()


class Check(unittest.TestCase):
    """Check (scripts/check.sh) on an installed kit: what it reports, in both languages."""

    @classmethod
    def setUpClass(cls):
        cls.kit = InstallKit()
        assert cls.kit.install().returncode == 0
        # The installed kit is tiny: give it the amount of Books a real one has, and the stand-in AI the answer
        # the test question expects (the planning reply is what the stand-in Ollama answers to a plain question).
        for i in range(101):
            path = cls.kit.path("documents", "library", "Water Treatment", "book%d.md" % i)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write("x")
        os.makedirs(cls.kit.path("documents", "Official Guides"), exist_ok=True)
        with open(cls.kit.path("documents", "Official Guides", "x.pdf"), "w") as f:
            f.write("%PDF")
        cls.kit.ai.plan_reply = "112"
        cls.kit.ai.embedded["emergency-kit"] = ["d%d" % i for i in range(101)]
        cls.devs = os.path.join(cls.kit.root, "dev")
        os.makedirs(cls.devs)

    @classmethod
    def tearDownClass(cls):
        cls.kit.stop()

    def check(self, **extra):
        env = {"EK_DEV": self.devs}
        env.update(extra)
        return self.kit.run("scripts/check.sh", extra=env)

    def test_a_working_kit_says_so_in_both_languages(self):
        r = self.check()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("Усе працює", r.stdout)
        self.assertIn("Everything works", r.stdout)
        self.assertNotIn("⚠", r.stdout)
        for line in lines(r.stdout):
            if line.lstrip().startswith(("✅", "⚠", "ℹ")):
                self.assertIn(" / ", line)
        self.assertIn("The AI answers", r.stdout)

    def test_it_names_what_is_missing(self):
        os.rename(self.kit.path("maps", "ukraine.pmtiles"), self.kit.path("maps", "gone.pmtiles"))
        stem = sorted(os.listdir(self.kit.path("library")))[0]
        os.rename(self.kit.path("library", stem), self.kit.path("library", stem + ".gone"))
        try:
            r = self.check()
        finally:
            os.rename(self.kit.path("maps", "gone.pmtiles"), self.kit.path("maps", "ukraine.pmtiles"))
            os.rename(self.kit.path("library", stem + ".gone"), self.kit.path("library", stem))
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stdout, r"⚠️\s+Мапи ukraine немає.* / The map ukraine is missing")
        self.assertRegex(r.stdout, r"⚠️\s+Бібліотек є \d+ з \d+\. Бракує:.* / \d+ of \d+ Libraries are there\. Missing:")
        self.assertIn("need attention", r.stdout)

    def test_a_missing_model_is_reported(self):
        r = self.check(EK_FAKE_MODELS="gemma4:26b bge-m3 emergency")
        self.assertRegex(r.stdout, r"Моделі ШІ emergency-small немає.* / The AI model emergency-small is missing")

    def test_a_usb_gps_receiver_is_noticed(self):
        open(os.path.join(self.devs, "cu.usbmodem1101"), "w").close()
        try:
            r = self.check()
        finally:
            os.remove(os.path.join(self.devs, "cu.usbmodem1101"))
        self.assertIn("USB GPS-приймач підключено", r.stdout)
        self.assertIn("A USB GPS receiver is connected", r.stdout)


if __name__ == "__main__":
    unittest.main()
