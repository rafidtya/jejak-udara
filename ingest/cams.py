"""CAMS regional PM2.5 background (twin boundary term). Requires CAMS_ADS_KEY (P0.3b).

TODO(P1B.5): implement cdsapi pull of CAMS global atmospheric composition
analysis+forecast PM2.5 for the Jakarta region; store regional mean into
`regional_background`. Attribution: Copernicus Atmosphere Monitoring Service.
"""
from __future__ import annotations

import os

from .common import heartbeat


def poll() -> None:
    if not os.environ.get("CAMS_ADS_KEY"):
        heartbeat("cams", ok=False, error="CAMS_ADS_KEY missing in .env (P0.3b)")
        return
    raise NotImplementedError("P1B.5 — cdsapi request skeleton pending key registration")


if __name__ == "__main__":
    poll()
