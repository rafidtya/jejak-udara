"""One-time static loads: adm4 kelurahan codes, OSM roads/landuse (P1.4).

`--load-centroids` (PREFERRED): loads `adm4_code,name,lat,lon` directly from
D:\\Jalan.in\\data\\bmkg\\jakarta_zone_centroids.csv (267 rows, already includes
lon/lat -- no need to wait for a first live BMKG poll to populate geometry).

`--load-adm4` (fallback): parses the Kemendagri mirror SQL dump (cahyadsn/wilayah)
for codes+names only; geometry gets filled in later by ingest/bmkg.py's first poll.
Download: https://raw.githubusercontent.com/cahyadsn/wilayah/master/db/wilayah.sql
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

from .common import db

ADM4_RE = re.compile(r"\('(31\.\d{2}\.\d{2}\.\d{4})','([^']+)'\)")

# CSV is vendored into the repo (db/fixtures/) so the loader is machine-portable;
# original source: D:\Jalan.in\data\bmkg\jakarta_zone_centroids.csv (sibling project)
DEFAULT_CENTROIDS_CSV = Path(__file__).resolve().parent.parent / "db" / "fixtures" / "jakarta_zone_centroids.csv"


def load_centroids_csv(csv_path: Path) -> int:
    n = 0
    with open(csv_path, encoding="utf-8", newline="") as f, db() as conn:
        for row in csv.DictReader(f):
            conn.execute(
                """INSERT INTO kelurahan (adm4_code, name, geom_centroid)
                   VALUES (%s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                   ON CONFLICT (adm4_code) DO UPDATE
                   SET name = EXCLUDED.name, geom_centroid = EXCLUDED.geom_centroid""",
                (row["adm4_code"], row["name"], row["lon"], row["lat"]),
            )
            n += 1
    return n


def load_adm4(sql_path: Path) -> int:
    text = sql_path.read_text(encoding="utf-8", errors="ignore")
    pairs = ADM4_RE.findall(text)
    with db() as conn:
        for code, name in pairs:
            conn.execute(
                """INSERT INTO kelurahan (adm4_code, name)
                   VALUES (%s, %s) ON CONFLICT (adm4_code) DO NOTHING""",
                (code, name),
            )
    return len(pairs)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--load-centroids", action="store_true",
                    help="preferred: load pre-extracted lon/lat centroids directly")
    ap.add_argument("--centroids-csv", type=Path, default=DEFAULT_CENTROIDS_CSV)
    ap.add_argument("--load-adm4", action="store_true", help="fallback: codes/names only")
    ap.add_argument("--wilayah-sql", type=Path, default=Path("data/wilayah.sql"))
    args = ap.parse_args()
    if args.load_centroids:
        if not args.centroids_csv.exists():
            raise SystemExit(f"{args.centroids_csv} not found")
        n = load_centroids_csv(args.centroids_csv)
        print(f"loaded {n} Jakarta kelurahan centroids (with geometry)")
    elif args.load_adm4:
        if not args.wilayah_sql.exists():
            raise SystemExit(
                f"{args.wilayah_sql} not found — download wilayah.sql first (see docstring)"
            )
        n = load_adm4(args.wilayah_sql)
        print(f"loaded {n} Jakarta adm4 rows (codes/names only, no geometry yet)")


if __name__ == "__main__":
    main()
