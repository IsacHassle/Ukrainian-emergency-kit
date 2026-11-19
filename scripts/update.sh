#!/bin/bash
# Update: refreshes the kit when there is internet. Every message is on one line in both languages.
#   1. the kit's code (the newest from GitHub; your Libraries, map and Books are not touched)
#   2. the Libraries: newer versions are downloaded, checked, and replace the old ones
#   3. the Official Guides: saved again; a guide that did not change stays as it was
#   4. the Books of every Library that changed: new Books added, changed Books replaced
#   5. the Book index: only new and changed Books are read in again (scripts/embed-documents.sh)
# Without internet it says so and changes nothing.
#
# Run: double-click "Оновити - Update.command", or: bash scripts/update.sh
# For tests: the same EK_ variables as install.sh and check.sh (EK_APPS, EK_ANYTHINGLLM, EK_OLLAMA, EK_NO_PAUSE).
set -u
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=country.sh
. "$KIT/scripts/country.sh"   # the country's facts (config/country.json)
# shellcheck source=say.sh
. "$KIT/scripts/say.sh"
APPS="${EK_APPS:-/Applications}"
ANYTHINGLLM_ADDR="${EK_ANYTHINGLLM:-localhost:3001}"
OLLAMA_ADDR="${EK_OLLAMA:-127.0.0.1:11434}"
CODE_URL="https://github.com/$(country repo)/archive/refs/heads/main.tar.gz"
step() { printf '\n\033[1m==> %s / %s\033[0m\n' "$1" "$2"; }

# The whole script is one function, read before it runs: step 1 replaces the files of the kit, this one included.
main() {
  # Kiwix is where the biggest part of the update comes from, so it is the test of the internet.
  if ! curl -fsI --max-time 10 https://download.kiwix.org/zim/ >/dev/null 2>&1; then
    say "Немає інтернету. Нічого не змінено. Підключіться до Wi-Fi й запустіть оновлення знову" \
        "There is no internet. Nothing was changed. Connect to Wi-Fi and run the update again"
    return 1
  fi

  step "1/5 Код валізи" "1/5 The kit's code"
  tmp=$(mktemp -d)
  if curl -fsSL --max-time 300 -o "$tmp/code.tar.gz" "$CODE_URL" && mkdir "$tmp/code" && tar -xzf "$tmp/code.tar.gz" --strip-components=1 -C "$tmp/code" && [ -n "$(ls -A "$tmp/code")" ]; then
    cp -R "$tmp/code/." "$KIT/"
    chmod +x "$KIT"/scripts/*.sh "$KIT"/*.command 2>/dev/null
    say "Код валізи оновлено" "The kit's code is updated"
  else
    say "Не вдалося завантажити новий код, лишаю як є" "Could not download the new code, keeping it as it is"
  fi
  rm -rf "$tmp"

  step "2/5 Бібліотеки" "2/5 Libraries"
  before=$(cd "$KIT/library" 2>/dev/null && ls ./*.zim 2>/dev/null | sed 's|^\./||')
  bash "$KIT/scripts/update-libraries.sh"
  after=$(cd "$KIT/library" 2>/dev/null && ls ./*.zim 2>/dev/null | sed 's|^\./||')
  # A Library changed when its file name (its version) is not the one it had. The name without the version is
  # what the Books are taken out by.
  changed=$(printf '%s\n' "$before" "$after" | sort | uniq -u | sed 's/_[0-9]\{4\}-[0-9]\{2\}[a-z]\{0,1\}\.zim$//' | sort -u | grep . || true)

  step "3/5 Офіційні посібники" "3/5 Official Guides"
  bash "$KIT/scripts/get-documents.sh" --guides-only --refresh

  step "4/5 Книги з нових версій бібліотек" "4/5 Books from the new versions of the Libraries"
  if [ -n "$changed" ] && [ -x "$KIT/tools/venv/bin/python" ]; then
    # shellcheck disable=SC2086
    "$KIT/tools/venv/bin/python" "$KIT/scripts/extract-documents.py" --update $changed
  else
    say "Жодна бібліотека з книгами не змінилася" "No Library with Books has changed"
  fi

  step "5/5 Індекс книг у ШІ" "5/5 The Book index in the AI"
  if [ ! -d "$APPS/AnythingLLM.app" ]; then
    say "ШІ не встановлено, індекс пропущено" "The AI is not installed, the index is skipped"
  else
    if ! curl -fs -o /dev/null --max-time 3 "http://$ANYTHINGLLM_ADDR/api/ping"; then
      open -g -a Ollama; open -g -a AnythingLLM
      for _ in $(seq 1 45); do
        curl -fs -o /dev/null --max-time 3 "http://$ANYTHINGLLM_ADDR/api/ping" && break
        [ -n "${EK_NO_PAUSE:-}" ] || sleep 2
      done
    fi
    if curl -fs -o /dev/null --max-time 3 "http://$ANYTHINGLLM_ADDR/api/ping" && curl -fs -o /dev/null --max-time 3 "http://$OLLAMA_ADDR/api/version"; then
      bash "$KIT/scripts/embed-documents.sh"
      # What this run did, from the end of the log (it starts at the last "=== START").
      log="$KIT/logs/embed.log"
      new=$(awk '/=== START/ {n = 0} / UPLOADED / {n++} END {print n + 0}' "$log")
      replaced=$(awk '/=== START/ {n = 0} / REPLACED / {n++} END {print n + 0}' "$log")
      say "Книги в індексі: нових $new, змінених $replaced" "Books in the index: $new new, $replaced changed"
    else
      say "ШІ не запущено. Відкрийте AnythingLLM і Ollama й виконайте: bash scripts/embed-documents.sh" \
          "The AI is not running. Open AnythingLLM and Ollama and run: bash scripts/embed-documents.sh"
    fi
  fi

  step "Готово" "Done"
  say "Оновлення завершено. Перезапустіть валізу, щоб побачити нові версії" "The update is finished. Restart the kit to see the new versions"
  say "Перевірити: двічі клацніть «Перевірити - Check.command»" "Check: double-click \"Перевірити - Check.command\""
}
main "$@"
exit $?
