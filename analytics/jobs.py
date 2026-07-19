"""Nightly batch: DB -> layers (pure funcs) -> results tables (agents.md §6).

MVP scope: Layer B (surface + LOOCV) and district hotspots run on any snapshot.
Layer A (polar + dominant direction) runs where weather_history exists, else
skips with a logged reason -- never fabricated. Layer C (NMF) is gated on
multi-pollutant history depth (checked + reported, not silently attempted).
"""
from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime, timezone

import numpy as np

from ingest.common import db, utcnow
from .geo import bbox_metric, project, project_arr, unproject
from .layer_a_wind import dominant_direction, polar_aggregate, upwind_ray
from .layer_b_hotspot import grid_over_bbox, idw, loocv

CELL_M = 500.0
POLLUTANT = "pm25"


# ---------- data loading ----------

def latest_ispu() -> list[dict]:
    """Per station: the latest DOMINANT ISPU index (max sub-index = the ISPU
    definition). Uniform 0-500 scale, comparable across pollutants and across
    ALL stations -- avoids mixing ug/m3 with index units on the surface."""
    with db() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT ON (r.station_id)
                   r.station_id, r.value, r.ts,
                   ST_X(s.geom) AS lon, ST_Y(s.geom) AS lat,
                   s.meta->>'kecamatan' AS kecamatan
            FROM readings r JOIN stations s USING (station_id)
            -- value>0: an ISPU of 0 is physically impossible in Jakarta; it
            -- marks a non-functioning sensor. Excluded so it can't drag the
            -- interpolated surface / hotspots / twin anchoring downward.
            WHERE r.is_index AND r.qa_flag <> 'stale' AND r.value > 0
            ORDER BY r.station_id, r.ts DESC, r.value DESC
            """,
        ).fetchall()
    return [{"station_id": sid, "value": float(val), "ts": ts,
             "lon": lon, "lat": lat, "kecamatan": kec}
            for sid, val, ts, lon, lat, kec in rows]


# ---------- Layer B: surface + validation ----------

# SPKU spacing is ~1-2km (workflow.md C2a); full confidence within that, tapering
# to a faint (not zero -- still "here be estimate", not "invisible") floor by 6km.
_CONF_NEAR_M = 1500.0
_CONF_FAR_M = 6000.0
_CONF_FLOOR = 0.05


def _distance_confidence(grid_xy: np.ndarray, station_xy: np.ndarray) -> np.ndarray:
    """Per grid-cell opacity multiplier (0..1) from distance to the nearest real
    station. Linear taper CONF_NEAR->1.0 to CONF_FAR->CONF_FLOOR; clipped beyond."""
    d = np.sqrt(((grid_xy[:, None, :] - station_xy[None, :, :]) ** 2).sum(-1)).min(axis=1)
    frac = (d - _CONF_NEAR_M) / (_CONF_FAR_M - _CONF_NEAR_M)
    return np.clip(1.0 - frac * (1.0 - _CONF_FLOOR), _CONF_FLOOR, 1.0)

def run_layer_b() -> dict:
    rd = latest_ispu()
    if len(rd) < 10:
        return {"layer_b": "skipped", "reason": f"only {len(rd)} readings"}
    metric = "ISPU (indeks, dominan)"

    lonlat = np.array([[r["lon"], r["lat"]] for r in rd])
    xy = project_arr(lonlat)
    v = np.array([r["value"] for r in rd], dtype=float)

    grid_xy, shape = grid_over_bbox(bbox_metric(), cell_m=CELL_M)
    surface = idw(xy, v, grid_xy).reshape(shape)
    metrics = loocv(xy, v)
    confidence = _distance_confidence(grid_xy, xy)

    grid_json = {
        "bbox": [106.65, -6.40, 107.00, -6.05],
        "nrows": shape[0], "ncols": shape[1], "cell_m": CELL_M,
        "metric": metric, "n_stations": len(rd),
        "values": [round(float(x), 2) for x in surface.ravel()],
        # per-cell 0..1 opacity multiplier -- fades the surface out away from any
        # real station instead of painting a flat, equally-confident rectangle
        # over areas (neighboring cities, the bay) with zero actual coverage.
        "confidence": [round(float(x), 3) for x in confidence],
    }
    now = utcnow()
    with db() as conn:
        conn.execute(
            """INSERT INTO forecast_surfaces (run_ts, valid_ts, pollutant, grid, kind, scenario)
               VALUES (%s, %s, %s, %s, 'measured', NULL)
               ON CONFLICT (run_ts, valid_ts, pollutant, kind) DO UPDATE SET grid = EXCLUDED.grid""",
            (now, now, POLLUTANT, json.dumps(grid_json)),
        )
        conn.execute(
            """INSERT INTO validation_runs (kind, pollutant, metrics)
               VALUES ('loocv', %s, %s)""",
            (POLLUTANT, json.dumps({k: round(v_, 3) for k, v_ in metrics.items()} | {"metric": metric})),
        )
    return {"layer_b": "ok", "n_stations": len(rd), "metric": metric,
            "loocv_r2": round(metrics["r2"], 3), "loocv_rmse": round(metrics["rmse"], 2)}


# ---------- district hotspots (honest MVP: z-score of district mean vs city) ----------

def run_hotspots() -> dict:
    rd = [r for r in latest_ispu() if r["kecamatan"]]
    if len(rd) < 8:
        return {"hotspots": "skipped", "reason": "too few located readings"}
    by_dist: dict[str, list[float]] = {}
    for r in rd:
        by_dist.setdefault(r["kecamatan"], []).append(r["value"])
    dist_mean = {d: statistics.mean(vs) for d, vs in by_dist.items()}
    vals = list(dist_mean.values())
    mu, sd = statistics.mean(vals), (statistics.pstdev(vals) or 1.0)
    now = utcnow()
    n_hot = 0
    with db() as conn:
        conn.execute("DELETE FROM hotspots WHERE lower(ts_window) < now() - interval '2 days'")
        for d, m in dist_mean.items():
            z = (m - mu) / sd
            # NOTE: tstzrange(x,x) is EMPTY (half-open [x,x)) -> lower() returns
            # NULL. Use an inclusive point-in-time range '[]' instead (workflow.md).
            conn.execute(
                """INSERT INTO hotspots (ts_window, district, pollutant, gi_z, p_value, population_affected)
                   VALUES (tstzrange(%s, %s, '[]'), %s, %s, %s, NULL, NULL)""",
                (now, now, d, POLLUTANT, round(z, 3)),
            )
            if z > 1.0:
                n_hot += 1
    return {"hotspots": "ok", "n_districts": len(dist_mean), "n_flagged": n_hot}


# ---------- Layer A: polar + dominant direction (gated on wind history) ----------

def run_layer_a() -> dict:
    with db() as conn:
        wh = conn.execute("SELECT count(*) FROM weather_history").fetchone()[0]
        if wh == 0:
            return {"layer_a": "skipped", "reason": "no weather_history -- run ingest.openmeteo"}
        # stations with enough paired (concentration history + wind) samples
        pairs = conn.execute(
            """
            SELECT r.station_id, r.value, r.ts,
                   w.wd_deg, w.ws, ST_X(s.geom) lon, ST_Y(s.geom) lat
            FROM readings r
            JOIN stations s USING (station_id)
            JOIN LATERAL (
                SELECT wd_deg, ws FROM weather_history wh2
                WHERE wh2.station_id = r.station_id
                ORDER BY abs(extract(epoch FROM (wh2.ts - r.ts))) LIMIT 1
            ) w ON true
            -- value>0: drop broken 0-readings so they can't create spurious
            -- CPF / source directions (a 0 ug/m3 PM2.5 in Jakarta = dead sensor).
            WHERE r.pollutant = %s AND NOT r.is_index AND r.qa_flag <> 'stale' AND r.value > 0
            """,
            (POLLUTANT,),
        ).fetchall()
    if len(pairs) < 100:
        return {"layer_a": "thin", "reason": f"only {len(pairs)} paired samples -- accumulating"}

    import pandas as pd
    df = pd.DataFrame(pairs, columns=["station_id", "value", "ts", "wd_deg", "ws", "lon", "lat"])
    now = utcnow()
    n_dir = 0
    n_polar = 0
    with db() as conn:
        # candidates are a point-in-time snapshot; drop prior run's before
        # inserting fresh ones (same replace-per-run pattern as polar_stats)
        conn.execute("DELETE FROM source_candidates WHERE method='polar_dominant'")
        for sid, g in df.groupby("station_id"):
            if len(g) < 30:
                continue
            polar = polar_aggregate(g.rename(columns={"value": "value"}))
            # persist EVERY station's bins (not just ones with a directional
            # signal) -- GET /polar/{id} is a wind-rose chart, useful even
            # without a clear dominant direction. Fixed the earlier gap where
            # only dominant_direction() results were saved, leaving this table empty.
            # Replace-per-station (window_start shifts each run -> would
            # otherwise accumulate stale duplicate bins across batch runs).
            conn.execute("DELETE FROM polar_stats WHERE station_id=%s AND pollutant=%s",
                        (sid, POLLUTANT))
            w_start, w_end = g["ts"].min(), g["ts"].max()
            for _, row in polar.iterrows():
                conn.execute(
                    """INSERT INTO polar_stats
                       (station_id, pollutant, window_start, window_end, wd_bin, ws_bin, mean_conc, n, cpf)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (station_id, pollutant, window_start, wd_bin, ws_bin)
                       DO UPDATE SET mean_conc=EXCLUDED.mean_conc, n=EXCLUDED.n, cpf=EXCLUDED.cpf""",
                    (sid, POLLUTANT, w_start, w_end, int(row["wd_bin"]), int(row["ws_bin"]),
                     float(row["mean_conc"]), int(row["n"]), float(row["cpf"])),
                )
            n_polar += 1

            top = dominant_direction(polar)
            if not top or top["local"]:
                continue
            lon0, lat0 = float(g["lon"].iloc[0]), float(g["lat"].iloc[0])
            ray = upwind_ray((lon0, lat0), top["wd_deg"], length_km=8)
            # store a coarse candidate polygon: buffer around the ray endpoint
            ex, ey = ray[-1]
            conn.execute(
                """INSERT INTO source_candidates (episode_ts, geom, method, n_stations, notes)
                   VALUES (tstzrange(%s,%s,'[]'),
                           ST_Buffer(ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography, 1500)::geometry,
                           'polar_dominant', 1, %s)""",
                (now, now, float(ex), float(ey),
                 f"{sid}: arah {top['wd_deg']:.0f} deg, CPF={top['cpf']:.2f}"),
            )
            n_dir += 1
    return {"layer_a": "ok", "paired_samples": len(pairs), "directions": n_dir, "polar_stations": n_polar}


def run_once() -> dict:
    result = {"run_ts": utcnow().isoformat()}
    result.update(run_layer_b())
    result.update(run_hotspots())
    result.update(run_layer_a())
    print(json.dumps(result, indent=2))
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.parse_args()
    run_once()


if __name__ == "__main__":
    main()
