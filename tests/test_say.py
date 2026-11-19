"""One line in both languages: the Python helper (scripts/kit_say.py) and the check scripts that use it."""
import os
import subprocess
import sys
import unittest

from servedkit import REPO

sys.path.insert(0, os.path.join(REPO, "scripts"))
import kit_say  # noqa: E402


class SayTest(unittest.TestCase):
    def test_a_line_is_ukrainian_then_english_on_one_line(self):
        self.assertEqual(kit_say.line("Готово", "Done"), "Готово / Done")

    def test_the_language_check_reports_in_both_languages(self):
        run = subprocess.run([sys.executable, os.path.join(REPO, "scripts", "check-language.py")], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertRegex(run.stdout.strip(), r"^мовні файли в порядку: .* / language files ok: ")

    def test_die_writes_both_to_stderr_and_exits(self):
        run = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, %r); import kit_say; kit_say.die('Ні', 'No', 2)"
                              % os.path.join(REPO, "scripts")], capture_output=True, text=True)
        self.assertEqual((run.returncode, run.stderr.strip()), (2, "Ні / No"))


if __name__ == "__main__":
    unittest.main()
