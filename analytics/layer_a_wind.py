"""Layer A — wind-based source direction (polar binning + CPF).

Pure functions over dataframes (agents.md §6): no DB, no network.
Method: bivariate polar aggregation — bin (wind_direction, wind_speed),
aggregate concentration per bin. CPF = P(conc > threshold | bin).
A hot bin at low ws => local source; hot at high ws from one direction
=> transported source in that direction. wd_deg = direction wind comes FROM.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

WD_BIN_DEG = 10
WS_BIN_MS = 1


def polar_aggregate(df: pd.DataFrame, *, conc_col: str = "value",
                    wd_col: str = "wd_deg", ws_col: str = "ws",
                    cpf_quantile: float = 0.90) -> pd.DataFrame:
    """Aggregate concentration by (wind-direction bin, wind-speed bin).

    Input: one station's timestamp-aligned frame with concentration + wind.
    Output columns: wd_bin, ws_bin, mean_conc, n, cpf.
    """
    d = df[[conc_col, wd_col, ws_col]].dropna().copy()
    if d.empty:
        return pd.DataFrame(columns=["wd_bin", "ws_bin", "mean_conc", "n", "cpf"])
    threshold = d[conc_col].quantile(cpf_quantile)
    d["wd_bin"] = ((d[wd_col] % 360) // WD_BIN_DEG).astype(int) * WD_BIN_DEG
    d["ws_bin"] = (d[ws_col] // WS_BIN_MS).astype(int) * WS_BIN_MS
    grouped = d.groupby(["wd_bin", "ws_bin"])
    out = grouped[conc_col].agg(mean_conc="mean", n="count").reset_index()
    exceed = grouped[conc_col].apply(lambda s: float((s > threshold).mean())).rename("cpf")
    return out.merge(exceed.reset_index(), on=["wd_bin", "ws_bin"])


def dominant_direction(polar: pd.DataFrame, *, min_n: int = 5) -> dict | None:
    """The single most-implicated upwind direction (for triangulation rays).

    Returns {"wd_deg": bin_center, "cpf": value, "local": bool} or None.
    `local=True` when the hottest bin sits at low wind speed (<2 m/s):
    pollution accumulates in calm — source is near the station itself.
    """
    p = polar[polar["n"] >= min_n]
    if p.empty:
        return None
    top = p.loc[p["cpf"].idxmax()]
    return {
        "wd_deg": float(top["wd_bin"] + WD_BIN_DEG / 2),
        "cpf": float(top["cpf"]),
        "local": bool(top["ws_bin"] < 2),
    }


def upwind_ray(station_lonlat: tuple[float, float], wd_deg: float,
               length_km: float = 15.0, n_points: int = 30) -> np.ndarray:
    """Points along the upwind ray from a station (source lies where wind comes FROM).

    Flat-earth approximation adequate at city scale. Returns (n,2) lon/lat array.
    """
    lon0, lat0 = station_lonlat
    theta = np.deg2rad(wd_deg)  # FROM-direction: walk toward it to face the source
    km_per_deg_lat = 110.574
    km_per_deg_lon = 111.320 * np.cos(np.deg2rad(lat0))
    dists = np.linspace(0, length_km, n_points)
    lats = lat0 + (dists * np.cos(theta)) / km_per_deg_lat
    lons = lon0 + (dists * np.sin(theta)) / km_per_deg_lon
    return np.column_stack([lons, lats])
