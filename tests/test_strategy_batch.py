"""The package parser and batch loop use invented source and bar fixtures only."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_DOWN
from pathlib import Path

import pytest

from tidelab.strategy_batch import (Bar, UnsupportedPackage, evaluate_batch, evaluate_synthetic,
                                    load_json, parse_package,
                                    parse_synthetic_bars)
from tidelab.strategy_intake import load_record, record_digest


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "research" / "examples"


def inputs():
    record = load_record(EXAMPLES / "strategy-batch-synthetic-record-v1.json")
    package = load_json(EXAMPLES / "strategy-batch-packages" / "synthetic-sma-3-v1.json")
    bars = parse_synthetic_bars(load_json(EXAMPLES / "strategy-batch-synthetic-bars-v1.json"))
    return record, package, bars


def test_normalized_package_runs_with_closed_signal_and_next_open_fill():
    record, package, bars = inputs()
    parsed = parse_package(package, record)
    assert parsed.warmup == 3
    result = evaluate_synthetic(parsed, bars)
    assert result["status"] == "synthetic_contract_tested"
    assert result["decision_count"] >= 2
    assert result["fill_count"] >= 2
    assert result["source_sha256"] == record_digest(record)
    assert evaluate_synthetic(parsed, bars) == result


def test_buy_uses_next_open_after_closed_signal():
    record, package, _ = inputs()
    parsed = parse_package(package, record)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    prices = [(100, 100), (100, 101), (101, 102), (200, 200)]
    bars = [Bar(start + index * timedelta(hours=1), Decimal(opening), Decimal(closing))
            for index, (opening, closing) in enumerate(prices)]
    result = evaluate_synthetic(parsed, bars)
    fill_price = Decimal(200) * Decimal("1.001")
    units = (Decimal(2500) / (fill_price * Decimal("1.0025"))).quantize(
        Decimal("0.00000001"), rounding=ROUND_DOWN)
    expected = Decimal(10000) - units * fill_price * Decimal("1.0025") + units * 200
    assert result["fill_count"] == 1
    assert Decimal(result["terminal_equity"]) == expected


def test_binding_unknown_expression_and_capability_fail_closed():
    record, package, _ = inputs()
    wrong = deepcopy(package)
    wrong["source"]["record_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="source record identity"):
        parse_package(wrong, record)
    unknown = deepcopy(package)
    unknown["rule"]["entry"] = {"op": "execute_python", "code": "print(1)"}
    with pytest.raises(UnsupportedPackage, match="unsupported rule"):
        parse_package(unknown, record)
    short = deepcopy(package)
    short["requirements"]["position_mode"] = "long_short"
    with pytest.raises(UnsupportedPackage, match="does not support"):
        parse_package(short, record)
    classified = evaluate_batch([unknown, short], {(record["candidate_id"], 1): record}, inputs()[2])
    assert [item["status"] for item in classified] == ["unsupported_package"] * 2


def test_external_captured_source_is_not_executable_authority():
    record, package, _ = inputs()
    external = deepcopy(record)
    external["source"]["kind"] = "paper"
    external["source"]["locator"] = "https://example.org/paper"
    external["stage"] = "captured"
    external["claim"]["economic_rationale"] = None
    external["interpretation"] = deepcopy(load_record(
        EXAMPLES / "strategy-intake-synthetic-v1.json")["interpretation"])
    package["source"]["record_sha256"] = record_digest(external)
    with pytest.raises(ValueError, match="selected implementation authority"):
        parse_package(package, external)


def test_thousand_variants_are_accounted_without_strategy_specific_code():
    record, template, bars = inputs()
    packages = []
    for index in range(1000):
        item = deepcopy(template)
        item["strategy_id"] = f"synthetic-variant-{index}"
        item["rule"]["target_fraction"] = str((index + 1) / 1000)
        packages.append(item)
    outcomes = evaluate_batch(packages, {(record["candidate_id"], 1): record}, bars)
    assert len(outcomes) == 1000
    assert all(item["status"] == "synthetic_contract_tested" for item in outcomes)
    assert len({item["package_sha256"] for item in outcomes}) == 1000
    assert evaluate_batch(packages, {(record["candidate_id"], 1): record}, bars) == outcomes
    duplicate = evaluate_batch([template, template], {(record["candidate_id"], 1): record}, bars)
    assert [item["status"] for item in duplicate] == ["synthetic_contract_tested",
                                                       "rejected_before_test"]


def test_duplicate_json_and_gapped_synthetic_input_are_rejected(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"schema_version":1,"schema_version":2}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate JSON key"):
        load_json(path)
    _, _, bars = inputs()
    fixture = load_json(EXAMPLES / "strategy-batch-synthetic-bars-v1.json")
    del fixture["bars"][3]
    with pytest.raises(ValueError, match="gap or duplicate"):
        parse_synthetic_bars(fixture)
    assert len(bars) == 12
