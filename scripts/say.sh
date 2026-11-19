#!/bin/bash
# Source it for `say`: every line the kit's scripts print holds both languages, Ukrainian first, then English,
# separated by " / " ("Завантажую бібліотеки / Downloading libraries"). One line, so a volunteer who reads either
# language can follow it, and a log can be read by both.
#
#   . "$KIT/scripts/say.sh"
#   say "Завантажую бібліотеки" "Downloading libraries"
say() { printf '%s / %s\n' "$1" "$2"; }
