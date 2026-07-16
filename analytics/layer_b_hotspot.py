"""Layer B — spatial interpolation + LOOCV validation.

IDW implemented in numpy (zero extra deps); kriging upgrade via pykrige is a
drop-in behind the same interface (plan.md P2.2). Honesty rules: resolution
claims stay district-level; LOOCV metrics are user-facing (validation view).
"""
from __future__ import annotations

import numpy as np


def idw(known_xy: np.ndarray, known_v: np.ndarray, query_xy: np.ndarray,
        *, power: float = 2.0, eps: float = 1e-10) -> np.ndarray:
    """Inverse-distance-weighted interpolation. xy in a METRIC crs (EPSG:32748)."""
    d = np.linalg.norm(query_xy[:, None, :] - known_xy[None, :, :], axis=2)
    w = 1.0 / np.maximum(d, eps) ** power
    exact = d < eps  # query point coincides with a station
    out = (w * known_v[None, :]).sum(axis=1) / w.sum(axis=1)
    if exact.any():
        idx_q, idx_k = np.where(exact)
        out[idx_q] = known_v[idx_k]
    return out


def loocv(known_xy: np.ndarray, known_v: np.ndarray, *, power: float = 2.0) -> dict:
    """Leave-one-out cross-validation of the interpolator.

    THE validity answer for the heatmap: predict each station from all others,
    compare to what it measured. Returns rmse/mae/r2/bias.
    """
    n = len(known_v)
    preds = np.empty(n)
    for i in range(n):
        mask = np.arange(n) != i
        preds[i] = idw(known_xy[mask], known_v[mask], known_xy[i:i + 1], power=power)[0]
    resid = preds - known_v
    ss_res = float((resid ** 2).sum())
    ss_tot = float(((known_v - known_v.mean()) ** 2).sum())
    return {
        "rmse": float(np.sqrt((resid ** 2).mean())),
        "mae": float(np.abs(resid).mean()),
        "bias": float(resid.mean()),
        "r2": 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan"),
        "n": n,
    }


def grid_over_bbox(bbox_xy: tuple[float, float, float, float], cell_m: float = 500.0
                   ) -> tuple[np.ndarray, tuple[int, int]]:
    """Fishnet of cell centers over (xmin, ymin, xmax, ymax) metric bbox.

    Returns (points (n,2), (nrows, ncols)) for reshaping results into a raster.
    """
    xmin, ymin, xmax, ymax = bbox_xy
    xs = np.arange(xmin + cell_m / 2, xmax, cell_m)
    ys = np.arange(ymin + cell_m / 2, ymax, cell_m)
    gx, gy = np.meshgrid(xs, ys)
    return np.column_stack([gx.ravel(), gy.ravel()]), (len(ys), len(xs))
