from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest

from tidelab.pine_source import capture_pine, verify_pine
from tidelab.strategy_intake import IntakeRegistry
from test_strategy_intake import captured


SOURCE = b"// Synthetic Pine text for a storage test\r\n//@version=5\r\nstrategy('Fixture')\r\n"


def pilot() -> dict:
    item = captured()
    item["candidate_id"] = "synthetic-pine-pilot"
    item["source"].update(kind="tradingview_script",
                          locator="https://www.tradingview.com/script/example/",
                          revision="unverified")
    return item


def test_exact_bytes_and_receipt_are_local_and_idempotent(tmp_path: Path) -> None:
    source = tmp_path / "manual.pine"
    source.write_bytes(SOURCE)
    store = tmp_path / "pine_sources"
    item = pilot()
    result = capture_pine(item, source, store)
    digest = sha256(SOURCE).hexdigest()
    assert result["content_sha256"] == digest
    assert (store / f"{digest}.pine").read_bytes() == SOURCE
    assert capture_pine(item, source, store) == result
    assert (store / f"{item['candidate_id']}-{digest}.json").exists()

    specified = deepcopy(item)
    specified["version"] = 2
    specified["source"].update(content_sha256=digest, revision=f"sha256:{digest}")
    verified = verify_pine(specified, store)
    assert verified["local_snapshot"] == "verified"
    assert verified["publication_provenance"] == "manual_claim_not_independently_verified"

    registry = IntakeRegistry(tmp_path / "intake.sqlite3")
    registry.initialize()
    assert registry.register(item)
    specified["stage"] = "specified"
    specified["claim"]["economic_rationale"] = "Synthetic rationale for schema test."
    specified["interpretation"].update(
        product_scope="synthetic", timeframe="one hour",
        required_data=["invented bars"], required_capabilities=["synthetic long"],
        entry="Invented entry.", exit="Invented exit.", sizing="Invented size.",
        timing="After invented close.", open_questions=[])
    assert registry.register(specified)


def test_capture_changes_are_new_snapshots_and_tampering_fails(tmp_path: Path) -> None:
    source = tmp_path / "manual.pine"
    source.write_bytes(SOURCE)
    store = tmp_path / "pine_sources"
    item = pilot()
    first = capture_pine(item, source, store)
    source.write_bytes(SOURCE.replace(b"\r\n", b"\n"))
    second = capture_pine(item, source, store)
    assert first["content_sha256"] != second["content_sha256"]
    item["source"].update(content_sha256=first["content_sha256"],
                          revision=first["source_revision"])
    snapshot = Path(first["snapshot"])
    snapshot.write_bytes(b"changed")
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_pine(item, store)
    original = tmp_path / "original.pine"
    original.write_bytes(SOURCE)
    with pytest.raises(ValueError, match="existing Pine snapshot differs"):
        capture_pine(pilot(), original, store)


def test_specified_record_needs_matching_local_receipt(tmp_path: Path) -> None:
    item = pilot()
    digest = "a" * 64
    item["source"].update(content_sha256=digest, revision=f"sha256:{digest}")
    item["stage"] = "specified"
    item["claim"]["economic_rationale"] = "Synthetic rationale."
    item["interpretation"].update(
        product_scope="synthetic", timeframe="one hour", required_data=["bars"],
        required_capabilities=["long"], entry="Invented entry.", exit="Invented exit.",
        sizing="Invented size.", timing="Next invented bar.", open_questions=[])
    registry = IntakeRegistry(tmp_path / "intake.sqlite3")
    registry.initialize()
    with pytest.raises(FileNotFoundError):
        registry.register(item)
    item["source"]["revision"] = "published-v1"
    with pytest.raises(ValueError, match="revision must equal"):
        registry.register(item)


def test_capture_rejects_non_text_and_other_source_kind(tmp_path: Path) -> None:
    source = tmp_path / "source.pine"
    source.write_bytes(b"\x00bad")
    with pytest.raises(ValueError, match="nonempty text"):
        capture_pine(pilot(), source, tmp_path / "store")
    source.write_bytes(SOURCE)
    with pytest.raises(ValueError, match="captured TradingView"):
        capture_pine(captured(), source, tmp_path / "store")
