"""What-if engine: scenario = a diff on the source list -> before/after grids.

The demo centerpiece (plan.md P3.4). Stateless; performance budget <5s.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np

from .plume import Met, PlumeResult, Source, simulate


def apply_scenario(sources: list[Source], met: Met, scenario: dict[str, Any]
                   ) -> tuple[list[Source], Met]:
    """Scenario schema (POST /twin/whatif body):
      {"disable": ["label", ...],           # turn sources off
       "scale":   {"label": 0.5, ...},      # scale source strength
       "rain_mm": 4.0}                      # add rain washout
    """
    out = []
    disable = set(scenario.get("disable", []))
    scale = scenario.get("scale", {})
    for s in sources:
        s2 = replace(s)
        if s.label in disable:
            s2.enabled = False
        if s.label in scale:
            s2.q = s.q * float(scale[s.label])
        out.append(s2)
    met2 = replace(met, tp_mm=float(scenario.get("rain_mm", met.tp_mm)))
    return out, met2


def whatif(sources: list[Source], met: Met, grid_xy: np.ndarray, shape: tuple[int, int],
           scenario: dict[str, Any], *, background: float = 0.0) -> dict:
    before: PlumeResult = simulate(sources, met, grid_xy, shape, background=background)
    s2, m2 = apply_scenario(sources, met, scenario)
    after: PlumeResult = simulate(s2, m2, grid_xy, shape, background=background)
    delta = after.grid - before.grid
    denom = float(before.grid.mean()) or 1e-9
    return {
        "before": before.grid.tolist(),
        "after": after.grid.tolist(),
        "delta_mean_pct": round(100.0 * float(delta.mean()) / denom, 1),
        "delta_max": float(delta.min()),   # most-improved cell (negative = reduction)
        "scenario": scenario,
        "disclaimer": "Simulasi Gaussian plume — alat pendukung keputusan, bukan pengukuran. Lihat twin/ASSUMPTIONS.md",
    }
