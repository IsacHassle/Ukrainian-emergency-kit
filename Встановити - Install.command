#!/bin/bash
# Двічі клацніть, щоб встановити Тривожну валізу. Відкриється вікно Terminal і покаже, як іде робота.
# Це триває кілька годин (здебільшого завантаження). Можна закрити вікно й клацнути знову: робота триватиме з того місця, де зупинилась.
# Double-click to install the Emergency Kit. A Terminal window opens and shows how it goes.
# It takes a few hours (mostly downloading). You can close it and double-click again: it continues where it stopped.
cd "$(dirname "$0")" && exec bash ./install.sh
