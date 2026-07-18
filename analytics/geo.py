"""Local metric projection for analytics (equirectangular, origin at Jakarta
bbox SW corner). Adequate at city scale; Track-B may swap to pyproj EPSG:32748
behind this same interface.
"""
from __future__ import annotations

import math

import numpy as np

BBOX = (106.65, -6.40, 107.00, -6.05)  # lon_min, lat_min, lon_max, lat_max (mainland)
LAT0 = (BBOX[1] + BBOX[3]) / 2.0
KM_PER_DEG_LAT = 110.574
KM_PER_DEG_LON = 111.320 * math.cos(math.radians(LAT0))


def project(lon: float, lat: float) -> tuple[float, float]:
    return ((lon - BBOX[0]) * KM_PER_DEG_LON * 1000.0,
            (lat - BBOX[1]) * KM_PER_DEG_LAT * 1000.0)


def project_arr(lonlat: np.ndarray) -> np.ndarray:
    out = np.empty_like(lonlat, dtype=float)
    out[:, 0] = (lonlat[:, 0] - BBOX[0]) * KM_PER_DEG_LON * 1000.0
    out[:, 1] = (lonlat[:, 1] - BBOX[1]) * KM_PER_DEG_LAT * 1000.0
    return out


def unproject(x: float, y: float) -> tuple[float, float]:
    return (BBOX[0] + x / 1000.0 / KM_PER_DEG_LON,
            BBOX[1] + y / 1000.0 / KM_PER_DEG_LAT)


def bbox_metric() -> tuple[float, float, float, float]:
    x1, y1 = project(BBOX[0], BBOX[1])
    x2, y2 = project(BBOX[2], BBOX[3])
    return (x1, y1, x2, y2)
