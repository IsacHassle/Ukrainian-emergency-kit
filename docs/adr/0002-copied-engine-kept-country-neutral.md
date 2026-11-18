# The engine is copied from the Swedish kit and kept country-neutral

This kit started as a copy of the Swedish kit (Swedish-doomsdaykit, Krislåda) instead of sharing one engine
with it, so Ukraine could ship without reworking a kit Swedish families already use. To keep the two from
drifting for good, everything about a country lives in `config/` (country facts, sources, the map's shape, the
AI's instructions) and everything people read lives in `web/lang/`; the code holds neither. Moving the Swedish
kit onto this engine later should only take a Swedish `country.json` and `sv.json`, and a Windows version would
then serve both.
