# Credits and licences

The repository holds only the kit's own code and configuration (MIT licence, see `LICENSE`).
Everything below is downloaded by `install.sh` from its original source and keeps its own licence.
Nothing here is redistributed from this repository, except the map fonts and symbols in `web/map/assets/`
and the map viewer libraries in `web/map/lib/` (licences below), and the ready-made map search files
attached to the GitHub release, which are built from OpenStreetMap data.

## Offline libraries (Kiwix / openZIM)

Packaged by [Kiwix](https://kiwix.org) and [openZIM](https://openzim.org), downloaded from download.kiwix.org.

| Library | Source | Licence |
|---|---|---|
| WikiMed (Wikipedia Medicine), Swedish Wikipedia | Wikipedia contributors | CC BY-SA 4.0 |
| MDWiki | mdwiki.org contributors | CC BY-SA 4.0 |
| MedlinePlus | US National Library of Medicine | Public domain (US government work) |
| CDC Health Information | US Centers for Disease Control and Prevention | Public domain (US government work) |
| Ready.gov | US Federal Emergency Management Agency (FEMA) | Public domain (US government work) |
| NHS Medicines A to Z | NHS England (nhs.uk) | Open Government Licence v3.0 |
| Military Medicine | US military field manuals, via irp.fas.org | Public domain (US government work) |
| Medical Library, Water Treatment, Food for Preppers, A Library of Knots, Post Disaster Resource Library | Collections compiled by openZIM ("zimgit") from freely available books and guides | Each work keeps its own licence |
| Low-tech Magazine | Kris De Decker, solar.lowtechmagazine.com | CC BY-NC-SA 4.0 |
| Optional extras in `config/libraries.txt` | Wikipedia, iFixit, Stack Exchange, Appropedia, CD3WD | CC BY-SA or CC BY-NC-SA, see each source |

The books extracted by `scripts/extract-documents.py` come from these libraries and keep their licences.

## Official Guides (Ukrainian authorities)

Saved by `scripts/fetch-pages.py` from each authority's own website, on the user's own computer, for reading
without internet. The list is `config/pages.txt`. Not redistributed from this repository; a Kit Drive is a copy from
person to person.

- [dovidka.info](https://dovidka.info) (the government's information site, written with the State Emergency Service): advice pages in Ukrainian and English, the handbook *У разі надзвичайної ситуації або війни* (Центр стратегічних комунікацій та інформаційної безпеки, ДСНС, Міноборони) and the English brochure *Life in times of war*
- [Міністерство охорони здоров'я України (МОЗ)](https://moz.gov.ua): first aid, radiation, carbon monoxide
- [Центр громадського здоров'я (ЦГЗ)](https://phc.org.ua): water, infections, hypothermia
- [Товариство Червоного Хреста України](https://redcross.org.ua): mine danger, first aid leaflets and the first aid handbook for the public
- [ДСНС](https://dsns.gov.ua): optional, saved only where the site answers (it refuses requests from outside Ukraine)
Downloaded from msb.se / rib.msb.se, not redistributed.

## Maps

- Map data © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors, available under the
  [Open Database Licence (ODbL)](https://opendatacommons.org/licenses/odbl/). This includes the map search files.
- Map tiles cut from the [Protomaps](https://protomaps.com) daily builds; basemap style from
  [protomaps/basemaps](https://github.com/protomaps/basemaps) (BSD 3-Clause), as packaged by Project N.O.M.A.D.
- Fonts in `web/map/assets/fonts/`: Noto Sans (SIL Open Font Licence 1.1), via
  [protomaps/basemaps-assets](https://github.com/protomaps/basemaps-assets).
- Map symbols in `web/map/assets/sprites/`: protomaps/basemaps-assets (BSD 3-Clause / CC0).
- [MapLibre GL JS](https://github.com/maplibre/maplibre-gl-js) (BSD 3-Clause) and
  [PMTiles](https://github.com/protomaps/PMTiles) (BSD 3-Clause) in `web/map/lib/`.
- Addresses from OpenStreetMap Sweden, via [Geofabrik](https://download.geofabrik.de).

## AI

- [Ollama](https://ollama.com) (MIT) and [AnythingLLM](https://anythingllm.com) (MIT), installed from their official downloads.
- Gemma 4 models by Google, under the [Gemma Terms of Use](https://ai.google.dev/gemma/terms).
- [bge-m3](https://huggingface.co/BAAI/bge-m3) by BAAI (MIT), for searching the books.

## Programs

- [kiwix-tools](https://github.com/kiwix/kiwix-tools) (GPL-3.0), downloaded into `tools/`.
- [go-pmtiles](https://github.com/protomaps/go-pmtiles) (BSD 3-Clause), downloaded into `tools/`.
- [python-libzim](https://github.com/openzim/python-libzim) (GPL-3.0), Beautiful Soup (MIT), markdownify (MIT).

## Inspiration

This kit is built from the Swedish kit, [IsacHassle/Swedish-doomsdaykit](https://github.com/IsacHassle/Swedish-doomsdaykit) (MIT), at version 1.9.

[Project N.O.M.A.D.](https://github.com/Crosstalk-Solutions/project-nomad) by Crosstalk Solutions (Apache 2.0),
an offline knowledge server. This kit started from its library list and map style, rebuilt for a Mac and for Sweden.
