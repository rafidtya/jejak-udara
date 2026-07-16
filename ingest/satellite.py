"""Satellite ingestion via Google Earth Engine (Phase 1B).

Auth: service account (GEE_SERVICE_ACCOUNT + GEE_SERVICE_ACCOUNT_KEY in .env).
Honesty rule (agents.md §4): column densities / AOD are NOT ground truth;
cloud gaps stay NULL with qa='cloud'. Derived PM2.5 requires a calibration run
recorded in validation_runs (kind='aod_calibration').

Products (plan.md P1B):
  s5p_no2     COPERNICUS/S5P/OFFL/L3_NO2       tropospheric_NO2_column_number_density
  s5p_so2     COPERNICUS/S5P/OFFL/L3_SO2       SO2_column_number_density
  s5p_co      COPERNICUS/S5P/OFFL/L3_CO        CO_column_number_density
  s5p_aer_ai  COPERNICUS/S5P/OFFL/L3_AER_AI    absorbing_aerosol_index
  maiac_aod   MODIS/061/MCD19A2_GRANULES       Optical_Depth_055
"""
from __future__ import annotations

import os

from .common import heartbeat

# Jakarta bbox (lon/lat): west, south, east, north
JAKARTA_BBOX = (106.3, -6.6, 107.2, -5.9)
GRID_CELL_DEG = 0.02  # ~2.2 km cells for the demo store

PRODUCTS = {
    "s5p_no2": ("COPERNICUS/S5P/OFFL/L3_NO2", "tropospheric_NO2_column_number_density"),
    "s5p_so2": ("COPERNICUS/S5P/OFFL/L3_SO2", "SO2_column_number_density"),
    "s5p_co": ("COPERNICUS/S5P/OFFL/L3_CO", "CO_column_number_density"),
    "s5p_aer_ai": ("COPERNICUS/S5P/OFFL/L3_AER_AI", "absorbing_aerosol_index"),
    "maiac_aod": ("MODIS/061/MCD19A2_GRANULES", "Optical_Depth_055"),
}


def _init_gee():
    """Lazy import + auth — earthengine-api is an optional dependency ([satellite])."""
    import ee  # noqa: PLC0415

    sa = os.environ.get("GEE_SERVICE_ACCOUNT")
    key_path = os.environ.get("GEE_SERVICE_ACCOUNT_KEY")
    if not sa or not key_path:
        raise RuntimeError("GEE credentials missing in .env (P0.3b)")
    creds = ee.ServiceAccountCredentials(sa, key_path)
    ee.Initialize(creds)
    return ee


def daily_composite(product: str, date_iso: str) -> None:
    """Pull one product's daily mean composite over the Jakarta bbox into satellite_grids.

    TODO(P1B.1/P1B.2): implement grid sampling via ee.Image.sampleRectangle /
    reduceRegions over a GRID_CELL_DEG fishnet, then bulk-insert with qa flags.
    Skeleton kept minimal until GEE credentials exist (P0.3b).
    """
    ee = _init_gee()
    collection_id, band = PRODUCTS[product]
    img = (
        ee.ImageCollection(collection_id)
        .filterDate(date_iso, date_iso + "T23:59:59")
        .filterBounds(ee.Geometry.Rectangle(list(JAKARTA_BBOX)))
        .select(band)
        .mean()
    )
    _ = img  # placeholder until sampling implemented
    raise NotImplementedError("P1B: implement fishnet sampling + insert (see docstring)")


def poll_all(date_iso: str | None = None) -> None:
    from datetime import date

    d = date_iso or date.today().isoformat()
    try:
        for product in PRODUCTS:
            daily_composite(product, d)
        heartbeat("satellite", ok=True)
    except Exception as exc:
        heartbeat("satellite", ok=False, error=repr(exc))


if __name__ == "__main__":
    poll_all()
