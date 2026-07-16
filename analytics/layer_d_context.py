"""Layer D — context fusion & corroboration (plan.md P2.13).

TODO(P2.13): implement once static GIS tables are loaded (P1.4/P1B.4):
  - hotspot ∩ road density (OSM)          -> traffic evidence
  - hotspot ∩ industrial masks (DW/OSM)   -> industry evidence
  - hotspot ∩ low-NDVI bare land          -> dust evidence
  - episode ∩ FIRMS fire, WITH UPWIND CHECK (fire bearing vs wd_deg ±45°)
  - hotspot ∩ WorldPop                    -> population_affected

Each check appends a human-readable string to the factor/hotspot `evidence[]`
and nudges the combined confidence. Pure spatial SQL where possible.
"""
from __future__ import annotations


def upwind_bearing_ok(fire_bearing_deg: float, wd_deg: float, tolerance: float = 45.0) -> bool:
    """A fire corroborates a burning episode only if it sits upwind.

    fire_bearing_deg: bearing FROM station TO fire. wd_deg: wind FROM direction.
    They must roughly coincide for the smoke to reach the station.
    """
    diff = abs((fire_bearing_deg - wd_deg + 180) % 360 - 180)
    return diff <= tolerance
