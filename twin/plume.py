"""Gaussian plume core — multi-source, ground-level, urban dispersion.

Pure numpy, metric coordinates (EPSG:32748). See ASSUMPTIONS.md before touching.
C(x,y) = Q / (2*pi*u*sy*sz) * exp(-y^2/2sy^2) * 2*exp(-H^2/2sz^2)   [ground refl.]
Briggs urban (McElroy-Pooler) sigma curves by Pasquill stability class.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# Briggs URBAN dispersion: sigma_y, sigma_z as functions of downwind distance x (m)
# class: (a_y, b_y_form), (a_z...) — implemented directly per published forms.


def _sigma_y(x: np.ndarray, stability: str) -> np.ndarray:
    coef = {"A": 0.32, "B": 0.32, "C": 0.22, "D": 0.16, "E": 0.11, "F": 0.11}[stability]
    return coef * x * (1 + 0.0004 * x) ** -0.5


def _sigma_z(x: np.ndarray, stability: str) -> np.ndarray:
    if stability in ("A", "B"):
        return 0.24 * x * (1 + 0.001 * x) ** 0.5
    if stability == "C":
        return 0.20 * x
    if stability == "D":
        return 0.14 * x * (1 + 0.0003 * x) ** -0.5
    return 0.08 * x * (1 + 0.0015 * x) ** -0.5  # E, F


def stability_class(ws: float, tcc: float, is_day: bool) -> str:
    """Crude Pasquill class from wind speed (m/s) + cloud cover % (ASSUMPTIONS.md #3)."""
    if is_day:
        if ws < 2:
            return "A" if tcc < 50 else "B"
        if ws < 4:
            return "B" if tcc < 50 else "C"
        if ws < 6:
            return "C" if tcc < 50 else "D"
        return "D"
    # night
    if ws < 2:
        return "F" if tcc < 50 else "E"
    if ws < 4:
        return "E" if tcc < 50 else "D"
    return "D"


@dataclass
class Source:
    x: float                  # metric coords (EPSG:32748)
    y: float
    q: float                  # emission strength (relative until P3.2 calibration)
    height: float = 5.0       # effective release height (m); near-ground default
    label: str = ""
    enabled: bool = True      # what-if lever


@dataclass
class Met:
    wd_deg: float             # wind FROM, degrees clockwise from north
    ws: float                 # m/s
    tcc: float = 50.0         # cloud %
    is_day: bool = True
    tp_mm: float = 0.0        # rain (what-if washout)


@dataclass
class PlumeResult:
    grid: np.ndarray          # (nrows, ncols) concentration, relative units
    shape: tuple[int, int] = field(default=(0, 0))


def simulate(sources: list[Source], met: Met, grid_xy: np.ndarray,
             shape: tuple[int, int], *, background: float = 0.0) -> PlumeResult:
    """Superpose ground-level plumes from all enabled sources onto a metric grid.

    grid_xy: (n,2) cell centers (from analytics.layer_b_hotspot.grid_over_bbox).
    background: CAMS regional term (uniform; ASSUMPTIONS.md #6).
    """
    ws = max(met.ws, 0.5)  # calm guard: Gaussian plume undefined at u->0
    stab = stability_class(ws, met.tcc, met.is_day)
    # wind blows TOWARD wd_deg+180; downwind unit vector:
    theta = np.deg2rad((met.wd_deg + 180.0) % 360.0)
    downwind = np.array([np.sin(theta), np.cos(theta)])   # (east, north)
    crosswind = np.array([downwind[1], -downwind[0]])

    conc = np.full(len(grid_xy), float(background))
    for s in sources:
        if not s.enabled:
            continue
        rel = grid_xy - np.array([s.x, s.y])
        x_d = rel @ downwind          # downwind distance
        y_c = rel @ crosswind         # crosswind offset
        mask = x_d > 1.0              # plume exists only downwind
        if not mask.any():
            continue
        sy = _sigma_y(x_d[mask], stab)
        sz = _sigma_z(x_d[mask], stab)
        c = (s.q / (2 * np.pi * ws * sy * sz)
             * np.exp(-0.5 * (y_c[mask] / sy) ** 2)
             * 2 * np.exp(-0.5 * (s.height / sz) ** 2))   # ground reflection
        conc[mask] += c

    if met.tp_mm > 0:  # crude washout (ASSUMPTIONS.md #7)
        conc = background + (conc - background) * float(np.exp(-0.2 * met.tp_mm))

    return PlumeResult(grid=conc.reshape(shape), shape=shape)
