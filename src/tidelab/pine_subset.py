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
COMMENT_GRAMMAR_VERSION = "tidelab-pine-v5-subset-2"
IMPORT_GRAMMAR_VERSION = "tidelab-pine-v5-subset-3"
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


_TOKEN = re.compile(r'[ \t]+|"[A-Za-z0-9 _-]{1,64}"|[A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)*|[0-9]+|[(),=<>]')
_NAME = re.compile(r'[A-Za-z_][A-Za-z_0-9]{0,63}')
_RESERVED = set("_ close open high low volume time time_close bar_index barstate ta strategy input math syminfo timeframe request na true false var varip const int float bool string color if else for while switch break continue return import export method type array matrix map and or not".split())
_RESERVED.update("catch class do ellipse in is polygon range struct text throw try".split())


def _tokens(line: str) -> list[str]:
    """Consume every character; never join separated identifiers or run source."""
    result, pos = [], 0
    while pos < len(line):
        match = _TOKEN.match(line, pos)
        if match is None:
            raise PineFrontendError("unsupported_token")
        token = match.group()
        if not token.isspace():
            result.append(token)
        pos = match.end()
    return result


def _expression(tokens: list[str], symbols: dict[str, tuple]) -> tuple:
    # Only the existing close-versus-SMA rule, with prior-name substitution.
    def atom(parts):
        if parts == ["close"]:
            return ("close",)
        if len(parts) == 1:
            name = parts[0]
            if re.fullmatch(r'[0-9]{1,5}', name):
                return ("integer", int(name))
            if _NAME.fullmatch(name):
                if name not in symbols:
                    raise PineFrontendError("unsupported_reference:" + name)
                return symbols[name]
        if (len(parts) == 6 and parts[:2] == ["ta.sma", "("]
                and parts[3] == "," and parts[5] == ")"):
            source, window = atom(parts[2:3]), atom(parts[4:5])
            if source != ("close",) or window[0] != "integer":
                raise PineFrontendError("unsupported_sma_arguments")
            if not 2 <= window[1] <= 10000:
                raise PineFrontendError("unsupported_sma_window")
            return ("sma", window[1])
        raise PineFrontendError("unsupported_signal_expression")

    comparisons = [i for i, token in enumerate(tokens) if token in (">", "<")]
    if not comparisons:
        return atom(tokens)
    if len(comparisons) == 1:
        index = comparisons[0]
        left, right = atom(tokens[:index]), atom(tokens[index+1:])
        if left == ("close",) and right[0] == "sma":
            return ("gt" if tokens[index] == ">" else "lt", right[1])
    raise PineFrontendError("unsupported_signal_expression")


def _import_lines(source: str) -> list[str]:
    """Normalize grammar 3 to the unchanged eight-line semantic contract.

    Declarations are recomputed each bar, never persistent/reassigned. Indentation
    is checked before normalization so nested/local declarations cannot escape.
    """
    statements = []
    for raw in source[:-1].split("\n")[1:]:
        # Quotes in this subset have no escapes. Lexing below rejects unsupported
        # strings; scanning still protects comment delimiters within a string.
        quoted = False
        for i, char in enumerate(raw):
            if char == '"':
                quoted = not quoted
            if not quoted and raw[i:i+2] == "//":
                if raw[i+2:].lstrip(" \t").startswith("@"):
                    raise PineFrontendError("unsupported_pine_directive")
                raw = raw[:i]
                break
        if not raw.strip(" \t"):
            continue
        indent = raw[:len(raw) - len(raw.lstrip(" \t"))]
        statements.append((indent, _tokens(raw)))
    if len(statements) < 5:
        raise PineFrontendError("incomplete_subset_program")
    indent, header = statements.pop(0)
    if indent or len(header) < 4:
        raise PineFrontendError("unsupported_strategy_options")
    title, size = header[2], header[-2]
    canonical_header = (f'strategy({title}, overlay=false, pyramiding=0, '
        f'process_orders_on_close=false, calc_on_every_tick=false, '
        f'default_qty_type=strategy.percent_of_equity, default_qty_value={size})')
    if header != _tokens(canonical_header) or _HEADER.fullmatch(canonical_header) is None:
        raise PineFrontendError("unsupported_strategy_options")
    symbols = {}
    while statements and statements[0][1][0] != "if":
        indent, tokens = statements.pop(0)
        if indent or len(tokens) < 3 or tokens[1] != "=" or not _NAME.fullmatch(tokens[0]):
            raise PineFrontendError("unsupported_declaration")
        name = tokens[0]
        if name in _RESERVED or name in symbols:
            raise PineFrontendError("unsupported_alias_name:" + name)
        if len(symbols) >= 64:
            raise PineFrontendError("unsupported_alias_limit")
        symbols[name] = _expression(tokens[2:], symbols)
    if len(statements) != 4:
        raise PineFrontendError("unsupported_order_semantics")
    signals = []
    for offset, call in ((0, 'strategy.entry("L", strategy.long)'), (2, 'strategy.close("L")')):
        indent, condition = statements[offset]
        body_indent, body = statements[offset+1]
        if (indent or condition[0] != "if" or body_indent not in ("    ", "\t")
                or body != _tokens(call)):
            raise PineFrontendError("unsupported_order_semantics")
        signals.append(_expression(condition[1:], symbols))
    if (signals[0][0] != "gt" or signals[1][0] != "lt"
            or signals[0][1] != signals[1][1]):
        raise PineFrontendError("unsupported_signal_pair")
    window = signals[0][1]
    return ["//@version=5", canonical_header,
        f"entrySignal = close > ta.sma(close, {window})",
        f"exitSignal = close < ta.sma(close, {window})", "if entrySignal",
        '    strategy.entry("L", strategy.long)', "if exitSignal", '    strategy.close("L")']


def compile_pine(source_bytes: bytes, record: Mapping[str, Any], *,
                 grammar_version: str = GRAMMAR_VERSION) -> dict[str, Any]:
    """Compile an explicit grammar while preserving original source identity."""
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
    if grammar_version not in (GRAMMAR_VERSION, COMMENT_GRAMMAR_VERSION, IMPORT_GRAMMAR_VERSION):
        raise PineFrontendError("unsupported_grammar_version")
    if grammar_version in (COMMENT_GRAMMAR_VERSION, IMPORT_GRAMMAR_VERSION):
        # LF alone terminates a comment. Never interpret Unicode/control line
        # separators as boundaries that could turn comment text into code.
        if any(c in source for c in "\v\f\x1c\x1d\x1e\x85\u2028\u2029"):
            raise PineFrontendError("invalid_source_encoding")
        lines = source[:-1].split("\n")
    else:
        lines = source.splitlines()
    if not lines or lines[0] != "//@version=5":
        raise PineFrontendError("unsupported_pine_version")
    if grammar_version == IMPORT_GRAMMAR_VERSION:
        lines = _import_lines(source)
    if grammar_version == COMMENT_GRAMMAR_VERSION:
        statements = [lines[0]]
        for line in lines[1:]:
            stripped = line.lstrip(" \t")
            if stripped.startswith("//"):
                if stripped[2:].lstrip(" \t").startswith("@"):
                    raise PineFrontendError("unsupported_pine_directive")
                continue
            statements.append(line)
        lines = statements
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
