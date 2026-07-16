"""SPKU parser tests on a fixture mirroring the live-verified payload shape
(2026-07-16 live pull, workflow.md B2c) -- including the timestamp-tz bug fix
and the two P0.1c discoveries (dailyIspu30Days, metrics[].history[])."""
from ingest.spku import parse_detail

FIXTURE = {
    "datasourceKode": "DKI_PM25_64", "datasourceName": "Test Station",
    "type": "Sensor", "kecamatanNama": "Test", "kotaKabupatenNama": "Test",
    "latitude": -6.1647214778, "longitude": 106.8453837867,   # mainland
    "lastUpdate": "2026-07-16T03:00:00Z",                      # HAS 'Z' -- the bug this fixes
    "ispuValue": 64, "ispuCategory": "Sedang",
    "ispuParameter": "PM25", "ispuConcentration": 25.44,
    "metrics": [{
        "metricID": 6, "metricName": "PM25", "parameterName": "Particulate Matter 2.5",
        "currentIspu": 64, "currentRaw": 32.99,
        "history": [
            {"time": "2026-07-16T08:00:00", "value": 23.71},   # naive -- WIB assumed
            {"time": "2026-07-16T08:30:00", "value": 25.35},
        ],
    }],
    "dailyIspu30Days": [
        {"date": "2026-06-17T00:00:00Z", "maxIspu": 0, "dominantMetric": "PM25", "concentration": 46.08},
        {"date": "2026-07-16T00:00:00Z", "maxIspu": 69, "dominantMetric": "PM25", "concentration": 42.54},
    ],
    "forecast": [{"label": "H+1", "date": "17 Juli 2026", "icon": "cloud-rain",
                 "ispu": 121, "category": "Tidak Sehat"}],
}

OFFSHORE_FIXTURE = {**FIXTURE, "datasourceKode": "LCS-14", "latitude": -5.7454, "longitude": 106.6127}


def test_z_suffixed_timestamp_treated_as_utc_not_wib():
    """The bug this fixes: 'Z' means already-UTC. Wrongly applying a WIB
    offset on top would shift the timestamp 7h into the future."""
    station, rows, in_scope = parse_detail(FIXTURE)
    assert in_scope
    dominant = [r for r in rows if r["pollutant"] == "pm25" and r["is_index"] and r["value"] == 64]
    assert dominant, "expected the dominant ISPU row"
    assert dominant[0]["ts"].hour == 3, f"expected 03:00 UTC (Z respected), got {dominant[0]['ts']}"


def test_naive_nested_timestamp_assumed_wib():
    _, rows, _ = parse_detail(FIXTURE)
    hist = [r for r in rows if r["value"] == 23.71]
    assert hist, "expected a history row"
    # 08:00 WIB (UTC+7) -> 01:00 UTC
    assert hist[0]["ts"].hour == 1


def test_daily_bootstrap_rows_present():
    _, rows, _ = parse_detail(FIXTURE)
    daily = [r for r in rows if r["value"] in (0, 46.08, 69, 42.54)]
    assert len(daily) == 4, "2 days x (maxIspu + concentration) = 4 rows"


def test_history_rows_present_when_populated():
    _, rows, _ = parse_detail(FIXTURE)
    hist_values = {r["value"] for r in rows if r["unit"] == "ug/m3" and r["value"] in (23.71, 25.35)}
    assert hist_values == {23.71, 25.35}


def test_offshore_station_flagged_out_of_scope():
    _, _, in_scope = parse_detail(OFFSHORE_FIXTURE)
    assert not in_scope


def test_readings_pk_distinguishes_index_from_concentration():
    """The schema fix this pull motivated: same pollutant+ts, two rows, one
    is_index=True (64) and one is_index=False (25.44) -- both must survive."""
    _, rows, _ = parse_detail(FIXTURE)
    dominant_rows = [r for r in rows if r["value"] in (64, 25.44)]
    assert {r["is_index"] for r in dominant_rows} == {True, False}
