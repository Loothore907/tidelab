"""Import local OKX daily or monthly one-minute candlestick archives."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

from tidelab.domain import MarketEvent, canonical_json, decimal_text, isoformat_utc, utc_now
from tidelab.storage import TideStore


SOURCE = "okx.historical_archive.candlesticks.1m"
FIELDS = ("instrument_name", "open", "high", "low", "close", "vol", "vol_ccy", "vol_quote", "open_time", "confirm")


@dataclass(frozen=True)
class ArchiveResult:
    archive_sha256: str
    symbol: str
    period: str
    minute_rows: int
    duplicate_minutes: int
    hourly_bars: int
    inserted: int
    duplicates: int
    start: str
    end: str

    def as_dict(self) -> dict[str, str | int]:
        return vars(self)


def _period_bounds(period: str) -> tuple[datetime, datetime]:
    try:
        date = datetime.strptime(period, "%Y-%m" if len(period) == 7 else "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ValueError("period must be YYYY-MM or YYYY-MM-DD") from exc
    if date.strftime("%Y-%m" if len(period) == 7 else "%Y-%m-%d") != period:
        raise ValueError("period must be YYYY-MM or YYYY-MM-DD")
    next_date = ((date.replace(day=28) + timedelta(days=4)).replace(day=1)
                 if len(period) == 7 else date + timedelta(days=1))
    # OKX's downloadable day runs from 16:00 UTC to 15:59 UTC the next day.
    return date - timedelta(hours=8), next_date - timedelta(hours=8)


def _read_events(path: Path, symbol: str, period: str, received_at: datetime) -> tuple[list[MarketEvent], int, int, str]:
    if not symbol or not all(part.isalnum() for part in symbol.split("-")):
        raise ValueError("symbol must be an OKX spot symbol such as BTC-USDT")
    start, end = _period_bounds(period)
    minimum_age = timedelta(days=2 if len(period) == 7 else 1)
    if received_at.astimezone(timezone.utc) < end + minimum_age:
        raise ValueError("archive is too recent to treat as final")
    digest = sha256(path.read_bytes()).hexdigest()
    expected_name = f"{symbol}-candlesticks-{period}.csv"
    events: list[MarketEvent] = []
    minute_count = 0
    duplicate_minutes = 0
    group: list[dict[str, str]] = []
    previous_time: datetime | None = None
    previous_row: dict[str, str] | None = None

    with ZipFile(path) as archive:
        if archive.namelist() != [expected_name]:
            raise ValueError(f"archive must contain only {expected_name}")
        with archive.open(expected_name) as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
            if tuple(reader.fieldnames or ()) != FIELDS:
                raise ValueError("unexpected OKX candlestick columns")
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    raise ValueError("archive row has missing or extra columns")
                if row["instrument_name"] != symbol:
                    raise ValueError("archive contains another symbol")
                if row["confirm"] not in {"0", "1"}:
                    raise ValueError("unexpected confirm value")
                try:
                    timestamp_ms = int(row["open_time"])
                    when = datetime.fromtimestamp(timestamp_ms // 1000, tz=timezone.utc)
                except (ValueError, OverflowError) as exc:
                    raise ValueError("invalid minute timestamp") from exc
                if timestamp_ms % 60000 or when < start or when >= end:
                    raise ValueError("minute lies outside the exact archive period")
                if previous_time is not None and when == previous_time:
                    if row != previous_row:
                        raise ValueError("archive has conflicting rows for one minute")
                    duplicate_minutes += 1
                    continue
                if previous_time is not None and when - previous_time != timedelta(minutes=1):
                    raise ValueError("archive has a missing or unordered minute")
                previous_time = when
                previous_row = row
                values = {name: Decimal(decimal_text(row[name], name)) for name in ("open", "high", "low", "close", "vol")}
                if min(values["open"], values["high"], values["low"], values["close"]) <= 0:
                    raise ValueError("OHLC prices must be positive")
                if values["high"] < max(values["open"], values["close"]) or values["low"] > min(values["open"], values["close"]):
                    raise ValueError("invalid OHLC range")
                if values["vol"] < 0:
                    raise ValueError("volume must be nonnegative")
                group.append(row)
                minute_count += 1
                if len(group) == 60:
                    hour = when - timedelta(minutes=59)
                    if hour.minute != 0:
                        raise ValueError("archive does not align to UTC hours")
                    high = max(Decimal(item["high"]) for item in group)
                    low = min(Decimal(item["low"]) for item in group)
                    volume = sum((Decimal(item["vol"]) for item in group), Decimal(0))
                    payload = {
                        "open": decimal_text(group[0]["open"], "open"),
                        "high": decimal_text(high, "high"),
                        "low": decimal_text(low, "low"),
                        "close": decimal_text(group[-1]["close"], "close"),
                        "volume": decimal_text(volume, "volume"),
                    }
                    events.append(MarketEvent(
                        venue="okx",
                        instrument_id=f"okx:{symbol}",
                        event_type="bar",
                        event_time=hour,
                        received_at=received_at,
                        source=SOURCE,
                        payload=payload,
                        native={"archive_sha256": digest, "minute_rows": 60, "archive_period": period},
                        interval_seconds=3600,
                        closed=True,
                        source_key=f"{symbol}:1h:{isoformat_utc(hour)}",
                    ))
                    group.clear()
    expected_minutes = int((end - start).total_seconds() // 60)
    if minute_count != expected_minutes or group or not events:
        raise ValueError(f"archive coverage is incomplete: {minute_count}/{expected_minutes} minute rows")
    return events, minute_count, duplicate_minutes, digest


def import_okx_archive(path: str | Path, *, symbol: str, period: str, store: TideStore) -> ArchiveResult:
    archive_path = Path(path)
    received_at = utc_now()
    events, minute_count, duplicate_minutes, digest = _read_events(archive_path, symbol, period, received_at)
    store.initialize()
    inserted = duplicates = 0
    with store.connect() as connection:
        for event in events:
            payload_json = canonical_json(dict(event.payload))
            existing = connection.execute("SELECT payload_json FROM market_events WHERE event_id=?", (event.event_id,)).fetchone()
            if existing is not None:
                if existing["payload_json"] != payload_json:
                    raise ValueError("archive revises a stored hourly bar; review before replacing research input")
                duplicates += 1
                continue
            connection.execute(
                """INSERT INTO market_events
                   (event_id, schema_version, venue, instrument_id, event_type, event_time_utc,
                    received_at_utc, source, interval_seconds, closed, payload_json, native_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (event.event_id, event.schema_version, event.venue, event.instrument_id, event.event_type,
                 isoformat_utc(event.event_time), isoformat_utc(event.received_at), event.source,
                 event.interval_seconds, 1, payload_json, canonical_json(dict(event.native))),
            )
            inserted += 1
    start, end = _period_bounds(period)
    return ArchiveResult(digest, symbol, period, minute_count, duplicate_minutes, len(events), inserted, duplicates,
                         isoformat_utc(start), isoformat_utc(end))
