#!/bin/bash
# Uppdaterar biblioteken till de senaste versionerna hos Kiwix.
# Skriver in de nya versionerna i config/libraries.txt (även de avstängda extrabiblioteken),
# hämtar dem, kontrollerar dem och tar bort de gamla versionerna när de nya är på plats.
# Läser sedan in nya böcker i AI:n.
#
# Kör:  bash scripts/update-libraries.sh
set -eu
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CFG="$KIT/config/libraries.txt"

python3 - "$CFG" <<'PY'
import re, sys, urllib.request
cfg = sys.argv[1]
listings = {}

def newest(url):
    folder, name = url.rsplit("/", 1)
    stem = name.rsplit("_", 1)[0]
    if folder not in listings:
        listings[folder] = urllib.request.urlopen(folder + "/", timeout=60).read().decode()
    found = sorted(set(re.findall(re.escape(stem) + r'_(\d{4}-\d{2})\.zim"', listings[folder])))
    return f"{folder}/{stem}_{found[-1]}.zim" if found else url

lines, changed = [], 0
for line in open(cfg).read().split("\n"):
    m = re.search(r"https://download\.kiwix\.org/zim/\S+?\.zim", line)
    if m:
        new = newest(m.group(0))
        if new != m.group(0):
            print("Ny version:", new.rsplit("/", 1)[1])
            line = line.replace(m.group(0), new)
            changed += 1
    lines.append(line)
open(cfg, "w").write("\n".join(lines))
print(f"{changed} bibliotek har nyare versioner." if changed else "Alla bibliotek är redan i senaste versionen.")
PY

bash "$KIT/scripts/download-library.sh"
bash "$KIT/scripts/get-documents.sh" --uppdatera   # also refreshes the authorities' pages
if curl -fs -o /dev/null http://localhost:3001/api/ping; then
  bash "$KIT/scripts/embed-documents.sh"
else
  echo "Öppna AnythingLLM och kör: bash scripts/embed-documents.sh, så läser AI:n in nya böcker."
fi
echo "Klart. Starta om Krislådan så syns de nya versionerna."
