"""Open-Meteo historical hourly wind -> weather_history.

Why this exists: BMKG has no history API (bmkg.md), but Layer A (polar/CPF)
needs PAST wind aligned to PAST concentration. Open-Meteo's forecast endpoint
exposes `past_days` (recent reanalysis-blended hourly), free, no key -- ideal
for pairing with SPKU's sub-hourly `metrics[].history[]` bootstrap.

Convention: `wind_direction_10m` is meteorological (direction wind comes FROM),
degrees clockwise from north -- matches our wd_deg. Stored UTC.
Attribution required: Open-Meteo (CC-BY 4.0).
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from .common import db, dead_letter, fetch_json, heartbeat

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
PAST_DAYS = 35          # covers the SPKU daily-30 bootstrap window
SPACING_S = 0.4         # gentle; free tier allows ~600/min


def _stations() -> list[tuple[str, float, float]]:
    with db() as conn:
        rows = conn.execute(
            "SELECT station_id, ST_Y(geom), ST_X(geom) FROM stations"
        ).fetchall()
    return [(r[0], r[1], r[2]) for r in rows]


def parse_hourly(payload: dict) -> list[dict]:
    """Pure: Open-Meteo hourly block -> [{ts, wd_deg, ws}]."""
    h = payload.get("hourly") or {}
    times = h.get("time") or []
    wd = h.get("wind_direction_10m") or []
    ws = h.get("wind_speed_10m") or []
    out = []
    for t, d, s in zip(times, wd, ws):
        # Open-Meteo returns naive local-time strings; we request timezone=UTC
        try:
            ts = datetime.fromisoformat(t).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        out.append({"ts": ts, "wd_deg": d, "ws": s})
    return out


def poll_one(station_id: str, lat: float, lon: float) -> int:
    status, body = fetch_json(FORECAST_URL, params={
        "latitude": lat, "longitude": lon,
        "hourly": "wind_speed_10m,wind_direction_10m",
        "wind_speed_unit": "ms", "past_days": PAST_DAYS, "forecast_days": 1,
        "timezone": "UTC",
    })
    if status != 200 or not isinstance(body, dict):
        dead_letter("open-meteo", f"{FORECAST_URL}?station={station_id}", status,
                    body if isinstance(body, dict) else {"error": "bad body"},
                    parsed_ok=False, parse_error=f"http {status}")
        return 0
    rows = parse_hourly(body)
    with db() as conn:
        for r in rows:
            conn.execute(
                """INSERT INTO weather_history (station_id, ts, wd_deg, ws)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (station_id, ts) DO UPDATE
                   SET wd_deg = EXCLUDED.wd_deg, ws = EXCLUDED.ws""",
                (station_id, r["ts"], r["wd_deg"], r["ws"]),
            )
    return len(rows)


def poll_all() -> None:
    stations = _stations()
    if not stations:
        heartbeat("open-meteo", ok=False, error="no stations yet -- run SPKU ingest first")
        return
    total = 0
    for sid, lat, lon in stations:
        total += poll_one(sid, lat, lon)
        time.sleep(SPACING_S)
    heartbeat("open-meteo", ok=True, rows=total)
    print(f"open-meteo: {len(stations)} stations, {total} hourly wind rows")


if __name__ == "__main__":
    poll_all()
