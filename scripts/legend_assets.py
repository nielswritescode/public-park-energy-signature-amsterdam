"""Legend swatches for the parks listed in the legend -> assets/legend/parks/*.png

Also writes a starter legend.md (outline colour + park name). It never overwrites
an existing legend.md unless asked to, because legend.md is yours to edit.
"""
import re
import unicodedata

import numpy as np
from PIL import Image, ImageDraw

import style as st
from common import ROOT
from render import NeonLayer

OUT = ROOT / "assets" / "legend" / "parks"
LEGEND_MD = ROOT / "legend.md"
W, H = 48, 30
EDGE = (190, 190, 190)
PARK_FILL = dict(st.AREAS_BY_KIND)["park"]


def slug(name):
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-") or "park"


def swatch(colour_index):
    """A small park with the same glowing outline it has on the map."""
    layer = NeonLayer(W, H)
    ring = np.array([[10, 8], [W - 11, 8], [W - 11, H - 9], [10, H - 9]], dtype=float)
    layer.outline(ring, st.NEON_PALETTE[colour_index], 2, 1)
    img = layer.composite(Image.new("RGB", (W, H), PARK_FILL), 0.4, 1)
    ImageDraw.Draw(img).rectangle([0, 0, W - 1, H - 1], outline=EDGE)
    return img


def starter_legend(rows):
    lines = [
        "<!-- Edit this file freely: it is the legend shown next to the map on the main page.",
        "     After editing, run  python scripts/build_readme.py  to refresh README.md.",
        "     Each row is a swatch image plus the park it stands for. Add, remove or rename rows;",
        "     swatches live in assets/legend/parks/. -->",
        "",
        "### Legend",
        "",
        "| Outline | Park |",
        "|:-:|:--|",
    ]
    lines += [f"| ![{name}]({path}) | {name} |" for name, path in rows]
    lines += ["", "*Smaller parks reuse these colours.*", ""]
    return "\n".join(lines)


def make(legend, reset=False):
    """legend: [(park name, palette index, area in ha)], largest first."""
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()
    rows, seen = [], set()
    for name, colour, _ in legend:
        base = slug(name)
        file, n = base, 2
        while file in seen:
            file, n = f"{base}-{n}", n + 1
        seen.add(file)
        swatch(colour).save(OUT / f"{file}.png", optimize=True)
        rows.append((name, f"assets/legend/parks/{file}.png"))
    print(f"wrote {len(rows)} legend swatches to {OUT}")
    if reset or not LEGEND_MD.exists():
        LEGEND_MD.write_text(starter_legend(rows), encoding="utf-8")
        print(f"wrote {LEGEND_MD.name} ({len(rows)} parks)")
    else:
        print(f"kept your existing {LEGEND_MD.name} (use --reset-legend to regenerate it)")
