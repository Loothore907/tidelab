from hashlib import sha256
from pathlib import Path

import pytest

from tidelab.experiment_identity import build_experiment_identity, export_experiment_identity


def _inputs(engine_name: str = "lean") -> dict:
    root = Path(__file__).resolve().parents[1]
    fixture_digest = sha256((root / "scripts/lean_fallback/fixtures/20260101.csv").read_bytes()).hexdigest()
    cost_digest = sha256((root / "scripts/lean_fallback/TideLabConservativePaperFillProbe.cs").read_bytes()).hexdigest()
    configuration_digest = sha256(b'{"strategy":"h1-skeleton","version":1}').hexdigest()
    version = "2.0.0rc5" if engine_name == "nautilus_trader" else "pinned-source"
    source_revision = "v2.0.0rc5" if engine_name == "nautilus_trader" else "88bce0fc6fe282378ee73c54cef1090d0d7a73ee"
    return {
        "engine": {"name": engine_name, "version": version, "source_revision": source_revision},
        "code": {"repository": "Loothore907:tidelab", "revision": "aeeb2ba71bb992e9485e0213757aa84c416f587b"},
        "configuration": {"id": "h1-synthetic-v1", "sha256": configuration_digest},
        "data": {"source_id": "tl001a-invented", "revision": "v1", "sha256": fixture_digest,
                 "kind": "synthetic", "rights_reference": "TideLab-authored"},
        "cost": {"model_id": "conservative-paper", "revision": "v1", "sha256": cost_digest},
        "trial": {"strategy_id": "h1-skeleton", "strategy_version": "v1", "trial_id": "trial-001",
                  "sequence": 1, "origin": "human", "parent_trial_id": None},
    }


def test_portable_identity_changes_with_engine_cost_and_trial(tmp_path):
    lean = build_experiment_identity(**_inputs())
    assert lean == build_experiment_identity(**_inputs())
    assert set(lean) == {"schema_version", "engine", "code", "configuration", "data", "cost", "trial", "identity_sha256"}
    for changed in (
        _inputs("nautilus_trader"),
        {**_inputs(), "cost": {**_inputs()["cost"], "revision": "v2"}},
        {**_inputs(), "trial": {**_inputs()["trial"], "trial_id": "trial-002", "sequence": 2,
                                    "parent_trial_id": "trial-001"}},
    ):
        assert build_experiment_identity(**changed)["identity_sha256"] != lean["identity_sha256"]
    destination = tmp_path / "experiment.json"
    export_experiment_identity(lean, destination, public_synthetic=True)
    exported = destination.read_text(encoding="utf-8")
    assert lean["identity_sha256"] in exported
    assert "20260101" not in exported
    with pytest.raises(FileExistsError):
        export_experiment_identity(lean, destination)


def test_public_export_and_incomplete_provenance_fail_closed(tmp_path):
    inputs = _inputs()
    inputs["data"] = {**inputs["data"], "kind": "third_party", "rights_reference": "unknown"}
    identity = build_experiment_identity(**inputs)
    with pytest.raises(ValueError, match="public export"):
        export_experiment_identity(identity, tmp_path / "public.json", public_synthetic=True)
    assert not (tmp_path / "public.json").exists()
    export_experiment_identity(identity, tmp_path / "local.json")
    with pytest.raises(ValueError, match="exactly"):
        build_experiment_identity(**{**_inputs(), "data": {"source_id": "missing"}})
    with pytest.raises(ValueError, match="portable"):
        build_experiment_identity(**{**_inputs(), "code": {"repository": "local", "revision": "C:/private/path"}})
    with pytest.raises(ValueError, match="SHA-256"):
        build_experiment_identity(**{**_inputs(), "cost": {**_inputs()["cost"], "sha256": "unknown"}})
    synthetic = build_experiment_identity(**{**_inputs(), "data": {**_inputs()["data"], "rights_reference": "unknown"}})
    with pytest.raises(ValueError, match="public export"):
        export_experiment_identity(synthetic, tmp_path / "unverified.json", public_synthetic=True)
    with pytest.raises(ValueError, match="unexpected fields"):
        export_experiment_identity({**synthetic, "raw_data": "private"}, tmp_path / "extra.json")
    with pytest.raises(ValueError, match="digest"):
        export_experiment_identity({**synthetic, "identity_sha256": "0" * 64}, tmp_path / "tampered.json")
