#!/bin/bash
# Makes a Kit Drive: a USB drive that installs the whole kit on another Mac with no internet.
#
#   bash scripts/make-kit-drive.sh [drive]      (or double-click "Створити USB - Make USB.command")
#
# Run it on a Kit Mac that has the kit fully installed. With no argument it lists the drives that are plugged in
# and asks which one. The drive must be exFAT (a Mac and most other computers read it, and it holds files over
# 4 GB, which the AI models are) and 64 GB or more. Free space is checked before anything is copied.
#
# Everything goes into one folder on the drive, so other files on the drive are left alone:
#
#   Emergency-Kit-Drive/
#     kit-drive.json      says this is a Kit Drive (format, models, when it was made); the installer looks for it
#     checksums.sha256    "<sha256>  <path>" for every other file in this folder, paths relative to this folder
#     kit/                the kit folder: code, Libraries, map, map search, Books, Official Guides, tools (without
#                         tools/venv: it holds symlinks and fixed paths, and is made again by get-tools.sh with
#                         internet; the Books are already taken out of the Libraries, so the install needs none).
#                         exFAT keeps no permissions, so the install must chmod +x scripts and tools/ again.
#     installers/         Ollama.dmg and AnythingLLM.dmg, as the internet install kept them
#     models/             the kit's three AI models in Ollama's own store layout (manifests/ and blobs/), so
#                         they copy straight into ~/.ollama/models
#     licences/           LICENSE, CREDITS.md and the READMEs
#
# Only the kit's own three models are copied: the two in the country config (ai.models) and bge-m3, each with the
# blobs its manifest names and no other. The Swedish kit's `crisis` models share blobs with `emergency`, but their
# manifests are never copied. Run it again to finish an interrupted copy: files already on the drive are skipped.
#
# For tests: EK_FREE_GB, EK_DRIVE_GB and EK_DRIVE_FS stand in for the drive's free space, size and format, and
# OLLAMA_MODELS (as Ollama itself reads it) points at another model folder than ~/.ollama/models.
set -eu
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=country.sh
. "$KIT/scripts/country.sh"   # the country's facts (config/country.json)
# shellcheck source=say.sh
. "$KIT/scripts/say.sh"
step() { printf '\n\033[1m==> %s / %s\033[0m\n' "$1" "$2"; }
STORE="${OLLAMA_MODELS:-$HOME/.ollama/models}"
MODELS="$(country ai.models.main):latest $(country ai.models.small):latest bge-m3:latest"
MIN_DRIVE_GB=59   # a "64 GB" drive shows as about 59.6 GiB

# Which drive: the argument, or a choice among the plugged-in drives.
DEST="${1:-}"
if [ -z "$DEST" ]; then
  vols=()
  for v in /Volumes/*; do [ -d "$v" ] && [ "$(stat -f %d "$v")" != "$(stat -f %d /)" ] && vols+=("$v"); done
  if [ ${#vols[@]} -eq 0 ]; then
    say "Не знайдено жодного USB-диска. Підключіть диск і запустіть знову" "No USB drive found. Plug one in and run this again"; exit 1
  fi
  say "Які диски підключено:" "The drives that are plugged in:"
  i=1; for v in "${vols[@]}"; do echo "  $i) $v"; i=$((i + 1)); done
  read -r -p "Номер диска / Number of the drive: " n
  DEST="${vols[$((n - 1))]:-}"
  [ -n "$DEST" ] || { say "Такого диска немає" "There is no such drive"; exit 1; }
fi
if [ ! -d "$DEST" ]; then
  say "Немає такої теки або диска: $DEST" "There is no such folder or drive: $DEST"; exit 1
fi
DEST="$(cd "$DEST" && pwd)"
OUT="$DEST/Emergency-Kit-Drive"
case "$OUT/" in "$KIT"/*) say "Не можна робити диск усередині самої валізи" "A Kit Drive cannot be made inside the kit itself"; exit 1 ;; esac

# What the drive must be: exFAT, 64 GB or more, with room for the kit. All of it is checked before anything is copied.
fs="${EK_DRIVE_FS:-$(diskutil info "$DEST" 2>/dev/null | sed -n 's/^ *File System Personality: *//p')}"
if [ -n "$fs" ] && [ "$fs" != "ExFAT" ]; then
  say "Диск має формат $fs, а потрібен exFAT. Відформатуйте його в Дисковій утиліті (Стерти, формат exFAT) і запустіть знову" \
      "The drive is formatted as $fs, it needs exFAT. Erase it in Disk Utility (format exFAT) and run this again"; exit 1
fi
drive_gb=${EK_DRIVE_GB:-$(df -k "$DEST" | awk 'NR==2 {print int(($3 + $4) / 1048576)}')}
if [ "$drive_gb" -lt "$MIN_DRIVE_GB" ]; then
  say "Диск замалий ($drive_gb ГБ): потрібен диск від 64 ГБ" "The drive is too small ($drive_gb GB): it needs to be 64 GB or more"; exit 1
fi

# The kit's three models: the blobs each manifest names. A model that is missing stops the run here.
list=$(mktemp)
trap 'rm -f "$list"' EXIT
# shellcheck disable=SC2086
miss=$(/usr/bin/python3 - "$STORE" "$list" $MODELS <<'PY'
import json, os, sys
store, out, models = sys.argv[1], sys.argv[2], sys.argv[3:]
paths, digests, missing = [], {}, []
for m in models:
    name, tag = m.split(":")
    rel = os.path.join("manifests", "registry.ollama.ai", "library", name, tag)
    try:
        with open(os.path.join(store, rel), encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, ValueError):
        missing.append(m)
        continue
    paths.append(rel)
    for layer in [manifest["config"]] + manifest["layers"]:
        blob = os.path.join("blobs", layer["digest"].replace(":", "-"))
        if not os.path.isfile(os.path.join(store, blob)):
            missing.append(m + " (" + blob + ")")
        digests[blob] = 1
with open(out, "w", encoding="utf-8") as f:
    f.write("".join(p + "\n" for p in paths + sorted(digests)))
print(" ".join(missing))
PY
)
if [ -n "$miss" ]; then
  say "У сховищі Ollama немає моделей: $miss. Спершу завершіть встановлення валізи" "These models are not in Ollama's store: $miss. Finish installing the kit first"; exit 1
fi

kit_excludes=(--exclude=/logs/ --exclude=/.git/ --exclude=/node_modules/ --exclude=/tests/ --exclude=/installers/ --exclude=/tools/venv/
              --exclude=.DS_Store '--exclude=*.part' --exclude=__pycache__/)
kb() { du -sk "$@" | awk '{s += $1} END {print s}'; }
need_kb=$(( $(kb "$KIT") ))   # an upper bound for the kit folder (it still counts what is left out)
models_kb=$(( $(cd "$STORE" && xargs -I{} du -sk "{}" < "$list" | awk '{s += $1} END {print s}') ))
need_kb=$(( (need_kb + models_kb) * 102 / 100 + 1024 ))
if [ -n "${EK_FREE_GB:-}" ]; then free_kb=$(( EK_FREE_GB * 1048576 )); else free_kb=$(df -k "$DEST" | awk 'NR==2 {print $4}'); fi
if [ -d "$OUT" ]; then free_kb=$(( free_kb + $(kb "$OUT") )); fi   # a second run only needs what is not copied yet
if [ "$free_kb" -lt "$need_kb" ]; then
  say "На диску вільно лише $((free_kb / 1048576)) ГБ, а потрібно $((need_kb / 1048576 + 1)) ГБ. Звільніть місце або візьміть більший диск" \
      "Only $((free_kb / 1048576)) GB free on the drive, it needs $((need_kb / 1048576 + 1)) GB. Free up space or use a bigger drive"; exit 1
fi

copy() {   # from, to, rsync options. exFAT keeps no permissions, and times only to 2 seconds.
  rsync -rt --modify-window=2 --partial "${@:3}" "$1" "$2"
}
mkdir -p "$OUT/kit" "$OUT/installers" "$OUT/models" "$OUT/licences"

step "1/5 Тека валізи (бібліотеки, мапа, книги)" "1/5 The kit folder (Libraries, map, Books)"
copy "$KIT/" "$OUT/kit/" "${kit_excludes[@]}" --delete-excluded
step "2/5 Інсталятори програм" "2/5 The app installers"
if [ -d "$KIT/installers" ]; then copy "$KIT/installers/" "$OUT/installers/" '--exclude=*.part'; fi
step "3/5 Моделі ШІ (лише три моделі валізи)" "3/5 The AI models (the kit's three only)"
# Ollama's own store layout, so the install from the drive can copy models/ straight into the store.
while IFS= read -r p; do mkdir -p "$OUT/models/$(dirname "$p")"; copy "$STORE/$p" "$OUT/models/$p"; done < "$list"
step "4/5 Ліцензії та подяки" "4/5 Licences and credits"
for f in LICENSE CREDITS.md README.md README.en.md; do if [ -f "$KIT/$f" ]; then cp "$KIT/$f" "$OUT/licences/$f"; fi; done

step "5/5 Контрольні суми (читаю все з диска, це триває)" "5/5 Checksums (reading everything back from the drive, this takes a while)"
/usr/bin/python3 - "$OUT" "$MODELS" "$(country kit_name.en)" <<'PY'
import datetime, json, sys
out, models, name = sys.argv[1], sys.argv[2].split(), sys.argv[3]
with open(out + "/kit-drive.json", "w", encoding="utf-8") as f:
    json.dump({"format": 1, "kit": name, "models": models,
               "made": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}, f, ensure_ascii=False, indent=1)
PY
sumlist="$OUT/checksums.sha256.part"
(cd "$OUT" && find . -type f ! -name checksums.sha256 ! -name checksums.sha256.part ! -name .DS_Store | sed 's|^\./||' | LC_ALL=C sort |
  while IFS= read -r p; do shasum -a 256 "$p"; done) > "$sumlist"
mv "$sumlist" "$OUT/checksums.sha256"

step "Готово" "Done"
say "Диск готовий: $OUT" "The Kit Drive is ready: $OUT"
say "Файлів у списку контрольних сум: $(wc -l < "$OUT/checksums.sha256" | tr -d ' ')" "Files in the checksum list: $(wc -l < "$OUT/checksums.sha256" | tr -d ' ')"
say "Безпечно витягніть диск у Finder, перш ніж відключати" "Eject the drive in Finder before unplugging it"
