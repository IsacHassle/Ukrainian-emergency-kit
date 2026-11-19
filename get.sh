#!/bin/bash
# Downloads the Emergency Kit and installs it in the folder Emergency-Kit in your home folder.
# Завантажує Тривожну валізу й встановлює її в теку Emergency-Kit у вашій домашній теці.
# Paste into Terminal / Вставте в Terminal:
#   curl -fsSL https://raw.githubusercontent.com/IsacHassle/Ukrainian-emergency-kit/main/get.sh | bash
set -eu
DEST="${EK_DIR:-$HOME/Emergency-Kit}"
if [ ! -f "$DEST/install.sh" ]; then
  echo "Завантажую валізу до $DEST / Downloading the kit to $DEST"
  mkdir -p "$DEST"
  curl -fsSL https://github.com/IsacHassle/Ukrainian-emergency-kit/archive/refs/heads/main.tar.gz | tar -xz --strip-components=1 -C "$DEST"
fi
exec bash "$DEST/install.sh" </dev/tty
