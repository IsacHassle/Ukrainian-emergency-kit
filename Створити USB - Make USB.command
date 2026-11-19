#!/bin/bash
# Двічі клацніть, щоб зробити диск для встановлення валізи на інших Mac без інтернету. Потрібен USB-диск від 64 ГБ у форматі exFAT.
# Double-click to make a Kit Drive that installs the kit on other Macs with no internet. Needs a USB drive of 64 GB or more, formatted as exFAT.
cd "$(dirname "$0")" && bash scripts/make-kit-drive.sh "$@"
echo; read -r -p "Натисніть Enter, щоб закрити / Press Enter to close."
