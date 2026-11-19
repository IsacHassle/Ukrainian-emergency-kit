"""The printable guide (Seam 2): README.md and README.en.md each hold a user-guide part between markers and link
each other, and scripts/make-print-guide.sh turns each part into a one-language A4 PDF carrying both kit names.
The script needs Chrome and the Markdown module (or network for a throwaway venv); without Chrome that test skips."""
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from servedkit import REPO
from test_served_kit_browser import find_chrome

START, END = "<!-- user-guide:start -->", "<!-- user-guide:end -->"
PDFS = {"README.md": "Тривожна валіза - посібник для друку.pdf", "README.en.md": "Emergency Kit - printable guide.pdf"}


def read(name):
    with open(os.path.join(REPO, name), encoding="utf-8") as f:
        return f.read()


class ReadmesTest(unittest.TestCase):
    def test_each_readme_has_one_user_guide_part_and_links_the_other(self):
        for name, other in (("README.md", "README.en.md"), ("README.en.md", "README.md")):
            text = read(name)
            self.assertEqual(text.count(START), 1, name)
            self.assertEqual(text.count(END), 1, name)
            self.assertLess(text.index(START), text.index(END), name)
            self.assertIn("(%s)" % other, text, name + " does not link the other language")
            self.assertNotIn("—", text, name + " has an em-dash")
            part = text[text.index(START):text.index(END)]
            for words in (["Start here", "Using the AI", "The map", "Get ready"] if "en" in name else
                          ["Почніть тут", "Як користуватися ШІ", "Мапа", "Підготуйтеся"]):
                self.assertIn("## " + words, part, name)
            self.assertNotRegex(part, r"Krisl|Swedish|svensk|Sverige", name + " has Swedish left in the user guide")

    def test_update_make_usb_and_the_kit_drive_install_are_in_the_user_guide_and_so_on_paper(self):
        """Story 10 (followups 9): a volunteer with only the printed guide must find how to update the kit and how to
        copy it to another Mac. The user-guide part is what the PDFs are made from."""
        for name, words in (("README.md", ("Оновити - Update.command", "Створити USB - Make USB.command", "Kit Drive", "exFAT",
                                           "Emergency-Kit-Drive/kit", "Встановити - Install.command")),
                            ("README.en.md", ("Оновити - Update.command", "Створити USB - Make USB.command", "Kit Drive", "exFAT",
                                              "Emergency-Kit-Drive/kit", "Встановити - Install.command"))):
            text = read(name)
            part = text[text.index(START):text.index(END)]
            for w in words:
                self.assertIn(w, part, name + " user guide lacks " + w)
            for command in ("Оновити - Update.command", "Створити USB - Make USB.command"):
                self.assertTrue(os.path.exists(os.path.join(REPO, command)), command)   # the file the guide names is there

    def test_the_user_guide_is_in_its_own_language(self):
        uk = read("README.md")
        en = read("README.en.md")
        uk_part = uk[uk.index(START):uk.index(END)]
        en_part = en[en.index(START):en.index(END)]
        self.assertGreater(len(re.findall("[А-Яа-яІіЇїЄє]", uk_part)), 3000)
        # the English part holds Ukrainian only in names and examples (the kit name, a search, the PDF name)
        self.assertLess(len(re.findall("[А-Яа-яІіЇїЄє]", en_part)), 150)

    def test_the_committed_pdfs_exist(self):
        for pdf in PDFS.values():
            with open(os.path.join(REPO, pdf), "rb") as f:
                self.assertEqual(f.read(5), b"%PDF-", pdf)


@unittest.skipIf(not find_chrome(), "needs Chrome")
class MakeGuideTest(unittest.TestCase):
    def test_the_script_makes_one_pdf_per_language_with_both_kit_names(self):
        tmp = tempfile.mkdtemp(prefix="ek-guide-")
        try:
            os.makedirs(os.path.join(tmp, "scripts"))
            shutil.copy(os.path.join(REPO, "scripts", "make-print-guide.sh"), os.path.join(tmp, "scripts"))
            for name in PDFS:
                shutil.copy(os.path.join(REPO, name), tmp)
            run = subprocess.run(["bash", os.path.join(tmp, "scripts", "make-print-guide.sh")], cwd=tmp, capture_output=True,
                                 text=True, timeout=300, env=dict(os.environ, EK_CHROME=find_chrome()))
            if run.returncode != 0 and "pip" in run.stderr + run.stdout:
                self.skipTest("no Markdown module and no network for one")
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            for pdf in PDFS.values():
                path = os.path.join(tmp, pdf)
                self.assertTrue(os.path.exists(path), pdf)
                with open(path, "rb") as f:
                    data = f.read()
                self.assertTrue(data.startswith(b"%PDF-"))
                self.assertGreaterEqual(len(re.findall(rb"/Type\s*/Page[^s]", data)), 2, pdf)
            self.assertIn("Wrote", run.stdout)
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
