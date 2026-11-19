"""The Library list (Seam 2): the download script run on a copy of the repo against a fake Kiwix.

The fake `curl` answers from a folder standing in for download.kiwix.org: files, a directory listing, and the
.sha256 next to each file. Nothing goes on the network.
"""
import hashlib
import os
import re
import shutil
import stat
import subprocess
import tempfile
import unittest

from servedkit import REPO

FAKE_CURL = r'''#!/bin/bash
# Stand-in curl: the site is the folder $FAKE_KIWIX, addresses are https://download.kiwix.org/zim/<folder>/<file>.
head=0; out=""; url=""
while [ $# -gt 0 ]; do
  case "$1" in
    -*I*) head=1 ;;
    -o) out="$2"; shift ;;
    -C|--retry|--retry-delay|--max-time) shift ;;
    https://*) url="$1" ;;
  esac
  shift
done
path="${url#https://download.kiwix.org/zim/}"
local="$FAKE_KIWIX/$path"
if [ -d "$local" ] || [[ "$url" == */ ]]; then ls "$FAKE_KIWIX/${path%/}" | sed 's/.*/<a href="&">&<\/a>/'; exit 0; fi
if [[ "$local" == *.sha256 ]]; then
  base="${local%.sha256}"; [ -f "$base" ] || exit 22
  echo "$(shasum -a 256 "$base" | awk '{print $1}')  $(basename "$base")"; exit 0
fi
[ -f "$local" ] || exit 22
[ $head = 1 ] && exit 0
if [ -n "$out" ]; then cp "$local" "$out"; else cat "$local"; fi
'''


def config_urls():
    with open(os.path.join(REPO, "config", "libraries.txt"), encoding="utf-8") as f:
        text = re.sub(r"#.*", "", f.read())
    return [l.split()[0] for l in text.splitlines() if l.strip()]


class LibraryListTest(unittest.TestCase):
    def test_the_list_names_the_ukrainian_set_and_neither_ready_gov_nor_cdc(self):
        names = [u.rsplit("/", 1)[1] for u in config_urls()]
        for stem in ("wikipedia_uk_medicine_maxi", "wikipedia_uk_all_mini", "wikipedia_en_medicine_maxi",
                     "mdwiki_en_all_maxi", "medlineplus.gov_en_all", "irp.fas.org_en_military-medicine",
                     "nhs.uk_en_medicines", "zimgit-medicine_en", "zimgit-water_en", "zimgit-food-preparation_en",
                     "zimgit-knots_en", "zimgit-post-disaster_en", "solar.lowtechmagazine.com_mul_all"):
            self.assertEqual(len([n for n in names if n.startswith(stem + "_")]), 1, stem)
        self.assertEqual(len(names), 13, names)
        self.assertFalse([n for n in names if "ready.gov" in n or "cdc.gov" in n or "_sv_" in n])
        for n in names:
            self.assertRegex(n, r"_\d{4}-\d{2}[a-z]?\.zim$")   # pinned


class NewestVersionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ek-lib-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.kit = os.path.join(self.tmp, "kit")
        shutil.copytree(os.path.join(REPO, "scripts"), os.path.join(self.kit, "scripts"), ignore=shutil.ignore_patterns("__pycache__"))
        os.makedirs(os.path.join(self.kit, "config"))
        self.site = os.path.join(self.tmp, "site")
        os.makedirs(os.path.join(self.site, "zimit"))
        os.makedirs(os.path.join(self.tmp, "bin"))
        curl = os.path.join(self.tmp, "bin", "curl")
        with open(curl, "w") as f:
            f.write(FAKE_CURL)
        os.chmod(curl, os.stat(curl).st_mode | stat.S_IEXEC)

    def put(self, name, data=b"zim"):
        with open(os.path.join(self.site, "zimit", name), "wb") as f:
            f.write(data)

    def download(self, listed):
        with open(os.path.join(self.kit, "config", "libraries.txt"), "w") as f:
            f.write("https://download.kiwix.org/zim/zimit/%s\n" % listed)
        env = dict(os.environ, PATH=os.path.join(self.tmp, "bin") + os.pathsep + os.environ["PATH"], FAKE_KIWIX=self.site)
        subprocess.run(["bash", os.path.join(self.kit, "scripts", "download-library.sh")], env=env, check=True,
                       capture_output=True, text=True, timeout=60)
        return sorted(os.listdir(os.path.join(self.kit, "library")))

    def test_a_pinned_file_that_still_exists_is_downloaded_as_listed(self):
        self.put("nhs.uk_en_medicines_2026-09b.zim")
        self.put("nhs.uk_en_medicines_2025-12.zim")
        self.assertEqual(self.download("nhs.uk_en_medicines_2025-12.zim"), ["nhs.uk_en_medicines_2025-12.zim"])

    def test_a_removed_pin_falls_back_to_the_newest_version(self):
        self.put("nhs.uk_en_medicines_2026-05.zim")
        self.put("nhs.uk_en_medicines_2026-09.zim")
        self.assertEqual(self.download("nhs.uk_en_medicines_2025-12.zim"), ["nhs.uk_en_medicines_2026-09.zim"])

    def test_the_newest_version_may_have_a_letter_after_the_month(self):
        self.put("nhs.uk_en_medicines_2026-09.zim")
        self.put("nhs.uk_en_medicines_2026-09b.zim")
        self.put("nhs.uk_en_medicines_2025-12.zim")
        self.assertEqual(self.download("nhs.uk_en_medicines_2025-11.zim"), ["nhs.uk_en_medicines_2026-09b.zim"])


if __name__ == "__main__":
    unittest.main()
