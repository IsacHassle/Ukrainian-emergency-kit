#!/bin/bash
# Тривожна валіза / Emergency Kit: installation. Every message is on one line in both languages.
#
#   ./install.sh           everything (about 45 GB, a few hours)
#   ./install.sh --no-ai   without the AI (about 20 GB)
#
# Needs a Mac with Apple silicon (M1 or newer) and internet while it installs. After that everything works without
# internet. Run it again at any time: it continues where it stopped and skips what is already done.
#
# For tests, EK_UNAME_S and EK_UNAME_M stand in for the kind of Mac, EK_FREE_GB for the free space and EK_APPS for
# the folder the apps go in (/Applications), so the refusals can be tested without a full disk or another Mac.
set -eu
KIT="$(cd "$(dirname "$0")" && pwd)"
AI=1
case "${1:-}" in --no-ai) AI=0 ;; esac
# shellcheck source=scripts/say.sh
. "$KIT/scripts/say.sh"
step() { printf '\n\033[1m==> %s / %s\033[0m\n' "$1" "$2"; }
APPS="${EK_APPS:-/Applications}"
KIT_HOME="$HOME/Emergency-Kit"

# A folder in Downloads moves to the home folder first, so that the kit has a fixed home.
if [[ "$KIT" == "$HOME/Downloads/"* ]] && [ ! -e "$KIT_HOME" ]; then
  say "Переношу валізу з Завантажень до $KIT_HOME" "Moving the kit from Downloads to $KIT_HOME"
  mv "$KIT" "$KIT_HOME"
  exec bash "$KIT_HOME/install.sh" "$@"
fi
cd "$KIT"
# A Kit Drive: this install.sh is in the kit/ folder of one (../kit-drive.json is its marker, see
# scripts/make-kit-drive.sh). Then nothing is downloaded: every file is checked against the checksum list, the kit
# is copied to its home and the install carries on from there, with the apps and the AI models taken from the drive.
DRIVE=""
if [ -z "${EK_DRIVE:-}" ] && [ -f "$KIT/../kit-drive.json" ]; then DRIVE="$(cd "$KIT/.." && pwd)"; fi
# shellcheck source=scripts/country.sh
. "$KIT/scripts/country.sh"   # the country's facts (config/country.json)

# The checks come first, before anything is downloaded.
if [ "${EK_UNAME_S:-$(uname -s)}" != Darwin ] || [ "${EK_UNAME_M:-$(uname -m)}" != arm64 ]; then
  say "Потрібен Mac з чипом Apple (M1 або новіший)" "The kit needs a Mac with an Apple chip (M1 or newer)"; exit 1
fi
need=$([ $AI = 1 ] && echo 55 || echo 22)
if [ -n "$DRIVE" ]; then
  mkdir -p "$HOME"
  free_gb=${EK_FREE_GB:-$(df -k "$HOME" | awk 'NR==2 {print int($4 / 1048576)}')}   # the space is needed on this Mac, not on the drive
  if [ "$free_gb" -lt "$need" ] && [ ! -d "$KIT_HOME" ]; then
    say "Тут вільно лише $free_gb ГБ, а валізі потрібно $need ГБ. Звільніть місце й запустіть знову" \
        "Only $free_gb GB free here, the kit needs $need GB. Free up some space and run it again"; exit 1
  fi
  step "Диск із валізою: перевіряю кожен файл" "Kit Drive: checking every file"
  bash "$KIT/scripts/install-from-drive.sh" verify "$DRIVE"
  step "Копіюю валізу на цей Mac" "Copying the kit to this Mac"
  bash "$KIT/scripts/install-from-drive.sh" copy "$DRIVE" "$KIT_HOME"
  EK_DRIVE="$DRIVE" exec bash "$KIT_HOME/install.sh" "$@"
fi
free_gb=${EK_FREE_GB:-$(df -k "$KIT" | awk 'NR==2 {print int($4 / 1048576)}')}
# Once the map is in place the install is a resume, and the space it still needs is smaller.
if [ ! -f "$KIT/maps/$(country map.pmtiles).pmtiles" ] && [ "$free_gb" -lt "$need" ]; then
  say "Тут вільно лише $free_gb ГБ, а валізі потрібно $need ГБ. Звільніть місце й запустіть знову" \
      "Only $free_gb GB free here, the kit needs $need GB. Free up some space and run it again"; exit 1
fi
chmod +x "$KIT"/scripts/*.sh "$KIT"/*.command
xattr -dr com.apple.quarantine "$KIT" 2>/dev/null || true   # so the double-click files open without a warning

# The app installers are kept in installers/ (a Kit Drive carries them to a Mac with no internet), so the app is
# installed from the kept file.
mkdir -p "$KIT/installers" "$APPS"
install_app() {   # name, address of the dmg file
  local dmg="$KIT/installers/$1.dmg" tmp vol
  if [ ! -s "$dmg" ]; then
    say "Завантажую інсталятор $1" "Downloading the $1 installer"
    curl -fL --progress-bar -o "$dmg.part" "$2"
    mv "$dmg.part" "$dmg"
  fi
  [ -d "$APPS/$1.app" ] && return 0
  say "Встановлюю $1" "Installing $1"
  tmp=$(mktemp -d)
  vol=$(hdiutil attach -nobrowse -readonly "$dmg" | awk -F'\t' '/\/Volumes\// {print $NF; exit}')
  [ -n "$vol" ] || vol=$(hdiutil attach -nobrowse -readonly "$dmg" | awk -F'\t' '{print $NF; exit}')
  cp -R "$vol/$1.app" "$APPS/"
  hdiutil detach -quiet "$vol"
  rm -rf "$tmp"
}

if [ -n "${EK_DRIVE:-}" ]; then
  step "1-4/5 Інструменти, бібліотеки, мапа й книги вже з диска" "1-4/5 Tools, Libraries, map and Books came from the drive"
else
  step "1/5 Інструменти" "1/5 Tools"
  bash scripts/get-tools.sh

  step "2/5 Бібліотеки для читання без інтернету (близько 13 ГБ)" "2/5 Libraries for reading offline (about 13 GB)"
  bash scripts/download-library.sh
  if tail -n 60 logs/download.log | grep -q "^FAIL"; then
    say "Деякі бібліотеки не вдалося завантажити. Запустіть встановлення ще раз: воно спробує знову" \
        "Some libraries could not be downloaded. Run the installation again and it will try again"
  fi

  step "3/5 Мапа: $(country map.overview_label.uk) та світ (близько 3 ГБ)" "3/5 Map: $(country map.overview_label.en) and the world (about 3 GB)"
  bash scripts/get-maps.sh

  step "4/5 Офіційні посібники та книги" "4/5 Official Guides and Books"
  bash scripts/get-documents.sh
fi

if [ $AI = 1 ]; then
  step "5/5 ШІ на вашому Mac (близько 27 ГБ моделей, потім книги додаються до індексу)" "5/5 The AI on your Mac (about 27 GB of models, then the Books are indexed)"
  install_app Ollama "https://ollama.com/download/Ollama.dmg"
  install_app AnythingLLM "https://cdn.anythingllm.com/latest/AnythingLLMDesktop-Silicon.dmg"
  if [ -n "${EK_DRIVE:-}" ]; then
    # The models come from the drive, and the setup must not ask the internet for anything (EK_OFFLINE).
    bash scripts/install-from-drive.sh models "$EK_DRIVE"
    EK_OFFLINE=1 bash scripts/setup-ai.sh
  else
    bash scripts/setup-ai.sh
  fi
else
  step "5/5 ШІ пропущено (--no-ai)" "5/5 The AI is skipped (--no-ai)"
fi

# The Desktop shortcut: a link to the kit folder, named in Ukrainian, which is the name people know.
mkdir -p "$HOME/Desktop"
ln -sfn "$KIT" "$HOME/Desktop/$(country kit_name.uk)"
step "Готово" "Done"
say "Валіза лежить у $KIT (ярлик на робочому столі: «$(country kit_name.uk)»)" "The kit is in $KIT (shortcut on the Desktop: \"$(country kit_name.en)\")"
say "Запустити: двічі клацніть «Запустити - Start.command»" "Start: double-click \"Запустити - Start.command\""
say "Відкрити: http://localhost:8091 (телефони в тій самій Wi-Fi: адреса, яку покаже вікно запуску)" "Open: http://localhost:8091 (phones on the same Wi-Fi: the address the start window shows)"
say "Перевірити: двічі клацніть «Перевірити - Check.command»" "Check: double-click \"Перевірити - Check.command\""
say "Роздрукуйте «Тривожна валіза - посібник для друку.pdf» і покладіть біля валізи. Перевіряйте раз на місяць, вимкнувши Wi-Fi" \
    "Print \"Emergency Kit - printable guide.pdf\" and keep it with the kit. Check once a month with Wi-Fi turned off"
