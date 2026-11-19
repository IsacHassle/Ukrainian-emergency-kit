#!/bin/bash
# Gets the documents the AI reads and people open as PDFs (into documents/):
#   the books inside the offline libraries (scripts/extract-documents.py), and the Official Guides
#   (config/pages.txt, with the handbook "In case of emergency or war" among them) saved by scripts/fetch-pages.py.
# Run after the libraries are downloaded. Safe to re-run.
set -eu
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=country.sh
. "$KIT/scripts/country.sh"   # the country's facts (config/country.json)
D="$KIT/documents"
mkdir -p "$D"
# shellcheck source=say.sh
. "$KIT/scripts/say.sh"

# The kit's own guide, so the AI can explain how to use the kit.
cp "$KIT/README.md" "$D/Тривожна валіза - посібник.md"
cp "$KIT/README.en.md" "$D/Emergency Kit - guide.md"

"$KIT/tools/venv/bin/python" "$KIT/scripts/extract-documents.py"
# Needs only the system python3. Sources that refuse us (the State Emergency Service, from outside Ukraine) are skipped
# and reported, so a refusal must not stop the install; guides that failed for another reason are retried next run.
/usr/bin/python3 "$KIT/scripts/fetch-pages.py" "$@" || say "Деякі офіційні посібники не вдалося зберегти, запустіть встановлення ще раз пізніше" "Some Official Guides could not be saved, run the installation again later"
say "Документи готові" "The documents are ready"
