#!/bin/bash
# Downloads the offline maps into maps/:
#   world.pmtiles   the whole world, overview only (about 45 MB)
#   sweden.pmtiles  all of Sweden at full street detail (about 4.5 GB)
# cut from the latest Protomaps daily build of OpenStreetMap. Then gets the map search
# (every town, street, address and service in Sweden) for web/map/data/.
# Safe to re-run: finished maps are skipped.
set -eu
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
M="$KIT/maps"
PMTILES="$KIT/tools/pmtiles"
SWEDEN_BBOX="10.5,55.0,24.3,69.2"   # all of Sweden (the box also takes in edges of Norway, Finland, Denmark)
REPO="${KIT_REPO:-IsacHassle/Swedish-doomsdaykit}"
mkdir -p "$M"

# The newest daily build that exists (they are kept for a few days).
build=""
for d in 0 1 2 3 4 5 6 7; do
  day=$(date -v-"${d}"d +%Y%m%d)
  if curl -fsI "https://build.protomaps.com/$day.pmtiles" >/dev/null 2>&1; then build="https://build.protomaps.com/$day.pmtiles"; break; fi
done
[ -n "$build" ] || { echo "Kunde inte nå build.protomaps.com. Kontrollera internetanslutningen och försök igen."; exit 1; }

valid() { [ -f "$1" ] && [ "$(head -c 7 "$1")" = "PMTiles" ]; }

if ! valid "$M/world.pmtiles"; then
  echo "Hämtar världskartan (översikt)"
  "$PMTILES" extract "$build" "$M/world.pmtiles.part" --maxzoom=6 && mv "$M/world.pmtiles.part" "$M/world.pmtiles"
fi
if ! valid "$M/sweden.pmtiles"; then
  echo "Hämtar Sverigekartan (cirka 4,5 GB, det tar en stund)"
  "$PMTILES" extract "$build" "$M/sweden.pmtiles.part" --bbox="$SWEDEN_BBOX" && mv "$M/sweden.pmtiles.part" "$M/sweden.pmtiles"
fi

# Map search. Ready-made files from the GitHub release; or build your own from
# OpenStreetMap with scripts/build-map-index.py (needs osmium).
DATA="$KIT/web/map/data"
if [ ! -f "$DATA/places.json.gz" ]; then
  echo "Hämtar kartans sökning"
  tmp=$(mktemp -d)
  curl -fsSL -o "$tmp/map-search.tar.gz" "https://github.com/$REPO/releases/latest/download/map-search.tar.gz"
  mkdir -p "$DATA" && tar -xzf "$tmp/map-search.tar.gz" -C "$DATA"
  rm -rf "$tmp"
fi
echo "Kartorna är klara."
