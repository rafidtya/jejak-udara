"""JejakUdara API — thin read layer over results tables + the what-if pass-through.

Boundary (agents.md §2): the ONLY heavy compute allowed per-request is
POST /twin/whatif. Everything else reads persisted batch results.
Endpoints marked TODO return 501 until their results tables have data.
"""
from __future__ import annotations

from typing import Any

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from analytics.layer_b_hotspot import grid_over_bbox
from twin.plume import Met, Source
from twin.scenarios import whatif

app = FastAPI(
    title="JejakUdara API",
    description="Atribusi sumber & simulasi polusi udara Jakarta — hasil bersifat estimasi",
    version="0.1.0",
)

# Jakarta demo grid in metric UTM 48S (approx bbox), 1 km cells for the demo
_DEMO_BBOX_M = (683000.0, 9270000.0, 712000.0, 9330000.0)
_GRID_XY, _GRID_SHAPE = grid_over_bbox(_DEMO_BBOX_M, cell_m=1000.0)

# Demo sources — replaced by Layer C output at P3.1 integration
_DEMO_SOURCES = [
    Source(x=697000, y=9312000, q=100.0, label="traffic_corridor_demo"),
    Source(x=705000, y=9295000, q=60.0, label="industry_demo"),
]


class WhatIfRequest(BaseModel):
    disable: list[str] = Field(default_factory=list)
    scale: dict[str, float] = Field(default_factory=dict)
    rain_mm: float = 0.0
    wd_deg: float = 90.0   # demo met; production pulls live BMKG
    ws: float = 3.0


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/stations")
def stations() -> Any:
    raise HTTPException(501, "TODO(P4.1): reads `stations` once P0.1/P1.1 land")


@app.get("/surface")
def surface(pollutant: str = "pm25", kind: str = "measured") -> Any:
    raise HTTPException(501, "TODO(P4.1): reads `forecast_surfaces`/kriged rasters (P2.2)")


@app.get("/hotspots")
def hotspots() -> Any:
    raise HTTPException(501, "TODO(P4.1): reads `hotspots` (P2.3)")


@app.get("/sources")
def sources() -> Any:
    raise HTTPException(501, "TODO(P4.1): reads `source_factors` + evidence (P2.11)")


@app.get("/validation")
def validation() -> Any:
    raise HTTPException(501, "TODO(P4.1): reads `validation_runs` (P2.4/P3.6)")


@app.post("/twin/whatif")
def twin_whatif(req: WhatIfRequest) -> dict:
    """Scenario simulation — WORKS TODAY on demo sources (plume core is real)."""
    met = Met(wd_deg=req.wd_deg, ws=req.ws)
    result = whatif(
        _DEMO_SOURCES, met, np.asarray(_GRID_XY), _GRID_SHAPE,
        {"disable": req.disable, "scale": req.scale, "rain_mm": req.rain_mm},
    )
    # grids are big; demo endpoint returns stats + downsampled preview
    before = np.asarray(result["before"])
    after = np.asarray(result["after"])
    return {
        "delta_mean_pct": result["delta_mean_pct"],
        "scenario": result["scenario"],
        "disclaimer": result["disclaimer"],
        "preview_before": before[::4, ::4].round(4).tolist(),
        "preview_after": after[::4, ::4].round(4).tolist(),
        "grid_shape_full": list(_GRID_SHAPE),
    }
