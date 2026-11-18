#!/bin/bash
# Double-click this file in Finder to start the crisis kit and open the start page.
# Keep the Terminal window open while you use it. Close it (or press Ctrl+C) to stop.
open -g -a Ollama 2>/dev/null        # the AI engine
open -g -a AnythingLLM 2>/dev/null   # answers from the books (starts in the background)
exec bash "$(dirname "$0")/scripts/share-library.sh" --open
