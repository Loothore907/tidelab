from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

import pytest

from tidelab.cli import main
from tidelab.domain import MarketEvent
from tidelab.lean_hourly_export import export_lean_hourly_closes
from tidelab.storage import TideStore


START = datetime(2026, 1, 1, 23, tzinfo=timezone.utc)
SOURCE = "fixture.hourly"


def _event(hour: int, *, key: str | None = None) -> MarketEvent:
    when = START + timedelta(hours=hour)
    return MarketEvent(
        venue="fixture", instrument_id="fixture:BTC-USDT", event_type="bar",
        event_time=when, received_at=when + timedelta(hours=2), source=SOURCE,
        payload={"open": "100", "high": "102", "low": "99", "close": str(100 + hour), "volume": "1"},
        native={}, interval_seconds=3600, closed=True,
        source_key=key or f"hour-{hour}",
    )


def test_export_uses_utc_day_files_and_exact_closed_hourly_source(tmp_path: Path) -> None:
    store = TideStore(tmp_path / "bars.sqlite3")
    store.initialize()
    store.insert_events([_event(0), _event(1), _event(2)])
    output = tmp_path / "lean"
    result = export_lean_hourly_closes(
        store, venue="fixture", instrument_id="fixture:BTC-USDT", source=SOURCE,
        start=START, end=START + timedelta(hours=3), output_dir=output,
    )
    first = (output / "20260101.csv").read_text(encoding="utf-8")
    second = (output / "20260102.csv").read_text(encoding="utf-8")
    assert first == "2026-01-01 23:00:00,100\n"
    assert second == "2026-01-02 00:00:00,101\n2026-01-02 01:00:00,102\n"
    assert (result.bars, result.daily_files) == (3, 2)
    assert result.content_sha256 == sha256((first + second).encode()).hexdigest()
    with pytest.raises(FileExistsError):
        export_lean_hourly_closes(
            store, venue="fixture", instrument_id="fixture:BTC-USDT", source=SOURCE,
            start=START, end=START + timedelta(hours=3), output_dir=output,
        )


def test_gap_and_duplicate_fail_before_writing(tmp_path: Path) -> None:
    store = TideStore(tmp_path / "bars.sqlite3")
    store.initialize()
    store.insert_events([_event(0), _event(2)])
    output = tmp_path / "gap"
    with pytest.raises(ValueError, match="coverage"):
        export_lean_hourly_closes(
            store, venue="fixture", instrument_id="fixture:BTC-USDT", source=SOURCE,
            start=START, end=START + timedelta(hours=3), output_dir=output,
        )
    assert not output.exists()

    store.insert_events([_event(1), _event(1, key="second-source-row")])
    duplicate_output = tmp_path / "duplicate"
    assert main([
        "export-lean-h1", "--database", str(store.path), "--venue", "fixture",
        "--instrument", "fixture:BTC-USDT", "--source", SOURCE,
        "--start", "2026-01-01T23:00:00Z", "--end", "2026-01-02T02:00:00Z",
        "--output", str(duplicate_output),
    ]) == 2
    assert not duplicate_output.exists()
