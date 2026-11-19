"""Seam 2, the Book index: scripts/embed-documents.sh run on a copy of the kit's scripts in a temporary folder
against the stand-in Book index app (AnythingLLM). Checks what goes into the Book index workspace."""
import os
import shutil
import subprocess
import tempfile
import unittest

from servedkit import REPO
from standins import StandInAI


class BookIndexTest(unittest.TestCase):
    def setUp(self):
        self.ai = StandInAI().start()
        self.kit = tempfile.mkdtemp(prefix="ek-books-")
        for folder in ("scripts", "config"):
            shutil.copytree(os.path.join(REPO, folder), os.path.join(self.kit, folder))
        guides = os.path.join(self.kit, "documents", "Official Guides")
        for rel, text in {
            "dovidka.info - Укриття.md": "# Укриття\n",
            "МОЗ - Йодна профілактика.md": "# Йод\n",
            "en/dovidka.info - Shelter.md": "# Shelter\n",
        }.items():
            os.makedirs(os.path.dirname(os.path.join(guides, rel)), exist_ok=True)
            with open(os.path.join(guides, rel), "w", encoding="utf-8") as f:
                f.write(text)
        books = os.path.join(self.kit, "documents", "library", "Medical Library")
        os.makedirs(books)
        with open(os.path.join(books, "Where there is no Doctor.pdf"), "wb") as f:
            f.write(b"%PDF-1.4\n%%EOF\n")
        self.ai.store_add("Rädda-livet-sv-0000.json")   # another kit's file, already in the shared store

    def tearDown(self):
        self.ai.stop()
        shutil.rmtree(self.kit, ignore_errors=True)

    def embed(self):
        env = dict(os.environ, EK_ANYTHINGLLM="127.0.0.1:%d" % self.ai.anythingllm_port)
        return subprocess.run(["bash", os.path.join(self.kit, "scripts", "embed-documents.sh")], env=env, cwd=self.kit,
                              capture_output=True, text=True, timeout=120)

    def test_only_ukrainian_guides_and_the_books_go_into_the_book_index(self):
        run = self.embed()
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual(sorted(self.ai.uploads), ["Where there is no Doctor.pdf", "dovidka.info - Укриття.md", "МОЗ - Йодна профілактика.md"])
        indexed = self.ai.embedded["emergency-kit"]
        self.assertEqual(len(indexed), 3)
        self.assertFalse(any("Shelter" in d for d in indexed), indexed)   # the English guide is for reading only

    def test_another_kits_files_in_the_shared_store_are_never_embedded(self):
        self.embed()
        self.assertFalse(any("Rädda" in d for d in self.ai.embedded["emergency-kit"]))
        self.assertEqual(set(self.ai.embedded), {"emergency-kit"})   # no other workspace is written to

    def test_a_second_run_uploads_nothing_again(self):
        self.embed()
        self.embed()
        self.assertEqual(len(self.ai.uploads), 3)

    def test_every_line_of_the_log_holds_both_languages_and_update_can_count_uploads(self):
        self.embed()
        with open(os.path.join(self.kit, "logs", "embed.log"), encoding="utf-8") as f:
            lines = [l for l in f.read().splitlines() if l.strip()]
        self.assertTrue(lines)
        for line in lines:
            self.assertIn(" / ", line, line)
        self.assertEqual(sum(" / UPLOADED " in l for l in lines), 3)   # scripts/update.sh counts these

    def test_without_the_book_index_app_the_message_is_one_line_in_both_languages(self):
        env = dict(os.environ, EK_ANYTHINGLLM="127.0.0.1:1")
        run = subprocess.run(["bash", os.path.join(self.kit, "scripts", "embed-documents.sh")], env=env, cwd=self.kit,
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(run.returncode, 1)
        with open(os.path.join(self.kit, "logs", "embed.log"), encoding="utf-8") as f:
            log = f.read()
        self.assertIn("не запущено. Відкрийте його й спробуйте знову / AnythingLLM is not running", log)


if __name__ == "__main__":
    unittest.main()
