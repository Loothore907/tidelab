"""A registered H1 development command cannot run twice under one attempt ID."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from scripts import h1_v1_export_synthetic_identity, record_local_trial
from tidelab.experiment_identity import build_experiment_identity


def test_trial_wrapper_rejects_reused_attempt_before_command(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = tmp_path / "data"
    data.mkdir()
    identity = build_experiment_identity(
        engine={"name": "lean", "version": "pinned-source",
                "source_revision": "a" * 40},
        code={"repository": "Loothore907:tidelab", "revision": "b" * 40},
        configuration={"id": "h1-v1", "sha256": "c" * 64},
        data={"source_id": "invented-h1", "revision": "v1",
              "sha256": "d" * 64, "kind": "synthetic",
              "rights_reference": "TideLab-authored"},
        cost={"model_id": "h1-cost", "revision": "v1", "sha256": "e" * 64},
        trial={"strategy_id": "h1", "strategy_version": "v1",
               "trial_id": "synthetic-check", "sequence": 1,
               "origin": "human", "parent_trial_id": None},
    )
    manifest = data / "identity.json"
    manifest.write_text(json.dumps(identity), encoding="utf-8")
    sentinel = tmp_path / "command-ran.txt"
    monkeypatch.setattr(record_local_trial, "ROOT", tmp_path)

    def launch(log: str) -> None:
        monkeypatch.setattr(sys, "argv", ["record_local_trial.py",
            "--registry", str(data / "trials.sqlite3"),
            "--identity", str(manifest), "--phase", "development",
            "--attempt-id", "one-launch", "--log", str(data / log), "--",
            sys.executable, "-c",
            f"from pathlib import Path; Path({str(sentinel)!r}).open('a').write('x')"])
        record_local_trial.main()

    launch("first.log")
    assert sentinel.read_text(encoding="utf-8") == "x"
    with pytest.raises(SystemExit) as stopped:
        launch("second.log")
    assert stopped.value.code == 2
    assert sentinel.read_text(encoding="utf-8") == "x"
    assert not (data / "second.log").exists()


def test_cost_identity_covers_each_execution_and_accounting_source(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "scripts" / "lean_fallback"
    source.mkdir(parents=True)
    names = ("TideLabH1V1ResearchReplay.cs",
             "TideLabH1ConservativeExecution.cs",
             "TideLabH1V1TrialAccounting.cs")
    for name in names:
        (source / name).write_text(name, encoding="utf-8")
    monkeypatch.setattr(h1_v1_export_synthetic_identity, "ROOT", tmp_path)
    original = h1_v1_export_synthetic_identity.cost_digest()
    for name in names:
        path = source / name
        path.write_text(name + " changed", encoding="utf-8")
        assert h1_v1_export_synthetic_identity.cost_digest() != original
        path.write_text(name, encoding="utf-8")
