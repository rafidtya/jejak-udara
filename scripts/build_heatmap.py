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


def main() -> None:
    stations = [s for s in load_stations() if not s["stale"]]
    conc = [(s, s["concentration"]) for s in stations
            if s["concentration"] is not None and (s["parameter"] or "").upper() == "PM25"]
    if len(conc) >= 20:
        used, values = zip(*conc)
        metric = "PM2.5 (ug/m3)"
    else:  # concentration too sparse -- fall back to the ISPU index
        used = [s for s in stations if s["ispu"] is not None]
        values = [s["ispu"] for s in used]
        metric = "ISPU (indeks)"

    xy = np.array([project(s["lon"], s["lat"]) for s in used])
    v = np.array(values, dtype=float)

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
        "loocv": {k: round(val, 3) for k, val in metrics.items()},
        "values": [round(float(x), 2) for x in surface.ravel()],
        "disclaimer": "Permukaan interpolasi IDW (estimasi spasial), bukan pengukuran langsung. Titik stasiun = terukur.",
    }
    (FIXTURES_DIR / "heatmap.json").write_text(json.dumps(out), encoding="utf-8")
    print(f"heatmap.json: {shape[0]}x{shape[1]} cells, {len(used)} stations ({metric}), "
          f"LOOCV r2={metrics['r2']:.3f} rmse={metrics['rmse']:.2f}")


if __name__ == "__main__":
    main()
