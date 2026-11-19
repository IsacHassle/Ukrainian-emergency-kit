#!/bin/bash
# Kontrollerar att Krislådan fungerar, utan internet. Gör det en gång i månaden,
# helst med wifi avstängt. Visar en rad per del: ✅ fungerar, ⚠️ saknas eller fungerar inte.
#
# Kör: dubbelklicka på "Kontrollera Krislåda.command", eller: bash scripts/kontroll.sh
set -u
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=country.sh
. "$KIT/scripts/country.sh"   # the country's facts (config/country.json)
OK=0; BAD=0
ok()  { echo "  ✅ $*"; OK=$((OK + 1)); }
bad() { echo "  ⚠️  $*"; BAD=$((BAD + 1)); }
section() { printf '\n\033[1m%s\033[0m\n' "$*"; }

echo "$(country kit_name): kontroll $(date '+%Y-%m-%d %H:%M')"
if curl -fs -o /dev/null --max-time 3 https://www.google.com 2>/dev/null; then
  echo "(Internet är på. Stäng gärna av wifi och kör igen, så vet du att allt fungerar utan internet.)"
fi

section "Bibliotek"
want=$(sed 's/#.*//' "$KIT/config/libraries.txt" | awk '{print $1}' | grep -c .)
have=0; missing=""
while read -r url; do
  stem=$(basename "$url"); stem="${stem%_*}"
  if ls "$KIT/library/${stem}_"*.zim >/dev/null 2>&1; then have=$((have + 1)); else missing="$missing $stem"; fi
done < <(sed 's/#.*//' "$KIT/config/libraries.txt" | awk '{print $1}' | grep .)
if [ "$have" = "$want" ]; then ok "Alla $want bibliotek finns ($(du -sh "$KIT/library" | cut -f1))"
else bad "$have av $want bibliotek finns. Saknas:$missing. Kör installationen igen."; fi
[ -x "$KIT/tools/kiwix-tools/kiwix-serve" ] && ok "kiwix-serve (visar biblioteken) finns" || bad "kiwix-serve saknas. Kör installationen igen."

section "Kartor"
for m in world $(country map.pmtiles); do
  f="$KIT/maps/$m.pmtiles"
  if [ -f "$f" ] && [ "$(head -c 7 "$f")" = "PMTiles" ]; then ok "Karta: $m ($(du -h "$f" | cut -f1))"; else bad "Kartan $m saknas eller är trasig. Kör installationen igen."; fi
done
if [ -f "$KIT/web/map/data/places.json.gz" ] && ls "$KIT/web/map/data/letters/"*.json.gz >/dev/null 2>&1; then
  ok "Kartans sökning (orter, gator, adresser)"
else bad "Kartans sökning saknas. Kör installationen igen."; fi

if [ -f "$KIT/tools/certs/server.crt" ]; then ok "https för mobilens GPS (certifikat finns)"
else echo "  ℹ️  https för mobilens GPS skapas när du startar Krislådan första gången."; fi

gpsdev=$(ls /dev/cu.usbmodem* /dev/cu.usbserial* /dev/cu.SLAB_USBtoUART* /dev/cu.wchusbserial* 2>/dev/null | head -1)
if [ -n "$gpsdev" ]; then
  fix=$(curl -fs --max-time 3 http://localhost:8091/ai-api/gps 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print('ja' if d.get('fix') else 'nej')" 2>/dev/null)
  case "$fix" in
    ja) ok "USB GPS-mottagare inkopplad och har position ($(basename "$gpsdev"))" ;;
    nej) ok "USB GPS-mottagare inkopplad ($(basename "$gpsdev")), söker satelliter. Ställ den vid ett fönster." ;;
    *) ok "USB GPS-mottagare inkopplad ($(basename "$gpsdev")). Starta Krislådan och tryck 📍 på kartan för att testa." ;;
  esac
else
  echo "  ℹ️  Ingen USB GPS-mottagare inkopplad. Med en sådan visar kartan var du är utan internet (se guiden)."
fi

section "Dokument"
n=$(find "$KIT/documents" -type f \( -name '*.pdf' -o -name '*.md' \) | wc -l | tr -d ' ')
[ -s "$KIT/documents/Om-krisen-eller-kriget-kommer.pdf" ] && ok "Broschyren Om krisen eller kriget kommer" || bad "Broschyren saknas. Kör installationen igen med internet."
sv=$(ls "$KIT/documents/library/Svenska myndigheter/"*.md 2>/dev/null | wc -l | tr -d ' ')
[ "$sv" -gt 0 ] && ok "Svenska myndigheters råd: $sv sidor" || bad "Myndigheternas råd saknas. Kör installationen igen med internet."
[ "$n" -gt 100 ] && ok "Böcker och dokument: $n filer" || bad "Bara $n dokument. Kör installationen igen."

section "AI"
OLLAMA=$(command -v ollama || echo /Applications/Ollama.app/Contents/Resources/ollama)
if [ -d /Applications/Ollama.app ]; then
  curl -fs -o /dev/null --max-time 3 http://127.0.0.1:11434/api/version || { open -g -a Ollama; sleep 8; }
  if curl -fs -o /dev/null --max-time 3 http://127.0.0.1:11434/api/version; then
    ok "AI-motorn Ollama är igång"
    for m in $(country ai.models.main) $(country ai.models.small) bge-m3; do
      "$OLLAMA" show "$m" >/dev/null 2>&1 && ok "AI-modellen $m finns" || bad "AI-modellen $m saknas. Kör installationen igen."
    done
    echo "  …frågar AI:n en testfråga (tar upp till en minut)"
    answer=$(curl -fs --max-time 120 http://127.0.0.1:11434/api/chat -d "$(python3 -c 'import json,sys; print(json.dumps({"model": sys.argv[1], "stream": False, "think": False, "messages": [{"role": "user", "content": sys.argv[2]}]}))' "$(country ai.models.small)" "$(country ai.check.question)")" \
      | python3 -c "import json,sys; print(json.load(sys.stdin)['message']['content'])" 2>/dev/null)
    expect=$(country ai.check.expect)
    if echo "$answer" | grep -q "$expect"; then ok "AI:n svarar (testfråga: $expect)"; else bad "AI:n svarade inte som väntat: ${answer:-inget svar}"; fi
  else bad "AI-motorn Ollama startar inte. Öppna appen Ollama och kör kontrollen igen."; fi
else bad "Appen Ollama saknas. Kör installationen igen (eller ./install.sh --utan-ai om du inte vill ha AI)."; fi
if [ -d /Applications/AnythingLLM.app ]; then
  if curl -fs -o /dev/null --max-time 3 http://localhost:3001/api/ping; then
    docs=$(curl -fs "http://localhost:3001/api/workspace/$(country ai.workspace)" | python3 -c "import json,sys; print(len(json.load(sys.stdin)['workspace']['documents']))" 2>/dev/null || echo 0)
    [ "$docs" -gt 100 ] && ok "Böckerna i AI:n (AnythingLLM): $docs dokument" || bad "Bara $docs dokument i AI:n. Kör: bash scripts/embed-documents.sh"
  else
    echo "  ℹ️  AnythingLLM är inte igång (startas av Starta Krislåda.command). Svar ur böckerna kontrolleras då inte."
  fi
else bad "Appen AnythingLLM saknas. Kör installationen igen."; fi

section "Utrymme och ström"
free=$(df -h "$KIT" | awk 'NR==2 {print $4}')
ok "Ledigt utrymme: $free"
batt=$(pmset -g batt 2>/dev/null | grep -o '[0-9]*%' | head -1)
[ -n "$batt" ] && echo "  ℹ️  Batteri: $batt. Ladda Macen fullt och ha en powerbank redo."

echo
if [ "$BAD" = 0 ]; then
  printf '\033[1m✅ Allt fungerar (%s kontroller).\033[0m Starta Krislådan med "Starta Krislåda.command".\n' "$OK"
else
  printf '\033[1m⚠️  %s saker behöver åtgärdas, %s fungerar.\033[0m Se raderna ovan.\n' "$BAD" "$OK"
fi
