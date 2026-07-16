"""`make status` — ingestion heartbeat & gap report (plan.md P1.5).

The #1 project risk is a silently-dead scraper: history can't be re-scraped.
"""
from __future__ import annotations

from .common import db


def main() -> None:
    with db() as conn:
        rows = conn.execute(
            """SELECT source, last_success, last_error, error_msg, rows_24h
               FROM ingest_heartbeat ORDER BY source"""
        ).fetchall()
    if not rows:
        print("no heartbeats yet — have the pollers ever run?")
        return
    print(f"{'source':<12}{'last_success':<28}{'rows_24h':<10}last_error / msg")
    for source, ok_ts, err_ts, msg, rows_24h in rows:
        warn = " ⚠" if (ok_ts is None or (err_ts and ok_ts and err_ts > ok_ts)) else ""
        print(f"{source:<12}{str(ok_ts):<28}{rows_24h or 0:<10}{err_ts or ''} {msg or ''}{warn}")


if __name__ == "__main__":
    main()
