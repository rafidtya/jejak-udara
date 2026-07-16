"""Known-answer tests for Layer B: IDW must reconstruct a synthetic surface and
LOOCV must report near-perfect skill on smooth data."""
import numpy as np

from analytics.layer_b_hotspot import grid_over_bbox, idw, loocv


def _smooth_field(xy: np.ndarray) -> np.ndarray:
    return 50 + 30 * np.sin(xy[:, 0] / 3000.0) + 20 * np.cos(xy[:, 1] / 4000.0)


def test_idw_exact_at_stations():
    rng = np.random.default_rng(0)
    xy = rng.uniform(0, 10_000, (20, 2))
    v = _smooth_field(xy)
    pred = idw(xy, v, xy)
    assert np.allclose(pred, v)


def test_loocv_good_on_smooth_field():
    rng = np.random.default_rng(1)
    xy = rng.uniform(0, 10_000, (60, 2))
    v = _smooth_field(xy)
    m = loocv(xy, v)
    assert m["r2"] > 0.5, m
    assert m["n"] == 60


def test_grid_shape_consistent():
    pts, shape = grid_over_bbox((0, 0, 5000, 3000), cell_m=1000)
    assert len(pts) == shape[0] * shape[1] == 15
