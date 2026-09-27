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
