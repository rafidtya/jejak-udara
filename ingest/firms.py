"""NASA FIRMS active-fire pull (daily) for the greater-Jakarta bbox.

API: https://firms.modaps.eosdis.nasa.gov/api/area/  (CSV; key required).
Bbox includes an upwind margin so Layer D's "fire must be upwind" check has data.
"""
from __future__ import annotations

import csv
import io
import os

import httpx

from .common import db, dead_letter, heartbeat

# west, south, east, north — Jakarta + upwind margin
BBOX = "106.3,-6.6,107.2,-5.9"
PRODUCT = "VIIRS_SNPP_NRT"
DAYS = 1


def poll() -> None:
    key = os.environ.get("FIRMS_API_KEY")
    if not key:
        heartbeat("firms", ok=False, error="FIRMS_API_KEY missing in .env")
        return
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{PRODUCT}/{BBOX}/{DAYS}"
    try:
        r = httpx.get(url, timeout=60)
        text = r.text
    except httpx.HTTPError as exc:
        heartbeat("firms", ok=False, error=str(exc))
        return
    dead_letter("firms", url.replace(key, "***"), r.status_code, {"csv_head": text[:500]},
                parsed_ok=r.status_code == 200)
    if r.status_code != 200:
        heartbeat("firms", ok=False, error=f"http {r.status_code}")
        return
    n = 0
    with db() as conn:
        for row in csv.DictReader(io.StringIO(text)):
            conn.execute(
                """INSERT INTO fire_events (ts, geom, confidence, frp)
                   VALUES (%s::timestamptz,
                           ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s)""",
                (f"{row['acq_date']} {row['acq_time'][:2]}:{row['acq_time'][2:]}+00",
                 row["longitude"], row["latitude"],
                 row.get("confidence"), row.get("frp") or None),
            )
            n += 1
    heartbeat("firms", ok=True, rows=n)


if __name__ == "__main__":
    poll()
