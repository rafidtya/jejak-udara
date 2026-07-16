"""Shared ingest utilities: DB access, polite HTTP, dead-letter, heartbeat.

Boundary rule (agents.md §2): only ingest/ touches the network.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import httpx
import psycopg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://jejakudara:jejakudara@localhost:5432/jejakudara"
)
USER_AGENT = os.environ.get("SCRAPER_USER_AGENT", "JejakUdara-research/0.1")


def db() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL, autocommit=True)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def fetch_json(url: str, *, timeout: float = 30.0, params: dict | None = None) -> tuple[int, Any]:
    """Polite GET returning (status, parsed_json_or_None). Never raises on HTTP errors."""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    try:
        r = httpx.get(url, params=params, headers=headers, timeout=timeout, follow_redirects=False)
        body: Any = None
        if r.headers.get("content-type", "").startswith("application/json"):
            body = r.json()
        return r.status_code, body
    except httpx.HTTPError as exc:  # network-level failure
        return 0, {"_error": str(exc)}


def dead_letter(source: str, url: str, status: int, payload: Any,
                parsed_ok: bool = False, parse_error: str | None = None) -> int:
    """Store the raw payload BEFORE parsing (workflow.md C: parser fixes must be retroactive)."""
    with db() as conn:
        row = conn.execute(
            """INSERT INTO raw_payloads (source, url, http_status, payload, parsed_ok, parse_error)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
            (source, url, status, json.dumps(payload, default=str), parsed_ok, parse_error),
        ).fetchone()
        return row[0]


def mark_parsed(raw_id: int, ok: bool, error: str | None = None) -> None:
    with db() as conn:
        conn.execute(
            "UPDATE raw_payloads SET parsed_ok=%s, parse_error=%s WHERE id=%s",
            (ok, error, raw_id),
        )


def heartbeat(source: str, *, ok: bool, error: str | None = None, rows: int = 0) -> None:
    with db() as conn:
        if ok:
            conn.execute(
                """INSERT INTO ingest_heartbeat (source, last_success, rows_24h)
                   VALUES (%s, now(), %s)
                   ON CONFLICT (source) DO UPDATE
                   SET last_success = now(),
                       rows_24h = ingest_heartbeat.rows_24h + EXCLUDED.rows_24h""",
                (source, rows),
            )
        else:
            conn.execute(
                """INSERT INTO ingest_heartbeat (source, last_error, error_msg)
                   VALUES (%s, now(), %s)
                   ON CONFLICT (source) DO UPDATE
                   SET last_error = now(), error_msg = EXCLUDED.error_msg""",
                (source, error),
            )
