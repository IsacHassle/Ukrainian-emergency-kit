#!/bin/bash
# Turns README.md into "Krislåda - guide att skriva ut.pdf" (A4), using Google Chrome.
# Run after changing the README:  bash scripts/make-print-guide.sh
set -eu
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
[ -x "$CHROME" ] || { echo "Needs Google Chrome."; exit 1; }
"$KIT/tools/venv/bin/pip" install -q --disable-pip-version-check markdown
tmp=$(mktemp -d)
"$KIT/tools/venv/bin/python" - "$KIT/README.md" "$tmp/guide.html" <<'PY'
import sys, markdown
md = open(sys.argv[1]).read()
md = md[md.index("## Börja här"):md.index("## In English")]   # the user guide, not the install part
md = "# Krislåda\n\nAllt i krislådan fungerar utan internet. Spara det här papperet hos din hemberedskap: om Macen saknar ström är papperet det du fortfarande kan läsa.\n\n" + md
css = ("body{font:10.5pt/1.4 -apple-system,Helvetica,Arial,sans-serif;color:#111;margin:0}"
       "h1{font-size:20pt;margin:0 0 6pt}h2{font-size:13.5pt;margin:14pt 0 5pt;border-bottom:1px solid #999;padding-bottom:2pt}"
       "h3{font-size:11.5pt;margin:10pt 0 4pt}table{border-collapse:collapse;width:100%;margin:4pt 0 8pt;page-break-inside:avoid}"
       "th,td{border:1px solid #bbb;padding:3pt 5pt;text-align:left;vertical-align:top}th{background:#eee}"
       "code{font:9.5pt Menlo,monospace;background:#f2f2f2;padding:0 2pt}ol,ul{margin:3pt 0 6pt 16pt;padding:0}"
       "h2,h3{break-after:avoid;page-break-after:avoid}@page{size:A4;margin:14mm}")
open(sys.argv[2], "w").write(f"<!doctype html><meta charset=utf-8><title>Krislåda</title><style>{css}</style>"
                             + markdown.markdown(md, extensions=["tables"]))
PY
"$CHROME" --headless --disable-gpu --no-pdf-header-footer --print-to-pdf="$KIT/Krislåda - guide att skriva ut.pdf" "file://$tmp/guide.html" 2>/dev/null
rm -rf "$tmp"
echo "Skrev Krislåda - guide att skriva ut.pdf"
