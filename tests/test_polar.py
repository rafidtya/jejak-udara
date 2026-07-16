"""Known-answer tests for Layer A polar/CPF: a synthetic easterly source must
light up the east wind-direction bins."""
import numpy as np
import pandas as pd

from analytics.layer_a_wind import dominant_direction, polar_aggregate, upwind_ray


def _synthetic(n: int = 2000, source_dir: float = 90.0) -> pd.DataFrame:
    """Concentration high only when wind blows FROM source_dir (east)."""
    rng = np.random.default_rng(42)
    wd = rng.uniform(0, 360, n)
    ws = rng.uniform(0.5, 8, n)
    near = np.abs((wd - source_dir + 180) % 360 - 180) < 30
    value = np.where(near, 80 + rng.normal(0, 5, n), 20 + rng.normal(0, 5, n))
    return pd.DataFrame({"value": value, "wd_deg": wd, "ws": ws})


def test_polar_finds_source_direction():
    polar = polar_aggregate(_synthetic())
    top = dominant_direction(polar)
    assert top is not None
    assert abs((top["wd_deg"] - 90 + 180) % 360 - 180) <= 30, top


def test_cpf_in_unit_interval():
    polar = polar_aggregate(_synthetic())
    assert polar["cpf"].between(0, 1).all()


def test_upwind_ray_points_east_for_easterly():
    ray = upwind_ray((106.8, -6.2), wd_deg=90.0, length_km=10)
    assert ray[-1][0] > ray[0][0]          # lon increases -> heading east (toward source)
    assert abs(ray[-1][1] - ray[0][1]) < 0.02
