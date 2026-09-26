"""Exact-byte, non-executing Pine v5 subset frontend for synthetic examples.

This is a TideLab normalization contract, not a TradingView interpreter.
Unsupported Pine semantics are rejected before a strategy package exists.
"""

from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
import re
from typing import Any, Mapping

from tidelab.strategy_intake import record_digest, validate_record


GRAMMAR_VERSION = "tidelab-pine-v5-subset-1"
MAX_SOURCE_BYTES = 16 * 1024
_HEADER = re.compile(
    r'strategy\("([A-Za-z0-9 _-]{1,64})", overlay=false, pyramiding=0, '
    r'process_orders_on_close=false, calc_on_every_tick=false, '
    r'default_qty_type=strategy.percent_of_equity, default_qty_value=([0-9]+)\)'
)
_SIGNAL = re.compile(r'(entrySignal|exitSignal) = close ([<>]) ta\.sma\(close, ([0-9]+)\)')


class PineFrontendError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def compile_pine(source_bytes: bytes, record: Mapping[str, Any]) -> dict[str, Any]:
    """Compile only the documented eight-line grammar into package v1."""
    if len(source_bytes) > MAX_SOURCE_BYTES:
        raise PineFrontendError("source_size_exceeded")
    digest = sha256(source_bytes).hexdigest()
    checked = validate_record(dict(record))
    if (checked["source"]["kind"] != "synthetic_example"
            or checked["source"]["content_sha256"] != digest):
        raise PineFrontendError("source_binding_mismatch")
    try:
        source = source_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise PineFrontendError("invalid_utf8") from exc
    if source.startswith("\ufeff") or "\r" in source or not source.endswith("\n"):
        raise PineFrontendError("invalid_source_encoding")
    lines = source.splitlines()
    if not lines or lines[0] != "//@version=5":
        raise PineFrontendError("unsupported_pine_version")
    if len(lines) < 8:
        raise PineFrontendError("incomplete_subset_program")
    if len(lines) > 8:
        raise PineFrontendError("unsupported_extra_statement")
    header = _HEADER.fullmatch(lines[1])
    if header is None:
        raise PineFrontendError("unsupported_strategy_options")
    percent = int(header.group(2))
    if not 1 <= percent <= 100:
        raise PineFrontendError("unsupported_position_size")
    expressions = []
    for line, name in zip(lines[2:4], ("entrySignal", "exitSignal")):
        match = _SIGNAL.fullmatch(line)
        if match is None or match.group(1) != name:
            raise PineFrontendError("unsupported_signal_expression")
        window = int(match.group(3))
        if not 2 <= window <= 10000:
            raise PineFrontendError("unsupported_sma_window")
        expressions.append({"op": "gt" if match.group(2) == ">" else "lt",
                            "left": {"op": "close", "lag": 0},
                            "right": {"op": "sma", "window": window, "lag": 0}})
    if (expressions[0]["op"] != "gt" or expressions[1]["op"] != "lt"
            or expressions[0]["right"]["window"] != expressions[1]["right"]["window"]):
        raise PineFrontendError("unsupported_signal_pair")
    if lines[4:] != ["if entrySignal", '    strategy.entry("L", strategy.long)',
                     "if exitSignal", '    strategy.close("L")']:
        raise PineFrontendError("unsupported_order_semantics")
    return {"schema_version": 1, "strategy_id": f"synthetic-pine-{digest[:16]}",
            "version": 1,
            "source": {"candidate_id": checked["candidate_id"], "version": checked["version"],
                       "record_sha256": record_digest(checked)},
            "requirements": {"interval_seconds": 3600, "product_class": "spot",
                             "position_mode": "long_cash"},
            "rule": {"entry": expressions[0], "exit": expressions[1],
                     "target_fraction": str(Decimal(percent) / Decimal(100))}}
