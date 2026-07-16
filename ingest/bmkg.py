"""BMKG per-kelurahan forecast poller.

Contract VERIFIED (db/SCHEMA.md; research: D:\\Jalan.in\\bmkg.md 2026-06-25):
- adm4-only queries; adm1/adm2 return 301 to the docs page.
- <=60 req/min; we poll 267 Jakarta codes twice daily (way under limit, sequential).
- `data[0].cuaca` is a NESTED per-day array (3 days x ~8 x 3-hourly), not flat.
- We store EVERY run: BMKG has no historical API — unshipped runs are gone forever.
"""
from __future__ import annotations

import time
from typing import Any, Iterator

from .common import db, dead_letter, fetch_json, heartbeat, mark_parsed

BASE_URL = "https://api.bmkg.go.id/publik/prakiraan-cuaca"
REQUEST_SPACING_S = 1.1  # ~55/min worst case, politely under the 60/min limit


def jakarta_adm4_codes() -> list[str]:
    with db() as conn:
        rows = conn.execute("SELECT adm4_code FROM kelurahan ORDER BY adm4_code").fetchall()
    return [r[0] for r in rows]


def _iter_entries(payload: dict) -> Iterator[dict]:
    """Flatten the nested per-day `cuaca` arrays (the #1 parse gotcha)."""
    for block in payload.get("data", []):
        for day in block.get("cuaca", []):
            yield from day


def parse_run(payload: dict) -> tuple[dict | None, list[dict]]:
    """Return (location_meta, [forecast rows]). Pure function — unit-tested on fixtures."""
    loc = payload.get("lokasi") or {}
    meta = None
    if loc.get("adm4"):
        meta = {
            "adm4_code": loc["adm4"],
            "name": loc.get("desa", ""),
            "lon": loc.get("lon"),
            "lat": loc.get("lat"),
        }
    rows = []
    for e in _iter_entries(payload):
        if not e.get("utc_datetime"):
            continue
        rows.append({
            "valid_ts": e["utc_datetime"],          # UTC per convention
            "analysis_ts": e.get("analysis_date"),
            "wd_deg": e.get("wd_deg"),
            "ws": e.get("ws"),
            "hu": e.get("hu"),
            "t": e.get("t"),
            "tcc": e.get("tcc"),
            "tp": e.get("tp"),
        })
    return meta, rows


def poll_one(adm4: str, run_label: str) -> int:
    status, body = fetch_json(BASE_URL, params={"adm4": adm4})
    raw_id = dead_letter("bmkg", f"{BASE_URL}?adm4={adm4}", status, body)
    if status != 200 or not isinstance(body, dict):
        mark_parsed(raw_id, False, f"http {status}")
        return 0
    try:
        meta, rows = parse_run(body)
    except Exception as exc:  # parser bug — raw payload is safe, fix retroactively
        mark_parsed(raw_id, False, repr(exc))
        return 0
    with db() as conn:
        if meta and meta["lon"] is not None:
            conn.execute(
                """INSERT INTO kelurahan (adm4_code, name, geom_centroid)
                   VALUES (%s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                   ON CONFLICT (adm4_code) DO UPDATE
                   SET geom_centroid = EXCLUDED.geom_centroid""",
                (meta["adm4_code"], meta["name"], meta["lon"], meta["lat"]),
            )
        for r in rows:
            conn.execute(
                """INSERT INTO weather_forecasts
                   (adm4_code, run_ts, valid_ts, wd_deg, ws, hu, t, tcc, tp)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT DO NOTHING""",
                (adm4, run_label, r["valid_ts"], r["wd_deg"], r["ws"],
                 r["hu"], r["t"], r["tcc"], r["tp"]),
            )
    mark_parsed(raw_id, True)
    return len(rows)


def poll_all() -> None:
    from .common import utcnow
    run_label = utcnow().isoformat()
    codes = jakarta_adm4_codes()
    if not codes:
        heartbeat("bmkg", ok=False, error="kelurahan table empty — run `make seed` (P0.2)")
        return
    total = 0
    for code in codes:
        total += poll_one(code, run_label)
        time.sleep(REQUEST_SPACING_S)
    heartbeat("bmkg", ok=True, rows=total)


if __name__ == "__main__":
    poll_all()
