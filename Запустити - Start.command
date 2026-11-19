#!/bin/bash
# Двічі клацніть, щоб запустити валізу й відкрити початкову сторінку. Не закривайте вікно Terminal, поки користуєтеся нею.
# Закрийте вікно (або натисніть Ctrl+C), щоб зупинити.
# Double-click to start the kit and open the start page. Keep the Terminal window open while you use it.
# Close it (or press Ctrl+C) to stop.
open -g -a Ollama 2>/dev/null        # the AI engine
open -g -a AnythingLLM 2>/dev/null   # answers from the Books (starts in the background)
exec bash "$(dirname "$0")/scripts/share-library.sh" --open
