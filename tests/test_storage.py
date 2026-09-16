from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from tidelab.domain import MarketEvent
from tidelab.storage import TideStore


def bar(hour: int) -> MarketEvent:
    timestamp = datetime(2026, 9, 15, hour, tzinfo=timezone.utc)
    return MarketEvent(
        venue="coinbase_advanced",
        instrument_id="coinbase_advanced:BTC-USD",
        event_type="bar",
        event_time=timestamp,
        received_at=timestamp + timedelta(hours=2),
        source="coinbase.public_rest.candles",
        interval_seconds=3600,
        closed=True,
        payload={"open": "1", "high": "1", "low": "1", "close": "1", "volume": "1"},
        native={"start": str(int(timestamp.timestamp()))},
        source_key=f"ONE_HOUR:{int(timestamp.timestamp())}",
    )


def test_restart_is_idempotent_and_report_finds_gap(tmp_path: Path) -> None:
    store = TideStore(tmp_path / "tidelab.sqlite3")
    store.initialize()
    first_run = store.start_ingestion_run(
        "fixture",
        "coinbase_advanced",
        "coinbase_advanced:BTC-USD",
        datetime(2026, 9, 15, 10, tzinfo=timezone.utc),
        datetime(2026, 9, 15, 13, tzinfo=timezone.utc),
    )
    first = store.insert_events([bar(10), bar(12)])
    store.finish_ingestion_run(
        first_run,
        fetched=2,
        inserted=first.inserted,
        duplicate_attempts=first.duplicates,
        incomplete_skipped=0,
        status="complete",
    )

    second_run = store.start_ingestion_run(
        "fixture",
        "coinbase_advanced",
        "coinbase_advanced:BTC-USD",
        datetime(2026, 9, 15, 10, tzinfo=timezone.utc),
        datetime(2026, 9, 15, 13, tzinfo=timezone.utc),
    )
    second = store.insert_events([bar(10), bar(12)])
    store.finish_ingestion_run(
        second_run,
        fetched=2,
        inserted=second.inserted,
        duplicate_attempts=second.duplicates,
        incomplete_skipped=0,
        status="complete",
    )

    report = store.hourly_report(
        venue="coinbase_advanced",
        instrument_id="coinbase_advanced:BTC-USD",
        start=datetime(2026, 9, 15, 10, tzinfo=timezone.utc),
        end=datetime(2026, 9, 15, 13, tzinfo=timezone.utc),
        stale_after_seconds=7200,
        now=datetime(2026, 9, 15, 13, tzinfo=timezone.utc),
    )

    assert first.inserted == 2
    assert second.inserted == 0
    assert second.duplicates == 2
    assert report.stored_bars == 2
    assert report.missing_bars == ("2026-09-15T11:00:00Z",)
    assert report.duplicate_attempts == 2
    assert report.latest_close == "2026-09-15T13:00:00Z"
    assert report.stale is False


def test_restart_after_interruption_fills_missing_without_duplication(tmp_path: Path) -> None:
    store = TideStore(tmp_path / "recovery.sqlite3")
    store.initialize()
    start = datetime(2026, 9, 15, 10, tzinfo=timezone.utc)
    end = datetime(2026, 9, 15, 13, tzinfo=timezone.utc)

    interrupted_run = store.start_ingestion_run(
        "fixture",
        "coinbase_advanced",
        "coinbase_advanced:BTC-USD",
        start,
        end,
    )
    partial = store.insert_events([bar(10)])
    store.finish_ingestion_run(
        interrupted_run,
        fetched=1,
        inserted=partial.inserted,
        duplicate_attempts=0,
        incomplete_skipped=0,
        status="interrupted",
        error="fixture interruption",
    )

    recovery_run = store.start_ingestion_run(
        "fixture",
        "coinbase_advanced",
        "coinbase_advanced:BTC-USD",
        start,
        end,
    )
    recovered = store.insert_events([bar(10), bar(11), bar(12)])
    store.finish_ingestion_run(
        recovery_run,
        fetched=3,
        inserted=recovered.inserted,
        duplicate_attempts=recovered.duplicates,
        incomplete_skipped=0,
        status="complete",
    )

    report = store.hourly_report(
        venue="coinbase_advanced",
        instrument_id="coinbase_advanced:BTC-USD",
        start=start,
        end=end,
        stale_after_seconds=7200,
        now=end,
    )

    assert recovered.inserted == 2
    assert recovered.duplicates == 1
    assert report.stored_bars == 3
    assert report.missing_bars == ()
    assert report.duplicate_attempts == 1
