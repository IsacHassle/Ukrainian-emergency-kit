#!/bin/bash
# Reads the country config (config/country.json) for the shell scripts, so no script has a country's facts
# written into it (ADR 0002). Source it, then ask for one fact by its path:
#
#   . "$KIT/scripts/country.sh"
#   main_model=$(country ai.models.main)
#   country map.bbox            # a list prints one item per line
#   country map.regions.0.slug  # numbers index into lists
#
# A text per language prints in the country's default language. EK_COUNTRY names another config file (tests).
# Uses the macOS system python3, as the other scripts do.
country() {
  /usr/bin/python3 - "${EK_COUNTRY:-${KIT:?}/config/country.json}" "$1" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as f:
    c = json.load(f)
v = c
for k in sys.argv[2].split("."):
    v = v[int(k)] if isinstance(v, list) else v[k]
if isinstance(v, dict) and c["default_language"] in v:
    v = v[c["default_language"]]
for item in (v if isinstance(v, list) else [v]):
    print(item)
PY
}
