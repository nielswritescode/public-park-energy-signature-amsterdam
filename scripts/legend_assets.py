"""Legend swatches drawn from the same palette as the map -> assets/legend/*.png

Also writes a starter legend.md, but never overwrites it: legend.md is yours to edit.
"""
from PIL import Image, ImageDraw

import style as st
from common import ROOT
from render import neon

OUT = ROOT / "assets" / "legend"
LEGEND_MD = ROOT / "legend.md"
W, H = 48, 30
EDGE = (190, 190, 190)


def area(fill, right=None):
    img = Image.new("RGB", (W, H), fill)
    if right:
        ImageDraw.Draw(img).rectangle([W // 2, 0, W, H], fill=right)
    return img


def road(rows):
    """rows: [(y, fill, casing, fill_w, casing_w)] drawn on the land colour."""
    img = Image.new("RGB", (W, H), st.LAND)
    d = ImageDraw.Draw(img)
    for y, _, casing, _, cw in rows:
        d.line([(-2, y), (W + 2, y)], fill=casing, width=cw)
    for y, fill, _, fw, _ in rows:
        d.line([(-2, y), (W + 2, y)], fill=fill, width=fw)
    return img


def park():
    img = Image.new("RGB", (W, H), dict(st.AREAS_BY_KIND)["park"])
    mask, hot = Image.new("L", (W, H), 0), Image.new("L", (W, H), 0)
    box = [10, 8, W - 11, H - 9]
    ImageDraw.Draw(mask).rectangle(box, outline=255, width=2)
    ImageDraw.Draw(hot).rectangle(box, outline=255, width=1)
    return neon(img, mask, hot, 0.4)


def buildings():
    img = Image.new("RGB", (W, H), st.LAND)
    d = ImageDraw.Draw(img)
    for x0, y0, x1, y1 in ((4, 5, 16, 14), (19, 5, 30, 14), (33, 5, 44, 14), (4, 18, 22, 26), (26, 18, 44, 26)):
        d.rectangle([x0, y0, x1, y1], fill=st.BUILDING, outline=st.BUILDING_EDGE)
    return img


def railway():
    img = Image.new("RGB", (W, H), st.LAND)
    d = ImageDraw.Draw(img)
    d.line([(0, H // 2), (W, H // 2)], fill=st.RAIL, width=4)
    for x in range(3, W, 8):
        d.line([(x, H // 2), (x + 3, H // 2)], fill=(255, 255, 255), width=2)
    return img


def paths():
    img = Image.new("RGB", (W, H), st.LAND)
    d = ImageDraw.Draw(img)
    d.line([(0, 10), (W, 10)], fill=st.ROADS["hw:footway"][0], width=2)
    d.line([(0, 20), (W, 20)], fill=st.ROADS["hw:cycleway"][0], width=2)
    return img


def sports():
    img = Image.new("RGB", (W, H), dict(st.AREAS_BY_KIND)["sports"])
    ImageDraw.Draw(img).rectangle([8, 6, W - 9, H - 7], outline=(181, 226, 198), width=2)
    return img


def swatches():
    A = dict(st.AREAS_BY_KIND)
    R = st.ROADS
    return {
        "park": park(),
        "green": area(A["grass"], A["wood"]),
        "water": area(st.WATER),
        "buildings": buildings(),
        "motorway": road([(H // 2, R["hw:motorway"][0], R["hw:motorway"][1], 7, 10)]),
        "main-road": road([(9, R["hw:primary"][0], R["hw:primary"][1], 5, 8),
                           (21, R["hw:secondary"][0], R["hw:secondary"][1], 5, 8)]),
        "street": road([(H // 2, (255, 255, 255), R["hw:residential"][1], 5, 7)]),
        "paths": paths(),
        "railway": railway(),
        "residential": area(A["residential"]),
        "industrial": area(A["industrial"], A["commercial"]),
        "sports": sports(),
        "farmland": area(A["farmland"], A["allotments"]),
    }


STARTER_LEGEND = """<!-- Edit this file freely: it is the legend shown next to the map on the main page.
     After editing, run  python scripts/build_readme.py  to refresh README.md.
     Swatches live in assets/legend/ - drop in your own PNGs and point at them below. -->

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
"""


def make():
    OUT.mkdir(parents=True, exist_ok=True)
    items = swatches()
    for name, img in items.items():
        ImageDraw.Draw(img).rectangle([0, 0, W - 1, H - 1], outline=EDGE)
        img.save(OUT / f"{name}.png", optimize=True)
    print(f"wrote {len(items)} legend swatches to {OUT}")
    if not LEGEND_MD.exists():
        LEGEND_MD.write_text(STARTER_LEGEND, encoding="utf-8")
        print(f"wrote starter {LEGEND_MD.name}")


if __name__ == "__main__":
    make()
