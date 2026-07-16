"""Known-answer tests for the Gaussian plume core (agents.md §6 testing bar)."""
import numpy as np

from analytics.layer_b_hotspot import grid_over_bbox
from twin.plume import Met, Source, simulate, stability_class
from twin.scenarios import whatif

BBOX = (0.0, 0.0, 10_000.0, 10_000.0)  # 10x10 km synthetic domain
GRID, SHAPE = grid_over_bbox(BBOX, cell_m=500.0)
CENTER = Source(x=5000.0, y=5000.0, q=100.0, label="s1")


def _peak_xy(grid: np.ndarray) -> tuple[float, float]:
    idx = np.unravel_index(np.nanargmax(grid), grid.shape)
    flat = idx[0] * grid.shape[1] + idx[1]
    return tuple(GRID[flat])


def test_plume_peaks_downwind():
    # wind FROM west (270deg) => blows TOWARD east => peak must be EAST of source
    res = simulate([CENTER], Met(wd_deg=270.0, ws=3.0), GRID, SHAPE)
    px, py = _peak_xy(res.grid)
    assert px > CENTER.x, f"peak at x={px}, expected east of {CENTER.x}"
    assert abs(py - CENTER.y) < 1500, "peak should stay near the centerline"


def test_no_concentration_upwind():
    res = simulate([CENTER], Met(wd_deg=270.0, ws=3.0), GRID, SHAPE)
    upwind_mask = GRID[:, 0] < (CENTER.x - 500)
    assert float(res.grid.ravel()[upwind_mask].max()) == 0.0


def test_stronger_wind_dilutes():
    weak = simulate([CENTER], Met(wd_deg=270.0, ws=2.0), GRID, SHAPE)
    strong = simulate([CENTER], Met(wd_deg=270.0, ws=8.0), GRID, SHAPE)
    assert strong.grid.max() < weak.grid.max()


def test_background_superposes():
    res = simulate([CENTER], Met(wd_deg=270.0, ws=3.0), GRID, SHAPE, background=10.0)
    assert float(res.grid.min()) >= 10.0


def test_whatif_disable_reduces():
    out = whatif([CENTER], Met(wd_deg=270.0, ws=3.0), GRID, SHAPE, {"disable": ["s1"]})
    assert out["delta_mean_pct"] < 0, "disabling the only source must reduce mean conc"


def test_stability_class_bounds():
    assert stability_class(1.0, 20.0, True) == "A"
    assert stability_class(1.0, 20.0, False) == "F"
    assert stability_class(7.0, 80.0, True) == "D"
