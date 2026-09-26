"""Deterministic normalized-strategy parser and synthetic batch contract test.

This layer has no model, source-code execution, market-data reader, broker, or
promotion decision. Raw papers, repositories and Pine need explicit frontends;
their text is never silently treated as a runnable definition.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_DOWN
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from tidelab.domain import canonical_json, parse_utc
from tidelab.strategy_intake import record_digest, validate_record


_ID = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_HOUR = timedelta(hours=1)
_MAX_PACKAGE_BYTES = 64 * 1024
_MAX_NODES = 64
_MAX_DEPTH = 12
SYNTHETIC_ENGINE = "tidelab-strategy-batch-v1"
SYNTHETIC_COST = {"fee_rate": "0.0025", "adverse_rate": "0.001",
                  "initial_cash": "10000", "quantity_unit": "0.00000001"}
_UNIT = Decimal(SYNTHETIC_COST["quantity_unit"])


class UnsupportedPackage(ValueError):
    """A well-formed requested rule or capability lacks an evaluator adapter."""


@dataclass(frozen=True)
class Bar:
    start: datetime
    open: Decimal
    close: Decimal


@dataclass(frozen=True)
class ParsedStrategy:
    strategy_id: str
    version: int
    source_candidate_id: str
    source_version: int
    source_sha256: str
    entry: dict[str, Any]
    exit: dict[str, Any]
    target_fraction: Decimal
    warmup: int
    package_sha256: str


def _decimal(value: Any, name: str, *, positive: bool = False) -> Decimal:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a decimal string")
    try:
        parsed = Decimal(value)
    except (ValueError, ArithmeticError) as exc:
        raise ValueError(f"{name} must be a decimal string") from exc
    if not parsed.is_finite() or (positive and parsed <= 0):
        raise ValueError(f"{name} must be finite and positive")
    return parsed


def _expr(node: Any, kind: str, depth: int, counter: list[int]) -> int:
    if depth > _MAX_DEPTH or not isinstance(node, dict):
        raise ValueError("rule expression exceeds depth or is not an object")
    counter[0] += 1
    if counter[0] > _MAX_NODES:
        raise ValueError("rule expression exceeds node limit")
    op = node.get("op")
    if kind == "number" and op == "number":
        if set(node) != {"op", "value"}:
            raise ValueError("number expression has unexpected fields")
        _decimal(node["value"], "number")
        return 1
    if kind == "number" and op in {"close", "sma"}:
        expected = {"op", "lag"} | ({"window"} if op == "sma" else set())
        if set(node) != expected or type(node["lag"]) is not int or not 0 <= node["lag"] <= 10000:
            raise ValueError("invalid closed-bar lag")
        if op == "sma" and (type(node["window"]) is not int
                            or not 2 <= node["window"] <= 10000):
            raise ValueError("invalid moving-average window")
        return node["lag"] + (node["window"] if op == "sma" else 1)
    if kind == "boolean" and op in {"gt", "lt"}:
        if set(node) != {"op", "left", "right"}:
            raise ValueError("comparison has unexpected fields")
        return max(_expr(node["left"], "number", depth + 1, counter),
                   _expr(node["right"], "number", depth + 1, counter))
    if kind == "boolean" and op in {"and", "or"}:
        args = node.get("args")
        if set(node) != {"op", "args"} or not isinstance(args, list) or not 2 <= len(args) <= 8:
            raise ValueError("logical expression needs 2 to 8 clauses")
        return max(_expr(arg, "boolean", depth + 1, counter) for arg in args)
    if kind == "boolean" and op == "not":
        if set(node) != {"op", "arg"}:
            raise ValueError("not expression has unexpected fields")
        return _expr(node["arg"], "boolean", depth + 1, counter)
    raise UnsupportedPackage("unsupported rule operation or type")


def parse_package(package: Mapping[str, Any], record: Mapping[str, Any]) -> ParsedStrategy:
    """Type-check one normalized package against an exact intake record."""
    if (not isinstance(package, dict) or set(package) !=
            {"schema_version", "strategy_id", "version", "source", "requirements", "rule"}):
        raise ValueError("strategy package fields differ")
    if (type(package["schema_version"]) is not int or package["schema_version"] != 1
            or type(package["version"]) is not int or package["version"] < 1):
        raise ValueError("unsupported strategy package version")
    if not isinstance(package["strategy_id"], str) or not _ID.fullmatch(package["strategy_id"]):
        raise ValueError("invalid strategy identifier")
    source = package["source"]
    if not isinstance(source, dict) or set(source) != {"candidate_id", "version", "record_sha256"}:
        raise ValueError("source binding fields differ")
    checked = validate_record(dict(record))
    if (source["candidate_id"] != checked["candidate_id"]
            or type(source["version"]) is not int or source["version"] != checked["version"]
            or not isinstance(source["record_sha256"], str)
            or _SHA.fullmatch(source["record_sha256"]) is None
            or source["record_sha256"] != record_digest(checked)):
        raise ValueError("source record identity differs")
    if (checked["source"]["kind"] != "synthetic_example"
            and (checked["stage"] != "implementation_selected"
                 or checked["rights"]["implementation_use"] != "documented")):
        raise ValueError("external source lacks selected implementation authority")
    requirements = package["requirements"]
    if (not isinstance(requirements, dict) or requirements !=
            {"interval_seconds": 3600, "product_class": "spot",
             "position_mode": "long_cash"}):
        raise UnsupportedPackage("batch evaluator does not support required capabilities")
    rule = package["rule"]
    if not isinstance(rule, dict) or set(rule) != {"entry", "exit", "target_fraction"}:
        raise ValueError("rule fields differ")
    fraction = _decimal(rule["target_fraction"], "target_fraction", positive=True)
    if fraction > 1:
        raise ValueError("target_fraction exceeds cash-only exposure")
    nodes = [0]
    warmup = max(_expr(rule["entry"], "boolean", 0, nodes),
                 _expr(rule["exit"], "boolean", 0, nodes))
    digest = sha256(canonical_json(package).encode("utf-8")).hexdigest()
    return ParsedStrategy(package["strategy_id"], package["version"],
                          source["candidate_id"], source["version"],
                          source["record_sha256"], rule["entry"], rule["exit"],
                          fraction, warmup, digest)


def load_json(path: Path, *, max_bytes: int = _MAX_PACKAGE_BYTES) -> dict[str, Any]:
    if path.stat().st_size > max_bytes:
        raise ValueError("input exceeds size limit")
    return parse_json_bytes(path.read_bytes(), max_bytes=max_bytes)


def parse_json_bytes(raw: bytes, *, max_bytes: int = _MAX_PACKAGE_BYTES) -> dict[str, Any]:
    if len(raw) > max_bytes:
        raise ValueError("input exceeds size limit")
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    result = json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                        parse_constant=lambda _: (_ for _ in ()).throw(
                            ValueError("nonfinite JSON number")))
    if not isinstance(result, dict):
        raise ValueError("input must be a JSON object")
    return result


def parse_synthetic_bars(fixture: Mapping[str, Any]) -> tuple[Bar, ...]:
    if (not isinstance(fixture, dict) or set(fixture) != {"kind", "interval_seconds", "bars"}
            or fixture["kind"] != "tidelab_synthetic"
            or fixture["interval_seconds"] != 3600
            or not isinstance(fixture["bars"], list) or len(fixture["bars"]) < 3):
        raise ValueError("only complete TideLab synthetic hourly fixtures are accepted")
    bars = []
    for item in fixture["bars"]:
        if not isinstance(item, dict) or set(item) != {"start_utc", "open", "close"}:
            raise ValueError("synthetic bar fields differ")
        when = parse_utc(item["start_utc"])
        if (when.tzinfo != timezone.utc or when.minute or when.second or when.microsecond
                or (bars and when != bars[-1].start + _HOUR)):
            raise ValueError("synthetic hourly clock has a gap or duplicate")
        bars.append(Bar(when, _decimal(item["open"], "open", positive=True),
                        _decimal(item["close"], "close", positive=True)))
    return tuple(bars)


def _numeric(node: Mapping[str, Any], closes: Sequence[Decimal], index: int) -> Decimal:
    op = node["op"]
    if op == "number":
        return Decimal(node["value"])
    if op == "close":
        return closes[index - node["lag"]]
    window = node["window"]
    end = index - node["lag"] + 1
    return sum(closes[end - window:end]) / Decimal(window)


def _boolean(node: Mapping[str, Any], closes: Sequence[Decimal], index: int) -> bool:
    op = node["op"]
    if op == "gt":
        return _numeric(node["left"], closes, index) > _numeric(node["right"], closes, index)
    if op == "lt":
        return _numeric(node["left"], closes, index) < _numeric(node["right"], closes, index)
    if op == "and":
        return all(_boolean(arg, closes, index) for arg in node["args"])
    if op == "or":
        return any(_boolean(arg, closes, index) for arg in node["args"])
    return not _boolean(node["arg"], closes, index)


def signal_trace(strategy: ParsedStrategy, bars: Sequence[Bar]) -> list[dict[str, int | bool]]:
    """Closed-bar predicates, before any synthetic next-open execution."""
    closes = [bar.close for bar in bars]
    return [{"index": index, "entry": _boolean(strategy.entry, closes, index),
             "exit": _boolean(strategy.exit, closes, index)}
            for index in range(strategy.warmup - 1, len(bars) - 1)]


def evaluate_synthetic(strategy: ParsedStrategy, bars: Sequence[Bar], *,
                       initial_cash: Decimal = Decimal(SYNTHETIC_COST["initial_cash"]),
                       fee_rate: Decimal = Decimal(SYNTHETIC_COST["fee_rate"]),
                       adverse_rate: Decimal = Decimal(SYNTHETIC_COST["adverse_rate"]),
                       trace: list[dict[str, Any]] | None = None) -> dict[str, str | int]:
    """One closed-bar/next-open full-fill contract test, never a market claim."""
    if (len(bars) <= strategy.warmup or any(
            not isinstance(value, Decimal) or not value.is_finite() or value < 0
            for value in (initial_cash, fee_rate, adverse_rate))
            or initial_cash <= 0 or adverse_rate >= 1):
        raise ValueError("incomplete synthetic history or invalid cost")
    for index, bar in enumerate(bars):
        if (bar.start.tzinfo != timezone.utc or bar.start.minute or bar.start.second
                or bar.start.microsecond or (index and bar.start != bars[index - 1].start + _HOUR)
                or any(not value.is_finite() or value <= 0 for value in (bar.open, bar.close))):
            raise ValueError("synthetic bars need complete UTC hours and positive prices")
    cash, units = initial_cash, Decimal(0)
    pending: tuple[str, Decimal] | None = None
    fills = decisions = 0
    closes = [bar.close for bar in bars]
    for index, bar in enumerate(bars):
        fill = None
        if pending:
            side, target = pending
            if side == "sell":
                price = bar.open * (1 - adverse_rate)
                quantity = units
                cash += units * price * (1 - fee_rate)
                units = Decimal(0)
            else:
                price = bar.open * (1 + adverse_rate)
                amount = min(target, cash)
                bought = (amount / (price * (1 + fee_rate))).quantize(_UNIT, rounding=ROUND_DOWN)
                if bought <= 0:
                    raise ValueError("synthetic target below executable unit")
                quantity = bought
                cash -= bought * price * (1 + fee_rate)
                units += bought
            fill = {"index": index, "utc": bar.start.isoformat().replace("+00:00", "Z"),
                    "side": side, "quantity": str(quantity), "price": str(price),
                    "fee": str(quantity * price * fee_rate)}
            fills += 1
            pending = None
        entry = exit_signal = None
        action = "hold"
        if index + 1 >= strategy.warmup and index != len(bars) - 1:
            entry = _boolean(strategy.entry, closes, index)
            exit_signal = _boolean(strategy.exit, closes, index)
            if units and exit_signal:
                pending = ("sell", Decimal(0))
            elif not units and entry:
                pending = ("buy", cash * strategy.target_fraction)
            if pending:
                action = pending[0]
                decisions += 1
        if cash < 0 or units < 0:
            raise AssertionError("synthetic cash or inventory became negative")
        if trace is not None:
            trace.append({"index": index,
                          "close_utc": (bar.start + _HOUR).isoformat().replace("+00:00", "Z"),
                          "entry": entry, "exit": exit_signal, "action": action,
                          "fill": fill, "cash": str(cash), "units": str(units),
                          "equity": str(cash + units * bar.close)})
    equity = cash + units * bars[-1].close
    return {"status": "synthetic_contract_tested", "strategy_id": strategy.strategy_id,
            "version": strategy.version, "package_sha256": strategy.package_sha256,
            "source_candidate_id": strategy.source_candidate_id,
            "source_version": strategy.source_version,
            "source_sha256": strategy.source_sha256, "decision_count": decisions,
            "fill_count": fills, "terminal_equity": str(equity),
            "net_return": str((equity - initial_cash) / initial_cash)}


def evaluate_batch(packages: Sequence[Mapping[str, Any]], records: Mapping[tuple[str, int], Mapping[str, Any]],
                   bars: Sequence[Bar]) -> list[dict[str, Any]]:
    """Account for every supplied variant, including invalid and unsupported ones."""
    outcomes = []
    seen: set[tuple[str, int]] = set()
    for index, package in enumerate(packages):
        digest = sha256(canonical_json(package).encode("utf-8")).hexdigest()
        try:
            source = package["source"]
            record = records[(source["candidate_id"], source["version"])]
            parsed = parse_package(package, record)
            key = (parsed.strategy_id, parsed.version)
            if key in seen:
                raise ValueError("duplicate strategy version in batch")
            seen.add(key)
            result = evaluate_synthetic(parsed, bars)
            outcomes.append({"index": index, **result})
        except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
            outcomes.append({"index": index, "status": "rejected_before_test",
                             "package_sha256": digest,
                             "strategy_id": package.get("strategy_id")
                             if isinstance(package.get("strategy_id"), str) else None,
                             "reason": type(exc).__name__})
            if isinstance(exc, UnsupportedPackage):
                outcomes[-1]["status"] = "unsupported_package"
    return outcomes
