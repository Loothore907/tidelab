from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from tidelab.domain import isoformat_utc
from tidelab.storage import TideStore
from tidelab.universe_coverage import audit_universe_coverage


START = datetime(2024, 1, 1, tzinfo=timezone.utc)
END = datetime(2024, 3, 1, tzinfo=timezone.utc)
NATIVE = json.dumps({"archive_sha256": "a" * 64, "minute_rows": 60, "archive_period": "2024-01"})


def _plan(path: Path) -> Path:
    path.write_text(json.dumps({
        "schema_version": 1, "plan_id": "invented-two-market-v1", "venue": "okx",
        "source": "okx.historical_archive.candlesticks.1m",
        "start": isoformat_utc(START), "end": isoformat_utc(END),
        "minimum_contiguous_months": 1,
        "instruments": ["okx:BTC-USDT", "okx:ETH-USDT"],
    }), encoding="utf-8")
    return path


def _bars(store: TideStore, instrument: str, start: datetime, end: datetime,
          *, omit: datetime | None = None, source: str = "okx.historical_archive.candlesticks.1m",
          native: str = NATIVE) -> None:
    with store.connect() as db:
        when = start
        while when < end:
            if when != omit:
                key = f"{instrument}:{source}:{isoformat_utc(when)}"
                db.execute("""INSERT INTO market_events
                    (event_id, schema_version, venue, instrument_id, event_type,
                     event_time_utc, received_at_utc, source, interval_seconds,
                     closed, payload_json, native_json)
                    VALUES (?, 1, 'okx', ?, 'bar', ?, ?, ?, 3600, 1, '{}', ?)""",
                    (key, instrument, isoformat_utc(when), isoformat_utc(when + timedelta(days=2)),
                     source, native))
            when += timedelta(hours=1)


def test_coverage_gates_exact_market_and_records_missing_market(tmp_path: Path) -> None:
    store = TideStore(tmp_path / "invented.sqlite3")
    store.initialize()
    _bars(store, "okx:BTC-USDT", START, datetime(2024, 2, 1, tzinfo=timezone.utc))

    report = audit_universe_coverage(store.path, _plan(tmp_path / "plan.json"))

    btc, eth = report["markets"]
    assert report["purpose"] == "private_coverage_only"
    assert btc["status"] == "coverage_eligible"
    assert btc["exact_source_hours"] == 744
    assert btc["longest_run"]["end"] == "2024-02-01T00:00:00Z"
    assert eth["status"] == "excluded_no_exact_source_bars"
    assert report["comparable_coverage"] is False
    assert eth["missing_hours"] == 1440
    assert eth["gaps"] == [{"start": "2024-01-01T00:00:00Z",
                            "end": "2024-03-01T00:00:00Z", "hours": 1440}]
    assert "price" not in json.dumps(report)


def test_other_source_cannot_fill_gap_and_bad_provenance_excludes(tmp_path: Path) -> None:
    store = TideStore(tmp_path / "invented.sqlite3")
    store.initialize()
    missing = START + timedelta(days=12)
    _bars(store, "okx:BTC-USDT", START, datetime(2024, 2, 1, tzinfo=timezone.utc), omit=missing)
    _bars(store, "okx:BTC-USDT", missing, missing + timedelta(hours=1), source="unrelated.source")
    _bars(store, "okx:ETH-USDT", START, datetime(2024, 2, 1, tzinfo=timezone.utc), native="{}")

    btc, eth = audit_universe_coverage(store.path, _plan(tmp_path / "plan.json"))["markets"]

    assert btc["status"] == "excluded_short_continuity"
    assert btc["other_source_rows_ignored"] == 1
    assert any(gap["start"] == isoformat_utc(missing) and gap["hours"] == 1 for gap in btc["gaps"])
    assert eth["status"] == "excluded_invalid_source_rows"
    assert eth["invalid_source_rows"] == 744


def test_individually_complete_markets_still_need_one_shared_window(tmp_path: Path) -> None:
    store = TideStore(tmp_path / "invented.sqlite3")
    store.initialize()
    middle = datetime(2024, 2, 1, tzinfo=timezone.utc)
    _bars(store, "okx:BTC-USDT", START, middle)
    _bars(store, "okx:ETH-USDT", middle, END)

    report = audit_universe_coverage(store.path, _plan(tmp_path / "plan.json"))

    assert [market["status"] for market in report["markets"]] == ["coverage_eligible"] * 2
    assert report["comparable_coverage"] is False
    assert report["common_contiguous_window"] is None

    _bars(store, "okx:ETH-USDT", START, middle)
    report = audit_universe_coverage(store.path, tmp_path / "plan.json")
    assert report["comparable_coverage"] is True
    assert report["common_contiguous_window"]["end"] == "2024-02-01T00:00:00Z"


def test_audit_requires_existing_database_and_plan_cannot_swap_markets(tmp_path: Path) -> None:
    plan = _plan(tmp_path / "plan.json")
    missing = tmp_path / "absent.sqlite3"
    with pytest.raises(FileNotFoundError):
        audit_universe_coverage(missing, plan)
    assert not missing.exists()

    terms = json.loads(plan.read_text(encoding="utf-8"))
    terms["instruments"].append("okx:BTC-USDT")
    plan.write_text(json.dumps(terms), encoding="utf-8")
    with pytest.raises(ValueError, match="distinct exact venue"):
        audit_universe_coverage(missing, plan)
