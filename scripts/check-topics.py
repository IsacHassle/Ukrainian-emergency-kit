#!/usr/bin/env python3
"""Checks that every Emergency Topic's WikiMed article exists in the real Libraries.

Reads config/country.json, finds the newest file of each WikiMed Library in a folder (default: the kit's
library/, else the build cache ~/.cache/emergency-kit-build/zim) and opens every article path with libzim.
Needs libzim (the kit's Python from scripts/get-tools.sh). Exit 0 all found, 1 something missing,
3 nothing to check against (no libzim or no Library files). Usage: check-topics.py [folder]
"""
import glob
import os
import sys

import kit_country

try:
    from libzim.reader import Archive
except ImportError:
    print("libzim is not installed, so the topics were not checked")
    sys.exit(3)

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.expanduser("~/.cache/emergency-kit-build/zim")
folders = [sys.argv[1]] if len(sys.argv) > 1 else [os.path.join(KIT, "library"), CACHE]
wikimed = {l["language"]: l["prefix"] for l in kit_country.COUNTRY["ai"]["libraries"]
           if l["kind"] == "encyclopedia" and "medicine" in l["prefix"]}
archives = {}
for code, prefix in wikimed.items():
    found = sorted(f for d in folders for f in glob.glob(os.path.join(d, prefix + "_*.zim")))
    if found:
        archives[code] = (Archive(found[-1]), os.path.basename(found[-1]))
if not archives:
    print("no WikiMed Library files in " + " or ".join(folders))
    sys.exit(3)

missing = 0
for t in kit_country.COUNTRY["emergency_topics"]:
    for code, (z, name) in archives.items():
        path = t["wikimed"].get(code)
        if not path or not z.has_entry_by_path(path):
            print(f"MISSING {t['id']}: {code} {path} not in {name}")
            missing += 1
        else:
            print(f"ok      {t['id']}: {code} {path}")
sys.exit(1 if missing else 0)
