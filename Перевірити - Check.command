#!/bin/bash
# Двічі клацніть, щоб перевірити, чи все в валізі працює. Робіть це раз на місяць, найкраще з вимкненим Wi-Fi.
# Double-click to check that the kit works. Do it once a month, best with Wi-Fi turned off.
cd "$(dirname "$0")" && bash scripts/check.sh
echo; read -r -p "Натисніть Enter, щоб закрити / Press Enter to close."
