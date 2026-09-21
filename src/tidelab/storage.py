from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
from typing import Any, Iterable, Iterator

from tidelab.domain import Instrument, MarketEvent, canonical_json, isoformat_utc, parse_utc, utc_now


@dataclass(frozen=True)
class InsertResult:
    inserted: int
    duplicates: int


@dataclass(frozen=True)
class HourlyReport:
    venue: str
    instrument_id: str
    start: str
    end: str
    expected_bars: int
    stored_bars: int
    missing_bars: tuple[str, ...]
    duplicate_attempts: int
    incomplete_skipped: int
    latest_close: str | None
    freshness_seconds: int | None
    stale: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "venue": self.venue,
            "instrument_id": self.instrument_id,
            "start": self.start,
            "end": self.end,
            "expected_bars": self.expected_bars,
            "stored_bars": self.stored_bars,
            "missing_bars": list(self.missing_bars),
            "duplicate_attempts": self.duplicate_attempts,
            "incomplete_skipped": self.incomplete_skipped,
            "latest_close": self.latest_close,
            "freshness_seconds": self.freshness_seconds,
            "stale": self.stale,
        }


class TideStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_info (
                    schema_version INTEGER PRIMARY KEY,
                    applied_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS instruments (
                    instrument_id TEXT PRIMARY KEY,
                    schema_version INTEGER NOT NULL,
                    venue TEXT NOT NULL,
                    venue_instrument_id TEXT NOT NULL,
                    product_class TEXT NOT NULL,
                    base_asset TEXT NOT NULL,
                    quote_asset TEXT NOT NULL,
                    base_increment TEXT NOT NULL,
                    quote_increment TEXT NOT NULL,
                    base_min_size TEXT NOT NULL,
                    quote_min_size TEXT NOT NULL,
                    status TEXT NOT NULL,
                    fetched_at_utc TEXT NOT NULL,
                    capabilities_json TEXT NOT NULL,
                    native_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS market_events (
                    event_id TEXT PRIMARY KEY,
                    schema_version INTEGER NOT NULL,
                    venue TEXT NOT NULL,
                    instrument_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_time_utc TEXT NOT NULL,
                    received_at_utc TEXT NOT NULL,
                    source TEXT NOT NULL,
                    interval_seconds INTEGER,
                    closed INTEGER NOT NULL CHECK (closed IN (0, 1)),
                    payload_json TEXT NOT NULL,
                    native_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS market_events_lookup
                ON market_events (venue, instrument_id, event_type, interval_seconds, event_time_utc);

                CREATE TABLE IF NOT EXISTS ingestion_runs (
                    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    venue TEXT NOT NULL,
                    instrument_id TEXT NOT NULL,
                    requested_start_utc TEXT,
                    requested_end_utc TEXT,
                    started_at_utc TEXT NOT NULL,
                    finished_at_utc TEXT,
                    fetched INTEGER NOT NULL DEFAULT 0,
                    inserted INTEGER NOT NULL DEFAULT 0,
                    duplicate_attempts INTEGER NOT NULL DEFAULT 0,
                    incomplete_skipped INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    error TEXT
                );

                CREATE TABLE IF NOT EXISTS stream_sessions (
                    session_id TEXT PRIMARY KEY,
                    venue TEXT NOT NULL,
                    instrument_id TEXT NOT NULL,
                    started_at_utc TEXT NOT NULL,
                    finished_at_utc TEXT,
                    status TEXT NOT NULL,
                    message_count INTEGER NOT NULL DEFAULT 0,
                    sequence_gap_count INTEGER NOT NULL DEFAULT 0,
                    error TEXT
                );

                CREATE TABLE IF NOT EXISTS stream_messages (
                    observation_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES stream_sessions(session_id),
                    channel TEXT NOT NULL,
                    sequence_num INTEGER,
                    message_time_utc TEXT,
                    received_at_utc TEXT NOT NULL,
                    native_json TEXT NOT NULL
                );
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_info(schema_version, applied_at_utc) VALUES (?, ?)",
                (1, isoformat_utc(utc_now())),
            )

    def upsert_instrument(self, instrument: Instrument) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO instruments (
                    instrument_id, schema_version, venue, venue_instrument_id, product_class,
                    base_asset, quote_asset, base_increment, quote_increment, base_min_size,
                    quote_min_size, status, fetched_at_utc, capabilities_json, native_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(instrument_id) DO UPDATE SET
                    schema_version=excluded.schema_version,
                    product_class=excluded.product_class,
                    base_asset=excluded.base_asset,
                    quote_asset=excluded.quote_asset,
                    base_increment=excluded.base_increment,
                    quote_increment=excluded.quote_increment,
                    base_min_size=excluded.base_min_size,
                    quote_min_size=excluded.quote_min_size,
                    status=excluded.status,
                    fetched_at_utc=excluded.fetched_at_utc,
                    capabilities_json=excluded.capabilities_json,
                    native_json=excluded.native_json
                """,
                (
                    instrument.instrument_id,
                    instrument.schema_version,
                    instrument.venue,
                    instrument.venue_instrument_id,
                    instrument.product_class,
                    instrument.base_asset,
                    instrument.quote_asset,
                    instrument.base_increment,
                    instrument.quote_increment,
                    instrument.base_min_size,
                    instrument.quote_min_size,
                    instrument.status,
                    isoformat_utc(instrument.fetched_at),
                    canonical_json(instrument.capabilities.as_dict()),
                    canonical_json(dict(instrument.native)),
                ),
            )

    def insert_events(self, events: Iterable[MarketEvent]) -> InsertResult:
        inserted = 0
        duplicates = 0
        with self.connect() as connection:
            for event in events:
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO market_events (
                        event_id, schema_version, venue, instrument_id, event_type,
                        event_time_utc, received_at_utc, source, interval_seconds, closed,
                        payload_json, native_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event.schema_version,
                        event.venue,
                        event.instrument_id,
                        event.event_type,
                        isoformat_utc(event.event_time),
                        isoformat_utc(event.received_at),
                        event.source,
                        event.interval_seconds,
                        int(event.closed),
                        canonical_json(dict(event.payload)),
                        canonical_json(dict(event.native)),
                    ),
                )
                if cursor.rowcount == 1:
                    inserted += 1
                else:
                    duplicates += 1
        return InsertResult(inserted=inserted, duplicates=duplicates)

    def start_ingestion_run(
        self,
        source: str,
        venue: str,
        instrument_id: str,
        start: datetime | None,
        end: datetime | None,
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO ingestion_runs (
                    source, venue, instrument_id, requested_start_utc, requested_end_utc,
                    started_at_utc, status
                ) VALUES (?, ?, ?, ?, ?, ?, 'running')
                """,
                (
                    source,
                    venue,
                    instrument_id,
                    isoformat_utc(start) if start else None,
                    isoformat_utc(end) if end else None,
                    isoformat_utc(utc_now()),
                ),
            )
            return int(cursor.lastrowid)

    def finish_ingestion_run(
        self,
        run_id: int,
        *,
        fetched: int,
        inserted: int,
        duplicate_attempts: int,
        incomplete_skipped: int,
        status: str,
        error: str | None = None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE ingestion_runs SET
                    finished_at_utc=?, fetched=?, inserted=?, duplicate_attempts=?,
                    incomplete_skipped=?, status=?, error=?
                WHERE run_id=?
                """,
                (
                    isoformat_utc(utc_now()),
                    fetched,
                    inserted,
                    duplicate_attempts,
                    incomplete_skipped,
                    status,
                    error,
                    run_id,
                ),
            )

    def start_stream_session(self, session_id: str, venue: str, instrument_id: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO stream_sessions (
                    session_id, venue, instrument_id, started_at_utc, status
                ) VALUES (?, ?, ?, ?, 'running')
                """,
                (session_id, venue, instrument_id, isoformat_utc(utc_now())),
            )

    def insert_stream_message(
        self,
        *,
        observation_id: str,
        session_id: str,
        channel: str,
        sequence_num: int | None,
        message_time: str | None,
        received_at: datetime,
        native: dict[str, Any],
    ) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO stream_messages (
                    observation_id, session_id, channel, sequence_num, message_time_utc,
                    received_at_utc, native_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    observation_id,
                    session_id,
                    channel,
                    sequence_num,
                    message_time,
                    isoformat_utc(received_at),
                    canonical_json(native),
                ),
            )
            return cursor.rowcount == 1

    def finish_stream_session(
        self,
        session_id: str,
        *,
        status: str,
        message_count: int,
        sequence_gap_count: int,
        error: str | None = None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE stream_sessions SET
                    finished_at_utc=?, status=?, message_count=?, sequence_gap_count=?, error=?
                WHERE session_id=?
                """,
                (
                    isoformat_utc(utc_now()),
                    status,
                    message_count,
                    sequence_gap_count,
                    error,
                    session_id,
                ),
            )

    def hourly_report(
        self,
        *,
        venue: str,
        instrument_id: str,
        start: datetime,
        end: datetime,
        stale_after_seconds: int,
        now: datetime | None = None,
    ) -> HourlyReport:
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("report bounds must be timezone-aware")
        if end <= start:
            raise ValueError("report end must be after start")
        now = (now or utc_now()).astimezone(timezone.utc)
        start = start.astimezone(timezone.utc)
        end = end.astimezone(timezone.utc)

        expected: list[datetime] = []
        cursor = start
        while cursor < end:
            expected.append(cursor)
            cursor += timedelta(hours=1)

        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT event_time_utc FROM market_events
                WHERE venue=? AND instrument_id=? AND event_type='bar'
                  AND interval_seconds=3600 AND closed=1
                  AND event_time_utc>=? AND event_time_utc<?
                ORDER BY event_time_utc
                """,
                (venue, instrument_id, isoformat_utc(start), isoformat_utc(end)),
            ).fetchall()
            totals = connection.execute(
                """
                SELECT
                    COALESCE(SUM(duplicate_attempts), 0) AS duplicate_attempts,
                    COALESCE(SUM(incomplete_skipped), 0) AS incomplete_skipped
                FROM ingestion_runs
                WHERE venue=? AND instrument_id=? AND status='complete'
                  AND requested_start_utc=? AND requested_end_utc=?
                """,
                (venue, instrument_id, isoformat_utc(start), isoformat_utc(end)),
            ).fetchone()

        stored = {parse_utc(row["event_time_utc"]) for row in rows}
        missing = tuple(isoformat_utc(slot) for slot in expected if slot not in stored)
        latest_start = max(stored) if stored else None
        latest_close_dt = latest_start + timedelta(hours=1) if latest_start else None
        freshness = max(0, int((now - latest_close_dt).total_seconds())) if latest_close_dt else None
        stale = freshness is None or freshness > stale_after_seconds

        return HourlyReport(
            venue=venue,
            instrument_id=instrument_id,
            start=isoformat_utc(start),
            end=isoformat_utc(end),
            expected_bars=len(expected),
            stored_bars=len(stored),
            missing_bars=missing,
            duplicate_attempts=int(totals["duplicate_attempts"]),
            incomplete_skipped=int(totals["incomplete_skipped"]),
            latest_close=isoformat_utc(latest_close_dt) if latest_close_dt else None,
            freshness_seconds=freshness,
            stale=stale,
        )
