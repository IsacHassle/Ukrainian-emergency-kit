#!/bin/bash
# Downloads the offline libraries listed in config/libraries.txt into library/.
# Safe to re-run at any time: finished files are skipped, partial ones resume,
# and every file is checked against Kiwix's published SHA-256 before it is kept.
#
# Kiwix removes old versions after a while. If a listed version is gone, the newest
# version of the same library is downloaded instead, so the kit keeps installing.
# When a newer version is in place, older versions of that library are removed.
#
# Run:   bash scripts/download-library.sh [list-file]
# Watch: tail -f logs/download.log

set -u
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # the kit folder (where this repo is)
DIR="$KIT/library"
LIST="${1:-$KIT/config/libraries.txt}"
LOG="$KIT/logs/download.log"
mkdir -p "$DIR" "$(dirname "$LOG")"
# shellcheck source=say.sh
. "$KIT/scripts/say.sh"

# The listed URL if Kiwix still has it, otherwise the newest version of the same library.
# A version is a year and month, sometimes with a letter after (nhs.uk_en_medicines_2026-09b).
resolve() {
  local url="$1" dir name stem newest
  if curl -sfIL -o /dev/null --max-time 60 "$url"; then echo "$url"; return; fi
  dir="${url%/*}/"; name=$(basename "$url"); stem="${name%_*}"
  newest=$(curl -sfL --max-time 60 "$dir" | grep -oE "\"${stem//./\\.}_[0-9]{4}-[0-9]{2}[a-z]?\.zim\"" | tr -d '"' | sort | tail -1)
  if [ -n "$newest" ]; then echo "$dir$newest"; else echo "$url"; fi
}

fetch() {
  local listed="$1" url name stem f want got ok old
  name=$(basename "$listed")
  if [ -f "$DIR/$name" ]; then echo "SKIP $name (вже є / already there)"; return 0; fi
  url=$(resolve "$listed")
  name=$(basename "$url"); stem="${name%_*}"; f="$DIR/$name"
  if [ -f "$f" ]; then echo "SKIP $name (вже є / already there)"; return 0; fi
  [ "$url" != "$listed" ] && echo "NEW  $name (Kiwix більше не має $(basename "$listed"), беру найновішу версію / Kiwix no longer has $(basename "$listed"), taking the newest version)"

  want=$(curl -sSL --fail "$url.sha256" 2>/dev/null | awk '{print $1}')
  if [ -f "$f.part" ] && [ -n "$want" ] && [ "$(shasum -a 256 "$f.part" | awk '{print $1}')" = "$want" ]; then
    mv "$f.part" "$f"; echo "OK   $name"
  else
    echo "GET  $name"
    ok=0
    for attempt in 1 2 3 4 5; do
      curl -sSL --fail -C - --retry 5 --retry-delay 15 -o "$f.part" "$url" && { ok=1; break; }
      echo "RETRY $name (спроба $attempt / attempt $attempt)"; sleep 30
    done
    if [ $ok = 0 ]; then echo "FAIL $name (завантаження перервалося, запустіть ще раз: воно продовжиться з того місця / the download stopped, run again and it continues where it stopped)"; return 0; fi
    got=$(shasum -a 256 "$f.part" | awk '{print $1}')
    if [ -n "$want" ] && [ "$got" = "$want" ]; then
      mv "$f.part" "$f"; echo "OK   $name"
    else
      rm -f "$f.part"; echo "FAIL $name (контрольна сума не збігається, запустіть ще раз / the checksum does not match, run again)"; return 0
    fi
  fi
  # A newer version is in place: remove the older ones of the same library.
  for old in "$DIR/${stem}_"*.zim; do
    [ "$old" != "$f" ] && [ -f "$old" ] && rm -f "$old" && echo "DEL  $(basename "$old") (замінено на $name / replaced by $name)"
  done
  return 0
}
export -f resolve fetch
export DIR

echo "=== START $(date)" >> "$LOG"
sed 's/#.*//' "$LIST" | awk '{print $1}' | grep . | xargs -P 3 -I{} bash -c 'fetch "$1"' _ {} 2>&1 | tee -a "$LOG"
echo "=== DONE $(date)" >> "$LOG"
