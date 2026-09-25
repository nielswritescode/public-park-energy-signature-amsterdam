"""Map style: an OpenStreetMap-Carto-like palette plus the neon park outline.

Line widths are in pixels at the reference resolution (REF_RES metres/pixel) and
are rescaled when rendering at another resolution, so the map looks the same at
any size.
"""

REF_RES = 2.5

LAND = (242, 239, 233)
WATER = (170, 211, 223)

# Public parks get a neon outline + glow, each park in its own colour. Nothing else on
# the map is this saturated. Colours are generated in OKLCH (constant lightness, so none
# looks weaker than another on the pale map) and spaced by the golden angle so that
# consecutive colours are far apart in hue.
PALETTE_SIZE = 30


def _oklch_to_srgb(L, C, h_deg):
    """OKLCH -> 8-bit sRGB, reducing chroma until the colour fits the sRGB gamut."""
    import math

    def convert(c):
        a, b = c * math.cos(math.radians(h_deg)), c * math.sin(math.radians(h_deg))
        l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
        m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
        s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
        return (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
                -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
                -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)

    lo, hi = 0.0, C
    for _ in range(24):
        mid = (lo + hi) / 2
        if all(-1e-6 <= v <= 1 + 1e-6 for v in convert(mid)):
            lo = mid
        else:
            hi = mid
    gamma = lambda v: 12.92 * v if v <= 0.0031308 else 1.055 * max(v, 0) ** (1 / 2.4) - 0.055
    return tuple(round(min(1, max(0, gamma(v))) * 255) for v in convert(lo))


def neon_palette(n, lightness=(0.66, 0.75)):
    """Hues skip 80-130 degrees: yellow-greens only look olive at this lightness, not neon."""
    def hue(k):
        return 130.0 + ((k * 137.508 + 200.0) % 360.0) * (310.0 / 360.0)

    return [_oklch_to_srgb(lightness[k % 2], 0.33, hue(k) % 360) for k in range(n)]


def neon_hot(rgb):
    """The bright 'tube' core of an outline: the colour pushed towards white."""
    return tuple(round(c + (255 - c) * 0.8) for c in rgb)


NEON_PALETTE = neon_palette(PALETTE_SIZE)

# Filled areas, in draw order (bottom to top). (fill, outline or None)
AREAS = [
    ("residential", (224, 223, 223), None),
    ("commercial", (242, 218, 217), None),
    ("industrial", (235, 219, 232), None),
    ("construction", (199, 199, 180), None),
    ("farmland", (238, 240, 213), None),
    ("allotments", (201, 225, 191), None),
    ("cemetery", (170, 203, 175), None),
    ("school", (240, 240, 216), None),
    ("hospital", (240, 240, 216), None),
    ("airport", (218, 218, 224), None),
    ("sand", (245, 233, 198), None),
    ("recreation", (223, 252, 226), None),
    ("sports", (223, 252, 226), (181, 226, 198)),
    ("golf", (222, 246, 192), None),
    ("grass", (205, 235, 176), None),
    ("garden", (205, 235, 176), None),
    ("scrub", (200, 215, 171), None),
    ("wetland", (197, 223, 208), None),
    ("wood", (173, 209, 158), None),
    ("park", (200, 250, 204), None),
    ("pitch", (170, 224, 203), (138, 204, 175)),
    ("playground", (223, 252, 226), (200, 220, 203)),
    ("parking", (238, 238, 238), (221, 221, 221)),
    ("water", WATER, None),
]
AREAS_BY_KIND = [(k, fill) for k, fill, _ in AREAS]
BUILDING = (217, 208, 201)
BUILDING_EDGE = (190, 176, 165)

# highway class -> (fill, casing or None, fill width, casing width, rank)
ROADS = {
    "hw:motorway": ((232, 146, 162), (220, 42, 103), 5.4, 7.4, 9),
    "hw:motorway_link": ((232, 146, 162), (220, 42, 103), 3.4, 5.0, 8),
    "hw:trunk": ((249, 178, 156), (200, 78, 47), 5.0, 6.8, 8),
    "hw:trunk_link": ((249, 178, 156), (200, 78, 47), 3.2, 4.6, 7),
    "hw:primary": ((252, 214, 164), (160, 107, 0), 4.6, 6.2, 7),
    "hw:primary_link": ((252, 214, 164), (160, 107, 0), 3.0, 4.4, 6),
    "hw:secondary": ((247, 250, 191), (112, 125, 5), 4.2, 5.6, 6),
    "hw:secondary_link": ((247, 250, 191), (112, 125, 5), 2.8, 4.2, 5),
    "hw:tertiary": ((255, 255, 255), (143, 143, 143), 3.8, 5.0, 5),
    "hw:tertiary_link": ((255, 255, 255), (143, 143, 143), 2.6, 3.8, 4),
    "hw:residential": ((255, 255, 255), (187, 187, 187), 3.0, 4.2, 4),
    "hw:service": ((255, 255, 255), (187, 187, 187), 1.7, 2.7, 3),
    "hw:pedestrian": ((237, 237, 237), (153, 153, 153), 2.4, 3.4, 3),
    "hw:track": ((172, 131, 57), None, 0.9, 0, 2),
    "hw:footway": ((248, 150, 140), None, 0.8, 0, 1),
    "hw:cycleway": ((140, 150, 240), None, 0.9, 0, 1),
}
RAIL = (153, 153, 153)
TRAM = (176, 176, 176)
WATERWAY_W = {"ww:river": 5.0, "ww:canal": 3.6, "ww:stream": 1.1, "ww:ditch": 0.9}

# Text
LABEL = (74, 74, 74)
PARK_LABEL = (32, 105, 52)
HALO = (255, 255, 255)

# Neon outline geometry (pixels at REF_RES)
NEON_LINE_W = 2.6
NEON_HOT_W = 1.0
# (blur sigma in px, alpha at the line centre)
NEON_HALOS = ((16, 0.17), (6.5, 0.32), (2.6, 0.66))
