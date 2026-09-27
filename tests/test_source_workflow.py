"""Source-to-results acceptance on authored prices; no private stores or grants."""
from copy import deepcopy
from decimal import Decimal
import json
import os
from pathlib import Path
import shutil
import sqlite3

import pytest

from tidelab import source_workflow as workflow, historical_batch as batch
from tidelab.synthetic_batch_ledger import SyntheticBatchLedger

CORPUS = workflow.EXAMPLES / "source-workflow-v1"


@pytest.fixture
def setup(tmp_path, monkeypatch):
    examples = tmp_path / "examples"
    shutil.copytree(CORPUS, examples)
    monkeypatch.setattr(workflow, "EXAMPLES", examples)
    monkeypatch.setattr(workflow, "DATA", tmp_path / "output")
    return examples / "manifest.json", tmp_path / "output/run"


def change(path, mutate):
    value = batch.read(path)
    mutate(value)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_corpus_complete_identities_determinism_and_independent_trace(setup):
    manifest, output = setup
    first = workflow.run(manifest, output)
    second = workflow.run(manifest, output.with_name("second"))
    assert first["semantic_sha256"] == second["semantic_sha256"]
    assert first["trace_sha256"] == second["trace_sha256"]
    assert first["historical"]["batch_id"] != second["historical"]["batch_id"]
    assert first["compilation_counts"] == {"compiled": 6, "invalid": 1, "unsupported": 2, "needs_source_parser": 1}
    assert first["job_counts"] == {"completed": 10, "duplicate": 4, "failed": 2}
    assert first["distinct_rule_structures"] == 3
    assert first["historical"]["submitted_jobs"] == 16
    assert first["historical"]["attempt_count"] == 12
    assert first["parity"]["status"] == "not_run"
    assert len(first["inputs"]) == 10
    for item in first["inputs"]:
        assert len(item["jobs"]) == (2 if item["status"] == "compiled" else 0)
        for index in item["jobs"]:
            assert first["ordered_jobs"][index]["package"] == item["id"]
            assert first["admission"][index]["inputs"]["package_sha256"] == item["package_sha256"]
            assert first["admission"][index]["inputs"]["record_sha256"] == item["record_sha256"]
    assert [first["admission"][i]["duplicate_of"] for i in (2,3,8,9)] == [0,1,0,1]
    ledger = SyntheticBatchLedger(output / "sources.sqlite3").summary()
    assert ledger["open_runs"] == 0
    # Independent gap arithmetic at common 0.03-unit lot size: 12.45 units,
    # entry at 200.2, exit at 49.95, 0.25% notional fees.
    trace = [json.loads(x) for x in (output / "attempt/job-0/trace.jsonl").read_text().splitlines()]
    assert trace[0]["index"] == 3 and trace[0]["action"] == "buy" and trace[0]["fill"] is None
    assert trace[1]["fill"]["index"] == 4
    assert Decimal(trace[1]["fill"]["quantity"]) == Decimal("12.45")
    expected = Decimal(10000) - Decimal("12.45") * Decimal("200.2") * Decimal("1.0025") + Decimal("12.45") * Decimal("49.95") * Decimal("0.9975")
    assert Decimal(trace[2]["cash"]) == expected
    calendar = [json.loads(x) for x in (output / "attempt/job-6/trace.jsonl").read_text().splitlines()]
    assert [r["index"] for r in calendar if r["action"] == "buy"] == [3]
    assert [r["index"] for r in calendar if r["action"] == "sell"] == [27]
    assert [r["fill"]["index"] for r in calendar if r["fill"]] == [4,28]
    assert first["historical"]["jobs"][12]["metrics"]["net_return"] == "0"
    assert first["historical"]["jobs"][14]["metrics"]["fill_count"] == 1
    for index in (10,11):
        assert "below executable unit" in batch.read(output / f"attempt/job-{index}/failure.json")["reason"]


@pytest.mark.parametrize("damage", ["source", "record", "trace", "history"])
def test_exact_identity_failure_retains_every_input_before_backend(setup, monkeypatch, damage):
    manifest, output = setup
    value = batch.read(manifest)
    ref = value["history"] if damage == "history" else value["inputs"][0][damage]
    path = manifest.parent / ref["path"]
    path.write_bytes(path.read_bytes() + b" ")
    original = workflow._capture
    def check_inventory(*args):
        with sqlite3.connect(output / "sources.sqlite3") as db:
            assert db.execute("SELECT COUNT(*) FROM variants").fetchone()[0] == 10
        return original(*args)
    monkeypatch.setattr(workflow, "_capture", check_inventory)
    result = workflow.run(manifest, output)
    assert len(result["inputs"]) == 10
    assert result["inputs"][0]["status"] == "invalid"
    assert "identity" in result["inputs"][0]["reason"]
    assert result["inputs"][0]["jobs"] == []
    if damage == "history":
        assert not (output / "history.sqlite3").exists()
        assert not (output / "trials.sqlite3").exists()


def test_conformance_mismatch_is_not_silently_rebaselined(setup):
    manifest, output = setup
    value = batch.read(manifest)
    path = manifest.parent / value["inputs"][0]["trace"]["path"]
    change(path, lambda t: t["signals"][0].update(entry=False))
    value["inputs"][0]["trace"]["sha256"] = batch.digest(path.read_bytes())
    manifest.write_text(json.dumps(value), encoding="utf-8")
    result = workflow.run(manifest, output)
    assert result["inputs"][0]["status"] == "conformance_failed"
    assert result["inputs"][0]["jobs"] == []


def test_add_supported_input_requires_configuration_only(setup):
    manifest, output = setup
    value = batch.read(manifest)
    originals = CORPUS.parent / "pine-subset-v1"
    def file(name, raw):
        (manifest.parent / name).write_bytes(raw)
        return {"path": name, "sha256": batch.digest(raw)}
    source = file("additional.pine", (originals / "synthetic-sma-2.pine").read_bytes())
    record = file("additional.record.json", (originals / "synthetic-sma-2.record.json").read_bytes())
    # Independent SMA(2) truth sets on this fixed history: equality from bar 7.
    trace = file("additional.trace.json", json.dumps({"source_sha256": source["sha256"],
        "history_sha256": value["history"]["sha256"], "signals": [
            {"index": i, "entry": i in (1,2,3,6), "exit": i in (4,5)} for i in range(1,29)]}).encode())
    item = {"id": "additional-pine", "format": "pine_subset", "source": source, "record": record, "trace": trace}
    value["inputs"].append(item)
    manifest.write_text(json.dumps(value), encoding="utf-8")
    result = workflow.run(manifest, output)
    assert result["inputs"][-1]["status"] == "compiled"
    assert result["inputs"][-1]["jobs"] == [12,13]
    assert result["job_counts"] == {"completed": 12, "duplicate": 4, "failed": 2}
    assert result["distinct_rule_structures"] == 3


class Crash(BaseException):
    pass


@pytest.mark.parametrize("point", ["started", "last_artifact"])
def test_interruption_uses_existing_recovery_never_replay(setup, monkeypatch, point):
    manifest, output = setup
    artifacts = 0
    def stop(stage):
        nonlocal artifacts
        if stage == "artifact":
            artifacts += 1
        if stage == point or (point == "last_artifact" and artifacts == 16):
            raise Crash()
    with pytest.raises(Crash):
        workflow.run(manifest, output, checkpoint=stop)
    for name in ("replay_package", "read_partition"):
        monkeypatch.setattr(batch, name, lambda *a, **kw: pytest.fail("replay/data read during recovery"))
    monkeypatch.setattr(workflow, "compile_pine", lambda *a: pytest.fail("recompile"))
    monkeypatch.setattr(workflow, "run_parity", lambda *a, **kw: pytest.fail("LEAN rerun"))
    if point == "started":
        with pytest.raises(ValueError, match="explicit_abort"):
            workflow.recover(output)
    result = workflow.recover(output, abort=point == "started")
    assert len(result["historical"]["jobs"]) == 16
    assert result["historical"]["terminal_attempt_count"] == 12
    assert result["job_counts"] == ({"aborted": 16} if point == "started" else {"completed": 10, "duplicate": 4, "failed": 2})
    assert workflow.recover(output) == result


def test_recovery_rejects_tampered_source_artifact(setup):
    manifest, output = setup
    workflow.run(manifest, output)
    path = output / "sources/source-0.raw"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="digest_mismatch"):
        workflow.recover(output)


def test_output_cannot_target_existing_private_stores(setup):
    manifest, output = setup
    with pytest.raises(ValueError, match="dedicated_synthetic_output"):
        workflow.run(manifest, output.parents[1] / "research_program")
    workflow.run(manifest, output)
    with pytest.raises(FileExistsError):
        workflow.run(manifest, output)


@pytest.mark.skipif(not os.environ.get("TIDELAB_LEAN_ROOT"), reason="actual pinned LEAN CI")
def test_manifest_through_actual_pinned_lean_and_artifact_recovery(setup, monkeypatch):
    manifest, output = setup
    result = workflow.run(manifest, output, lean_root=Path(os.environ["TIDELAB_LEAN_ROOT"]),
                          dotnet=os.environ.get("TIDELAB_DOTNET", "dotnet"))
    assert result["status"] == "accounted"
    assert result["parity"]["status"] == "matched", result["parity"]
    assert [x["job_index"] for x in result["parity"]["cases"]] == [0,1,4,5,6,7]
    monkeypatch.setattr(batch, "replay_package", lambda *a, **kw: pytest.fail("replay"))
    monkeypatch.setattr(workflow, "run_parity", lambda *a, **kw: pytest.fail("parity replay"))
    assert workflow.recover(output) == result


EXPANDED = CORPUS.parent / "source-workflow-v2"


def assert_expanded(result):
    expected = batch.read(EXPANDED / "expected.json")
    assert result["status"] == "accounted"
    assert len(result["inputs"]) == expected["inputs"]
    assert result["compilation_counts"] == expected["compilation_counts"]
    assert result["job_counts"] == expected["job_counts"]
    assert result["distinct_rule_structures"] == expected["distinct_rule_structures"]
    assert result["historical"]["submitted_jobs"] == expected["jobs"]
    assert result["historical"]["attempt_count"] == expected["attempts"]
    assert result["historical"]["terminal_attempt_count"] == expected["attempts"]
    for item in result["inputs"]:
        assert len(item["jobs"]) == (2 if item["status"] == "compiled" else 0)
        if item["id"] in expected["rejections"]:
            status, reason = expected["rejections"][item["id"]]
            assert item["status"] == status
            if reason is not None:
                assert item["reason"] == reason


def test_expanded_corpus_with_unchanged_workflow(tmp_path, monkeypatch):
    monkeypatch.setattr(workflow, "DATA", tmp_path)
    first = workflow.run(EXPANDED / "manifest.json", tmp_path / "first")
    second = workflow.run(EXPANDED / "manifest.json", tmp_path / "second")
    assert_expanded(first)
    assert_expanded(second)
    assert first["semantic_sha256"] == second["semantic_sha256"]
    assert first["trace_sha256"] == second["trace_sha256"]
    assert len(first["trace_sha256"]) == 18  # Includes both retained partial failures.
    # Independent fill locations: channel rejects the current wick as its own
    # breakout reference; RSI waits for its existing below-30 / above-70 signals.
    for index, expected_fills in ((14,[484,486]), (16,[481,483,486,487])):
        trace = [json.loads(line) for line in (tmp_path / f"first/attempt/job-{index}/trace.jsonl").read_text().splitlines()]
        assert [r["fill"]["index"] for r in trace if r["fill"]] == expected_fills
    monkeypatch.setattr(batch, "replay_package", lambda *a, **kw: pytest.fail("replay during recovery"))
    assert workflow.recover(tmp_path / "first") == first


def test_expanded_expected_traces_independent_arithmetic():
    """Audit this fixed fixture only; no package parser/evaluator is called."""
    from datetime import datetime, timedelta
    from fractions import Fraction
    manifest = batch.read(EXPANDED / "manifest.json")
    history = batch.read(EXPANDED / "history.json")["bars"]
    closes = [Fraction(b["close"]) for b in history]
    # The first 480 equal closes imply zero gain/loss. The selected LEAN contract
    # defines zero-loss RSI as 100. Independent rational recurrence thereafter.
    gain = loss = Fraction(0)
    rsi = []
    for i, close in enumerate(closes):
        if i:
            delta = close - closes[i-1]
            gain = (13 * gain + max(delta, 0)) / 14
            loss = (13 * loss + max(-delta, 0)) / 14
        rsi.append(Fraction(100) if not loss else 100 * gain / (gain + loss))
    for item in manifest["inputs"]:
        if item["trace"] is None:
            continue
        trace = batch.read(EXPANDED / item["trace"]["path"])["signals"]
        for row in trace:
            i = row["index"]
            if item["id"] == "calendar":
                close_time = datetime.fromisoformat(history[i]["start_utc"].replace("Z", "+00:00")) + timedelta(hours=1)
                entry = close_time.isoweekday() == 1 and close_time.hour == 0
                exit_signal = close_time.isoweekday() == 2 and close_time.hour == 0
            elif item["id"] == "rsi":
                entry, exit_signal = rsi[i] < 30, rsi[i] > 70
            elif item["id"] == "channel":
                entry = closes[i] > max(Fraction(b["high"]) for b in history[i-480:i])
                exit_signal = closes[i] < min(Fraction(b["low"]) for b in history[i-240:i])
            else:
                window = 2 if item["id"] == "pine-sma2" else 3
                average = sum(closes[i-window+1:i+1]) / window
                entry, exit_signal = closes[i] > average, closes[i] < average
                if item["id"] == "logic":
                    entry = entry and closes[i] > closes[i-1]
                    exit_signal = exit_signal or closes[i] <= closes[i-1]
            assert (row["entry"], row["exit"]) == (entry, exit_signal), (item["id"], i)
    # Newly supplied normalized rules are exact reuse, not a retuned hypothesis.
    from tidelab.rsi_private import package as rsi_package
    from tidelab.channel_breakout import package as channel_package
    for name, builder in (("rsi", rsi_package), ("channel", channel_package)):
        assert batch.read(EXPANDED / f"{name}.json") == builder(batch.read(EXPANDED / f"{name}.record.json"))


@pytest.mark.skipif(not os.environ.get("TIDELAB_LEAN_ROOT"), reason="actual pinned LEAN CI")
def test_expanded_corpus_actual_lean(tmp_path, monkeypatch):
    monkeypatch.setattr(workflow, "DATA", tmp_path)
    result = workflow.run(EXPANDED / "manifest.json", tmp_path / "expanded",
        lean_root=Path(os.environ["TIDELAB_LEAN_ROOT"]), dotnet=os.environ.get("TIDELAB_DOTNET", "dotnet"))
    assert_expanded(result)
    assert result["parity"]["status"] == "matched", result["parity"]
    assert [r["job_index"] for r in result["parity"]["cases"]] == batch.read(EXPANDED / "expected.json")["parity_job_indices"]


COMMENTS = CORPUS.parent / "pine-comments-v2"


def assert_comments(result):
    assert result["status"] == "accounted"
    assert result["compilation_counts"] == {"compiled": 3, "unsupported": 3}
    assert result["distinct_rule_structures"] == 1  # Comments are not new rules.
    assert result["job_counts"] == {"completed": 6, "duplicate": 4}
    assert result["historical"]["submitted_jobs"] == 10
    assert result["historical"]["attempt_count"] == 6
    assert [x["reason"] for x in result["inputs"][3:]] == [
        "unsupported_pine_directive", "unsupported_strategy_options", "unsupported_signal_expression"]
    for item in result["inputs"]:
        assert len(item["jobs"]) == (2 if item["status"] == "compiled" else 0)
        for index in item["jobs"]:
            assert result["admission"][index]["inputs"]["package_sha256"] == item["package_sha256"]
    assert len({x["file_sha256"] for x in result["inputs"][:3]}) == 3
    assert len({x["package_sha256"] for x in result["inputs"][:3]}) == 3
    assert [result["admission"][i]["duplicate_of"] for i in (2,3,4,5)] == [0,1,0,1]


def test_comment_corpus_determinism_trace_and_no_replay_recovery(tmp_path, monkeypatch):
    from fractions import Fraction
    manifest = batch.read(COMMENTS / "manifest.json")
    history = batch.read(COMMENTS / manifest["history"]["path"])["bars"]
    closes = [Fraction(b["close"]) for b in history]
    # Independent direct arithmetic on every frozen expected source trace.
    for item in manifest["inputs"][:3]:
        trace = batch.read(COMMENTS / item["trace"]["path"])
        assert trace["source_sha256"] == item["source"]["sha256"]
        for row in trace["signals"]:
            i = row["index"]
            average = sum(closes[i-2:i+1]) / 3
            assert (row["entry"], row["exit"]) == (closes[i] > average, closes[i] < average)
    monkeypatch.setattr(workflow, "DATA", tmp_path)
    first = workflow.run(COMMENTS / "manifest.json", tmp_path / "first")
    second = workflow.run(COMMENTS / "manifest.json", tmp_path / "second")
    assert_comments(first)
    assert_comments(second)
    assert first["semantic_sha256"] == second["semantic_sha256"]
    assert first["trace_sha256"] == second["trace_sha256"]
    monkeypatch.setattr(batch, "replay_package", lambda *a, **kw: pytest.fail("replay"))
    monkeypatch.setattr(workflow, "compile_pine", lambda *a, **kw: pytest.fail("compile"))
    assert workflow.recover(tmp_path / "first") == first
    # Even a change confined to a comment invalidates retained source identity.
    path = tmp_path / "first/sources/source-0.raw"
    path.write_bytes(path.read_bytes() + b"// another comment\n")
    with pytest.raises(ValueError, match="digest_mismatch"):
        workflow.recover(tmp_path / "first")


def test_grammar_selection_fails_closed_and_is_pine_only(setup):
    manifest, output = setup
    change(manifest, lambda m: m["inputs"][1].update(grammar_version="unknown-version"))
    result = workflow.run(manifest, output)
    assert result["inputs"][1]["status"] == "unsupported"
    assert result["inputs"][1]["reason"] == "unsupported_grammar_version"
    assert result["inputs"][1]["jobs"] == []
    change(manifest, lambda m: m["inputs"][0].update(grammar_version="tidelab-pine-v5-subset-2"))
    with pytest.raises(ValueError, match="invalid_source_inventory"):
        workflow.run(manifest, output.with_name("invalid"))


@pytest.mark.skipif(not os.environ.get("TIDELAB_LEAN_ROOT"), reason="actual pinned LEAN CI")
def test_comment_corpus_actual_lean(tmp_path, monkeypatch):
    monkeypatch.setattr(workflow, "DATA", tmp_path)
    result = workflow.run(COMMENTS / "manifest.json", tmp_path / "comments",
        lean_root=Path(os.environ["TIDELAB_LEAN_ROOT"]), dotnet=os.environ.get("TIDELAB_DOTNET", "dotnet"))
    assert_comments(result)
    assert result["parity"]["status"] == "matched", result["parity"]
    assert [r["job_index"] for r in result["parity"]["cases"]] == [0,1]
    monkeypatch.setattr(batch, "replay_package", lambda *a, **kw: pytest.fail("replay"))
    monkeypatch.setattr(workflow, "run_parity", lambda *a, **kw: pytest.fail("parity replay"))
    assert workflow.recover(tmp_path / "comments") == result
