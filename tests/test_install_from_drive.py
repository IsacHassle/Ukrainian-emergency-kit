"""Installing from a Kit Drive (Seam 2): a test Kit Drive is made from an installed test kit, then installed on a
"second Mac": its own HOME, its own Ollama model folder and its own Book index storage (a second stand-in AI),
with every download attempt failing loudly. Nothing here touches the real Mac."""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from installkit import InstallKit
from test_installer import bilingual, lines
from test_kit_drive import DRIVE_FOLDER, files_under, sha256

MODELS = ["bge-m3:latest", "emergency-small:latest", "emergency:latest"]


class DriveCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = InstallKit()   # the Kit Mac that makes the drive
        assert cls.source.install().returncode == 0
        cls.store, _, _ = cls.source.fake_model_store()
        cls.master = tempfile.mkdtemp(prefix="ek-drive-")
        r = cls.source.make_drive(cls.master, cls.store)
        assert r.returncode == 0, r.stdout + r.stderr

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.master, True)
        cls.source.stop()

    def setUp(self):
        # Each test gets its own copy of the drive and its own second Mac.
        self.drive_root = tempfile.mkdtemp(prefix="ek-drive-copy-")
        self.addCleanup(shutil.rmtree, self.drive_root, True)
        self.drive = os.path.join(self.drive_root, DRIVE_FOLDER)
        shutil.copytree(os.path.join(self.master, DRIVE_FOLDER), self.drive)
        self.mac = InstallKit()
        self.addCleanup(self.mac.stop)
        # The second Mac has its own Ollama model folder, with a model of its own already in it.
        self.models = os.path.join(self.mac.root, "its-ollama-models")
        self.own = os.path.join(self.models, "manifests", "registry.ollama.ai", "library", "llama3", "8b")
        os.makedirs(os.path.dirname(self.own))
        with open(self.own, "w") as f:
            f.write('{"its": "own"}')

    def install(self, *args):
        return self.mac.install_from_drive(self.drive, *args, models=self.models)

    def stored(self):
        return sorted(files_under(self.models))


class Installing(DriveCase):
    def setUp(self):
        super().setUp()
        self.result = self.install()

    def test_it_succeeds_with_messages_in_both_languages(self):
        self.assertEqual(self.result.returncode, 0, self.result.stdout + self.result.stderr)
        bilingual(self, self.result.stdout)
        self.assertIn("Готово / Done", self.result.stdout)

    def test_nothing_was_downloaded(self):
        calls = self.mac.calls()
        self.assertEqual([c for c in calls if c.startswith("curl")], [], "the install asked the internet for something")
        self.assertEqual([c for c in calls if c.startswith("ollama pull")], [])
        self.assertNotIn("NO INTERNET", self.result.stdout + self.result.stderr)
        self.assertEqual(self.mac.net.requests, [])

    def test_the_kit_is_copied_complete_and_runs_from_its_home(self):
        kit, src = self.mac.kit, os.path.join(self.drive, "kit")
        for rel in files_under(src):
            self.assertEqual(sha256(os.path.join(kit, rel)), sha256(os.path.join(src, rel)), rel)
        self.assertFalse(os.path.exists(os.path.join(kit, "tools", "venv")), "the venv is not on the drive")
        for app in ("Ollama", "AnythingLLM"):
            self.assertTrue(os.path.exists(os.path.join(kit, "installers", app + ".dmg")), app)
        for rel in ("install.sh", "scripts/serve-web.py", "tools/pmtiles", "tools/kiwix-tools/kiwix-serve"):
            self.assertTrue(os.access(os.path.join(kit, rel), os.X_OK), rel + " must be executable again (exFAT drops permissions)")
        self.assertTrue(os.access(os.path.join(kit, "Запустити - Start.command"), os.X_OK))
        self.assertTrue(os.path.exists(os.path.join(kit, "maps", "ukraine.pmtiles")))
        self.assertTrue(os.path.islink(os.path.join(self.mac.home, "Desktop", "Тривожна валіза")))

    def test_the_apps_are_installed_from_the_drive(self):
        for app in ("Ollama", "AnythingLLM"):
            self.assertTrue(os.path.isdir(os.path.join(self.mac.apps, app + ".app")), app)

    def test_the_models_are_in_the_ollama_folder_and_ollama_lists_them(self):
        for name in ("emergency", "emergency-small", "bge-m3"):
            self.assertTrue(os.path.exists(os.path.join(self.models, "manifests", "registry.ollama.ai", "library", name, "latest")), name)
        for blob in os.listdir(os.path.join(self.drive, "models", "blobs")):
            self.assertEqual(sha256(os.path.join(self.models, "blobs", blob)), sha256(os.path.join(self.drive, "models", "blobs", blob)))
        listed = subprocess.run(["ollama", "list"], env=self.mac.env({"OLLAMA_MODELS": self.models}), capture_output=True, text=True).stdout
        for m in MODELS + ["llama3:8b"]:
            self.assertIn(m, listed)
        self.assertIn("ollama list", self.mac.calls())

    def test_what_was_in_the_ollama_folder_is_left_alone(self):
        with open(self.own) as f:
            self.assertEqual(f.read(), '{"its": "own"}')

    def test_the_book_index_is_built_on_this_mac(self):
        ai = self.mac.ai
        self.assertEqual(list(ai.embedded), ["emergency-kit"])
        self.assertGreater(len(ai.embedded["emergency-kit"]), 0)
        self.assertGreater(len(ai.uploads), 0)
        # Its storage is its own: the Kit Mac that made the drive uploaded into another one.
        self.assertNotEqual(ai.storage, self.source.ai.storage)
        self.assertTrue(os.path.exists(os.path.join(self.mac.kit, "logs", "embed-uploaded.txt")))

    def test_the_drive_itself_is_unchanged(self):
        master = os.path.join(self.master, DRIVE_FOLDER)
        self.assertEqual(files_under(self.drive), files_under(master))
        with open(os.path.join(self.drive, "checksums.sha256"), encoding="utf-8") as f:
            for line in f:
                digest, path = re.match(r"([0-9a-f]{64})  (.+)\n?$", line).groups()
                self.assertEqual(sha256(os.path.join(self.drive, path)), digest, path)

    def test_running_it_again_is_fine_and_still_offline(self):
        r = subprocess.run(["bash", os.path.join(self.drive, "kit", "install.sh")], cwd=self.mac.root,
                           env=self.mac.env({"EK_NO_INTERNET": "1", "EK_FAKE_DOWNLOADS": os.path.join(self.mac.root, "nothing-here"),
                                             "OLLAMA_MODELS": self.models}), capture_output=True, text=True, timeout=300)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual([c for c in self.mac.calls() if c.startswith("curl")], [])


class Damaged(DriveCase):
    def stops_with_one_line_naming(self, path, word_uk, word_en):
        r = self.install()
        self.assertNotEqual(r.returncode, 0, r.stdout)
        said = [l for l in lines(r.stdout) if path in l]
        self.assertEqual(len(said), 1, r.stdout)
        self.assertRegex(said[0], "(?i)" + word_uk + r".* / .*" + word_en)
        bilingual(self, r.stdout)
        # Nothing was copied, installed or placed.
        self.assertFalse(os.path.exists(self.mac.kit), "no kit folder after a failed check")
        self.assertEqual(os.listdir(self.mac.apps), [])
        self.assertEqual(self.stored(), ["manifests/registry.ollama.ai/library/llama3/8b"])
        self.assertEqual([c for c in self.mac.calls() if c.startswith("curl")], [])
        return r

    def test_a_changed_file(self):
        rel = "kit/config/country.json"
        with open(os.path.join(self.drive, rel), "ab") as f:
            f.write(b" ")
        self.stops_with_one_line_naming(rel, "змінено", "changed")

    def test_a_changed_model_file(self):
        blob = sorted(os.listdir(os.path.join(self.drive, "models", "blobs")))[0]
        rel = "models/blobs/" + blob
        with open(os.path.join(self.drive, rel), "wb") as f:
            f.write(b"bad")
        self.stops_with_one_line_naming(rel, "змінено", "changed")

    def test_a_missing_file(self):
        rel = "kit/scripts/check.sh"
        os.remove(os.path.join(self.drive, rel))
        self.stops_with_one_line_naming(rel, "немає", "missing")

    def test_an_extra_file(self):
        rel = "kit/scripts/extra.sh"
        with open(os.path.join(self.drive, rel), "w") as f:
            f.write("echo hi")
        self.stops_with_one_line_naming(rel, "Зайвий", "extra")

    def test_a_missing_checksum_list(self):
        os.remove(os.path.join(self.drive, "checksums.sha256"))
        self.stops_with_one_line_naming("checksums.sha256", "немає", "missing")


class Existing(DriveCase):
    def test_a_model_the_mac_already_has_is_not_overwritten(self):
        mine = os.path.join(self.models, "manifests", "registry.ollama.ai", "library", "emergency", "latest")
        os.makedirs(os.path.dirname(mine))
        with open(mine, "w") as f:
            f.write("my own emergency model")
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(mine) as f:
            self.assertEqual(f.read(), "my own emergency model")

    def test_a_mac_that_is_not_apple_silicon_is_refused_before_anything(self):
        self.mac.uname_m = "x86_64"
        r = self.install()
        self.assertNotEqual(r.returncode, 0)
        self.assertRegex(r.stdout, r"Потрібен Mac з чипом Apple.* / .*Apple chip")
        self.assertEqual(self.stored(), ["manifests/registry.ollama.ai/library/llama3/8b"])


if __name__ == "__main__":
    unittest.main()
