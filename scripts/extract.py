"""Read the OSM extract, classify features, project to metres, cache to disk.

    python scripts/extract.py
"""
import pickle
import re
import time
import warnings

import numpy as np
import pyogrio
import shapely

from common import FEATURES, PBF, project, read_bbox_lonlat

warnings.filterwarnings("ignore", message="Non closed ring")

TAG_RE = re.compile(r'"((?:[^"\\]|\\.)*)"=>"((?:[^"\\]|\\.)*)"')
RESTRICTED_ACCESS = {"private", "no", "customers", "permit", "members"}


def parse_tags(s):
    return dict(TAG_RE.findall(s)) if s else {}


def read_layer(layer, bbox):
    t0 = time.time()
    meta, _, geom, fields = pyogrio.raw.read(PBF, layer=layer, bbox=bbox, encoding="utf-8")
    cols = [str(c) for c in meta["fields"]]
    print(f"  read {layer}: {len(geom):,} features in {time.time() - t0:.0f}s")
    return shapely.from_wkb(geom), dict(zip(cols, fields))


def to_metres(geoms):
    def fn(coords):
        x, y = project(coords[:, 0], coords[:, 1])
        return np.column_stack([x, y])

    return shapely.transform(geoms, fn)


def val(col, i):
    v = col[i]
    return None if v is None or (isinstance(v, float) and np.isnan(v)) or v == "" else v


# --- polygons -----------------------------------------------------------------

def area_kind(f, t):
    """Map an area's tags to a drawing class (None = not drawn)."""
    lei, lu, nat, am = f["leisure"], f["landuse"], f["natural"], f["amenity"]
    if f["building"] and f["building"] != "no":
        return "building"
    if nat == "water" or lu in ("reservoir", "basin") or t.get("waterway") in ("riverbank", "dock"):
        return "water"
    if lei in ("park", "common") or lu == "village_green":
        return "park"
    if lei == "garden":
        return "garden"
    if lei == "pitch":
        return "pitch"
    if lei in ("sports_centre", "stadium", "track", "swimming_pool"):
        return "sports"
    if lei == "playground":
        return "playground"
    if lei == "golf_course":
        return "golf"
    if lei in ("recreation_ground", "nature_reserve") or lu == "recreation_ground":
        return "recreation"
    if nat == "wood" or lu == "forest":
        return "wood"
    if nat in ("scrub", "heath", "grassland"):
        return "scrub"
    if nat == "wetland":
        return "wetland"
    if nat in ("beach", "sand"):
        return "sand"
    if lu in ("grass", "meadow", "greenfield", "flowerbed"):
        return "grass"
    if lu in ("farmland", "farmyard", "orchard", "vineyard", "plant_nursery"):
        return "farmland"
    if lu == "allotments":
        return "allotments"
    if lu == "cemetery" or am == "grave_yard":
        return "cemetery"
    if lu == "residential":
        return "residential"
    if lu in ("commercial", "retail"):
        return "commercial"
    if lu in ("industrial", "railway"):
        return "industrial"
    if lu in ("construction", "brownfield", "landfill", "quarry"):
        return "construction"
    if am in ("parking", "bicycle_parking"):
        return "parking"
    if am in ("school", "university", "college", "kindergarten"):
        return "school"
    if am in ("hospital", "clinic"):
        return "hospital"
    if f["aeroway"] in ("aerodrome", "apron", "runway", "taxiway", "helipad"):
        return "airport"
    return None


def extract_polygons(bbox):
    geoms, cols = read_layer("multipolygons", bbox)
    geoms = to_metres(geoms)
    prim = ("building", "landuse", "leisure", "natural", "amenity", "aeroway", "name", "other_tags")
    out = {}
    parks = []
    for i in range(len(geoms)):
        g = geoms[i]
        if g is None or g.is_empty:
            continue
        f = {k: val(cols[k], i) for k in prim}
        t = parse_tags(f["other_tags"]) if f["other_tags"] else {}
        kind = area_kind(f, t)
        if kind is None:
            continue
        rec = (g, f["name"])
        out.setdefault(kind, []).append(rec)
        if kind == "park" and t.get("access") not in RESTRICTED_ACCESS:
            parks.append(rec)
    return out, parks


# --- lines --------------------------------------------------------------------

HIGHWAYS = {
    "motorway": "motorway", "motorway_link": "motorway_link",
    "trunk": "trunk", "trunk_link": "trunk_link",
    "primary": "primary", "primary_link": "primary_link",
    "secondary": "secondary", "secondary_link": "secondary_link",
    "tertiary": "tertiary", "tertiary_link": "tertiary_link",
    "unclassified": "residential", "residential": "residential",
    "living_street": "residential", "road": "residential",
    "service": "service", "pedestrian": "pedestrian",
    "footway": "footway", "path": "footway", "steps": "footway",
    "cycleway": "cycleway", "bridleway": "footway", "track": "track",
}
RAILWAYS = {"rail": "rail", "tram": "tram", "light_rail": "tram", "subway": "subway",
            "narrow_gauge": "tram"}
WATERWAYS = {"river": "river", "canal": "canal", "stream": "stream", "ditch": "ditch",
             "drain": "ditch"}


def extract_lines(bbox):
    geoms, cols = read_layer("lines", bbox)
    geoms = to_metres(geoms)
    out = {}
    for i in range(len(geoms)):
        g = geoms[i]
        if g is None or g.is_empty:
            continue
        hw, rw, ww = val(cols["highway"], i), val(cols["railway"], i), val(cols["waterway"], i)
        if hw in HIGHWAYS:
            kind = "hw:" + HIGHWAYS[hw]
        elif rw in RAILWAYS:
            kind = "rw:" + RAILWAYS[rw]
        elif ww in WATERWAYS:
            kind = "ww:" + WATERWAYS[ww]
        else:
            continue
        t = parse_tags(val(cols["other_tags"], i) or "")
        if t.get("area") == "yes":
            continue
        try:
            layer = int(t.get("layer", 0))
        except ValueError:
            layer = 0
        z = val(cols["z_order"], i)
        rec = dict(
            geom=g,
            name=val(cols["name"], i),
            bridge=t.get("bridge") not in (None, "no"),
            tunnel=t.get("tunnel") not in (None, "no") or t.get("covered") == "yes",
            layer=layer,
            z=int(z) if z is not None else 0,
            service=t.get("service"),
        )
        out.setdefault(kind, []).append(rec)
    return out


# --- places -------------------------------------------------------------------

def extract_places(bbox):
    geoms, cols = read_layer("points", bbox)
    out = []
    for i in range(len(geoms)):
        place, name = val(cols["place"], i), val(cols["name"], i)
        if place in ("city", "town", "village", "suburb", "hamlet", "borough") and name:
            x, y = project(geoms[i].x, geoms[i].y)
            out.append(dict(name=name, place=place, x=float(x), y=float(y)))
    return out


def main():
    bbox = read_bbox_lonlat()
    print(f"reading {PBF.name}, bbox lon/lat = {tuple(round(b, 4) for b in bbox)}")
    polys, parks = extract_polygons(bbox)
    lines = extract_lines(bbox)
    places = extract_places(bbox)

    print("\npolygons by class:")
    for k, v in sorted(polys.items(), key=lambda kv: -len(kv[1])):
        print(f"  {k:12s} {len(v):>8,}")
    print("lines by class:")
    for k, v in sorted(lines.items(), key=lambda kv: -len(kv[1])):
        print(f"  {k:18s} {len(v):>8,}")
    print(f"places: {len(places)}  |  public parks: {len(parks)}")

    FEATURES.parent.mkdir(parents=True, exist_ok=True)
    with open(FEATURES, "wb") as fh:
        pickle.dump(dict(polys=polys, parks=parks, lines=lines, places=places), fh, protocol=5)
    print(f"\nwrote {FEATURES} ({FEATURES.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
