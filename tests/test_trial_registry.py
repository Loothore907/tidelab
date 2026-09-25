from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

import pytest

from tidelab.experiment_identity import build_experiment_identity
from tidelab.trial_registry import TrialRegistry


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _identity(trial_id: str = "trial-1", sequence: int = 1,
              version: str = "v1") -> dict:
    return build_experiment_identity(
        engine={"name": "lean", "version": "pinned-source", "source_revision": "a" * 40},
        code={"repository": "Loothore907:tidelab", "revision": "b" * 40},
        configuration={"id": "h1-v1", "sha256": "c" * 64},
        data={"source_id": "invented-h1", "revision": "v1", "sha256": "d" * 64,
              "kind": "synthetic", "rights_reference": "TideLab-authored"},
        cost={"model_id": "h1-cost", "revision": "v1", "sha256": "e" * 64},
        trial={"strategy_id": "h1", "strategy_version": version,
               "trial_id": trial_id, "sequence": sequence, "origin": "human",
               "parent_trial_id": None},
    )


def test_restart_preserves_failure_and_open_attempt_blocks_new_launch(tmp_path: Path) -> None:
    path = tmp_path / "trials.sqlite3"
    registry = TrialRegistry(path)
    registry.initialize()
    identity = _identity()
    assert registry.start("attempt-1", identity, "development", NOW)
    restarted = TrialRegistry(path)
    assert restarted.status("attempt-1") == "open"
    with pytest.raises(RuntimeError, match="unfinished"):
        restarted.start("attempt-2", identity, "development", NOW + timedelta(seconds=1))
    assert restarted.finish("attempt-1", "failed", NOW + timedelta(seconds=2),
                            reason_code="exit-7", artifact_sha256="f" * 64)
    assert restarted.finish("attempt-1", "failed", NOW + timedelta(seconds=2),
                            reason_code="exit-7", artifact_sha256="f" * 64) is False
    assert restarted.status("attempt-1") == "failed"
    assert restarted.start("attempt-2", identity, "development", NOW + timedelta(seconds=3))
    assert restarted.finish("attempt-2", "completed", NOW + timedelta(seconds=4))
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM trial_attempts").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM trial_outcomes").fetchone()[0] == 2
        with pytest.raises(sqlite3.DatabaseError, match="immutable"):
            db.execute("DELETE FROM trial_attempts WHERE attempt_id='attempt-1'")


def test_validation_and_untouched_cannot_be_opened_twice(tmp_path: Path) -> None:
    registry = TrialRegistry(tmp_path / "trials.sqlite3")
    registry.initialize()
    first = _identity()
    registry.start("validation-1", first, "validation", NOW)
    registry.finish("validation-1", "aborted", NOW + timedelta(seconds=1),
                    reason_code="fixture-error")
    with pytest.raises(RuntimeError, match="already opened"):
        registry.start("validation-2", first, "validation", NOW + timedelta(seconds=2))
    correction = _identity("trial-2", 2)
    registry.start("validation-2", correction, "validation", NOW + timedelta(seconds=2))
    registry.finish("validation-2", "completed", NOW + timedelta(seconds=3))
    registry.start("untouched-1", correction, "untouched", NOW + timedelta(seconds=4))
    registry.finish("untouched-1", "failed", NOW + timedelta(seconds=5),
                    reason_code="replay-failed")
    with pytest.raises(RuntimeError, match="already opened"):
        registry.start("untouched-2", first, "untouched", NOW + timedelta(seconds=6))
    v2 = _identity("trial-3", 3, "v2")
    assert registry.start("untouched-v2", v2, "untouched", NOW + timedelta(seconds=7))


def test_identity_and_terminal_record_cannot_change(tmp_path: Path) -> None:
    registry = TrialRegistry(tmp_path / "trials.sqlite3")
    registry.initialize()
    identity = _identity()
    with pytest.raises(ValueError, match="digest"):
        registry.start("attempt-1", {**identity, "identity_sha256": "0" * 64},
                       "development", NOW)
    assert registry.start("attempt-1", identity, "development", NOW)
    assert registry.start("attempt-1", identity, "development", NOW) is False
    with pytest.raises(ValueError, match="different terms"):
        registry.start("attempt-1", identity, "validation", NOW)
    with pytest.raises(ValueError, match="before"):
        registry.finish("attempt-1", "completed", NOW - timedelta(seconds=1))
    registry.finish("attempt-1", "completed", NOW + timedelta(seconds=1),
                    artifact_sha256="f" * 64)
    with pytest.raises(ValueError, match="differently"):
        registry.finish("attempt-1", "failed", NOW + timedelta(seconds=2),
                        reason_code="late-correction")
    assert registry.status("attempt-1") == "completed"
