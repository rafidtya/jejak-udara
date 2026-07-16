"""SPKU (udara.jakarta.go.id) two-stage SSR scraper.

CONTRACT VERIFIED 2026-07-03 (db/SCHEMA.md; source: D:\\Jalan.in\\udara.md,
a sibling project's live research). No JSON API -- the portal is SSR HTML:

  Stage 1: GET /lokasi-spku          -> all 105 stations in one page, discover
                                         each station's /spku/<uuid> path.
  Stage 2: GET /spku/<uuid>          -> `var SPKU_DETAIL_DATA = {...};` embedded
                                         in the HTML -- brace-balanced extract, json.loads.

Quirks implemented here (db/SCHEMA.md has the full rationale):
  - staleness: lastUpdate can be MONTHS old while ispuValue still looks live.
    Tagged qa_flag='stale', never silently dropped.
  - lastUpdate has no tz suffix -> treat as WIB (UTC+7), store as UTC.
  - Kepulauan Seribu (2 stations) excluded by mainland bbox, not by name.
  - WAF/bot protection -> gentle scraping: spacing + honest UA (common.py).

P0.1c RESOLVED by a live pull (curl, 2 gentle requests) -- confirmed shapes:
  - dailyIspu30Days[]: {date, maxIspu, dominantMetric, concentration} x 30 days.
    Implemented below (_daily_rows) -- a real historical bootstrap, no waiting.
  - metrics[].history[]: NOT in the original research (that sample showed history
    always empty) -- but a live "Sensor"-type station returned populated
    {time, value} pairs at ~30-min resolution. Per-pollutant, sub-hourly, real
    concentration values -- exactly what Layer C wants, available on day one.
    Unconfirmed whether "Reference"-type stations ever populate this (the one
    Reference sample seen so far had history=[]) -- extract opportunistically,
    never assume it's present.
  - forecast[]: shape confirmed exactly as documented ({label,date,icon,ispu,category}).
    Left for twin/backtest.py (P3.6): score against DLH's own forecast, not just persistence.

BUG CAUGHT by the live pull (workflow.md B2c): top-level `lastUpdate` came back
WITH a trailing 'Z' (already UTC) in the live sample, contradicting the earlier
"no tz suffix, assume WIB" note from the three-week-old capture this module was
first built against. `_parse_ts` below handles BOTH cases per-value (checks for
an offset before assuming WIB) rather than assuming one behavior per field --
the API's timestamp convention isn't fully stable across fields/time, so treat
every timestamp on its own merits.

Still unexplored (present in the payload, not yet used): ispuHistory, rawHistory,
weatherHistory, rawMeteoHistory, meteorologyHours, tahunPengadaan, lastMaintenanceAt.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone

import httpx

from .common import dead_letter, db, heartbeat, mark_parsed, utcnow

BASE = "https://udara.jakarta.go.id"
LIST_URL = f"{BASE}/lokasi-spku"
DETAIL_URL_TMPL = f"{BASE}/spku/{{uuid}}"

REQUEST_SPACING_S = 2.0          # WAF is real -- stay gentle (db/SCHEMA.md quirk 3)
STALE_CUTOFF = timedelta(hours=6)  # tuning choice, not a fact -- matches sibling project
WIB_OFFSET = timedelta(hours=7)

# mainland bbox (lon_min, lat_min, lon_max, lat_max) -- excludes Kepulauan Seribu
MAINLAND_BBOX = (106.65, -6.40, 107.00, -6.05)

UUID_RE = re.compile(
    r"/spku/([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)
DETAIL_MARKER = "var SPKU_DETAIL_DATA = "


def _fetch_html(url: str) -> tuple[int, str | None]:
    """Plain-text GET (the SPKU responses are HTML, not JSON -- common.fetch_json
    only parses application/json bodies, so we fetch raw text here)."""
    headers = {"User-Agent": os.environ.get("SCRAPER_USER_AGENT", "JejakUdara-research/0.1")}
    try:
        r = httpx.get(url, headers=headers, timeout=30.0, follow_redirects=True)
        return r.status_code, r.text
    except httpx.HTTPError:
        return 0, None


def discover_station_uuids(html: str) -> list[str]:
    """Stage 1 parse: every /spku/<uuid> occurrence, deduped, order preserved."""
    seen: list[str] = []
    for m in UUID_RE.finditer(html):
        u = m.group(1)
        if u not in seen:
            seen.append(u)
    return seen


def _extract_balanced_json(text: str, marker: str) -> dict | None:
    """Find `marker{...}` and return the parsed object, respecting nested
    braces and string literals (metrics[]/forecast[] nest objects -- a naive
    `\\{.*?\\};` regex truncates on the first inner `}`)."""
    start = text.find(marker)
    if start == -1:
        return None
    i = text.find("{", start)
    if i == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    j = i
    while j < len(text):
        c = text[j]
        if in_string:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_string = False
        else:
            if c == '"':
                in_string = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[i:j + 1])
                    except json.JSONDecodeError:
                        return None
        j += 1
    return None


def _parse_ts(raw: str | None) -> datetime | None:
    """Parse a timestamp to UTC, per-value -- do NOT assume one tz convention
    per field. If the string carries its own offset (e.g. trailing 'Z'),
    respect it. If naive, assume WIB (UTC+7) -- the documented default for
    this API, observed on nested metrics[].history[].time."""
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc)
    return dt.replace(tzinfo=timezone(WIB_OFFSET)).astimezone(timezone.utc)


def _daily_rows(station_id: str, daily: list[dict] | None) -> list[dict]:
    """dailyIspu30Days[] -> historical readings (P0.1c, confirmed shape).
    {date, maxIspu, dominantMetric, concentration} per day, 30 days.
    Historical + already-reported by DLH -> qa_flag='ok' (not the live-staleness check)."""
    rows: list[dict] = []
    for d in daily or []:
        ts = _parse_ts(d.get("date"))
        pollutant = (d.get("dominantMetric") or "").lower()
        if not ts or not pollutant:
            continue
        if d.get("maxIspu") is not None:
            rows.append({"station_id": station_id, "ts": ts, "pollutant": pollutant,
                         "value": d["maxIspu"], "unit": "index", "is_index": True, "qa_flag": "ok"})
        if d.get("concentration") is not None:
            rows.append({"station_id": station_id, "ts": ts, "pollutant": pollutant,
                         "value": d["concentration"], "unit": "ug/m3", "is_index": False,
                         "qa_flag": "ok"})
    return rows


def _history_rows(station_id: str, metrics: list[dict] | None) -> list[dict]:
    """metrics[].history[] -> sub-hourly per-pollutant readings, when present
    (bonus discovery, P0.1c -- opportunistic, not guaranteed on every station)."""
    rows: list[dict] = []
    for m in metrics or []:
        pollutant = (m.get("metricName") or "").lower()
        for h in m.get("history") or []:
            ts = _parse_ts(h.get("time"))
            if not ts or not pollutant or h.get("value") is None:
                continue
            rows.append({"station_id": station_id, "ts": ts, "pollutant": pollutant,
                         "value": h["value"], "unit": "ug/m3", "is_index": False, "qa_flag": "ok"})
    return rows


def parse_detail(payload: dict) -> tuple[dict, list[dict], bool]:
    """Pure function: SPKU_DETAIL_DATA -> (station_row, reading_rows, in_scope).

    in_scope=False for Kepulauan Seribu stations (caller should skip insert).
    """
    lon, lat = payload.get("longitude"), payload.get("latitude")
    in_scope = (
        lon is not None and lat is not None
        and MAINLAND_BBOX[0] <= lon <= MAINLAND_BBOX[2]
        and MAINLAND_BBOX[1] <= lat <= MAINLAND_BBOX[3]
    )

    station = {
        "station_id": payload.get("datasourceKode"),
        "name": payload.get("datasourceName", ""),
        "kind": "reference" if payload.get("type") == "Reference" else "low_cost",
        "lon": lon,
        "lat": lat,
        "meta": {
            "kecamatan": payload.get("kecamatanNama"),
            "kota": payload.get("kotaKabupatenNama"),
        },
    }

    # lastUpdate: per-value tz handling (workflow.md B2c) -- some samples carry
    # 'Z' (already UTC), others are naive (assume WIB). _parse_ts handles both.
    ts_utc = _parse_ts(payload.get("lastUpdate"))
    is_stale = ts_utc is None or (utcnow() - ts_utc) > STALE_CUTOFF

    qa = "stale" if is_stale else "ok"
    rows: list[dict] = []
    if ts_utc and station["station_id"]:
        dominant = (payload.get("ispuParameter") or "").lower() or None
        if dominant and payload.get("ispuValue") is not None:
            rows.append({"station_id": station["station_id"], "ts": ts_utc,
                         "pollutant": dominant, "value": payload["ispuValue"],
                         "unit": "index", "is_index": True, "qa_flag": qa})
        if dominant and payload.get("ispuConcentration") is not None:
            rows.append({"station_id": station["station_id"], "ts": ts_utc,
                         "pollutant": dominant, "value": payload["ispuConcentration"],
                         "unit": "ug/m3", "is_index": False, "qa_flag": qa})
        for m in payload.get("metrics") or []:
            p = (m.get("metricName") or "").lower()
            if not p:
                continue
            if m.get("currentIspu") is not None:
                rows.append({"station_id": station["station_id"], "ts": ts_utc,
                             "pollutant": p, "value": m["currentIspu"],
                             "unit": "index", "is_index": True, "qa_flag": qa})
            if m.get("currentRaw") is not None:  # null in the FIRST sample seen, populated in later ones
                rows.append({"station_id": station["station_id"], "ts": ts_utc,
                             "pollutant": p, "value": m["currentRaw"],
                             "unit": "ug/m3", "is_index": False, "qa_flag": qa})

    if station["station_id"]:
        rows.extend(_daily_rows(station["station_id"], payload.get("dailyIspu30Days")))
        rows.extend(_history_rows(station["station_id"], payload.get("metrics")))

    return station, rows, in_scope


def poll_all() -> None:
    status, html = _fetch_html(LIST_URL)
    raw_id = dead_letter("spku", LIST_URL, status, {"html_len": len(html or "")},
                         parsed_ok=bool(html))
    if status != 200 or not html:
        mark_parsed(raw_id, False, f"http {status}")
        heartbeat("spku", ok=False, error=f"list page http {status}")
        return
    uuids = discover_station_uuids(html)
    mark_parsed(raw_id, True)
    if not uuids:
        heartbeat("spku", ok=False, error="0 stations discovered -- portal structure may have changed")
        return

    total_readings = 0
    total_skipped_offshore = 0
    for uuid in uuids:
        url = DETAIL_URL_TMPL.format(uuid=uuid)
        d_status, d_html = _fetch_html(url)
        d_raw_id = dead_letter("spku", url, d_status, {"html_len": len(d_html or "")})
        if d_status != 200 or not d_html:
            mark_parsed(d_raw_id, False, f"http {d_status}")
            time.sleep(REQUEST_SPACING_S)
            continue
        payload = _extract_balanced_json(d_html, DETAIL_MARKER)
        if payload is None:
            mark_parsed(d_raw_id, False, "SPKU_DETAIL_DATA not found/unbalanced")
            time.sleep(REQUEST_SPACING_S)
            continue
        try:
            station, rows, in_scope = parse_detail(payload)
        except Exception as exc:
            mark_parsed(d_raw_id, False, repr(exc))
            time.sleep(REQUEST_SPACING_S)
            continue
        mark_parsed(d_raw_id, True)

        if not in_scope or not station["station_id"]:
            total_skipped_offshore += 1
            time.sleep(REQUEST_SPACING_S)
            continue

        with db() as conn:
            conn.execute(
                """INSERT INTO stations (station_id, name, kind, geom, meta)
                   VALUES (%s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s)
                   ON CONFLICT (station_id) DO UPDATE
                   SET name = EXCLUDED.name, kind = EXCLUDED.kind,
                       geom = EXCLUDED.geom, meta = EXCLUDED.meta""",
                (station["station_id"], station["name"], station["kind"],
                 station["lon"], station["lat"], json.dumps(station["meta"])),
            )
            for r in rows:
                conn.execute(
                    """INSERT INTO readings (station_id, ts, pollutant, value, unit, is_index, qa_flag)
                       VALUES (%(station_id)s, %(ts)s, %(pollutant)s, %(value)s,
                               %(unit)s, %(is_index)s, %(qa_flag)s)
                       ON CONFLICT (station_id, ts, pollutant, is_index) DO NOTHING""",
                    r,
                )
        total_readings += len(rows)
        time.sleep(REQUEST_SPACING_S)

    heartbeat("spku", ok=True, rows=total_readings)
    print(f"spku: {len(uuids)} stations discovered, {total_readings} readings, "
          f"{total_skipped_offshore} excluded (offshore/missing id)")


if __name__ == "__main__":
    poll_all()
