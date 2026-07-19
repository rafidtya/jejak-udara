"""JejakUdara API — thin read layer over persisted results + the what-if pass.

Boundary (agents.md §2): endpoints read batch-produced tables; the ONLY heavy
per-request compute is POST /twin/whatif. Empty tables return empty results
(not errors) so a fresh DB still serves a valid, if sparse, API.
Honesty (agents.md §5): surfaces/sources carry their disclaimers + metrics.
"""
from __future__ import annotations

from typing import Any

import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from analytics.geo import bbox_metric, project, unproject
from analytics.jobs import latest_ispu
from analytics.layer_b_hotspot import grid_over_bbox
from ingest.common import db
from twin.plume import Met, Source
from twin.scenarios import whatif

app = FastAPI(
    title="JejakUdara API",
    description="Atribusi sumber & simulasi polusi udara Jakarta. "
                "Permukaan & simulasi bersifat ESTIMASI; titik stasiun = terukur.",
    version="0.2.0",
)
# Open CORS for the Figma-driven frontend (dev). Lock down for prod (Track B).
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_GRID_XY, _GRID_SHAPE = grid_over_bbox(bbox_metric(), cell_m=1000.0)


def q(sql: str, params: tuple = ()) -> list[tuple]:
    with db() as conn:
        return conn.execute(sql, params).fetchall()


# ---------------- metadata ----------------

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/meta")
def meta() -> dict[str, Any]:
    rows = q("""SELECT source, last_success, rows_24h FROM ingest_heartbeat ORDER BY source""")
    n = q("SELECT count(*) FROM stations")[0][0]
    return {
        "station_count": n,
        "ingestion": [{"source": s, "last_success": str(t) if t else None, "rows_24h": r}
                      for s, t, r in rows],
        "disclaimer": "Data snapshot dari sumber publik (DLH SPKU, BMKG, Open-Meteo).",
    }


# ---------------- measured layer ----------------

@app.get("/stations")
def stations() -> dict[str, Any]:
    """GeoJSON of stations with their latest dominant ISPU (measured points)."""
    rows = q("""
        SELECT DISTINCT ON (s.station_id)
               s.station_id, s.name, s.kind, ST_X(s.geom), ST_Y(s.geom),
               s.meta->>'kecamatan', r.value, r.ts, r.qa_flag
        FROM stations s
        LEFT JOIN readings r
          ON r.station_id = s.station_id AND r.is_index
        ORDER BY s.station_id, r.ts DESC NULLS LAST, r.value DESC
    """)
    feats = []
    for sid, name, kind, lon, lat, kec, val, ts, qa in rows:
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "station_id": sid, "name": name, "kind": kind, "kecamatan": kec,
                "ispu": val, "ts": str(ts) if ts else None, "stale": qa == "stale",
            },
        })
    return {"type": "FeatureCollection", "features": feats}


@app.get("/surface")
def surface(pollutant: str = "pm25", kind: str = "measured") -> dict[str, Any]:
    rows = q("""SELECT grid, run_ts FROM forecast_surfaces
                WHERE pollutant=%s AND kind=%s ORDER BY run_ts DESC LIMIT 1""",
             (pollutant, kind))
    if not rows:
        return {"available": False, "reason": "belum ada surface — jalankan analytics batch"}
    grid, run_ts = rows[0]
    return {"available": True, "run_ts": str(run_ts), **grid,
            "disclaimer": "Permukaan interpolasi (estimasi spasial), bukan pengukuran langsung. "
                           "Warna memudar menjauhi stasiun nyata — area tanpa cakupan sensor "
                           "(mis. kota tetangga) sengaja tidak digambar seyakin area berstasiun."}


@app.get("/hotspots")
def hotspots() -> list[dict[str, Any]]:
    rows = q("""SELECT district, pollutant, gi_z, lower(ts_window)
                FROM hotspots ORDER BY gi_z DESC NULLS LAST LIMIT 50""")
    return [{"district": d, "pollutant": p, "gi_z": z, "ts": str(t),
             "flagged": (z or 0) > 1.0} for d, p, z, t in rows]


# ---------------- attribution layer ----------------

@app.get("/sources")
def sources() -> dict[str, Any]:
    cand = q("""SELECT ST_AsGeoJSON(geom), method, notes, lower(episode_ts)
                FROM source_candidates ORDER BY id DESC LIMIT 50""")
    factors = q("""SELECT label, confidence, profile, diurnal, evidence, run_ts
                   FROM source_factors ORDER BY run_ts DESC LIMIT 20""")
    import json as _json
    return {
        "candidates": [{"geometry": _json.loads(g), "method": m, "notes": n, "ts": str(t)}
                       for g, m, n, t in cand],
        "factors": [{"label": l, "confidence": c, "profile": pr, "diurnal": di,
                     "evidence": ev, "run_ts": str(rt)}
                    for l, c, pr, di, ev, rt in factors],
        "disclaimer": "Atribusi bersifat probabilistik; setiap sumber punya tingkat keyakinan.",
    }


@app.get("/polar/{station_id}")
def polar(station_id: str) -> list[dict[str, Any]]:
    rows = q("""SELECT wd_bin, ws_bin, mean_conc, n, cpf FROM polar_stats
                WHERE station_id=%s ORDER BY wd_bin, ws_bin""", (station_id,))
    return [{"wd_bin": wd, "ws_bin": ws, "mean_conc": mc, "n": n, "cpf": cpf}
            for wd, ws, mc, n, cpf in rows]


@app.get("/validation")
def validation() -> list[dict[str, Any]]:
    rows = q("""SELECT DISTINCT ON (kind, pollutant) kind, pollutant, metrics, run_ts
                FROM validation_runs ORDER BY kind, pollutant, run_ts DESC""")
    return [{"kind": k, "pollutant": p, "metrics": m, "run_ts": str(t)}
            for k, p, m, t in rows]


# ---------------- digital twin ----------------

class WhatIfRequest(BaseModel):
    disable: list[str] = Field(default_factory=list)
    scale: dict[str, float] = Field(default_factory=dict)
    rain_mm: float = 0.0
    wd_deg: float = 270.0
    ws: float = 3.0


def _twin_sources() -> list[Source]:
    """Illustrative sources anchored to the 3 worst live ISPU stations
    (labeled illustrative; strengths in plume units, calibration is Track B)."""
    rd = sorted(latest_ispu(), key=lambda r: -r["value"])[:3]
    labels, strengths = ["lalu_lintas", "industri", "pembakaran"], [1.5e7, 1.0e7, 6.0e6]
    out = []
    for r, lab, q_ in zip(rd, labels, strengths):
        x, y = project(r["lon"], r["lat"])
        out.append(Source(x=x, y=y, q=q_, label=lab))
    return out


@app.post("/twin/whatif")
def twin_whatif(req: WhatIfRequest) -> dict[str, Any]:
    sources = _twin_sources()
    if not sources:
        return {"available": False, "reason": "belum ada data stasiun untuk menautkan sumber"}
    met = Met(wd_deg=req.wd_deg, ws=req.ws)
    r = whatif(sources, met, np.asarray(_GRID_XY), _GRID_SHAPE,
               {"disable": req.disable, "scale": req.scale, "rain_mm": req.rain_mm},
               background=18.0)
    before, after = np.asarray(r["before"]), np.asarray(r["after"])
    return {
        "available": True,
        "delta_mean_pct": r["delta_mean_pct"],
        "delta_max_local_ugm3": round(float((after - before).min()), 1),
        "sources": [dict(zip(("lon", "lat"), unproject(s.x, s.y)), label=s.label) for s in sources],
        "nrows": _GRID_SHAPE[0], "ncols": _GRID_SHAPE[1],
        "bbox": [106.65, -6.40, 107.00, -6.05],
        "before": [round(float(x), 2) for x in before.ravel()],
        "after": [round(float(x), 2) for x in after.ravel()],
        "scenario": r["scenario"],
        "disclaimer": r["disclaimer"],
    }
