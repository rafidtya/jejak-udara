"""Track A: precompute the IDW concentration surface + REAL LOOCV metrics
from the frozen station snapshot -> web/public/fixtures/heatmap.json.

Uses the tested analytics.layer_b_hotspot functions (idw, loocv, grid_over_bbox).
Prefers raw PM2.5 concentration; falls back to ISPU index (recorded in `metric`).
Stale stations excluded (honesty rule: a months-dead station must not paint the map).
"""
from __future__ import annotations

import json

import numpy as np

from scripts.demo_common import BBOX, FIXTURES_DIR, bbox_metric, load_stations, project
from analytics.layer_b_hotspot import grid_over_bbox, idw, loocv

CELL_M = 500.0


def _daily_value(s: dict) -> float | None:
    """Latest daily concentration -- spatially smoother than an instantaneous
    reading, which the first real-data run proved too noisy to validate
    (LOOCV r2 was NEGATIVE on instant values; daily aggregation is the
    standard remedy, not cherry-picking -- see workflow.md D)."""
    for d in reversed(s.get("daily30") or []):
        if d.get("conc") is not None:
            return float(d["conc"])
    return None


def main() -> None:
    stations = [s for s in load_stations() if not s["stale"]]
    conc = [(s, _daily_value(s)) for s in stations]
    conc = [(s, v) for s, v in conc if v is not None]
    if len(conc) >= 20:
        used, values = zip(*conc)
        metric = "PM2.5 harian (ug/m3)"
    else:  # daily concentration too sparse -- fall back to the ISPU index
        used = [s for s in stations if s["ispu"] is not None]
        values = [s["ispu"] for s in used]
        metric = "ISPU (indeks)"

    xy = np.array([project(s["lon"], s["lat"]) for s in used])
    v = np.array(values, dtype=float)

    # QA outlier filter (plan.md P2.1): drop stations wildly inconsistent with
    # their k nearest neighbors -- mixed-quality low-cost sensors produce
    # spatial spikes that wreck both the surface and its LOOCV. Robust
    # median/MAD test, not a tuning fudge; count is reported user-facing.
    k = min(5, len(v) - 1)
    d2 = ((xy[:, None, :] - xy[None, :, :]) ** 2).sum(axis=2)
    np.fill_diagonal(d2, np.inf)
    nn = np.argsort(d2, axis=1)[:, :k]
    neigh_med = np.median(v[nn], axis=1)
    resid = v - neigh_med
    mad = np.median(np.abs(resid - np.median(resid))) or 1.0
    keep = np.abs(resid - np.median(resid)) <= 3.5 * 1.4826 * mad
    n_outliers = int((~keep).sum())
    used = [s for s, k_ in zip(used, keep) if k_]
    xy, v = xy[keep], v[keep]

    grid_xy, shape = grid_over_bbox(bbox_metric(), cell_m=CELL_M)
    surface = idw(xy, v, grid_xy).reshape(shape)
    metrics = loocv(xy, v)

    out = {
        "bbox": list(BBOX),                      # lon/lat for the map overlay corners
        "nrows": shape[0], "ncols": shape[1],
        "cell_m": CELL_M,
        "metric": metric,
        "n_stations_used": len(used),
        "n_stations_stale_excluded": len(load_stations()) - len(stations),
        "n_outliers_removed": n_outliers,
        "loocv": {k: round(val, 3) for k, val in metrics.items()},
        "values": [round(float(x), 2) for x in surface.ravel()],
        "disclaimer": "Permukaan interpolasi IDW (estimasi spasial), bukan pengukuran langsung. Titik stasiun = terukur.",
    }
    (FIXTURES_DIR / "heatmap.json").write_text(json.dumps(out), encoding="utf-8")
    print(f"heatmap.json: {shape[0]}x{shape[1]} cells, {len(used)} stations ({metric}), "
          f"{n_outliers} outliers removed, "
          f"LOOCV r2={metrics['r2']:.3f} rmse={metrics['rmse']:.2f}")


if __name__ == "__main__":
    main()
