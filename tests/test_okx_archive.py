from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import io

import pytest

from tidelab.okx_archive import import_okx_archive
from tidelab.storage import TideStore


def make_archive(path: Path, *, changed_minute: int | None = None, missing_minute: int | None = None,
                 duplicate_minute: int | None = None, conflicting_duplicate: bool = False) -> None:
    start = datetime(2023, 12, 31, 16, tzinfo=timezone.utc)
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        with archive.open("BTC-USDT-candlesticks-2024-01.csv", "w") as raw:
            writer = io.TextIOWrapper(raw, encoding="utf-8", newline="")
            writer.write("instrument_name,open,high,low,close,vol,vol_ccy,vol_quote,open_time,confirm\n")
            for minute in range(31 * 24 * 60):
                if minute == missing_minute:
                    continue
                price = "102" if minute == changed_minute else "101"
                timestamp = int((start + timedelta(minutes=minute)).timestamp() * 1000)
                line = f"BTC-USDT,100,{price},99,100,1,100,100,{timestamp},0\n"
                writer.write(line)
                if minute == duplicate_minute:
                    writer.write(line.replace(",100,100,", ",101,100,") if conflicting_duplicate else line)
            writer.flush()


def test_month_import_is_complete_idempotent_and_detects_revisions(tmp_path: Path) -> None:
    archive = tmp_path / "BTC-USDT-candlesticks-2024-01.zip"
    store = TideStore(tmp_path / "market.sqlite3")
    make_archive(archive)

    first = import_okx_archive(archive, symbol="BTC-USDT", period="2024-01", store=store)
    second = import_okx_archive(archive, symbol="BTC-USDT", period="2024-01", store=store)
    report = store.hourly_report(
        venue="okx", instrument_id="okx:BTC-USDT",
        start=datetime(2023, 12, 31, 16, tzinfo=timezone.utc),
        end=datetime(2024, 1, 31, 16, tzinfo=timezone.utc),
        stale_after_seconds=3600,
    )
    assert (first.minute_rows, first.hourly_bars, first.inserted) == (44640, 744, 744)
    assert (second.inserted, second.duplicates) == (0, 744)
    assert report.stored_bars == 744
    assert report.missing_bars == ()

    make_archive(archive, changed_minute=0)
    with pytest.raises(ValueError, match="revises a stored hourly bar"):
        import_okx_archive(archive, symbol="BTC-USDT", period="2024-01", store=store)


def test_missing_minute_is_rejected_before_storage(tmp_path: Path) -> None:
    archive = tmp_path / "BTC-USDT-candlesticks-2024-01.zip"
    store = TideStore(tmp_path / "market.sqlite3")
    make_archive(archive, missing_minute=100)
    with pytest.raises(ValueError, match="missing or unordered minute"):
        import_okx_archive(archive, symbol="BTC-USDT", period="2024-01", store=store)
    assert not store.path.exists()


def test_exact_duplicate_is_counted_but_conflicting_duplicate_is_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "BTC-USDT-candlesticks-2024-01.zip"
    store = TideStore(tmp_path / "market.sqlite3")
    make_archive(archive, duplicate_minute=100)
    result = import_okx_archive(archive, symbol="BTC-USDT", period="2024-01", store=store)
    assert result.duplicate_minutes == 1
    assert result.minute_rows == 44640

    make_archive(archive, duplicate_minute=100, conflicting_duplicate=True)
    with pytest.raises(ValueError, match="conflicting rows"):
        import_okx_archive(archive, symbol="BTC-USDT", period="2024-01", store=store)


def test_daily_archive_uses_okx_1600_utc_boundary(tmp_path: Path) -> None:
    archive = tmp_path / "BTC-USDT-candlesticks-2024-02-02.zip"
    store = TideStore(tmp_path / "market.sqlite3")
    start = datetime(2024, 2, 1, 16, tzinfo=timezone.utc)
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as z:
        with z.open("BTC-USDT-candlesticks-2024-02-02.csv", "w") as raw:
            writer = io.TextIOWrapper(raw, encoding="utf-8", newline="")
            writer.write("instrument_name,open,high,low,close,vol,vol_ccy,vol_quote,open_time,confirm\n")
            for minute in range(1440):
                timestamp = int((start + timedelta(minutes=minute)).timestamp() * 1000)
                writer.write(f"BTC-USDT,100,101,99,100,1,100,100,{timestamp},1\n")
            writer.flush()
    result = import_okx_archive(archive, symbol="BTC-USDT", period="2024-02-02", store=store)
    assert (result.minute_rows, result.hourly_bars, result.inserted) == (1440, 24, 24)
    assert result.start == "2024-02-01T16:00:00Z"
    assert result.end == "2024-02-02T16:00:00Z"
