"""Track A: freeze a REAL SPKU snapshot into demo fixtures (no DB needed).

Reuses the tested pure parsers from ingest/spku.py. Gentle scrape (2s spacing,
honest UA) -- same WAF discipline as the production poller. Output:

  web/public/fixtures/stations.json   -- one entry per mainland station:
      {station_id, name, kind, lon, lat, kecamatan, kota,
       ispu, category, parameter, concentration, last_update_utc, stale,
       daily30: [{date, ispu, conc}]}
  web/public/fixtures/meta.json       -- {captured_at_utc, station_count, source}

Run:  python -m scripts.build_fixtures          (from jejakudara/)
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingest.spku import (  # noqa: E402  (path bootstrap above)
    DETAIL_MARKER, DETAIL_URL_TMPL, LIST_URL,
    _extract_balanced_json, _fetch_html, _parse_ts, discover_station_uuids,
    MAINLAND_BBOX, STALE_CUTOFF,
)

OUT_DIR = Path(__file__).resolve().parent.parent / "web" / "public" / "fixtures"
SPACING_S = 2.0


def station_fixture(payload: dict) -> dict | None:
    lon, lat = payload.get("longitude"), payload.get("latitude")
    if lon is None or lat is None:
        return None
    if not (MAINLAND_BBOX[0] <= lon <= MAINLAND_BBOX[2]
            and MAINLAND_BBOX[1] <= lat <= MAINLAND_BBOX[3]):
        return None  # Kepulauan Seribu / out of scope
    kode = payload.get("datasourceKode")
    if not kode:
        return None

    ts = _parse_ts(payload.get("lastUpdate"))
    now = datetime.now(timezone.utc)
    stale = ts is None or (now - ts) > STALE_CUTOFF

    daily30 = []
    for d in payload.get("dailyIspu30Days") or []:
        dts = _parse_ts(d.get("date"))
        if not dts:
            continue
        daily30.append({
            "date": dts.date().isoformat(),
            "ispu": d.get("maxIspu"),
            "conc": d.get("concentration"),
        })

    return {
        "station_id": kode,
        "name": payload.get("datasourceName", ""),
        "kind": "reference" if payload.get("type") == "Reference" else "low_cost",
        "lon": lon, "lat": lat,
        "kecamatan": payload.get("kecamatanNama"),
        "kota": payload.get("kotaKabupatenNama"),
        "ispu": payload.get("ispuValue"),
        "category": payload.get("ispuCategory"),
        "parameter": payload.get("ispuParameter"),
        "concentration": payload.get("ispuConcentration"),
        "last_update_utc": ts.isoformat() if ts else None,
        "stale": stale,
        "daily30": daily30,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    status, html = _fetch_html(LIST_URL)
    if status != 200 or not html:
        raise SystemExit(f"list page failed: http {status}")
    uuids = discover_station_uuids(html)
    print(f"discovered {len(uuids)} station pages", flush=True)

    stations: list[dict] = []
    failures = 0
    for n, uuid in enumerate(uuids, 1):
        time.sleep(SPACING_S)
        d_status, d_html = _fetch_html(DETAIL_URL_TMPL.format(uuid=uuid))
        if d_status != 200 or not d_html:
            failures += 1
            print(f"[{n}/{len(uuids)}] http {d_status} -- skipped", flush=True)
            continue
        payload = _extract_balanced_json(d_html, DETAIL_MARKER)
        if payload is None:
            failures += 1
            print(f"[{n}/{len(uuids)}] no SPKU_DETAIL_DATA -- skipped", flush=True)
            continue
        fx = station_fixture(payload)
        if fx:
            stations.append(fx)
            print(f"[{n}/{len(uuids)}] {fx['station_id']}: ispu={fx['ispu']} "
                  f"stale={fx['stale']}", flush=True)
        else:
            print(f"[{n}/{len(uuids)}] out-of-scope/incomplete -- skipped", flush=True)

    stations.sort(key=lambda s: s["station_id"])
    (OUT_DIR / "stations.json").write_text(
        json.dumps(stations, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / "meta.json").write_text(json.dumps({
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "station_count": len(stations),
        "failures": failures,
        "source": "udara.jakarta.go.id (DLH DKI Jakarta) -- frozen snapshot for demo",
    }, ensure_ascii=False), encoding="utf-8")
    print(f"DONE: {len(stations)} stations written, {failures} failures", flush=True)


if __name__ == "__main__":
    main()
