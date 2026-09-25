"""Shared constants and the local map projection (no pyproj needed)."""
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
PBF = ROOT / "data" / "raw" / "Amsterdam.osm.pbf"
FEATURES = ROOT / "data" / "processed" / "features.pkl"

# Dam Square, Amsterdam: the centre of the +-10 km map.
CENTER_LAT, CENTER_LON = 52.3731, 4.8926
RADIUS_M = 10_000
READ_MARGIN_M = 1_500  # read a little beyond the map so edge features are complete


def _gauss_radius(lat_deg):
    """sqrt(M*N) on WGS84: the sphere radius that gives true metres locally."""
    a, e2 = 6378137.0, 0.00669437999014
    s = np.sin(np.radians(lat_deg))
    m = a * (1 - e2) / (1 - e2 * s * s) ** 1.5
    n = a / np.sqrt(1 - e2 * s * s)
    return float(np.sqrt(m * n))


_R = _gauss_radius(CENTER_LAT)
_PHI0 = np.radians(CENTER_LAT)


def project(lon, lat):
    """lon/lat (deg) -> metres east/north of the centre (stereographic).

    Conformal, and the scale error is ~6e-7 at 10 km, so distances are true.
    """
    lam = np.radians(np.asarray(lon, dtype=float) - CENTER_LON)
    phi = np.radians(np.asarray(lat, dtype=float))
    k = 2 * _R / (1 + np.sin(_PHI0) * np.sin(phi) + np.cos(_PHI0) * np.cos(phi) * np.cos(lam))
    x = k * np.cos(phi) * np.sin(lam)
    y = k * (np.cos(_PHI0) * np.sin(phi) - np.sin(_PHI0) * np.cos(phi) * np.cos(lam))
    return x, y


def read_bbox_lonlat():
    """Generous lon/lat bbox (min_lon, min_lat, max_lon, max_lat) for the read."""
    r = (RADIUS_M + READ_MARGIN_M) * 1.04
    dlat = np.degrees(r / _R)
    dlon = np.degrees(r / (_R * np.cos(_PHI0)))
    return (CENTER_LON - dlon, CENTER_LAT - dlat, CENTER_LON + dlon, CENTER_LAT + dlat)
