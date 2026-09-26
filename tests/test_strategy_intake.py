from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from tidelab.strategy_intake import (IntakeRegistry, load_record, record_digest,
                                     validate_record)


EXAMPLE = Path(__file__).resolve().parents[1] / "research/examples/strategy-intake-synthetic-v1.json"


def captured() -> dict:
    return deepcopy(json.loads(EXAMPLE.read_text(encoding="utf-8")))


def specified(kind: str = "paper") -> dict:
    item = captured()
    item["candidate_id"] = f"invented-{kind.replace('_', '-')}-candidate"
    item["stage"] = "specified"
    item["source"].update(kind=kind, locator="https://example.invalid/source",
                          revision="v1")
    if kind == "repository":
        item["source"]["revision"] = "a" * 40
    if kind == "tradingview_script":
        item["source"]["content_sha256"] = "b" * 64
        item["source"]["revision"] = "sha256:" + "b" * 64
    item["claim"]["economic_rationale"] = "An invented mechanism for schema testing."
    item["interpretation"].update(
        product_scope="invented spot product", timeframe="one hour",
        required_data=["closed hourly bars"], required_capabilities=["long or cash"],
        entry="Enter after an invented closed-bar event.",
        exit="Exit after a second invented closed-bar event.",
        sizing="Use a fixed hypothetical allocation.",
        timing="Signal after close; earliest fill at next open.", open_questions=[])
    return item


def selected() -> dict:
    item = specified()
    item["version"] = 2
    item["stage"] = "implementation_selected"
    item["rights"].update(implementation_use="documented",
                          evidence_reference="https://example.invalid/rights")
    item["decision"].update(
        issue_url="https://github.com/Loothore907/tidelab/issues/89",
        authority_reference="invented-test-only-decision",
        authorized_scope="synthetic implementation test only")
    return item


def test_public_example_is_metadata_only_and_cannot_start_implementation() -> None:
    item = load_record(EXAMPLE)
    assert item["stage"] == "captured"
    assert item["interpretation"]["entry"] is None
    assert len(record_digest(item)) == 64
    with pytest.raises(ValueError, match="implementation_selected"):
        IntakeRegistry(":memory:").check_implementation_record(item)


def test_source_kinds_are_intake_metadata_with_pinned_specification() -> None:
    for kind in ("paper", "repository", "tradingview_script", "other"):
        assert validate_record(specified(kind))["source"]["kind"] == kind
    item = specified("repository")
    item["source"]["revision"] = "main"
    with pytest.raises(ValueError, match="full commit SHA"):
        validate_record(item)
    item = specified("tradingview_script")
    item["source"]["content_sha256"] = None
    with pytest.raises(ValueError, match="content hash"):
        validate_record(item)


def test_specification_fails_closed_on_ambiguity_and_source_payload() -> None:
    item = specified()
    item["interpretation"]["open_questions"] = ["What is the exit? "]
    with pytest.raises(ValueError, match="ambiguous"):
        validate_record(item)
    item = specified()
    item["source"]["source_code"] = "unreviewed third-party code"
    with pytest.raises(ValueError, match="source requires exactly"):
        validate_record(item)
    item = specified()
    item["rights"]["implementation_use"] = ["documented"]
    with pytest.raises(ValueError, match="rights status"):
        validate_record(item)


def test_json_duplicate_keys_are_rejected(tmp_path: Path) -> None:
    target = tmp_path / "duplicated.json"
    target.write_text(EXAMPLE.read_text(encoding="utf-8").replace(
        '"schema_version": 1,', '"schema_version": 1, "schema_version": 1,'),
        encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate JSON key"):
        load_record(target)


def test_cli_validates_from_checkout_without_package_install() -> None:
    root = EXAMPLE.parents[2]
    result = subprocess.run(
        [sys.executable, str(root / "scripts/strategy_intake.py"), "validate", str(EXAMPLE)],
        cwd=root, capture_output=True, text=True, check=True)
    assert json.loads(result.stdout)["meaning"] == "metadata_shape_only"


def test_selection_requires_separate_rights_and_authority_record() -> None:
    item = specified()
    item["stage"] = "implementation_selected"
    with pytest.raises(ValueError, match="rights or exact authority"):
        validate_record(item)
    assert validate_record(selected())["stage"] == "implementation_selected"


def test_registry_preserves_versions_and_blocks_rule_change_on_selection(tmp_path: Path) -> None:
    registry = IntakeRegistry(tmp_path / "intake.sqlite3")
    registry.initialize()
    first = specified()
    assert registry.register(first)
    assert registry.register(first) is False
    changed = deepcopy(first)
    changed["interpretation"]["entry"] = "A different invented entry."
    with pytest.raises(ValueError, match="cannot change"):
        registry.register(changed)
    ready = selected()
    ready["interpretation"]["entry"] = "A different invented entry."
    with pytest.raises(ValueError, match="silently change"):
        registry.register(ready)
    assert registry.register(selected())
    assert registry.check_implementation_record(selected()) == record_digest(selected())
    assert registry.list_latest()[0]["stage"] == "implementation_selected"
    with sqlite3.connect(registry.path) as db:
        with pytest.raises(sqlite3.DatabaseError, match="immutable"):
            db.execute("DELETE FROM intake_versions")


def test_changed_interpretation_needs_new_specification_and_decision(tmp_path: Path) -> None:
    registry = IntakeRegistry(tmp_path / "intake.sqlite3")
    registry.initialize()
    registry.register(specified())
    registry.register(selected())
    revised = specified()
    revised["version"] = 3
    revised["interpretation"]["entry"] = "A revised invented entry."
    registry.register(revised)
    with pytest.raises(ValueError, match="latest registered"):
        registry.check_implementation_record(selected())
    revised["version"] = 5
    with pytest.raises(ValueError, match="consecutive"):
        registry.register(revised)
