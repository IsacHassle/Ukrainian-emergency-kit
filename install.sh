#!/bin/bash
# Krislåda (Swedish-doomsdaykit): installation.
#
#   ./install.sh           allt (cirka 45 GB, några timmar)
#   ./install.sh --utan-ai utan AI:n (cirka 20 GB)
#
# Kräver en Mac med Apple-chip (M1 eller nyare) och internet medan den installeras.
# Sedan fungerar allt utan internet. Kör den igen när som helst: den fortsätter där
# den slutade och hoppar över det som redan är klart.
set -eu
KIT="$(cd "$(dirname "$0")" && pwd)"
AI=1
case "${1:-}" in --utan-ai|--no-ai) AI=0 ;; esac
step() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }

# Ligger mappen i Hämtade filer? Flytta den till hemmappen först, så att Krislådan har ett fast hem.
if [[ "$KIT" == "$HOME/Downloads/"* ]] && [ ! -e "$HOME/Krislåda" ]; then
  echo "Flyttar Krislåda från Hämtade filer till $HOME/Krislåda"
  mv "$KIT" "$HOME/Krislåda"
  exec bash "$HOME/Krislåda/install.sh" "$@"
fi
cd "$KIT"

if [ "$(uname -s)" != Darwin ] || [ "$(uname -m)" != arm64 ]; then
  echo "Krislådan kräver en Mac med Apple-chip (M1 eller nyare)."; exit 1
fi
free_gb=$(df -g "$KIT" | awk 'NR==2 {print $4}')
need=$([ $AI = 1 ] && echo 50 || echo 22)
if [ ! -f "$KIT/maps/sweden.pmtiles" ] && [ "$free_gb" -lt "$need" ]; then
  echo "Bara $free_gb GB ledigt här, Krislådan behöver cirka $need GB. Frigör utrymme och kör igen."; exit 1
fi
chmod +x "$KIT"/scripts/*.sh "$KIT"/*.command
xattr -dr com.apple.quarantine "$KIT" 2>/dev/null || true   # so "Starta Krislåda.command" opens without a warning

install_app() {   # namn, adress till dmg-filen
  [ -d "/Applications/$1.app" ] && return 0
  step "Installerar $1"
  tmp=$(mktemp -d)
  curl -fL --progress-bar -o "$tmp/app.dmg" "$2"
  vol=$(hdiutil attach -nobrowse -readonly "$tmp/app.dmg" | awk -F'\t' '/\/Volumes\// {print $NF; exit}')
  cp -R "$vol/$1.app" /Applications/
  hdiutil detach -quiet "$vol"
  rm -rf "$tmp"
}

step "1/5 Verktyg"
bash scripts/get-tools.sh

step "2/5 Bibliotek för offline-läsning (cirka 14 GB)"
bash scripts/download-library.sh
if tail -n 60 logs/download.log | grep -q "^FAIL"; then
  echo "Några bibliotek kunde inte hämtas. Kör installationen igen så försöker den på nytt."
fi

step "3/5 Kartor över Sverige och världen (cirka 4,5 GB)"
bash scripts/get-maps.sh

step "4/5 Dokument och böcker"
bash scripts/get-documents.sh

if [ $AI = 1 ]; then
  step "5/5 AI på din Mac (cirka 27 GB modeller, sedan läses böckerna in)"
  install_app Ollama "https://ollama.com/download/Ollama.dmg"
  install_app AnythingLLM "https://cdn.anythingllm.com/latest/AnythingLLMDesktop-Silicon.dmg"
  bash scripts/setup-ai.sh
else
  step "5/5 AI hoppades över (--utan-ai)"
fi

ln -sfn "$KIT" "$HOME/Desktop/Krislåda"
step "Klart"
cat <<EOF
Krislådan finns i $KIT (genväg på skrivbordet: "Krislåda").

  Starta:   dubbelklicka på "Starta Krislåda.command"
  Öppna:    http://localhost:8091  (mobiler på samma wifi: adressen som visas)

Skriv ut "Krislåda - guide att skriva ut.pdf" och lägg den hos din hemberedskap.
Testa en gång i månaden med wifi avstängt.
EOF
