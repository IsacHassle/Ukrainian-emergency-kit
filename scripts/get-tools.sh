#!/bin/bash
# Downloads the small programs the kit runs on (into tools/):
#   kiwix-serve  serves the offline libraries          (download.kiwix.org)
#   pmtiles      cuts the Sweden map out of the world map (github.com/protomaps/go-pmtiles)
#   a Python environment with libzim, used to take the books out of the libraries
# Safe to re-run: anything already there is skipped.
set -eu
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
T="$KIT/tools"
mkdir -p "$T"

KIWIX_VERSION=3.8.2
PMTILES_VERSION=1.31.2

if [ ! -x "$T/kiwix-tools/kiwix-serve" ]; then
  echo "Hämtar kiwix-serve $KIWIX_VERSION"
  curl -fsSL "https://download.kiwix.org/release/kiwix-tools/kiwix-tools_macos-arm64-$KIWIX_VERSION.tar.gz" | tar -xz -C "$T"
  rm -rf "$T/kiwix-tools" && mv "$T/kiwix-tools_macos-arm64-$KIWIX_VERSION" "$T/kiwix-tools"
  xattr -dr com.apple.quarantine "$T/kiwix-tools" 2>/dev/null || true
fi

if [ ! -x "$T/pmtiles" ]; then
  echo "Hämtar pmtiles $PMTILES_VERSION"
  tmp=$(mktemp -d)
  curl -fsSL -o "$tmp/pmtiles.zip" "https://github.com/protomaps/go-pmtiles/releases/download/v$PMTILES_VERSION/go-pmtiles-${PMTILES_VERSION}_Darwin_arm64.zip"
  unzip -q -o "$tmp/pmtiles.zip" pmtiles -d "$T"
  rm -rf "$tmp"
  xattr -d com.apple.quarantine "$T/pmtiles" 2>/dev/null || true
fi

if [ ! -x "$T/venv/bin/python" ]; then
  echo "Förbereder Python för att plocka ut böckerna"
  python3 -m venv "$T/venv"
  "$T/venv/bin/pip" install -q --disable-pip-version-check libzim beautifulsoup4 markdownify
fi
echo "Verktygen är klara."
