#!/bin/bash
# Updates the Libraries to the newest versions at Kiwix.
# Writes the new versions into config/libraries.txt (the switched-off extras too), then downloads them, checks
# them against Kiwix's checksums and removes the old versions once the new ones are in place
# (scripts/download-library.sh does the last three). Needs internet. Update (scripts/update.sh) runs this.
#
# Run:  bash scripts/update-libraries.sh
set -eu
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CFG="$KIT/config/libraries.txt"
# shellcheck source=say.sh
. "$KIT/scripts/say.sh"

python3 - "$CFG" <<'PY'
import re, subprocess, sys
cfg = sys.argv[1]
listings = {}

def newest(url):
    folder, name = url.rsplit("/", 1)
    stem = name.rsplit("_", 1)[0]
    if folder not in listings:
        # curl, like the downloader: one way to reach Kiwix. A folder that cannot be read keeps its listed versions.
        got = subprocess.run(["curl", "-sfL", "--max-time", "60", folder + "/"], capture_output=True)
        listings[folder] = got.stdout.decode("utf-8", "replace") if got.returncode == 0 else ""
    # A version is a year and month, sometimes with a letter after (nhs.uk_en_medicines_2026-09b).
    found = sorted(set(re.findall(re.escape(stem) + r'_(\d{4}-\d{2}[a-z]?)\.zim"', listings[folder])))
    return f"{folder}/{stem}_{found[-1]}.zim" if found else url

lines, changed = [], 0
for line in open(cfg, encoding="utf-8").read().split("\n"):
    m = re.search(r"https://download\.kiwix\.org/zim/\S+?\.zim", line)
    if m:
        new = newest(m.group(0))
        if new != m.group(0):
            print(f"Нова версія / New version: {new.rsplit('/', 1)[1]}")
            line = line.replace(m.group(0), new)
            changed += 1
    lines.append(line)
open(cfg, "w", encoding="utf-8").write("\n".join(lines))
if changed:
    print(f"Бібліотек з новішою версією: {changed} / Libraries with a newer version: {changed}")
else:
    print("Усі бібліотеки вже найновіші / All the Libraries are already the newest")
PY

bash "$KIT/scripts/download-library.sh"
