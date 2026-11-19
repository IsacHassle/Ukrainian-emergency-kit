#!/bin/bash
# Starts the kit: the offline Libraries, the start page, the map, the Official Guides and the AI page, shared with
# every phone and laptop on the same Wi-Fi. No internet needed.
#
# Run:  bash scripts/share-library.sh   (this is what "Запустити - Start.command" runs)
# Stop: Ctrl+C (stops everything)
#
# The first time, macOS may ask whether kiwix-serve and Python may accept
# incoming connections. Click Allow, or other devices cannot connect.

KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # the kit folder (where this repo is)
# shellcheck source=country.sh
. "$KIT/scripts/country.sh"   # the country's facts (config/country.json)
# shellcheck source=say.sh
. "$KIT/scripts/say.sh"
LIB="$KIT/library"
SERVE="$KIT/tools/kiwix-tools/kiwix-serve"
# The ports can be chosen (EK_LIBRARY_PORT, EK_WEB_PORT) so a second kit or a test can run beside a kit
# that is already running. Without them: 8090 for the Library server and 8091 for the web server.
LIB_PORT="${EK_LIBRARY_PORT:-8090}"
WEB_PORT="${EK_WEB_PORT:-8091}"
export EK_KIWIX="127.0.0.1:$LIB_PORT"   # tells the web server and the start page builder where the Library server is

shopt -s nullglob
zims=("$LIB"/*.zim)
if [ ${#zims[@]} -eq 0 ]; then
  say "У $LIB немає бібліотек. Спершу встановіть валізу («Встановити - Install.command»)" "No Libraries found in $LIB. Install the kit first (\"Встановити - Install.command\")"
  exit 1
fi

# Stop any copy that is already running, so ports are free.
pkill -f "kiwix-serve --port=$LIB_PORT" 2>/dev/null
pkill -f "serve-web.py $WEB_PORT" 2>/dev/null
sleep 1

"$SERVE" --port="$LIB_PORT" "${zims[@]}" >/dev/null 2>&1 &
LIB_PID=$!
bash "$KIT/scripts/make-cert.sh" || true   # https for phones (GPS needs it); quick after the first time
python3 "$KIT/scripts/serve-web.py" "$WEB_PORT" >/dev/null 2>&1 &
WEB_PID=$!
trap 'kill $LIB_PID $WEB_PID 2>/dev/null; echo; say "  Зупинено" "  Stopped"' EXIT

for i in $(seq 1 30); do curl -sf -o /dev/null "http://localhost:$LIB_PORT/catalog/v2/entries" && break; sleep 1; done
python3 "$KIT/scripts/build-home.py" >/dev/null

IP=$(ipconfig getifaddr en0 || ipconfig getifaddr en1)
NAME=$(scutil --get LocalHostName 2>/dev/null)   # e.g. "Annas-MacBook-Air": stays the same when the IP changes
echo ""
say "  $(country kit_name.uk | tr '[:lower:]' '[:upper:]') працює (бібліотек: ${#zims[@]})" "  $(country kit_name.en | tr '[:lower:]' '[:upper:]') is running (Libraries: ${#zims[@]})"
echo ""
say "  На цьому Mac:           http://localhost:$WEB_PORT" "  On this Mac:             http://localhost:$WEB_PORT"
[ -n "$NAME" ] && say "  На телефонах (та сама Wi-Fi): http://$NAME.local:$WEB_PORT (на iPhone працює завжди)" "  On phones (same Wi-Fi):  http://$NAME.local:$WEB_PORT (always works on iPhone)"
[ -n "$IP" ] && say "  або за номером: http://$IP:$WEB_PORT (якщо перша адреса не працює, наприклад на Android)" "  or by number: http://$IP:$WEB_PORT (if the first address does not work, for example on Android)"
[ -n "$NAME" ] && say "  GPS на телефоні: https://$NAME.local:$((WEB_PORT + 352)) (налаштуйте один раз: відкрийте /mobil/ на телефоні)" "  GPS on the phone: https://$NAME.local:$((WEB_PORT + 352)) (set up once: open /mobil/ on the phone)"
echo ""
say "  Запитати ШІ: http://localhost:$WEB_PORT/ai/" "  Ask the AI: http://localhost:$WEB_PORT/ai/"
[ -n "$IP" ] && say "  Запитати ШІ з телефона: http://$IP:$WEB_PORT/ai/" "  Ask the AI from a phone: http://$IP:$WEB_PORT/ai/"
echo ""
say "  Не закривайте це вікно. Натисніть Ctrl+C, щоб вимкнути" "  Keep this window open. Press Ctrl+C to turn it off"
echo ""
[ "${1:-}" = "--open" ] && open "http://localhost:$WEB_PORT"
wait $LIB_PID
