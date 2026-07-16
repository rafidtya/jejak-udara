"""Track A: precompute REAL what-if scenarios with the tested Gaussian plume
engine (twin/plume.py + twin/scenarios.py) -> web/public/fixtures/scenarios.json.

Demo framing (honest): source locations are ILLUSTRATIVE (anchored to the highest
real ISPU readings in the frozen snapshot); the physics + deltas are the real
engine's output. Wind is a fixed labeled example condition, not live.
"""
from __future__ import annotations

import json

import numpy as np

from scripts.demo_common import BBOX, FIXTURES_DIR, bbox_metric, load_stations, project, unproject
from analytics.layer_b_hotspot import grid_over_bbox
from twin.plume import Met, Source
from twin.scenarios import whatif

CELL_M = 500.0
MET = Met(wd_deg=270.0, ws=3.0, tcc=60.0, is_day=True)  # contoh: angin baratan 3 m/s
BACKGROUND = 18.0  # ug/m3 -- plausible regional background for the demo


def demo_sources() -> list[Source]:
    """Anchor 3 illustrative sources at the worst real (non-stale) readings."""
    stations = sorted(
        (s for s in load_stations() if not s["stale"] and s["ispu"] is not None),
        key=lambda s: -s["ispu"],
    )
    labels = ["lalu_lintas", "industri", "pembakaran"]
    strengths = [120.0, 90.0, 60.0]
    out = []
    for st, label, q in zip(stations[:3], labels, strengths):
        x, y = project(st["lon"], st["lat"])
        out.append(Source(x=x, y=y, q=q, label=label))
    return out


SCENARIOS = [
    {"id": "baseline", "title": "Kondisi saat ini (baseline)", "diff": {}},
    {"id": "industri_off", "title": "Bagaimana jika: sumber industri dihentikan",
     "diff": {"disable": ["industri"]}},
    {"id": "lalin_50", "title": "Bagaimana jika: lalu lintas dikurangi 50%",
     "diff": {"scale": {"lalu_lintas": 0.5}}},
    {"id": "hujan_5mm", "title": "Bagaimana jika: hujan 5 mm (washout)",
     "diff": {"rain_mm": 5.0}},
]


def main() -> None:
    sources = demo_sources()
    grid_xy, shape = grid_over_bbox(bbox_metric(), cell_m=CELL_M)

    results = []
    for sc in SCENARIOS:
        r = whatif(sources, MET, np.asarray(grid_xy), shape, sc["diff"],
                   background=BACKGROUND)
        after = np.asarray(r["after"])
        results.append({
            "id": sc["id"], "title": sc["title"],
            "delta_mean_pct": r["delta_mean_pct"],
            "values": [round(float(x), 2) for x in after.ravel()],
        })

    out = {
        "bbox": list(BBOX), "nrows": shape[0], "ncols": shape[1], "cell_m": CELL_M,
        "met": {"wd_deg": MET.wd_deg, "ws": MET.ws,
                "label": "Contoh kondisi: angin baratan 3 m/s (bukan data live)"},
        "background_ugm3": BACKGROUND,
        "sources": [dict(zip(("lon", "lat"), unproject(s.x, s.y)),
                         label=s.label, q=s.q) for s in sources],
        "scenarios": results,
        "disclaimer": ("Simulasi Gaussian plume (mesin asli proyek, hasil pra-komputasi). "
                       "Lokasi sumber bersifat ilustratif untuk demo; fisika dan delta nyata. "
                       "Lihat twin/ASSUMPTIONS.md."),
    }
    (FIXTURES_DIR / "scenarios.json").write_text(json.dumps(out), encoding="utf-8")
    for r in results:
        print(f"{r['id']}: delta_mean={r['delta_mean_pct']}%")
    print(f"scenarios.json written ({shape[0]}x{shape[1]} grid x {len(results)} scenarios)")


if __name__ == "__main__":
    main()
