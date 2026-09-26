"""Synthetic batch attempts survive runs and fail closed on changed artifacts."""

from hashlib import sha256
import json
from pathlib import Path
import shutil
import sqlite3

import pytest

from scripts import pine_subset_batch, strategy_batch
from tidelab.domain import canonical_json
from tidelab.synthetic_batch_ledger import SyntheticBatchLedger


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "research" / "examples"


def test_both_frontends_share_durable_synthetic_accounting(tmp_path, monkeypatch):
    monkeypatch.setattr(strategy_batch, "ROOT", tmp_path)
    monkeypatch.setattr(pine_subset_batch, "ROOT", tmp_path)
    examples = tmp_path / "research" / "examples"
    packages = examples / "packages"
    pine = examples / "pine"
    packages.mkdir(parents=True)
    shutil.copytree(EXAMPLES / "pine-subset-v1", pine)
    shutil.copyfile(EXAMPLES / "strategy-batch-packages" / "synthetic-sma-3-v1.json",
                    packages / "synthetic-sma-3-v1.json")
    (packages / "broken.json").write_text('{"schema_version":', encoding="utf-8")
    record = examples / "record.json"
    fixture = examples / "bars.json"
    shutil.copyfile(EXAMPLES / "strategy-batch-synthetic-record-v1.json", record)
    shutil.copyfile(EXAMPLES / "strategy-batch-synthetic-bars-v1.json", fixture)
    output_a = tmp_path / "data" / "a.json"
    output_b = tmp_path / "data" / "b.json"
    output_c = tmp_path / "data" / "c.json"
    first = strategy_batch.run(packages, [record], fixture, output_a)
    second = pine_subset_batch.run(
        pine, [pine / "synthetic-sma-2.record.json", pine / "synthetic-sma-3.record.json",
               pine / "synthetic-unsupported-ema.record.json"], fixture, output_b)
    repeated = strategy_batch.run(packages, [record], fixture, output_c)
    ledger = SyntheticBatchLedger(tmp_path / "data" / "strategy_batch" / "synthetic_trials.sqlite3")
    summary = ledger.summary()
    assert first["ledger_recorded"] and second["ledger_recorded"]
    assert len({first["ledger_run_id"], second["ledger_run_id"],
                repeated["ledger_run_id"]}) == 3
    assert first["artifact_sha256"] == repeated["artifact_sha256"]
    assert summary["runs"] == 3 and summary["open_runs"] == 0
    assert summary["variants"] == 7
    assert summary["outcomes"] == {"rejected_before_test": 2,
                                   "synthetic_contract_tested": 4, "unsupported_pine": 1}
    assert len({item["fixture_sha256"] for item in summary["cohorts"]}) == 1
    assert len({item["cost_sha256"] for item in summary["cohorts"]}) == 1
    with sqlite3.connect(ledger.path) as db:
        stages = db.execute("""SELECT parse_status, conformance_status, test_status
            FROM outcomes WHERE status='unsupported_pine'""").fetchone()
    assert stages == ("unsupported", "not_run", "not_run")
    assert ledger.complete("b.json", output_b.read_bytes())["new_completion"] is False
    changed = json.loads(output_b.read_text(encoding="utf-8"))
    changed["outcomes"][0]["status"] = "conformance_failed"
    with pytest.raises(ValueError, match="artifact identity changed"):
        ledger.complete("b.json", (canonical_json(changed) + "\n").encode("utf-8"))
    with sqlite3.connect(ledger.path) as db, pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE variants SET input_file='changed' WHERE input_index=0")


def test_open_attempt_and_denominator_recovery(tmp_path):
    ledger = SyntheticBatchLedger(tmp_path / "trials.sqlite3")
    ledger.initialize()
    fixture_sha = "a" * 64
    input_sha = "b" * 64
    run_id = ledger.begin("batch/run.json", "synthetic_strategy_batch", fixture_sha,
                          [(input_sha, "input.json")])
    assert ledger.summary()["open_runs"] == 1
    assert ledger.summary()["open_outputs"][0]["output_key"] == "batch/run.json"
    body = {"schema_version": 1, "kind": "synthetic_strategy_batch",
            "engine": "tidelab-strategy-batch-v1",
            "cost": {"fee_rate": "0.0025", "adverse_rate": "0.001",
                     "initial_cash": "10000", "quantity_unit": "0.00000001"},
            "fixture_sha256": fixture_sha, "package_count": 1,
            "scope": "synthetic_contract_only_no_market_claim",
            "summary": {"rejected_before_test": 1},
            "outcomes": [{"index": 0, "status": "rejected_before_test",
                          "file_sha256": input_sha, "reason": "ValueError"}]}
    missing = dict(body, outcomes=[])
    with pytest.raises(ValueError, match="denominator incomplete"):
        ledger.complete("batch/run.json", (canonical_json(missing) + "\n").encode())
    assert ledger.summary()["open_runs"] == 1
    wrong_cost = dict(body, cost={**body["cost"], "fee_rate": "0.0"})
    with pytest.raises(ValueError, match="identity or cost differs"):
        ledger.complete("batch/run.json", (canonical_json(wrong_cost) + "\n").encode())
    wrong_source = dict(body, outcomes=[{**body["outcomes"][0], "file_sha256": "c" * 64}])
    with pytest.raises(ValueError, match="package file outcome differs"):
        ledger.complete("batch/run.json", (canonical_json(wrong_source) + "\n").encode())
    raw = (canonical_json(body) + "\n").encode()
    result = ledger.complete("batch/run.json", raw)
    assert result == {"run_id": run_id, "artifact_sha256": sha256(raw).hexdigest(),
                      "new_completion": True}
    assert ledger.summary()["open_runs"] == 0
    assert ledger.summary()["outcomes"] == {"rejected_before_test": 1}
