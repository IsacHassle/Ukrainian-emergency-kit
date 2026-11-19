#!/bin/bash
# Starts the crisis kit: the offline library, the start page, the map, the
# documents and the AI page, shared with every phone and laptop on the same Wi-Fi.
# No internet needed. This is what "Starta Krislåda.command" runs.
#
# Run:  bash scripts/share-library.sh   (this is what "Starta Krislåda.command" runs)
# Stop: Ctrl+C (stops everything)
#
# The first time, macOS may ask whether kiwix-serve and Python may accept
# incoming connections. Click Allow, or other devices cannot connect.

KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # the kit folder (where this repo is)
# shellcheck source=country.sh
. "$KIT/scripts/country.sh"   # the country's facts (config/country.json)
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
  echo "Inga bibliotek hittades i $LIB. Kör installationen först (Installera Krislåda.command)."
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
trap 'kill $LIB_PID $WEB_PID 2>/dev/null; echo; echo "  Stoppad."' EXIT

for i in $(seq 1 30); do curl -sf -o /dev/null "http://localhost:$LIB_PORT/catalog/v2/entries" && break; sleep 1; done
python3 "$KIT/scripts/build-home.py" >/dev/null

IP=$(ipconfig getifaddr en0 || ipconfig getifaddr en1)
NAME=$(scutil --get LocalHostName 2>/dev/null)   # e.g. "Annas-MacBook-Air": stays the same when the IP changes
echo ""
echo "  $(country kit_name | tr '[:lower:]' '[:upper:]') är igång (${#zims[@]} bibliotek)."
echo ""
echo "  På den här Macen:        http://localhost:$WEB_PORT"
[ -n "$NAME" ] && echo "  På mobiler (samma wifi): http://$NAME.local:$WEB_PORT   (fungerar alltid på iPhone)"
[ -n "$IP" ] && echo "                     eller: http://$IP:$WEB_PORT   (om den första inte fungerar, till exempel på Android)"
[ -n "$NAME" ] && echo "  Med GPS på mobilen:      https://$NAME.local:$((WEB_PORT + 352))   (ställ in en gång: öppna /mobil/ på mobilen)"
echo ""
echo "  Fråga AI:                http://localhost:$WEB_PORT/ai/"
[ -n "$IP" ] && echo "  Fråga AI från mobilen:   http://$IP:$WEB_PORT/ai/"
echo ""
echo "  Låt det här fönstret vara öppet. Tryck Ctrl+C för att stänga av."
echo ""
[ "${1:-}" = "--open" ] && open "http://localhost:$WEB_PORT"
wait $LIB_PID
