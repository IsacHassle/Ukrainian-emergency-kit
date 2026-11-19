#!/bin/bash
# Makes the printable guides (A4, one PDF per language) from the user-guide part of README.md (Ukrainian) and
# README.en.md (English), the part between <!-- user-guide:start --> and <!-- user-guide:end -->. Uses Google
# Chrome. Run after changing that part of a README:  bash scripts/make-print-guide.sh
# Both kit names are on each PDF. The kit's venv supplies the Markdown module; without it, a throwaway one is made.
set -eu
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHROME="${EK_CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
[ -x "$CHROME" ] || { echo "Потрібен Google Chrome. / Needs Google Chrome."; exit 1; }
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
PY="$KIT/tools/venv/bin/python"
if [ ! -x "$PY" ] || ! "$PY" -c "import markdown" 2>/dev/null; then
  python3 -m venv "$tmp/venv"
  "$tmp/venv/bin/pip" install -q --disable-pip-version-check markdown
  PY="$tmp/venv/bin/python"
fi
make_pdf() {   # make_pdf <readme> <language code> <pdf name>
  "$PY" - "$KIT/$1" "$tmp/$2.html" "$2" <<'PY'
import sys, markdown
src, out, lang = sys.argv[1:4]
md = open(src, encoding="utf-8").read()
md = md[md.index("<!-- user-guide:start -->") + len("<!-- user-guide:start -->"):md.index("<!-- user-guide:end -->")]
head = {"uk": ("Тривожна валіза / Emergency Kit", "Тривожна валіза працює без інтернету. Збережіть цей папір разом з тривожною валізою: якщо в Mac немає струму, папір ви ще зможете прочитати."),
        "en": ("Emergency Kit / Тривожна валіза", "The Emergency Kit works without internet. Keep this paper with the kit: if the Mac has no power, paper is what you can still read.")}[lang]
md = "# %s\n\n%s\n%s" % (head[0], head[1], md)
css = ("body{font:10.5pt/1.4 -apple-system,Helvetica,Arial,sans-serif;color:#111;margin:0}"
       "h1{font-size:20pt;margin:0 0 6pt}h2{font-size:13.5pt;margin:14pt 0 5pt;border-bottom:1px solid #999;padding-bottom:2pt}"
       "h3{font-size:11.5pt;margin:10pt 0 4pt}table{border-collapse:collapse;width:100%;margin:4pt 0 8pt;page-break-inside:avoid}"
       "th,td{border:1px solid #bbb;padding:3pt 5pt;text-align:left;vertical-align:top}th{background:#eee}"
       "code{font:9.5pt Menlo,monospace;background:#f2f2f2;padding:0 2pt}ol,ul{margin:3pt 0 6pt 16pt;padding:0}"
       "h2,h3{break-after:avoid;page-break-after:avoid}@page{size:A4;margin:14mm}")
open(out, "w", encoding="utf-8").write('<!doctype html><meta charset=utf-8><html lang="%s"><title>%s</title><style>%s</style>' % (lang, head[0], css)
                                       + markdown.markdown(md, extensions=["tables"]))
PY
  "$CHROME" --headless --disable-gpu --no-pdf-header-footer --print-to-pdf="$KIT/$3" "file://$tmp/$2.html" 2>/dev/null
  echo "Записано / Wrote $3"
}
make_pdf README.md uk "Тривожна валіза - посібник для друку.pdf"
make_pdf README.en.md en "Emergency Kit - printable guide.pdf"
