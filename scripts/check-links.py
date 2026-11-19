#!/usr/bin/env python3
"""Checks that everything the installer downloads is still there (used weekly by GitHub Actions).

Fails if something the standard kit needs is gone and has no replacement, so the repository
owner gets an email before anyone's installation breaks. Extras and authority pages only warn.
Run: python3 scripts/check-links.py          (everything)
     python3 scripts/check-links.py --guides  (only the Official Guide list, config/pages.txt)

An Official Guide that is gone (404) is a problem, one that moved (redirects to another page) or whose source
refuses us is a warning, and an optional source that refuses us (the State Emergency Service answers 403
behind Cloudflare from outside Ukraine) is only noted as refused: the guide saver skips those too.
"""
import datetime
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit_guides   # noqa: E402  (the guide list and the polite fetch, shared with the guide saver)

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {"User-Agent": "Mozilla/5.0 Krislada-link-check"}
problems, warnings = [], []
listings = {}


def ok(url):
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, method=method, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                if r.status < 400:
                    return True
        except Exception:
            pass
    return False


def check_guides():
    """Every address in the Official Guide list, once."""
    for guide in kit_guides.read_list():
        r = kit_guides.fetch(guide.url, limit=2048)
        optional = kit_guides.optional(guide.url)
        if r.state == "ok":
            if not kit_guides.same_page(guide.url, r.final_url):
                warnings.append(f"Official Guide moved (now {r.final_url}): {guide.url}")
        elif r.state == "refused":
            if optional:
                print(f"NOTE: refused (expected from outside Ukraine), not checked: {guide.url}")
            else:
                warnings.append(f"Official Guide refused the check ({r.detail}), not known to be gone: {guide.url}")
        elif r.state == "gone":
            (warnings if optional else problems).append(f"Official Guide gone ({r.detail}): {guide.url}")
        else:
            warnings.append(f"Official Guide did not answer ({r.detail}): {guide.url}")


def finish():
    for w in warnings:
        print("WARNING:", w)
    for p in problems:
        print("PROBLEM:", p)
    print(f"{len(problems)} problems, {len(warnings)} warnings")
    sys.exit(1 if problems else 0)


if "--guides" in sys.argv:
    check_guides()
    finish()


def newest_on_kiwix(url):
    folder, name = url.rsplit("/", 1)
    stem = name.rsplit("_", 1)[0]
    if folder not in listings:
        listings[folder] = urllib.request.urlopen(urllib.request.Request(folder + "/", headers=UA), timeout=60).read().decode()
    found = sorted(set(re.findall(re.escape(stem) + r'_(\d{4}-\d{2})\.zim"', listings[folder])))
    return f"{stem}_{found[-1]}.zim" if found else None


for line in open(os.path.join(KIT, "config", "libraries.txt")):
    m = re.search(r"https://download\.kiwix\.org/zim/\S+?\.zim", line)
    if not m:
        continue
    url, extra = m.group(0), line.lstrip().startswith("#")
    if ok(url):
        continue
    newer = newest_on_kiwix(url)
    note = f"{url.rsplit('/', 1)[1]} is gone from Kiwix" + (f"; the installer will use {newer}" if newer else "; no replacement found")
    (warnings if extra or newer else problems).append(note)

required = {
    "Ollama download": "https://ollama.com/download/Ollama.dmg",
    "AnythingLLM download": "https://cdn.anythingllm.com/latest/AnythingLLMDesktop-Silicon.dmg",
    "kiwix-tools": "https://download.kiwix.org/release/kiwix-tools/kiwix-tools_macos-arm64-3.8.2.tar.gz",
    "Map search (GitHub release)": "https://github.com/IsacHassle/Swedish-doomsdaykit/releases/latest/download/map-search.tar.gz",
}
pm = re.search(r"PMTILES_VERSION=(\S+)", open(os.path.join(KIT, "scripts", "get-tools.sh")).read()).group(1)
required["pmtiles"] = f"https://github.com/protomaps/go-pmtiles/releases/download/v{pm}/go-pmtiles-{pm}_Darwin_arm64.zip"
for what, url in required.items():
    if not ok(url):
        problems.append(f"{what}: {url} does not answer")

today = datetime.date.today()
if not any(ok(f"https://build.protomaps.com/{(today - datetime.timedelta(days=d)):%Y%m%d}.pmtiles") for d in range(8)):
    problems.append("No Protomaps map build from the last 8 days (scripts/get-maps.sh needs one)")

check_guides()
finish()
