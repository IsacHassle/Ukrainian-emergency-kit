#!/bin/bash
# Checks that the kit works, with no internet needed. Do it once a month, best with Wi-Fi turned off.
# One line per part, each in both languages: ✅ works, ⚠️ missing or not working, ℹ️ for your information.
# Exit code 0 when nothing needs attention, 1 otherwise.
#
# Run: double-click "Перевірити - Check.command", or: bash scripts/check.sh
# For tests: EK_APPS (the apps folder), EK_OLLAMA and EK_ANYTHINGLLM ("host:port"), EK_WEB_PORT, EK_DEV (where
# USB receivers show up, /dev) and EK_NO_PAUSE (do not wait for an app to start) point the check at stand-ins.
set -u
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=country.sh
. "$KIT/scripts/country.sh"   # the country's facts (config/country.json)
# shellcheck source=say.sh
. "$KIT/scripts/say.sh"
APPS="${EK_APPS:-/Applications}"
OLLAMA_ADDR="${EK_OLLAMA:-127.0.0.1:11434}"
ANYTHINGLLM_ADDR="${EK_ANYTHINGLLM:-localhost:3001}"
WEB_PORT="${EK_WEB_PORT:-8091}"
DEV="${EK_DEV:-/dev}"
OK=0; BAD=0
ok()   { echo "  ✅ $1 / $2"; OK=$((OK + 1)); }
bad()  { echo "  ⚠️  $1 / $2"; BAD=$((BAD + 1)); }
info() { echo "  ℹ️  $1 / $2"; }
section() { printf '\n\033[1m%s / %s\033[0m\n' "$1" "$2"; }

say "$(country kit_name.uk): перевірка $(date '+%Y-%m-%d %H:%M')" "$(country kit_name.en): check $(date '+%Y-%m-%d %H:%M')"
if curl -fs -o /dev/null --max-time 3 https://www.google.com 2>/dev/null; then
  say "(Інтернет увімкнено. Вимкніть Wi-Fi і запустіть перевірку ще раз, щоб переконатися, що все працює без інтернету)" \
      "(The internet is on. Turn Wi-Fi off and run the check again to be sure everything works without it)"
fi

section "Бібліотеки" "Libraries"
want=$(sed 's/#.*//' "$KIT/config/libraries.txt" | awk '{print $1}' | grep -c .)
have=0; missing=""
while read -r url; do
  stem=$(basename "$url"); stem="${stem%_*}"
  if ls "$KIT/library/${stem}_"*.zim >/dev/null 2>&1; then have=$((have + 1)); else missing="$missing $stem"; fi
done < <(sed 's/#.*//' "$KIT/config/libraries.txt" | awk '{print $1}' | grep .)
if [ "$have" = "$want" ]; then
  size=$(du -sh "$KIT/library" | cut -f1)
  ok "Усі бібліотеки є: $want ($size)" "All the Libraries are there: $want ($size)"
else
  bad "Бібліотек є $have з $want. Бракує:$missing. Запустіть встановлення ще раз" "$have of $want Libraries are there. Missing:$missing. Run the installation again"
fi
if [ -x "$KIT/tools/kiwix-tools/kiwix-serve" ]; then ok "kiwix-serve (показує бібліотеки) на місці" "kiwix-serve (shows the Libraries) is there"
else bad "kiwix-serve немає. Запустіть встановлення ще раз" "kiwix-serve is missing. Run the installation again"; fi

section "Мапа" "Map"
for m in world $(country map.pmtiles); do
  f="$KIT/maps/$m.pmtiles"
  if [ -f "$f" ] && [ "$(head -c 7 "$f")" = "PMTiles" ]; then
    size=$(du -h "$f" | cut -f1)
    ok "Мапа $m ($size)" "Map $m ($size)"
  else bad "Мапи $m немає або вона пошкоджена. Запустіть встановлення ще раз" "The map $m is missing or damaged. Run the installation again"; fi
done
if [ -f "$KIT/web/map/data/places.json.gz" ] && ls "$KIT/web/map/data/letters/"*.json.gz >/dev/null 2>&1; then
  ok "Пошук по мапі (міста, вулиці, адреси)" "The map search (towns, streets, addresses)"
else bad "Пошуку по мапі немає. Запустіть встановлення ще раз" "The map search is missing. Run the installation again"; fi

if [ -f "$KIT/tools/certs/server.crt" ]; then ok "https для GPS телефона (сертифікат є)" "https for the phone's GPS (the certificate is there)"
else info "https для GPS телефона створиться, коли ви вперше запустите валізу" "https for the phone's GPS is made the first time you start the kit"; fi

gpsdev=$(ls "$DEV"/cu.usbmodem* "$DEV"/cu.usbserial* "$DEV"/cu.SLAB_USBtoUART* "$DEV"/cu.wchusbserial* 2>/dev/null | head -1)
if [ -n "$gpsdev" ]; then
  g=$(basename "$gpsdev")
  fix=$(curl -fs --max-time 3 "http://localhost:$WEB_PORT/ai-api/gps" 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print('yes' if d.get('fix') else 'no')" 2>/dev/null)
  case "$fix" in
    yes) ok "USB GPS-приймач підключено й має позицію ($g)" "A USB GPS receiver is connected and has a position ($g)" ;;
    no) ok "USB GPS-приймач підключено ($g), шукає супутники. Покладіть його біля вікна" "A USB GPS receiver is connected ($g), looking for satellites. Put it by a window" ;;
    *) ok "USB GPS-приймач підключено ($g). Запустіть валізу й натисніть 📍 на мапі, щоб перевірити" "A USB GPS receiver is connected ($g). Start the kit and press 📍 on the map to test it" ;;
  esac
else
  info "USB GPS-приймач не підключено. З ним мапа показує, де ви, без інтернету (див. посібник)" "No USB GPS receiver is connected. With one the map shows where you are with no internet (see the guide)"
fi

section "Документи" "Documents"
# The Official Guides (saved by scripts/fetch-pages.py): the texts, and the handbook as PDF.
guides="$KIT/documents/$(country official_guides.folder)"
n=$(find "$KIT/documents" -type f \( -name '*.pdf' -o -name '*.md' \) 2>/dev/null | wc -l | tr -d ' ')
texts=$(ls "$guides/"*.md 2>/dev/null | wc -l | tr -d ' ')
if [ "$texts" -gt 0 ]; then ok "Офіційні посібники: $texts" "Official Guides: $texts"
else bad "Офіційних посібників немає. Запустіть встановлення з інтернетом" "No Official Guides. Run the installation with internet"; fi
pdfs=$(ls "$guides/"*.pdf 2>/dev/null | wc -l | tr -d ' ')
# How old the saved Official Guides are (scripts/fetch-pages.py writes the date it saved them in saved.json).
# More than 30 days is a warning: the advice changes, and Update needs internet.
saved_on=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['saved'])" "$guides/saved.json" 2>/dev/null || true)
if [ "$texts" -gt 0 ]; then
  age=$(python3 -c "import datetime,sys; print((datetime.date.today() - datetime.date.fromisoformat(sys.argv[1])).days)" "$saved_on" 2>/dev/null || true)
  if [ -z "$age" ]; then
    bad "Невідомо, коли збережено офіційні посібники. Двічі клацніть «Оновити - Update.command», коли є інтернет" "It is not known when the Official Guides were saved. Double-click \"Оновити - Update.command\" when you have internet"
  elif [ "$age" -gt 30 ]; then
    case $((age % 100)) in 11|12|13|14) uk_days="днів" ;; *) case $((age % 10)) in 1) uk_days="день" ;; 2|3|4) uk_days="дні" ;; *) uk_days="днів" ;; esac ;; esac
    en_days=$([ "$age" = 1 ] && echo day || echo days)
    bad "Офіційні посібники збережено $age $uk_days тому. Двічі клацніть «Оновити - Update.command», коли є інтернет" "The Official Guides were saved $age $en_days ago. Double-click \"Оновити - Update.command\" when you have internet"
  else
    ok "Офіційні посібники свіжі (збережено $saved_on)" "The Official Guides are up to date (saved $saved_on)"
  fi
fi
if [ "$pdfs" -gt 0 ]; then ok "Посібники в PDF: $pdfs" "Guides as PDF: $pdfs"
else bad "PDF-посібників немає" "No PDF guides"; fi
if [ "$n" -gt 100 ]; then ok "Книги й документи: файлів $n" "Books and documents: $n files"
else bad "Документів лише $n. Запустіть встановлення ще раз" "Only $n documents. Run the installation again"; fi

section "ШІ" "AI"
OLLAMA=$(command -v ollama || echo "$APPS/Ollama.app/Contents/Resources/ollama")
if [ -d "$APPS/Ollama.app" ]; then
  curl -fs -o /dev/null --max-time 3 "http://$OLLAMA_ADDR/api/version" || { open -g -a Ollama; [ -n "${EK_NO_PAUSE:-}" ] || sleep 8; }
  if curl -fs -o /dev/null --max-time 3 "http://$OLLAMA_ADDR/api/version"; then
    ok "Рушій ШІ Ollama працює" "The AI engine Ollama is running"
    for m in $(country ai.models.main) $(country ai.models.small) bge-m3; do
      if "$OLLAMA" show "$m" >/dev/null 2>&1; then ok "Модель ШІ $m є" "The AI model $m is there"
      else bad "Моделі ШІ $m немає. Запустіть встановлення ще раз" "The AI model $m is missing. Run the installation again"; fi
    done
    info "задаю ШІ тестове запитання (до хвилини)" "asking the AI a test question (up to a minute)"
    answer=$(curl -fs --max-time 120 "http://$OLLAMA_ADDR/api/chat" -d "$(python3 -c 'import json,sys; print(json.dumps({"model": sys.argv[1], "stream": False, "think": False, "messages": [{"role": "user", "content": sys.argv[2]}]}))' "$(country ai.models.small)" "$(country ai.check.question)")" \
      | python3 -c "import json,sys; print(json.load(sys.stdin)['message']['content'])" 2>/dev/null)
    expect=$(country ai.check.expect)
    if echo "$answer" | grep -q "$expect"; then ok "ШІ відповідає (тестове запитання, очікуємо: $expect)" "The AI answers (test question, expecting: $expect)"
    else bad "ШІ відповів не так, як очікувалося: ${answer:-без відповіді}" "The AI did not answer as expected: ${answer:-no answer}"; fi
  else bad "Рушій ШІ Ollama не запускається. Відкрийте програму Ollama й повторіть перевірку" "The AI engine Ollama does not start. Open the Ollama app and run the check again"; fi
else bad "Програми Ollama немає. Запустіть встановлення ще раз (або ./install.sh --no-ai, якщо ШІ не потрібен)" "The Ollama app is missing. Run the installation again (or ./install.sh --no-ai if you do not want the AI)"; fi
if [ -d "$APPS/AnythingLLM.app" ]; then
  if curl -fs -o /dev/null --max-time 3 "http://$ANYTHINGLLM_ADDR/api/ping"; then
    docs=$(curl -fs "http://$ANYTHINGLLM_ADDR/api/workspace/$(country ai.workspace)" | python3 -c "import json,sys; print(len(json.load(sys.stdin)['workspace']['documents']))" 2>/dev/null || echo 0)
    if [ "$docs" -gt 100 ]; then ok "Книги в ШІ (AnythingLLM): документів $docs" "The Books in the AI (AnythingLLM): $docs documents"
    else bad "У ШІ лише $docs документів. Запустіть: bash scripts/embed-documents.sh" "Only $docs documents in the AI. Run: bash scripts/embed-documents.sh"; fi
  else
    info "AnythingLLM не запущено (його запускає «Запустити - Start.command»). Відповіді з книг тоді не перевіряються" "AnythingLLM is not running (\"Запустити - Start.command\" starts it). Answers from the Books are not checked then"
  fi
else bad "Програми AnythingLLM немає. Запустіть встановлення ще раз" "The AnythingLLM app is missing. Run the installation again"; fi

section "Місце та живлення" "Space and power"
free=$(df -h "$KIT" | awk 'NR==2 {print $4}')
ok "Вільного місця: $free" "Free space: $free"
batt=$(pmset -g batt 2>/dev/null | grep -o '[0-9]*%' | head -1)
[ -n "$batt" ] && info "Батарея: $batt. Зарядіть Mac повністю й майте напоготові павербанк" "Battery: $batt. Charge the Mac fully and keep a power bank ready"

echo
if [ "$BAD" = 0 ]; then
  printf '\033[1m✅ Усе працює (перевірок: %s) / Everything works (%s checks).\033[0m Запустіть валізу: «Запустити - Start.command» / Start the kit: "Запустити - Start.command".\n' "$OK" "$OK"
else
  printf '\033[1m⚠️  Потребують уваги: %s, працює: %s / %s need attention, %s work.\033[0m Дивіться рядки вище / See the lines above.\n' "$BAD" "$OK" "$BAD" "$OK"
fi
[ "$BAD" = 0 ]
