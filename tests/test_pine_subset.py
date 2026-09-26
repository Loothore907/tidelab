"""Source frontend conformance uses TideLab-authored bytes and hand fixed traces."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import shutil

import pytest

from scripts import pine_subset_batch
from tidelab.pine_subset import PineFrontendError, compile_pine
from tidelab.strategy_batch import load_json, parse_package, parse_synthetic_bars, signal_trace
from tidelab.strategy_intake import load_record, record_digest


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "research" / "examples"
SOURCES = EXAMPLES / "pine-subset-v1"


@pytest.mark.parametrize("window", [2, 3])
def test_exact_source_compiles_and_matches_independent_trace(window):
    source = SOURCES / f"synthetic-sma-{window}.pine"
    record = load_record(SOURCES / f"synthetic-sma-{window}.record.json")
    trace = load_json(SOURCES / f"synthetic-sma-{window}.trace.json")
    bars = parse_synthetic_bars(load_json(EXAMPLES / "strategy-batch-synthetic-bars-v1.json"))
    package = compile_pine(source.read_bytes(), record)
    assert package["source"]["record_sha256"] == record_digest(record)
    assert trace["source_sha256"] == sha256(source.read_bytes()).hexdigest()
    assert signal_trace(parse_package(package, record), bars) == trace["signals"]
    assert package["rule"]["target_fraction"] == ("0.4" if window == 2 else "0.25")


def test_mutations_fail_closed_without_running_source():
    source = (SOURCES / "synthetic-sma-3.pine").read_bytes()
    record = load_record(SOURCES / "synthetic-sma-3.record.json")
    cases = [
        (b"//@version=5", b"//@version=6", "source_binding_mismatch"),
        (b"ta.sma", b"ta.ema", "source_binding_mismatch"),
    ]
    for old, new, reason in cases:
        with pytest.raises(PineFrontendError, match=reason):
            compile_pine(source.replace(old, new, 1), record)
    for old, new, reason in [
        (b"//@version=5", b"//@version=6", "unsupported_pine_version"),
        (b"ta.sma", b"ta.ema", "unsupported_signal_expression"),
        (b"pyramiding=0", b"pyramiding=1", "unsupported_strategy_options"),
        (b"strategy.close(\"L\")", b"strategy.exit(\"L\")", "unsupported_order_semantics"),
    ]:
        changed = source.replace(old, new, 1)
        bound = deepcopy(record)
        bound["source"]["content_sha256"] = sha256(changed).hexdigest()
        with pytest.raises(PineFrontendError, match=reason):
            compile_pine(changed, bound)


def test_authored_unsupported_source_has_named_outcome():
    source = SOURCES / "synthetic-unsupported-ema.pine"
    record = load_record(SOURCES / "synthetic-unsupported-ema.record.json")
    assert record["stage"] == "captured"
    with pytest.raises(PineFrontendError, match="unsupported_signal_expression"):
        compile_pine(source.read_bytes(), record)


def test_batch_retains_unsupported_source_and_conformance_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(pine_subset_batch, "ROOT", tmp_path)
    source_dir = tmp_path / "research" / "examples" / "pine"
    source_dir.mkdir(parents=True)
    fixture = tmp_path / "research" / "examples" / "bars.json"
    shutil.copyfile(EXAMPLES / "strategy-batch-synthetic-bars-v1.json", fixture)
    for window in (2, 3):
        for suffix in (".pine", ".record.json", ".trace.json"):
            shutil.copyfile(SOURCES / f"synthetic-sma-{window}{suffix}",
                            source_dir / f"synthetic-sma-{window}{suffix}")
    bad = source_dir / "synthetic-sma-2.pine"
    bad.write_bytes(bad.read_bytes().replace(b"ta.sma", b"ta.ema", 1))
    record_path = source_dir / "synthetic-sma-2.record.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["source"]["content_sha256"] = sha256(bad.read_bytes()).hexdigest()
    record_path.write_text(json.dumps(record), encoding="utf-8")
    missing = source_dir / "synthetic-sma-3.trace.json"
    trace = json.loads(missing.read_text(encoding="utf-8"))
    trace["signals"][0]["entry"] = False
    missing.write_text(json.dumps(trace), encoding="utf-8")
    output = tmp_path / "data" / "run.json"
    summary = pine_subset_batch.run(
        source_dir, [source_dir / "synthetic-sma-2.record.json",
                     source_dir / "synthetic-sma-3.record.json"], fixture, output)
    assert summary["source_count"] == 2
    assert summary["summary"] == {"conformance_failed": 1, "unsupported_pine": 1}
    outcomes = json.loads(output.read_text(encoding="utf-8"))["outcomes"]
    assert [item["reason"] for item in outcomes] == ["unsupported_signal_expression",
                                                      "conformance_trace_mismatch"]
    assert all(item["source_sha256"] for item in outcomes)
    with pytest.raises(FileExistsError):
        pine_subset_batch.run(source_dir, [source_dir / "synthetic-sma-2.record.json",
                                           source_dir / "synthetic-sma-3.record.json"],
                              fixture, output)
