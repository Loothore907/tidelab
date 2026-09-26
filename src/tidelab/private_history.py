"""Shared bounded private-input mechanics. None of these helpers grants access.

Callers must establish and consume a specific owner grant before opening prices.
The original RSI anchor is the permanent identity of this research program.
"""
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from tidelab import historical_batch as batch
from tidelab.candidate_screen import _bar
from tidelab.domain import canonical_json, isoformat_utc, parse_utc
from tidelab.historical_input import FIELDS
from tidelab.package_lean_parity import _domain
from tidelab.strategy_batch import Bar, parse_json_bytes, validate_ohlc
from tidelab.trial_registry import TrialRegistry

@dataclass(frozen=True)
class Window:
    first: str
    end: str
    rows: int
    source: str = "okx.historical_archive.candlesticks.1m"

    def __post_init__(self):
        first, end = parse_utc(self.first), parse_utc(self.end)
        if (type(self.rows) is not int or not 1 <= self.rows <= 10000
                or end - first != timedelta(hours=self.rows)
                or any(t.minute or t.second or t.microsecond for t in (first, end))):
            raise ValueError("invalid_private_window")

def canonical_registry(root: Path, grant: str, authority_hash: str, proposal_hash: str, record_hash: str) -> TrialRegistry:
    registry_path = root / "data/research_program/trials.sqlite3"
    anchor_path = root / "data/strategy_intake/RSI-BATCH-V1-STORE.json"
    if not anchor_path.exists() or not registry_path.exists():
        raise ValueError("canonical_program_store_missing")
    anchor = batch.read(anchor_path)
    reg = TrialRegistry(registry_path)
    receipt = reg.access(grant, "authorization")
    if (not receipt or receipt.get("store_id") != anchor.get("store_id") or not anchor.get("store_id")
            or anchor.get("grant") != grant or anchor.get("authority_sha256") != authority_hash
            or receipt.get("authority_sha256") != authority_hash or receipt.get("proposal_sha256") != proposal_hash
            or receipt.get("record_sha256") != record_hash):
        raise ValueError("program_store_identity_mismatch")
    return reg



def validate_rows(rows, market, window: Window, *, preserve_ohlc: bool = False):
    if len(rows) != window.rows: raise ValueError("window_count_mismatch")
    bars, archives = [], {}
    for index, row in enumerate(rows):
        when = parse_utc(window.first) + timedelta(hours=index)
        if (row["event_time_utc"] != isoformat_utc(when) or row["source"] != window.source or row["closed"] != 1
                or row["schema_version"] != 1 or row["venue"] != "okx" or row["instrument_id"] != market
                or row["event_type"] != "bar" or row["interval_seconds"] != 3600):
            raise ValueError("source_continuity_mismatch")
        payload = parse_json_bytes(row["payload_json"].encode())
        bar = _bar(when, canonical_json(payload))
        _domain(str(bar.open)); _domain(str(bar.close))
        native = parse_json_bytes(row["native_json"].encode())
        day = (when + timedelta(hours=8)).date()
        period = native.get("archive_period", native.get("archive_month"))
        digest = native.get("archive_sha256")
        if (period not in (day.isoformat(), day.strftime("%Y-%m")) or native.get("minute_rows") != 60
                or not isinstance(digest, str) or not batch.DIGEST.fullmatch(digest)
                or ("archive_period" in native and "archive_month" in native)
                or (len(period) == 10 and "archive_period" not in native)):
            raise ValueError("archive_provenance_mismatch")
        name = f"{market.removeprefix('okx:')}-candlesticks-{period}.zip"
        if name in archives and archives[name] != digest: raise ValueError("conflicting_archive_identity")
        archives[name] = digest
        bars.append(Bar(when, bar.open, bar.close, bar.high, bar.low) if preserve_ohlc else Bar(when, bar.open, bar.close))
        if preserve_ohlc:
            validate_ohlc(bars[-1])
    return tuple(bars), archives


def rows_for(db, market, window: Window):
    return db.execute(f"""SELECT {','.join(FIELDS)} FROM market_events WHERE venue='okx'
        AND instrument_id=? AND event_type='bar' AND interval_seconds=3600
        AND event_time_utc>=? AND event_time_utc<? ORDER BY event_time_utc,event_id""",
        (market, window.first, window.end)).fetchmany(window.rows + 1)
