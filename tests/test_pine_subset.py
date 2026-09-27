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


COMMENT_VERSION = "tidelab-pine-v5-subset-2"


def compile_changed(raw, record=None, **kwargs):
    bound = deepcopy(record or load_record(SOURCES / "synthetic-sma-3.record.json"))
    bound["source"]["content_sha256"] = sha256(raw).hexdigest()
    return compile_pine(raw, bound, grammar_version=COMMENT_VERSION, **kwargs)


def test_comments_preserve_raw_identity_and_rule_at_every_statement_boundary():
    raw = (SOURCES / "synthetic-sma-3.pine").read_bytes()
    record = load_record(SOURCES / "synthetic-sma-3.record.json")
    original = compile_pine(raw, record)
    lines = raw.splitlines(keepends=True)
    for i in range(1, len(lines) + 1):
        changed = b"".join(lines[:i]) + b" \t// quoted text, // delimiters and code are inert\n" + b"".join(lines[i:])
        compiled = compile_changed(changed)
        assert compiled["rule"] == original["rule"]
        assert compiled["requirements"] == original["requirements"]
        assert compiled["strategy_id"] == "synthetic-pine-" + sha256(changed).hexdigest()[:16]
        assert compiled["source"]["record_sha256"] != original["source"]["record_sha256"]
        with pytest.raises(PineFrontendError, match="source_binding_mismatch"):
            compile_pine(changed, record, grammar_version=COMMENT_VERSION)
        bound = deepcopy(record)
        bound["source"]["content_sha256"] = sha256(changed).hexdigest()
        with pytest.raises(PineFrontendError, match="unsupported_extra_statement"):
            compile_pine(changed, bound)  # Old manifests still select grammar 1.
    assert compile_changed(raw) == original


@pytest.mark.parametrize("suffix,reason", [
    (b"//@version=6\n", "unsupported_pine_directive"),
    (b" // @strategy_alert_message ignored?\n", "unsupported_pine_directive"),
    (b"\t//@version=5\n", "unsupported_pine_directive"),
    (b"\n", "unsupported_extra_statement"),
    (b"average = ta.sma(close, 3)\n", "unsupported_extra_statement"),
    (b"/* block comment */\n", "unsupported_extra_statement"),
    (b"// comment\r\n", "invalid_source_encoding"),
    (b"// comment\xe2\x80\xa8strategy.entry()\n", "invalid_source_encoding"),
    (b"// comment\x0bcode\n", "invalid_source_encoding"),
    (b"// \xff\n", "invalid_utf8"),
    (b"// " + b"x" * 16384 + b"\n", "source_size_exceeded"),
])
def test_comment_grammar_rejects_directives_and_unsupported_boundaries(suffix, reason):
    raw = (SOURCES / "synthetic-sma-3.pine").read_bytes()
    with pytest.raises(PineFrontendError, match=reason):
        compile_changed(raw + suffix)


@pytest.mark.parametrize("old,new,reason", [
    (b"//@version=5", b"// preamble\n//@version=5", "unsupported_pine_version"),
    (b"process_orders_on_close=false", b"process_orders_on_close=true", "unsupported_strategy_options"),
    (b"calc_on_every_tick=false", b"calc_on_every_tick=true", "unsupported_strategy_options"),
    (b"pyramiding=0", b"pyramiding=1", "unsupported_strategy_options"),
    (b"ta.sma(close, 3)", b"ta.sma(close, 3) // trailing", "unsupported_signal_expression"),
    (b"ta.sma", b"ta.rsi", "unsupported_signal_expression"),
    (b'    strategy.entry("L", strategy.long)', b'// strategy.entry("L", strategy.long)', "incomplete_subset_program"),
    (b'    strategy.entry("L", strategy.long)', b'strategy.entry("L", strategy.long)', "unsupported_order_semantics"),
    (b'strategy.close("L")', b'strategy.exit("L")', "unsupported_order_semantics"),
])
def test_comments_cannot_relax_execution_or_expression_contract(old, new, reason):
    raw = (SOURCES / "synthetic-sma-3.pine").read_bytes() + b"// ordinary comment\n"
    with pytest.raises(PineFrontendError, match=reason):
        compile_changed(raw.replace(old, new, 1))


IMPORT_VERSION = "tidelab-pine-v5-subset-3"
ALIAS = EXAMPLES / "source-workflow-v2/pine-sma-alias.pine"


def compile_import(raw):
    record = deepcopy(load_record(SOURCES / "synthetic-sma-3.record.json"))
    record["source"]["content_sha256"] = sha256(raw).hexdigest()
    return compile_pine(raw, record, grammar_version=IMPORT_VERSION)


def test_import_aliases_formatting_and_original_identity():
    raw = ALIAS.read_bytes()
    expected = compile_changed((SOURCES / "synthetic-sma-3.pine").read_bytes())
    forms = [raw,
        raw.replace(b"average = ta.sma(close, 3)", b"period = 3\nprice = close\naverage = ta.sma(price, period)\ncopy = average")
           .replace(b"close > average", b"price > copy").replace(b"close < average", b"price < copy"),
        raw.replace(b"average = ta.sma(close, 3)", b"\n// explanation\naverage=ta.sma ( close , 3 ) // trailing\n")
           .replace(b"    strategy", b"\tstrategy"),
        raw.replace(b"entrySignal", b"enter").replace(b"exitSignal", b"leave"),
        raw.replace(b"if entrySignal", b"if close > average")]
    for form in forms:
        result = compile_import(form)
        assert result["rule"] == expected["rule"]
        assert result["strategy_id"] == "synthetic-pine-" + sha256(form).hexdigest()[:16]
        with pytest.raises(PineFrontendError):
            compile_changed(form)  # Explicit old grammar still rejects aliases.


@pytest.mark.parametrize("old,new,reason", [
    (b"average =", b"var average =", "unsupported_declaration"),
    (b"average =", b"varip average =", "unsupported_declaration"),
    (b"average =", b"    average =", "unsupported_declaration"),
    (b"entrySignal =", b"average = close\nentrySignal =", "unsupported_alias_name:average"),
    (b"entrySignal =", b"average := close\nentrySignal =", "unsupported_token"),
    (b"average =", b"close = 3\naverage =", "unsupported_alias_name:close"),
    (b"average =", b"_ = 3\naverage =", "unsupported_alias_name:_"),
    (b"ta.sma(close, 3)", b"future\nfuture = ta.sma(close, 3)", "unsupported_reference:future"),
    (b"ta.sma(close, 3)", b"average", "unsupported_reference:average"),
    (b"ta.sma(close, 3)", b"ta.ema(close, 3)", "unsupported_signal_expression"),
    (b"ta.sma(close, 3)", b"ta.sma(close, close)", "unsupported_sma_arguments"),
    (b"ta.sma(close, 3)", b"ta.sma(close, 1)", "unsupported_sma_window"),
    (b"ta.sma(close, 3)", b"ta.sma(close, 10001)", "unsupported_sma_window"),
    (b"close > average", b"cl ose > average", "unsupported_signal_expression"),
    (b"close > average", b"close >= average", "unsupported_signal_expression"),
    (b"close < average", b"close < ta.sma(close, 2)", "unsupported_signal_pair"),
    (b"if entrySignal", b"if average", "unsupported_signal_pair"),
    (b"    strategy.entry", b"strategy.entry", "unsupported_order_semantics"),
    (b"    strategy.entry", b"        strategy.entry", "unsupported_order_semantics"),
    (b"if entrySignal", b" if entrySignal", "unsupported_order_semantics"),
    (b"process_orders_on_close=false", b"process_orders_on_close=true", "unsupported_strategy_options"),
    (b"calc_on_every_tick=false", b"calc_on_every_tick=true", "unsupported_strategy_options"),
    (b"pyramiding=0", b"pyramiding=1", "unsupported_strategy_options"),
    (b"strategy.close", b"strategy.exit", "unsupported_order_semantics"),
    (b"strategy.long", b"strategy.short", "unsupported_order_semantics"),
    (b"average =", b"// @directive\naverage =", "unsupported_pine_directive"),
    (b"average =", b"/* comment */\naverage =", "unsupported_token"),
    (b"average =", b"// comment\xe2\x80\xa8\naverage =", "invalid_source_encoding"),
    (b"\n", b"\r\n", "invalid_source_encoding"),
])
def test_import_rejects_ambiguous_or_changed_semantics(old, new, reason):
    with pytest.raises(PineFrontendError, match=reason):
        compile_import(ALIAS.read_bytes().replace(old, new, 1))


def test_import_bounds_and_raw_hash_binding():
    raw = ALIAS.read_bytes()
    many = b"".join(f"alias{i} = close\n".encode() for i in range(65))
    with pytest.raises(PineFrontendError, match="unsupported_alias_limit"):
        compile_import(raw.replace(b"average =", many + b"average ="))
    with pytest.raises(PineFrontendError, match="source_size_exceeded"):
        compile_import(raw + b"//" + b"x" * 16384 + b"\n")
    record = deepcopy(load_record(SOURCES / "synthetic-sma-3.record.json"))
    record["source"]["content_sha256"] = sha256(raw).hexdigest()
    with pytest.raises(PineFrontendError, match="source_binding_mismatch"):
        compile_pine(raw + b"// changed\n", record, grammar_version=IMPORT_VERSION)
