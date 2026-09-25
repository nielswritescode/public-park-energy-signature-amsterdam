# Public park energy signature — Amsterdam

Base map of Amsterdam, ±10 km around Dam Square, rendered from OpenStreetMap data. Every public park is outlined in glowing neon.

<table>
<tr>
<td valign="top">

[<img src="assets/amsterdam-map-preview.jpg" width="640" alt="Map of Amsterdam, ±10 km, with public parks outlined in neon">](assets/amsterdam-map.jpg)

<sub>Click the map for the full-resolution image (8000 × 8000 px, 2.5 m per pixel).</sub>

</td>
<td valign="top" width="250">

<!-- legend:start -->

### Legend

| | |
|:-:|:--|
| ![Public park](assets/legend/park.png) | **Public park**<br>neon glowing outline |
| ![Other green](assets/legend/green.png) | Grass, gardens, woods |
| ![Water](assets/legend/water.png) | Water |
| ![Buildings](assets/legend/buildings.png) | Buildings |
| ![Motorway](assets/legend/motorway.png) | Motorway / trunk road |
| ![Main road](assets/legend/main-road.png) | Primary / secondary road |
| ![Street](assets/legend/street.png) | Local street |
| ![Paths](assets/legend/paths.png) | Footpath / cycle path |
| ![Railway](assets/legend/railway.png) | Railway |
| ![Residential](assets/legend/residential.png) | Residential area |
| ![Industrial](assets/legend/industrial.png) | Industrial / commercial |
| ![Sports](assets/legend/sports.png) | Sports & recreation |
| ![Farmland](assets/legend/farmland.png) | Farmland / allotments |

<!-- legend:end -->

</td>
</tr>
</table>

## About the map

- **Area:** 20 × 20 km centred on Dam Square (52.3731° N, 4.8926° E), i.e. ±10 km.
- **Public parks:** OSM `leisure=park`, `leisure=common` and `landuse=village_green`, excluding anything tagged `access=private|no|customers|permit|members`. 380 are mapped inside the map area (about 7% of it). The 348 of at least 200 m² are outlined; the 32 smaller ones are skipped.
- **Rendering:** the map is drawn from raw OSM data with a small Python renderer, in an OpenStreetMap-Carto-like palette. It is drawn as a 4 × 4 grid of tiles that are concatenated into one image. No map tiles are downloaded from OSM's tile servers.

## Edit the legend

The legend next to the map lives in [`legend.md`](legend.md). Edit it as plain markdown, then run:

```
python scripts/build_readme.py
```

This copies `legend.md` into the block between the `legend:start` / `legend:end` markers above. Swatch images are in [`assets/legend/`](assets/legend/).

## Rebuild

```
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt     # Windows; use .venv/bin on Linux/macOS
curl -L -o data/raw/Amsterdam.osm.pbf https://download.bbbike.org/osm/bbbike/Amsterdam/Amsterdam.osm.pbf
python scripts/extract.py                         # classify OSM features, cache them
python scripts/render.py                          # render assets/amsterdam-map.jpg
python scripts/build_readme.py                    # refresh the legend on this page
```

Colours, line widths and the neon glow are all in [`scripts/style.py`](scripts/style.py). `python scripts/render.py --res 10 --grid 1` gives a quick draft.

## Data

Map data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), available under the [Open Database Licence](https://opendatacommons.org/licenses/odbl/). Extract: [BBBike Amsterdam](https://download.bbbike.org/osm/bbbike/Amsterdam/), built 19 Sep 2026.
