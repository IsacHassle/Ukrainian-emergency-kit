#!/bin/bash
# Двічі клацніть, щоб оновити валізу, коли є інтернет: код, офіційні посібники, бібліотеки й книги в ШІ. Раз на місяць.
# Double-click to update the kit when you have internet: the code, the Official Guides, the Libraries and the Books in the AI. Once a month.
cd "$(dirname "$0")" && bash scripts/update.sh
echo; read -r -p "Натисніть Enter, щоб закрити / Press Enter to close."
