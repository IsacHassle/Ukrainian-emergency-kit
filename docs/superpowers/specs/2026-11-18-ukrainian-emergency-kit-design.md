# Emergency Kit / Тривожна валіза: design

Date: 2026-11-18
Repo: `IsacHassle/Ukrainian-emergency-kit` (public, MIT)
Based on: `IsacHassle/Swedish-doomsdaykit` (Krislåda) 1.9

## Purpose

An offline crisis kit for civilians in Ukraine during the war. One Mac holds medical and safety
libraries, the official Ukrainian guides, a map with shelters and help nearby, and a local AI that
answers from all of it. Phones and laptops on the same Wi-Fi use it through a browser, so one Mac can
serve a family at home or many people in a shelter during a blackout. Nothing needs the internet once
installed, and nothing leaves the Mac.

## Decisions

| Question | Decision |
|---|---|
| Devices | Mac with Apple Silicon, as the Swedish kit. Phones and other computers use it over Wi-Fi. Windows is a later, separate project. |
| Languages | Every page in Ukrainian and English with a switch (УКР / ENG). Ukrainian is the default. The AI answers in the language people write in, Russian included. |
| Users | Families at home, and community points (shelters, schools, Invincibility Points) where one Mac serves many phones. |
| Map | All of Ukraine and Moldova in full detail, plus a strip of about 100 km into Poland, Slovakia, Hungary and Romania. |
| Getting it | Internet install from the original sources, or install from a USB drive filled by someone who already has the kit. |
| Name | Kit: **Emergency Kit / Тривожна валіза**. Repo: `Ukrainian-emergency-kit` (GitHub allows only ASCII). Install folder: `~/Emergency-Kit`, Desktop shortcut "Тривожна валіза". |
| Code | Start from a copy of the Swedish kit, but country-neutral: all text in language files, all country facts in config files. The Swedish repo is not changed. |

Never in the kit: anything military. The map and the AI deal with civilian help only. Phone
positions stay on the local Wi-Fi.

## Content

### Libraries (Kiwix), about 13 GB

| Library | Kiwix name | Size |
|---|---|---|
| WikiMed in Ukrainian | `wikipedia_uk_medicine_maxi` | 0.4 GB |
| Ukrainian Wikipedia, opening sections | `wikipedia_uk_all_mini` | 4.4 GB |
| WikiMed (English) | `wikipedia_en_medicine_maxi` | 1.9 GB |
| MDWiki | `mdwiki_en_all_maxi` | 2.3 GB |
| MedlinePlus | `medlineplus.gov_en_all` | 1.9 GB |
| Military Medicine (trauma, bleeding, evacuation) | `irp.fas.org_en_military-medicine` | 0.07 GB |
| NHS Medicines A to Z | `nhs.uk_en_medicines` | 0.02 GB |
| Medical Library, Water Treatment, Food for Preppers, Knots, Post Disaster | `zimgit-*` | 0.9 GB |
| Low-tech Magazine (heat, cooking, power without the grid) | `solar.lowtechmagazine.com_mul_all` | 0.7 GB |

Ready.gov and CDC from the Swedish kit are dropped: the Ukrainian guides cover the same ground, and
CDC is US travel advice. Versions are pinned in `config/libraries.txt` and the installer falls back to
the newest version, as in the Swedish kit.

### Official Ukrainian guides

Saved as text on the user's own Mac at install time (as the 1177 and MCF pages are in the Swedish
kit), listed in `config/pages.txt`, checked weekly by the link check:

- dovidka.info (Centre for Strategic Communications, written with the State Emergency Service), in
  Ukrainian and English, including the handbook "In case of emergency or war" as PDF in both languages.
- State Emergency Service (ДСНС, dsns.gov.ua): air raid alert, shelters and where not to hide,
  shelling in the street, trapped under rubble, mines and unexploded ordnance, fire, blackouts.
- Ministry of Health (МОЗ) and the Public Health Center (ЦГЗ): first aid before medical help arrives,
  drinking water, infections.
- Ukrainian Red Cross: first aid.

File names start with the source ("ДСНС - …", "dovidka.info - …"), so the AI can name them.
The exact page list is chosen during the build and must pass the link check.

### Books for the AI

As in the Swedish kit: PDFs taken out of the zimgit and Military Medicine libraries (each book once),
every NHS Medicines page, the official guides and handbook, and the kit's own guide in both languages.
Embedded with bge-m3, which handles Ukrainian.

### AI

- Models as in the Swedish kit: Gemma 4 26B ("crisis") and E4B ("crisis-small"), bge-m3 for search.
- `config/AI-PROMPT.txt` written for Ukraine: emergency numbers 101 (fire and rescue), 102 (police),
  103 (ambulance), 104 (gas), 112; air raid alert first steps; mines (do not touch, mark the place,
  call 101); carbon monoxide from generators and stoves; potassium iodide only on official instruction;
  Ukrainian guides first; answer in the user's language, never mixing languages.
- "From the books" mode searches the embedded books and the Kiwix libraries. The quick planning step
  returns article titles in both Ukrainian and English: Ukrainian titles for Ukrainian WikiMed, English
  titles for WikiMed, MDWiki and MedlinePlus. Which Kiwix libraries are searched comes from
  `config/country.json`.

### Start page emergency topics

One tap each; the official Ukrainian guide opens first, Ukrainian WikiMed second: bleeding and
tourniquet, blast injuries, crush injuries and being under rubble, CPR, burns, shock, hypothermia,
carbon monoxide, mines and unexploded ordnance, radiation. Defined in `config/country.json`.

## Map

- **Area:** Ukraine and Moldova in full detail; a strip of about 100 km into Poland, Slovakia, Hungary
  and Romania; the world as a coarse overview. Cut with the shape in `config/map-area.geojson`, not a
  rectangle, so Russia and Belarus are not carried in detail. Estimate: 6 to 8 GB.
- **Borders:** check how the Protomaps style draws Crimea and the occupied areas. If it shows Russia's
  claim as a border, change the style so the map follows Ukraine's internationally recognised borders.
- **Search:** every town, street and address in Ukraine and Moldova (Geofabrik extracts), towns and
  border crossings in the neighbouring strip. Matches Cyrillic and Latin ("Київ", "Kyiv", "Kiev") using
  `name`, `name:uk`, `name:en` and a Ukrainian-to-Latin transliteration. Built ahead of time and
  attached to the GitHub release as `map-search.tar.gz`, as in the Swedish kit.
- **Nearest:** shelters (`bunker_type=bomb_shelter`, `shelter_type=bomb_shelter`, `air_raid_shelter`),
  hospitals, clinics, pharmacies, drinking water, food shops, fuel, police, fire and rescue stations,
  border crossings. The shelter list always says: "Not every shelter is on the map. Follow local signs
  and your local authority." Invincibility Points are not in the map data and are left out.
- **Where am I:** USB GPS receiver or a phone sharing its position, as in the Swedish kit.

## Code organisation

The repo starts from a copy of the Swedish kit at 1.9; the commit that imports it says so, and
CREDITS.md names the Swedish kit and Project N.O.M.A.D.

### Country facts: `config/`

| File | Holds |
|---|---|
| `country.json` | Kit name per language, default language, emergency numbers, map search regions (Geofabrik names), Kiwix libraries the AI searches and in which language, emergency topics, extra checklist items |
| `map-area.geojson` | The map's shape |
| `libraries.txt` | Kiwix libraries to download |
| `pages.txt` | Official guides to save (replaces `swedish-pages.txt`) |
| `AI-PROMPT.txt` | The AI's instructions |
| `document-names.json` | Book names inside the zimgit libraries, as now |

Scripts read these instead of having a country written into them: `build-home.py`, `get-maps.sh`,
`build-map-index.py`, `fetch-pages.py` (renamed from `fetch-swedish-pages.py`), `get-documents.sh`,
`extract-documents.py`, `kit_search.py`, `kontroll.sh`, `check-links.py`.

### Text: `web/lang/`

- `uk.json` and `en.json` hold every text the pages show. Pages mark text with `data-t="key"`;
  `web/lib/i18n.js` fills them in and offers `t(key)` to page scripts.
- A switch УКР | ENG on every page. The choice is kept in `localStorage` (wrapped in try/catch, falling
  back to Ukrainian), so each phone remembers its own language.
- `build-home.py` writes the start page with the same keys, so it switches like the other pages.
- Terminal messages from the installer and scripts are written once in both languages on one line
  ("Завантажую бібліотеки / Downloading libraries").
- `README.md` in Ukrainian, `README.en.md` in English, linked at the top of each. The printable guide is
  made in both languages.

### Command files (double-click)

`Встановити - Install.command`, `Запустити - Start.command`, `Перевірити - Check.command`,
`Створити USB - Make USB.command`.

## Community points

### QR poster

A printable A4 page, in both languages. The person running the point types the Wi-Fi name and password;
the page draws one QR code that joins the Wi-Fi and one that opens the kit, plus the kit's address
written out and the emergency numbers. The password is only used to draw the code: never saved, never
sent. QR codes come from a small bundled library (MIT), so it works offline.

### Several people asking the AI

`serve-web.py` lets one AI answer run at a time, whichever model it uses, and the answer's search step
counts as part of it (two models at once would not fit in a 16 GB Mac). Others wait in a queue and the AI page shows
their place ("У черзі: ви 2-й / In queue: you are 2nd"), updated as the queue moves. A person who
leaves the page leaves the queue. The guide explains running a point with any Wi-Fi router powered by a
power bank or UPS.

## USB install

- **Make a drive:** `Створити USB - Make USB.command` on a Mac with the kit installed copies to a drive
  of 64 GB or more (exFAT): the kit folder with libraries, map, map search and documents; the three AI
  models from Ollama's model folder; the Ollama and AnythingLLM installers (the internet install keeps
  them for this); CREDITS.md and the licences; and a SHA-256 checksum list. It checks free space first.
- **Install from the drive:** `Встановити - Install.command` on the drive notices it is on a drive with
  a checksum list. It checks every file, copies the kit to `~/Emergency-Kit`, installs the apps, puts the
  models into Ollama, and builds the AI index locally (about 40 minutes). No internet needed.
- The repo itself still redistributes nothing; copying person to person follows each source's licence.

## Size

About 47 to 49 GB: libraries about 13 GB, map 6 to 8 GB, AI models 27 GB, books and index about 1 GB.
The installer checks for 55 GB free.

## Testing

**On every push (GitHub):** `bash -n` and ShellCheck on the scripts, Python syntax, `country.json` and
`map-area.geojson` valid, every key in `uk.json` exists in `en.json` and the reverse, every `data-t`
key used in `web/` exists. **Weekly:** link check of `config/pages.txt`.

**Before the first release, on the development Mac:**
- Installer steps in a fresh folder; a USB install using a separate Ollama model folder and AnythingLLM
  storage, to act as a second Mac.
- Map search: "Хрещатик 22, Київ", "Kyiv", "Kiev", "Львів", the Shehyni border crossing, a town in
  Moldova. Nearest shelter, hospital and pharmacy from Kyiv, Kharkiv and Odesa. How Crimea is drawn.
- AI in Ukrainian, Russian and English: tourniquet, a mine found in a field, a generator indoors, an air
  raid alert with children. Each answer has fitting sources and the right emergency numbers.
- Screenshots of every page in both languages on desktop and mobile width; three AI questions at once
  (queue); GPS with a simulated receiver.

**Known limits:** the Ukrainian text is written by a strong but non-native writer; the README asks for
corrections and a native speaker should read it before wide sharing. Not tested: a real USB GPS
receiver, a full install on a clean Mac, the USB drive on a second physical Mac.

## Out of scope

Windows (a separate project later, for both kits), an Android app, live air raid alerts (they need the
internet), a Russian interface, Invincibility Points, anything military, changes to the Swedish repo.
