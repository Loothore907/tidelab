"""Fixed TL-003 offline candidate screen; a historical estimate, never an order path."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_DOWN
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3

from tidelab.domain import canonical_json, parse_utc
from tidelab.universe_coverage import audit_universe_coverage


SOURCE = "okx.historical_archive.candlesticks.1m"
PLAN_SHA256 = "684cc9cabdd6854a2decd2d580fda08a399a7364ad6c95b0a6e1ac26a0354393"
START = datetime.fromisoformat("2023-07-01T00:00:00+00:00")
END = datetime.fromisoformat("2026-08-31T16:00:00+00:00")
PARTITIONS = {
    "development": (datetime.fromisoformat("2023-07-31T00:00:00+00:00"),
                    datetime.fromisoformat("2025-01-01T00:00:00+00:00")),
    "validation": (datetime.fromisoformat("2025-01-01T00:00:00+00:00"),
                   datetime.fromisoformat("2026-01-01T00:00:00+00:00")),
    "untouched": (datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                  datetime.fromisoformat("2026-08-31T15:00:00+00:00")),
}
FAMILIES = ("momentum-720-v1", "reversal-24-v1")
INITIAL_CASH = Decimal("10000")
UNIT = Decimal("0.00000001")
BASE = {"fee": Decimal("0.0025"), "half_spread": Decimal("0.0005"),
        "slippage": Decimal("0.0005")}
STRESS = {key: value * 2 for key, value in BASE.items()}
_HOUR = timedelta(hours=1)


@dataclass(frozen=True)
class Bar:
    start: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal


def _bar(start: datetime, payload_json: str) -> Bar:
    payload = json.loads(payload_json)
    if set(payload) != {"open", "high", "low", "close", "volume"}:
        raise ValueError("unexpected hourly OHLCV payload")
    try:
        prices = {key: Decimal(str(payload[key])) for key in ("open", "high", "low", "close")}
        volume = Decimal(str(payload["volume"]))
    except (ValueError, ArithmeticError) as exc:
        raise ValueError("invalid hourly decimal") from exc
    if (any(not value.is_finite() or value <= 0 for value in prices.values())
            or not volume.is_finite() or volume < 0
            or prices["high"] < max(prices["open"], prices["close"])
            or prices["low"] > min(prices["open"], prices["close"])):
        raise ValueError("invalid hourly OHLCV range")
    return Bar(start, prices["open"], prices["high"], prices["low"], prices["close"])


def preflight(database: Path, plan_path: Path) -> tuple[list[str], str]:
    """Read metadata only, before any screen price payload."""
    plan_bytes = plan_path.read_bytes()
    plan = json.loads(plan_bytes)
    audit = audit_universe_coverage(database, plan_path)
    common = audit["common_contiguous_window"]
    if (audit["plan_sha256"] != sha256(plan_bytes).hexdigest()
            or audit["plan_sha256"] != PLAN_SHA256
            or plan["source"] != SOURCE or plan["start"] != START.isoformat().replace("+00:00", "Z")
            or plan["end"] != "2026-09-01T00:00:00Z"
            or len(plan["instruments"]) != 5 or len(audit["markets"]) != 5
            or [market["instrument"] for market in audit["markets"]] != plan["instruments"]
            or any(market["status"] != "coverage_eligible" or market["invalid_source_rows"]
                   for market in audit["markets"])
            or not audit["comparable_coverage"] or common is None
            or parse_utc(common["start"]) > START or parse_utc(common["end"]) < END):
        raise ValueError("fixed five-market exact-source coverage gate failed")
    return plan["instruments"], audit["plan_sha256"]


def read_bars(database: Path, instrument: str, phase: str) -> tuple[list[Bar], str]:
    """Read one exact-source private partition and bind every stored row to a hash."""
    score_start, score_end = PARTITIONS[phase]
    first = score_start - 720 * _HOUR
    expected = int((score_end - first) / _HOUR) + 1
    uri = database.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """SELECT event_id, event_time_utc, source, closed, payload_json, native_json
               FROM market_events WHERE venue='okx' AND instrument_id=?
                 AND event_type='bar' AND interval_seconds=3600
                 AND event_time_utc>=? AND event_time_utc<=?
               ORDER BY event_time_utc, event_id""",
            (instrument, first.isoformat().replace("+00:00", "Z"),
             score_end.isoformat().replace("+00:00", "Z")),
        ).fetchall()
    if len(rows) != expected:
        raise ValueError("partition contains missing or duplicate hours")
    digest = sha256()
    bars = []
    for index, row in enumerate(rows):
        when = parse_utc(row["event_time_utc"])
        native = json.loads(row["native_json"])
        archive_day = (when + timedelta(hours=8)).date()
        period = native.get("archive_period", native.get("archive_month"))
        expected_periods = (archive_day.isoformat(), archive_day.strftime("%Y-%m"))
        digest_text = native.get("archive_sha256")
        if (when != first + index * _HOUR or row["source"] != SOURCE or row["closed"] != 1
                or native.get("minute_rows") != 60
                or not isinstance(digest_text, str)
                or re.fullmatch(r"[0-9a-f]{64}", digest_text) is None
                or period not in expected_periods
                or ("archive_month" in native and "archive_period" in native)):
            raise ValueError("partition source, closure or provenance changed")
        for field in (row["event_id"], row["event_time_utc"], row["payload_json"],
                      row["native_json"]):
            encoded = field.encode("utf-8")
            digest.update(len(encoded).to_bytes(8, "big") + encoded)
        bars.append(_bar(when, row["payload_json"]))
    return bars, digest.hexdigest()


def _fill(cash: Decimal, quantity: Decimal, action: str, opening: Decimal,
          allocation: Decimal, cost: dict[str, Decimal]) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    adverse = cost["half_spread"] + cost["slippage"]
    price = opening * (1 + adverse if action == "buy" else 1 - adverse)
    if action == "buy":
        bought = (allocation / (price * (1 + cost["fee"]))).quantize(UNIT, rounding=ROUND_DOWN)
        if bought <= 0:
            raise ValueError("allocated notional cannot buy one unit")
        notional = bought * price
        fee = notional * cost["fee"]
        if notional + fee > cash:
            raise ValueError("buy exceeds available cash")
        return cash - notional - fee, quantity + bought, fee, notional
    notional = quantity * price
    fee = notional * cost["fee"]
    return cash + notional - fee, Decimal(0), fee, notional


def replay(bars: list[Bar], family: str, cost: dict[str, Decimal],
           *, allocation: Decimal = Decimal("0.25"), benchmark: bool = False) -> dict[str, str | int]:
    """Synthetic or private hourly full-fill scenario; first 720 bars are warmup."""
    if family not in FAMILIES and not benchmark:
        raise ValueError("unregistered screen family")
    if len(bars) < 723 or not 0 < allocation <= 1:
        raise ValueError("incomplete screen partition")
    for index, bar in enumerate(bars):
        if index and bar.start != bars[index - 1].start + _HOUR:
            raise ValueError("noncontiguous screen bars")
    cash, quantity = INITIAL_CASH, Decimal(0)
    peak = INITIAL_CASH
    entry_cost = entry_signal_close = None
    fill_index = None
    pending = None
    paused = False
    fees = turnover = exposure_sum = Decimal(0)
    underwater = longest_underwater = total_underwater = 0
    max_drawdown = Decimal(0)
    results: list[Decimal] = []
    marks = 0
    for index in range(720, len(bars)):
        bar = bars[index]
        if index == len(bars) - 1:
            pending = "sell" if quantity else None
        if benchmark and index == 720:
            pending = "buy"
        if pending:
            if pending == "buy":
                equity = cash + quantity * bar.open
                cash, quantity, fee, notional = _fill(
                    cash, quantity, "buy", bar.open, equity * allocation, cost)
                entry_cost, fill_index = notional + fee, index
            else:
                cash, quantity, fee, notional = _fill(
                    cash, quantity, "sell", bar.open, Decimal(0), cost)
                if entry_cost is not None:
                    results.append(notional - fee - entry_cost)
                entry_cost = entry_signal_close = fill_index = None
            fees += fee
            turnover += notional
            pending = None
        if index == len(bars) - 1:
            max_drawdown = max(max_drawdown, (peak - cash) / peak)
            break
        equity = cash + quantity * bar.close
        peak = max(peak, equity)
        drawdown = (peak - equity) / peak
        max_drawdown = max(max_drawdown, drawdown)
        if equity < peak:
            underwater += 1
            total_underwater += 1
            longest_underwater = max(longest_underwater, underwater)
        else:
            underwater = 0
        exposure_sum += quantity * bar.close / equity if equity > 0 else Decimal(0)
        marks += 1
        if benchmark:
            continue
        if drawdown >= Decimal("0.20"):
            paused = True
            if quantity:
                pending = "sell"
            continue
        if quantity:
            if family == "momentum-720-v1":
                exit_signal = bar.close <= bars[index - 720].close
            else:
                exit_signal = (bar.close >= entry_signal_close
                               or index - fill_index + 1 >= 48)
            if exit_signal:
                pending = "sell"
        elif not paused and index < len(bars) - 2:
            if family == "momentum-720-v1":
                enter = bar.close > bars[index - 720].close
            else:
                enter = bar.close <= bars[index - 24].close * Decimal("0.95")
            if enter:
                pending = "buy"
                entry_signal_close = bar.close
    if quantity:
        raise AssertionError("partition was not liquidated")
    largest = max(results, default=Decimal(0))
    return {"net_return": str((cash - INITIAL_CASH) / INITIAL_CASH),
            "max_drawdown": str(max_drawdown),
            "underwater_hours": total_underwater,
            "longest_underwater_hours": longest_underwater,
            "average_exposure": str(exposure_sum / marks if marks else Decimal(0)),
            "turnover": str(turnover / INITIAL_CASH), "fees": str(fees),
            "round_trips": len(results), "largest_trade_result": str(largest),
            "net_result_excluding_largest_trade": str(cash - INITIAL_CASH - largest)}
def passes(base: dict[str, str | int], stress: dict[str, str | int],
           primary: dict[str, str | int]) -> str:
    if base["round_trips"] < 10:
        return "inconclusive_low_trade_count"
    if (Decimal(base["net_return"]) <= 0
            or Decimal(base["net_return"]) <= Decimal(primary["net_return"])
            or Decimal(stress["net_return"]) <= 0
            or Decimal(base["max_drawdown"]) > Decimal("0.15")):
        return "rejected"
    return "survived"
