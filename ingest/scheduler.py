"""APScheduler process wiring all pollers (plan.md P1 cadences).

Cadences: SPKU hourly (once P0.1 unblocks) | BMKG 2x daily (matches refresh)
| FIRMS daily | satellite daily | CAMS daily.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from . import bmkg, firms, spku

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")


def prune_raw_payloads() -> None:
    """Retention: successfully-parsed raw payloads older than 14 days are prunable
    (their data lives in readings/weather_forecasts). Failures are kept forever --
    they're the evidence needed to fix parsers retroactively. Keeps a 2GB/40GB VPS
    comfortable indefinitely."""
    from .common import db

    with db() as conn:
        conn.execute(
            "DELETE FROM raw_payloads WHERE parsed_ok AND fetched_at < now() - interval '14 days'"
        )


def main() -> None:
    sched = BlockingScheduler(timezone="UTC")
    sched.add_job(spku.poll_all, "cron", minute=5, id="spku_hourly")
    sched.add_job(bmkg.poll_all, "cron", hour="1,13", minute=10, id="bmkg_2x")
    sched.add_job(firms.poll, "cron", hour=2, minute=30, id="firms_daily")
    sched.add_job(prune_raw_payloads, "cron", hour=3, minute=0, id="prune_daily")
    # satellite + cams jobs registered once P0.3b credentials exist:
    # sched.add_job(satellite.poll_all, "cron", hour=6, id="satellite_daily")
    # sched.add_job(cams.poll, "cron", hour=5, id="cams_daily")
    logging.info("pollers scheduled — Ctrl+C to stop")
    sched.start()


if __name__ == "__main__":
    main()
