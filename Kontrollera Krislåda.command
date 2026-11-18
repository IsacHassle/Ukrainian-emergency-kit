#!/bin/bash
# Dubbelklicka för att kontrollera att Krislådan fungerar. Gör det en gång i månaden, gärna med wifi avstängt.
cd "$(dirname "$0")" && bash scripts/kontroll.sh
echo; read -r -p "Tryck Enter för att stänga."
