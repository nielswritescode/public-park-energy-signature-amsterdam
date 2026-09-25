"""Render the +-10 km Amsterdam map from the cached OSM features.

    python scripts/render.py                     # full 2.5 m/px map (8000 x 8000)
    python scripts/render.py --res 10 --grid 1   # quick draft (2000 x 2000)

The map is rendered as a grid of tiles (each with padding so lines and glows
continue across tile edges) and concatenated into one image.
"""
import argparse
import math
import os
import pickle
import time

import numpy as np
from shapely.geometry import Polygon
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import style as st
from common import CENTER_LAT, CENTER_LON, FEATURES, RADIUS_M, ROOT

Image.MAX_IMAGE_PIXELS = None
SS = 2  # supersampling factor for anti-aliasing
PAD = 96  # px of padding around each tile (covers the widest glow)
MIN_PARK_AREA_M2 = 200  # ignore slivers smaller than this (mapping artefacts)


# --- data prep -----------------------------------------------------------------

class PolySet:
    """Polygons exploded into (exterior, holes) rings with bounds for culling."""

    def __init__(self, recs):
        self.ext, self.holes, self.names, self.area = [], [], [], []
        for g, name in recs:
            for p in getattr(g, "geoms", [g]):
                if p.geom_type != "Polygon" or p.is_empty:
                    continue
                self.ext.append(np.asarray(p.exterior.coords))
                self.holes.append([np.asarray(r.coords) for r in p.interiors])
                self.names.append(name)
                self.area.append(p.area)
        self.bounds = np.array([[*e.min(0), *e.max(0)] for e in self.ext]).reshape(-1, 4)

    def within(self, win):
        xa, ya, xb, yb = win
        b = self.bounds
        return np.nonzero((b[:, 2] >= xa) & (b[:, 0] <= xb) & (b[:, 3] >= ya) & (b[:, 1] <= yb))[0]


class LineSet:
    def __init__(self, recs):
        self.recs = recs
        self.xy = [np.asarray(r["geom"].coords) for r in recs]
        self.bounds = np.array([[*c.min(0), *c.max(0)] for c in self.xy]).reshape(-1, 4)

    def within(self, win):
        xa, ya, xb, yb = win
        b = self.bounds
        return np.nonzero((b[:, 2] >= xa) & (b[:, 0] <= xb) & (b[:, 3] >= ya) & (b[:, 1] <= yb))[0]


def load_features(min_park_area):
    with open(FEATURES, "rb") as fh:
        d = pickle.load(fh)
    polys = {k: PolySet(v) for k, v in d["polys"].items()}
    lines = {k: LineSet(v) for k, v in d["lines"].items()}
    kept = [(g, n) for g, n in d["parks"] if g.area >= min_park_area]
    parks = PolySet(kept)
    print(f"public parks: {len(d['parks'])} in OSM, {len(kept)} drawn (>= {min_park_area:.0f} m2)")
    return polys, lines, parks, d["places"]


# --- drawing helpers -------------------------------------------------------------

class View:
    """Maps metres -> supersampled pixels for one padded tile."""

    def __init__(self, left, top, res, w, h):
        self.left, self.top, self.res, self.w, self.h = left, top, res, w, h  # w,h in final px

    @property
    def win(self):  # metres: xa, ya, xb, yb
        return (self.left, self.top - self.h * self.res, self.left + self.w * self.res, self.top)

    def px(self, xy):
        out = np.empty_like(xy, dtype=float)
        out[:, 0] = (xy[:, 0] - self.left) / self.res * SS
        out[:, 1] = (self.top - xy[:, 1]) / self.res * SS
        return out


def flat(a):
    return a.ravel().tolist()


def draw_line(d, pts, color, width):
    w = max(1, round(width))
    d.line(flat(pts), fill=color, width=w, joint="curve")
    if w >= 4:  # round caps
        r = w / 2 - 0.5
        for x, y in (pts[0], pts[-1]):
            d.ellipse([x - r, y - r, x + r, y + r], fill=color)


def fill_poly(img, d, ext, holes, color, outline=None):
    if len(ext) < 3:
        return
    if not holes:
        d.polygon(flat(ext), fill=color, outline=outline)
        return
    x0, y0 = np.floor(ext.min(0)).astype(int)
    x1, y1 = np.ceil(ext.max(0)).astype(int)
    x0, y0 = max(x0, 0), max(y0, 0)
    x1, y1 = min(x1, img.width), min(y1, img.height)
    if x1 <= x0 or y1 <= y0:
        return
    m = Image.new("L", (x1 - x0, y1 - y0), 0)
    md = ImageDraw.Draw(m)
    off = np.array([x0, y0])
    md.polygon(flat(ext - off), fill=255)
    for h in holes:
        if len(h) >= 3:
            md.polygon(flat(h - off), fill=0)
    img.paste(color, (x0, y0), m)


def mix(c1, c2, t):
    return tuple(round(a * (1 - t) + b * t) for a, b in zip(c1, c2))


# --- one tile --------------------------------------------------------------------

def render_tile(view, polys, lines, parks, res):
    k = st.REF_RES / res  # width scale so the map looks the same at any resolution
    W, H = view.w * SS, view.h * SS
    img = Image.new("RGB", (W, H), st.LAND)
    d = ImageDraw.Draw(img)
    win = view.win

    # 1. land-cover / land-use areas, bottom to top
    for kind, fill, outline in st.AREAS:
        ps = polys.get(kind)
        if ps is None:
            continue
        for i in ps.within(win):
            fill_poly(img, d, view.px(ps.ext[i]), [view.px(h) for h in ps.holes[i]], fill, outline)

    # 2. waterway lines (rivers/canals not mapped as areas, ditches, streams)
    for kind, wref in st.WATERWAY_W.items():
        ls = lines.get(kind)
        if ls is None:
            continue
        w = max(1.0, wref * k) * SS
        for i in ls.within(win):
            if not ls.recs[i]["tunnel"]:
                draw_line(d, view.px(ls.xy[i]), st.WATER, w)

    # 3. buildings
    ps = polys.get("building")
    if ps is not None:
        for i in ps.within(win):
            fill_poly(img, d, view.px(ps.ext[i]), [view.px(h) for h in ps.holes[i]],
                      st.BUILDING, st.BUILDING_EDGE)

    # 4. roads: tunnels, then ground level, then rail, then bridges
    roads = []
    for kind, (fill, casing, wf, wc, rank) in st.ROADS.items():
        ls = lines.get(kind)
        if ls is None:
            continue
        for i in ls.within(win):
            r = ls.recs[i]
            grp = 0 if (r["tunnel"] or r["layer"] < 0) else (2 if r["bridge"] or r["layer"] > 0 else 1)
            roads.append((grp, r["layer"], rank, i, ls, fill, casing, wf, wc))
    roads.sort(key=lambda t: (t[0], t[1], t[2]))

    def paint(group, casings):
        for grp, _, _, i, ls, fill, casing, wf, wc in roads:
            if grp != group:
                continue
            pts = view.px(ls.xy[i])
            if casings:
                if casing is None or group == 0:
                    continue
                c = mix(casing, (0, 0, 0), 0.35) if group == 2 else casing
                draw_line(d, pts, c, max(1.0, (wc + (0.8 if group == 2 else 0)) * k) * SS)
            else:
                col = mix(fill, st.LAND, 0.55) if group == 0 else fill
                draw_line(d, pts, col, max(1.0, wf * k) * SS)

    paint(0, False)
    paint(1, True)
    paint(1, False)
    for kind, col, wref in (("rw:tram", st.TRAM, 1.1), ("rw:rail", st.RAIL, 2.0)):
        ls = lines.get(kind)
        if ls is None:
            continue
        for i in ls.within(win):
            r = ls.recs[i]
            if r["tunnel"]:
                continue
            draw_line(d, view.px(ls.xy[i]), col, max(1.0, wref * k) * SS)
    paint(2, True)
    paint(2, False)

    # 5. neon outline mask for public parks
    mask = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(mask)
    hot = Image.new("L", (W, H), 0)
    hd = ImageDraw.Draw(hot)
    lw = max(1.0, st.NEON_LINE_W * k) * SS
    hw = max(1.0, st.NEON_HOT_W * k) * SS
    for i in parks.within(win):
        pts = view.px(parks.ext[i])
        pts = np.vstack([pts, pts[:1]])
        md.line(flat(pts), fill=255, width=round(lw), joint="curve")
        hd.line(flat(pts), fill=255, width=round(hw), joint="curve")

    out = img.resize((view.w, view.h), Image.LANCZOS)
    m = mask.resize((view.w, view.h), Image.LANCZOS)
    h = hot.resize((view.w, view.h), Image.LANCZOS)
    return neon(out, m, h, k)


def neon(base, mask, hot, k):
    """Composite the glowing outline over the base map."""
    if not mask.getbbox():
        return base
    arr = np.asarray(base, dtype=np.float32) / 255.0
    neon_c = np.array(st.NEON, dtype=np.float32) / 255.0
    hot_c = np.array(st.NEON_HOT, dtype=np.float32) / 255.0
    line_w = max(1.0, st.NEON_LINE_W * k)

    def over(a, colour, alpha):
        alpha = alpha[..., None]
        return a * (1 - alpha) + colour * alpha

    for sigma, target in st.NEON_HALOS:
        s = max(0.8, sigma * k)
        blurred = np.asarray(mask.filter(ImageFilter.GaussianBlur(s)), dtype=np.float32) / 255.0
        peak = line_w / (math.sqrt(2 * math.pi) * s)
        arr = over(arr, neon_c, np.clip(blurred / peak * target, 0, 0.92))
    arr = over(arr, neon_c, np.asarray(mask, dtype=np.float32) / 255.0)
    arr = over(arr, hot_c, np.asarray(hot, dtype=np.float32) / 255.0)
    return Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB")


# --- labels, scale bar, attribution ---------------------------------------------

def font(name, size):
    for path in (f"C:/Windows/Fonts/{name}", name):
        try:
            return ImageFont.truetype(path, max(8, round(size)))
        except OSError:
            continue
    return ImageFont.load_default(max(8, round(size)))


def add_labels(img, places, parks, res):
    k = st.REF_RES / res
    d = ImageDraw.Draw(img)
    half = RADIUS_M
    to_px = lambda x, y: ((x + half) / res, (half - y) / res)
    sizes = {"city": 76, "town": 54, "borough": 46, "suburb": 46, "village": 42, "hamlet": 34}
    prio = {"city": 0, "town": 1, "borough": 2, "suburb": 2, "village": 3, "hamlet": 4}
    taken = []

    def place(text, x, y, fnt, fill, stroke):
        l, t, r, b = d.textbbox((x, y), text, font=fnt, anchor="mm", stroke_width=stroke)
        box = (l - 8, t - 8, r + 8, b + 8)
        if r < 0 or b < 0 or l > img.width or t > img.height:
            return
        if any(not (box[2] < o[0] or box[0] > o[2] or box[3] < o[1] or box[1] > o[3]) for o in taken):
            return
        taken.append(box)
        d.text((x, y), text, font=fnt, fill=fill, anchor="mm", stroke_width=stroke, stroke_fill=st.HALO)

    for p in sorted(places, key=lambda p: prio[p["place"]]):
        x, y = to_px(p["x"], p["y"])
        if 0 <= x < img.width and 0 <= y < img.height:
            place(p["name"], x, y, font("segoeui.ttf", sizes[p["place"]] * k), st.LABEL, max(2, round(5 * k)))

    # names of the larger public parks, in italic green
    pf = font("segoeuii.ttf", 34 * k)
    order = sorted((i for i in range(len(parks.ext)) if parks.names[i] and parks.area[i] >= 120_000),
                   key=lambda i: -parks.area[i])
    for i in order:
        pt = Polygon(parks.ext[i]).representative_point()
        x, y = to_px(pt.x, pt.y)
        if 0 <= x < img.width and 0 <= y < img.height:
            place(parks.names[i], x, y, pf, st.PARK_LABEL, max(2, round(5 * k)))


def add_furniture(img, res):
    k = st.REF_RES / res
    d = ImageDraw.Draw(img)
    m = round(40 * k)
    # scale bar: 2 km
    bar = 2000 / res
    x0, y1 = m, img.height - m
    d.rectangle([x0 - m / 2, y1 - 60 * k, x0 + bar + m / 2, y1 + m / 3], fill=(255, 255, 255))
    d.line([x0, y1 - 18 * k, x0, y1, x0 + bar, y1, x0 + bar, y1 - 18 * k], fill=(40, 40, 40), width=max(2, round(5 * k)))
    d.text((x0 + bar / 2, y1 - 34 * k), "2 km", font=font("segoeui.ttf", 34 * k), fill=(40, 40, 40), anchor="mm")
    # attribution (required by the ODbL)
    text = "\u00a9 OpenStreetMap contributors"
    f = font("segoeui.ttf", 34 * k)
    l, t, r, b = d.textbbox((0, 0), text, font=f)
    x1, y2 = img.width - m / 2, img.height - m / 2
    d.rectangle([x1 - (r - l) - m, y2 - (b - t) - m * 0.8, x1, y2], fill=(255, 255, 255))
    d.text((x1 - m / 2, y2 - m * 0.4), text, font=f, fill=(40, 40, 40), anchor="rd")


# --- main ------------------------------------------------------------------------

def save(img, path):
    """JPEG (q90, no chroma subsampling) keeps the 8000 px map ~26 MB instead of ~73 MB as PNG."""
    if path.lower().endswith((".jpg", ".jpeg")):
        img.save(path, quality=90, subsampling=0, optimize=True)
    else:
        img.save(path, optimize=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", type=float, default=2.5, help="metres per pixel")
    ap.add_argument("--grid", type=int, default=4, help="tiles per side")
    ap.add_argument("--out", default=str(ROOT / "assets" / "amsterdam-map.jpg"))
    ap.add_argument("--preview", type=int, default=2000, help="README preview width in px (0 = skip)")
    ap.add_argument("--min-park-area", type=float, default=MIN_PARK_AREA_M2)
    ap.add_argument("--crop", help="cx,cy,half in metres from the centre: render just that window (for tuning)")
    a = ap.parse_args()

    t0 = time.time()
    polys, lines, parks, places = load_features(a.min_park_area)
    print(f"features loaded in {time.time() - t0:.0f}s")

    if a.crop:
        cx, cy, half = (float(v) for v in a.crop.split(","))
        n = round(2 * half / a.res)
        view = View(left=cx - half - PAD * a.res, top=cy + half + PAD * a.res, res=a.res, w=n + 2 * PAD, h=n + 2 * PAD)
        tile = render_tile(view, polys, lines, parks, a.res).crop((PAD, PAD, PAD + n, PAD + n))
        tile.save(a.out)
        print(f"saved crop {a.out} ({n} x {n} px, {time.time() - t0:.0f}s)")
        return

    size = round(2 * RADIUS_M / a.res)
    step = math.ceil(size / a.grid)
    print(f"map {size} x {size} px at {a.res} m/px, {a.grid} x {a.grid} tiles of ~{step} px")
    full = Image.new("RGB", (size, size), st.LAND)

    for gy in range(a.grid):
        for gx in range(a.grid):
            i0, j0 = gx * step, gy * step
            w, h = min(step, size - i0), min(step, size - j0)
            view = View(left=-RADIUS_M + (i0 - PAD) * a.res, top=RADIUS_M - (j0 - PAD) * a.res,
                        res=a.res, w=w + 2 * PAD, h=h + 2 * PAD)
            t = time.time()
            tile = render_tile(view, polys, lines, parks, a.res)
            full.paste(tile.crop((PAD, PAD, PAD + w, PAD + h)), (i0, j0))
            print(f"  tile {gy * a.grid + gx + 1}/{a.grid ** 2} in {time.time() - t:.0f}s")

    add_labels(full, places, parks, a.res)
    add_furniture(full, a.res)

    out = a.out
    save(full, out)
    print(f"saved {out} ({os.path.getsize(out) / 1e6:.1f} MB)")
    if a.preview:
        root, ext = os.path.splitext(out)
        pout = f"{root}-preview{ext}"
        save(full.resize((a.preview, a.preview), Image.LANCZOS), pout)
        print(f"saved {pout} ({os.path.getsize(pout) / 1e6:.1f} MB)")
    import legend_assets
    legend_assets.make()
    print(f"total {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
