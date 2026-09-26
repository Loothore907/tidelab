"""Independent arithmetic and real LEAN integration for invented inputs only."""
from copy import deepcopy
from decimal import Decimal
import json
import os
from pathlib import Path

import pytest

from tidelab.package_lean_parity import (compare_traces, run_parity, validate_input)
from tidelab.strategy_batch import evaluate_synthetic, UnsupportedPackage

EXAMPLES = Path(__file__).resolve().parents[1] / "research/examples"
PACKAGE = EXAMPLES / "strategy-batch-packages/synthetic-sma-3-v1.json"
RECORD = EXAMPLES / "strategy-batch-synthetic-record-v1.json"
GAP = EXAMPLES / "strategy-parity-gap-bars-v1.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def python_gap():
    strategy, bars = validate_input(read(PACKAGE), read(RECORD), read(GAP))
    trace = []
    summary = evaluate_synthetic(strategy, bars, trace=trace)
    return trace, summary


def assert_gap(trace):
    # Independent worked example: floor(2500 / 200.7005, 8 places), then
    # buy at 200.2 and sell at 49.95 with a 0.25% fee on each notional.
    assert [row["action"] for row in trace] == ["hold", "hold", "buy", "sell", "hold"]
    assert trace[0]["entry"] is None and trace[1]["entry"] is None
    buy, sell = trace[3]["fill"], trace[4]["fill"]
    assert buy["utc"] == "2026-01-01T03:00:00Z"
    assert sell["utc"] == "2026-01-01T04:00:00Z"
    assert Decimal(buy["quantity"]) == Decimal("12.45637155")
    assert Decimal(buy["price"]) == Decimal("200.2")
    assert Decimal(buy["fee"]) == Decimal("6.2344139607750")
    assert Decimal(trace[3]["cash"]) == Decimal("7500.0000017292250")
    assert Decimal(trace[3]["equity"]) == Decimal("8621.0734412292250")
    assert Decimal(sell["price"]) == Decimal("49.95")
    assert Decimal(sell["fee"]) == Decimal("1.55548939730625")
    assert Decimal(trace[4]["cash"]) == Decimal("8120.64027125441875")
    assert Decimal(trace[4]["units"]) == 0


def test_gap_golden_values_and_existing_summary():
    trace, summary = python_gap()
    assert_gap(trace)
    assert summary["fill_count"] == 2
    assert Decimal(summary["terminal_equity"]) == Decimal("8120.64027125441875")


@pytest.mark.parametrize("field,value", [("utc", "2026-01-01T02:00:00Z"),
                                         ("fee", "6"), ("quantity", "12.45637154")])
def test_comparator_detects_timing_fee_and_quantity_mutations(field, value):
    trace, _ = python_gap()
    altered = deepcopy(trace)
    altered[3]["fill"][field] = value
    differences = compare_traces(trace, altered)
    assert [item["field"] for item in differences] == [f"trace[3].fill.{field}"]


def test_comparison_rejects_nonfinite_missing_and_wrong_types():
    assert compare_traces({"fee": "1"}, {"fee": "NaN"})
    assert compare_traces({"fee": "1"}, {})
    assert compare_traces({"fee": "1"}, {"fee": 1})
    assert compare_traces({"entry": True}, {"entry": 1})
    assert not compare_traces({"fee": "1"}, {"fee": "1.000000000000000001"})
    assert compare_traces({"fee": "1"}, {"fee": "1.00000000000000001"})


def test_parity_domain_is_bounded_without_changing_general_parser():
    fixture = read(GAP)
    fixture["bars"][0]["close"] = "100.000000001"
    with pytest.raises(UnsupportedPackage, match="decimal_domain"):
        validate_input(read(PACKAGE), read(RECORD), fixture)


def test_unsupported_attempt_is_retained_without_engine(tmp_path):
    package = read(PACKAGE)
    package["rule"]["entry"] = {"op": "ema"}
    path = tmp_path / "unsupported.json"
    path.write_text(json.dumps(package))
    output = tmp_path / "attempt"
    result = run_parity(path, RECORD, GAP, tmp_path / "absent", "absent", output)
    assert result["status"] == "unsupported"
    assert read(output / "package.json") == package
    assert (output / "identities.json").exists()
    assert (output / "attempt.json").exists()
    assert not (output / "build.log").exists()
    with pytest.raises(FileExistsError):
        run_parity(PACKAGE, RECORD, GAP, tmp_path, "absent", output)


def test_invalid_input_failure_is_retained(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text('{"x":1,"x":2}')
    result = run_parity(path, RECORD, GAP, tmp_path, "absent", tmp_path / "attempt")
    assert result["status"] == "failed"
    assert "duplicate JSON key" in result["reason"]
    assert (tmp_path / "attempt/result.json").exists()


@pytest.mark.skipif(not os.environ.get("TIDELAB_LEAN_ROOT"), reason="requires pinned LEAN and .NET 10; exercised by lean-package-parity CI")
@pytest.mark.parametrize("case", ["gap", "repeat", "logic", "open_terminal", "no_trade"])
def test_actual_lean_order_fill_portfolio_route(tmp_path, case):
    package, record, fixture = PACKAGE, RECORD, GAP
    if case == "logic":
        package = EXAMPLES / "strategy-parity-logic-v1.json"
        record = EXAMPLES / "strategy-parity-logic-record-v1.json"
    if case in {"open_terminal", "no_trade"}:
        fixture = tmp_path / "bars.json"
        bars = read(GAP)
        if case == "open_terminal":
            bars["bars"] = bars["bars"][:4]
        else:
            for bar in bars["bars"]:
                bar.update(open="100", close="100")
        fixture.write_text(json.dumps(bars))
    output = tmp_path / "attempt"
    result = run_parity(package, record, fixture, Path(os.environ["TIDELAB_LEAN_ROOT"]),
                        os.environ.get("TIDELAB_DOTNET", "dotnet"), output)
    assert result["status"] == "matched", f"{result}; evidence: {output}"
    lean = read(output / "lean.json")
    if case in {"gap", "repeat", "logic"}:
        assert lean["order_count"] == lean["fill_count"] == 2
        assert_gap(lean["trace"])
    elif case == "open_terminal":
        assert lean["order_count"] == lean["fill_count"] == 1
        assert Decimal(lean["trace"][-1]["units"]) == Decimal("12.45637155")
        assert Decimal(lean["trace"][-1]["equity"]) == Decimal("8621.0734412292250")
    else:
        assert lean["order_count"] == lean["fill_count"] == 0
        assert Decimal(lean["trace"][-1]["equity"]) == 10000
