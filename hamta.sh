#!/bin/bash
# Hämtar Krislåda och installerar den i mappen Krislåda i din hemmapp.
# Klistra in i Terminal:
#   curl -fsSL https://raw.githubusercontent.com/IsacHassle/Swedish-doomsdaykit/main/hamta.sh | bash
set -eu
DEST="${KRISLADA_DIR:-$HOME/Krislåda}"
if [ ! -f "$DEST/install.sh" ]; then
  echo "Hämtar Krislåda till $DEST"
  mkdir -p "$DEST"
  curl -fsSL https://github.com/IsacHassle/Swedish-doomsdaykit/archive/refs/heads/main.tar.gz | tar -xz --strip-components=1 -C "$DEST"
fi
exec bash "$DEST/install.sh" </dev/tty
