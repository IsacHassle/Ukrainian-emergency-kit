"""Making a Kit Drive (Seam 2): scripts/make-kit-drive.sh run from an installed test kit into a test folder that
stands in for the USB drive. The free space, the drive's size and its format are faked the way the installer
test fakes them. Nothing is written to a real drive, and the real Ollama model folder is never read: the test
brings its own, holding a `crisis` model too."""
import hashlib
import json
import os
import re
import shutil
import tempfile
import unittest

from installkit import InstallKit
from test_installer import bilingual, lines

DRIVE_FOLDER = "Emergency-Kit-Drive"


def files_under(folder):
    out = []
    for base, _, names in os.walk(folder):
        for n in names:
            out.append(os.path.relpath(os.path.join(base, n), folder))
    return sorted(out)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class KitDriveCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kit = InstallKit()
        assert cls.kit.install().returncode == 0
        cls.store, cls.kit_digests, cls.other_digests = cls.kit.fake_model_store()

    @classmethod
    def tearDownClass(cls):
        cls.kit.stop()

    def setUp(self):
        self.drive = tempfile.mkdtemp(prefix="ek-drive-")
        self.addCleanup(shutil.rmtree, self.drive, True)
        self.out = os.path.join(self.drive, DRIVE_FOLDER)


class Making(KitDriveCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.drive0 = tempfile.mkdtemp(prefix="ek-drive-")
        cls.result = cls.kit.make_drive(cls.drive0, cls.store)
        cls.out0 = os.path.join(cls.drive0, DRIVE_FOLDER)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.drive0, True)
        super().tearDownClass()

    def test_it_succeeds_with_messages_in_both_languages(self):
        self.assertEqual(self.result.returncode, 0, self.result.stdout + self.result.stderr)
        bilingual(self, self.result.stdout)
        self.assertIn("Готово / Done", self.result.stdout)

    def test_the_drive_holds_every_item_of_the_spec(self):
        out, kit = self.out0, self.kit
        have = lambda *p: os.path.exists(os.path.join(out, *p))
        for name in os.listdir(kit.path("library")):
            self.assertTrue(have("kit", "library", name), name)
        self.assertTrue(have("kit", "maps", "ukraine.pmtiles"))
        self.assertTrue(have("kit", "web", "map", "data", "places.json.gz"))
        self.assertTrue(have("kit", "documents", "Official Guides", "saved.json"))
        self.assertTrue(have("kit", "install.sh"))
        self.assertTrue(have("kit", "scripts", "make-kit-drive.sh"))
        for app in ("Ollama", "AnythingLLM"):
            self.assertTrue(have("installers", app + ".dmg"))
        for name in ("LICENSE", "CREDITS.md"):
            self.assertTrue(have("licences", name), name)
        self.assertTrue(have("models", "manifests", "registry.ollama.ai", "library", "emergency", "latest"))
        self.assertTrue(have("checksums.sha256"))
        self.assertTrue(have("kit-drive.json"))

    def test_the_kit_folder_copy_leaves_out_logs_and_part_files(self):
        names = files_under(os.path.join(self.out0, "kit"))
        self.assertEqual([n for n in names if n.startswith(("logs/", ".git/", "node_modules/", "tools/venv/")) or n.endswith(".part")], [])

    def test_the_checksum_list_covers_every_file_and_matches(self):
        listed = {}
        with open(os.path.join(self.out0, "checksums.sha256"), encoding="utf-8") as f:
            for line in f:
                digest, path = re.match(r"([0-9a-f]{64})  (.+)\n?$", line).groups()
                listed[path] = digest
        on_drive = [n for n in files_under(self.out0) if n != "checksums.sha256"]
        self.assertEqual(sorted(listed), on_drive)
        for path, digest in listed.items():
            self.assertEqual(sha256(os.path.join(self.out0, path)), digest, path)

    def test_the_marker_says_what_the_drive_is(self):
        with open(os.path.join(self.out0, "kit-drive.json"), encoding="utf-8") as f:
            marker = json.load(f)
        self.assertEqual(marker["format"], 1)
        self.assertEqual(sorted(marker["models"]), ["bge-m3:latest", "emergency-small:latest", "emergency:latest"])

    def test_only_the_kits_own_models_are_copied(self):
        store = os.path.join(self.out0, "models")
        blobs = {"sha256:" + n[len("sha256-"):] for n in os.listdir(os.path.join(store, "blobs"))}
        self.assertEqual(blobs, self.kit_digests)
        self.assertEqual(blobs & self.other_digests, set())
        library = os.path.join(store, "manifests", "registry.ollama.ai", "library")
        self.assertEqual(sorted(os.listdir(library)), ["bge-m3", "emergency", "emergency-small"])

    def test_running_it_again_is_fine(self):
        again = self.kit.make_drive(self.drive0, self.store)
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)


class Refusals(KitDriveCase):
    def refused(self, extra=None, store="default"):
        r = self.kit.make_drive(self.drive, self.store if store == "default" else store, extra)
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertFalse(os.path.exists(self.out), "nothing is copied after a refusal")
        for line in lines(r.stdout):
            self.assertIn(" / ", line)
        return r.stdout

    def test_too_little_free_space_is_refused_before_copying(self):
        out = self.refused({"EK_FREE_GB": "0"})
        self.assertRegex(out, r"вільно .* ГБ.* / .*GB free")

    def test_a_drive_below_64_gb_is_refused(self):
        out = self.refused({"EK_DRIVE_GB": "32", "EK_FREE_GB": "30"})
        self.assertIn("64", out)

    def test_a_drive_that_is_not_exfat_is_refused(self):
        out = self.refused({"EK_DRIVE_FS": "MS-DOS FAT32"})
        self.assertIn("exFAT", out)

    def test_exfat_is_accepted(self):
        r = self.kit.make_drive(self.drive, self.store, {"EK_DRIVE_FS": "ExFAT"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_missing_model_is_refused_before_copying(self):
        empty = tempfile.mkdtemp(prefix="ek-models-")
        self.addCleanup(shutil.rmtree, empty, True)
        out = self.refused(store=empty)
        self.assertIn("emergency", out)

    def test_a_missing_destination_is_refused(self):
        r = self.kit.make_drive(os.path.join(self.drive, "nope"), self.store)
        self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
