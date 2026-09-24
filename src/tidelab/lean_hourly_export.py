"""Export complete local hourly closes for LEAN's TideLabH1Bar reader.

This is a signal-input bridge, not a backtest or execution model. Real market
data and its derived CSV files must remain in ignored local storage.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path

from tidelab.domain import decimal_text, isoformat_utc, parse_utc
from tidelab.storage import TideStore


@dataclass(frozen=True)
class LeanHourlyExport:
    venue: str
    instrument_id: str
    source: str
    start: str
    end: str
    bars: int
    daily_files: int
    content_sha256: str

    def as_dict(self) -> dict[str, str | int]:
        return asdict(self)


def _exact_utc_hour(value: datetime, name: str) -> datetime:
    if value.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")
    utc = value.astimezone(timezone.utc)
    if utc.minute or utc.second or utc.microsecond:
        raise ValueError(f"{name} must align to an exact UTC hour")
    return utc


def export_lean_hourly_closes(
    store: TideStore, *, venue: str, instrument_id: str, source: str,
    start: datetime, end: datetime, output_dir: str | Path,
) -> LeanHourlyExport:
    """Write UTC daily CSVs only after a full, single-source coverage check.

    The two-column rows match the existing LEAN TideLabH1Bar custom reader.
    They contain close prices only, so they cannot support fill or cost claims.
    """
    start = _exact_utc_hour(start, "start")
    end = _exact_utc_hour(end, "end")
    if end <= start:
        raise ValueError("end must follow start")
    if not venue or not instrument_id.startswith(f"{venue}:") or not source:
        raise ValueError("venue, matching instrument_id, and exact source are required")
    if not store.path.is_file():
        raise ValueError("local source database does not exist")
    destination = Path(output_dir)
    if destination.exists():
        raise FileExistsError(f"output directory already exists: {destination}")

    with store.connect() as connection:
        rows = connection.execute(
            """SELECT event_time_utc, payload_json FROM market_events
               WHERE venue=? AND instrument_id=? AND source=? AND event_type='bar'
                 AND interval_seconds=3600 AND closed=1
                 AND event_time_utc>=? AND event_time_utc<?
               ORDER BY event_time_utc""",
            (venue, instrument_id, source, isoformat_utc(start), isoformat_utc(end)),
        ).fetchall()

    expected = int((end - start) / timedelta(hours=1))
    if len(rows) != expected:
        raise ValueError(f"hourly coverage is incomplete or duplicated: {len(rows)}/{expected}")
    daily: dict[str, list[str]] = {}
    digest = sha256()
    for offset, row in enumerate(rows):
        when = parse_utc(row["event_time_utc"])
        if when != start + timedelta(hours=offset):
            raise ValueError("hourly data has a gap, duplicate, or wrong order")
        payload = json.loads(row["payload_json"])
        if not isinstance(payload, dict) or "close" not in payload:
            raise ValueError("hourly bar lacks a close")
        close = decimal_text(payload["close"], "close")
        if Decimal(close) <= 0:
            raise ValueError("hourly close must be positive")
        line = f"{when:%Y-%m-%d %H:%M:%S},{close}\n"
        daily.setdefault(when.strftime("%Y%m%d"), []).append(line)
        digest.update(line.encode("utf-8"))

    destination.mkdir(parents=True, exist_ok=False)
    for day, lines in daily.items():
        with (destination / f"{day}.csv").open("x", encoding="utf-8", newline="\n") as output:
            output.writelines(lines)
    return LeanHourlyExport(
        venue, instrument_id, source, isoformat_utc(start), isoformat_utc(end),
        expected, len(daily), digest.hexdigest(),
    )
