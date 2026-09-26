"""Bounded read-only hourly snapshot reader; synthetic source only in v1."""
from datetime import timedelta
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
import json
import sqlite3

from tidelab.domain import canonical_json, isoformat_utc, parse_utc
from tidelab.strategy_batch import Bar
from tidelab.package_lean_parity import _domain

SOURCE = "tidelab.synthetic.hourly.v1"
HOUR = timedelta(hours=1)
FIELDS = ("event_id", "schema_version", "venue", "instrument_id", "event_type",
          "event_time_utc", "received_at_utc", "source", "interval_seconds",
          "closed", "payload_json", "native_json")


def row_digest(rows) -> str:
    digest = sha256()
    for row in rows:
        raw = canonical_json({key: row[key] for key in FIELDS}).encode()
        digest.update(len(raw).to_bytes(8, "big") + raw)
    return digest.hexdigest()


def read_partition(database: Path, descriptor: dict, market: str, *, capture=None) -> tuple[Bar, ...]:
    """Caller must reserve trials first; never discovers a digest from real data."""
    if (descriptor["kind"] != "synthetic" or descriptor["source"] != SOURCE
            or descriptor["venue"] != "tidelab" or descriptor["rights_reference"] != "TideLab-authored"):
        raise ValueError("real_data_not_enabled")
    part = descriptor["partitions"][market]
    start, end = parse_utc(part["start"]), parse_utc(part["end"])
    first = start - part["warmup_bars"] * HOUR
    count = int((end - first) / HOUR)
    if not 3 <= count <= 10000:
        raise ValueError("bar_limit")
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        db.execute("BEGIN")
        rows = db.execute(f"""SELECT {','.join(FIELDS)} FROM market_events
            WHERE venue=? AND instrument_id=? AND event_type='bar' AND interval_seconds=3600
              AND event_time_utc>=? AND event_time_utc<? ORDER BY event_time_utc,event_id""",
            (descriptor["venue"], market, isoformat_utc(first), isoformat_utc(end))).fetchmany(count + 1)
        if len(rows) != count:
            raise ValueError("missing_or_duplicate_hours")
        bars = []
        for index, row in enumerate(rows):
            if (row["event_time_utc"] != isoformat_utc(first + index * HOUR)
                    or row["source"] != SOURCE or row["closed"] != 1 or row["schema_version"] != 1
                    or json.loads(row["native_json"]) != {"kind": "tidelab_synthetic", "author": "TideLab"}):
                raise ValueError("source_clock_or_provenance_mismatch")
            payload = json.loads(row["payload_json"])
            if set(payload) != {"open", "high", "low", "close", "volume"}:
                raise ValueError("invalid_ohlcv")
            for value in payload.values():
                if not isinstance(value, str):
                    raise ValueError("decimal_text_required")
                _domain(value)
            values = {key: Decimal(value) for key, value in payload.items()}
            if (any(values[key] <= 0 for key in ("open", "high", "low", "close"))
                    or values["volume"] < 0 or values["high"] < max(values["open"], values["close"])
                    or values["low"] > min(values["open"], values["close"])
                    or values["high"] < values["low"]):
                raise ValueError("invalid_ohlcv")
            bars.append(Bar(first + index * HOUR, values["open"], values["close"]))
        if row_digest(rows) != part["sha256"]:
            raise ValueError("snapshot_digest_mismatch")
    if capture is not None:
        capture([dict(row) for row in rows])
    return tuple(bars)
