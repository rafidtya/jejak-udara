"""BMKG parser test on a fixture mirroring the VERIFIED response shape
(nested per-day cuaca arrays — the #1 parse gotcha, workflow.md B3)."""
from ingest.bmkg import parse_run

FIXTURE = {
    "lokasi": {
        "adm4": "31.71.03.1001", "desa": "Kemayoran",
        "lon": 106.8453837867, "lat": -6.1647214778,
    },
    "data": [{
        "cuaca": [
            [  # day 1
                {"utc_datetime": "2026-06-25 09:00:00", "wd_deg": 280, "ws": 2.7,
                 "hu": 69, "t": 29, "tcc": 100, "tp": 0,
                 "analysis_date": "2026-06-25T00:00:00"},
                {"utc_datetime": "2026-06-25 12:00:00", "wd_deg": 300, "ws": 3.1,
                 "hu": 72, "t": 28, "tcc": 90, "tp": 0.4,
                 "analysis_date": "2026-06-25T00:00:00"},
            ],
            [  # day 2
                {"utc_datetime": "2026-06-26 09:00:00", "wd_deg": 250, "ws": 2.0,
                 "hu": 65, "t": 30, "tcc": 40, "tp": 0,
                 "analysis_date": "2026-06-25T00:00:00"},
            ],
        ],
    }],
}


def test_parse_flattens_nested_days():
    meta, rows = parse_run(FIXTURE)
    assert meta["adm4_code"] == "31.71.03.1001"
    assert meta["lat"] == -6.1647214778
    assert len(rows) == 3            # 2 + 1 across nested day arrays
    assert rows[0]["wd_deg"] == 280
    assert rows[2]["tp"] == 0


def test_parse_tolerates_empty():
    meta, rows = parse_run({})
    assert meta is None and rows == []
