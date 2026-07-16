"""Shared helpers for Track-A demo fixture scripts.

Local equirectangular projection (adequate at city scale, consistent across
heatmap + scenarios; the real engine will use EPSG:32748 via pyproj later).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# mainland Jakarta bbox (lon_min, lat_min, lon_max, lat_max) -- matches ingest/spku.py
BBOX = (106.65, -6.40, 107.00, -6.05)
LAT0 = (BBOX[1] + BBOX[3]) / 2.0
KM_PER_DEG_LAT = 110.574
KM_PER_DEG_LON = 111.320 * math.cos(math.radians(LAT0))

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "web" / "public" / "fixtures"


def project(lon: float, lat: float) -> tuple[float, float]:
    """lon/lat -> local metric (meters), origin at bbox SW corner."""
    x = (lon - BBOX[0]) * KM_PER_DEG_LON * 1000.0
    y = (lat - BBOX[1]) * KM_PER_DEG_LAT * 1000.0
    return x, y


def unproject(x: float, y: float) -> tuple[float, float]:
    """local metric (meters) -> lon/lat. Exact inverse of project()."""
    lon = BBOX[0] + x / 1000.0 / KM_PER_DEG_LON
    lat = BBOX[1] + y / 1000.0 / KM_PER_DEG_LAT
    return lon, lat


def bbox_metric() -> tuple[float, float, float, float]:
    x1, y1 = project(BBOX[0], BBOX[1])
    x2, y2 = project(BBOX[2], BBOX[3])
    return (x1, y1, x2, y2)


def load_stations() -> list[dict]:
    p = FIXTURES_DIR / "stations.json"
    if not p.exists():
        raise SystemExit("stations.json missing -- run scripts.build_fixtures first")
    return json.loads(p.read_text(encoding="utf-8"))
