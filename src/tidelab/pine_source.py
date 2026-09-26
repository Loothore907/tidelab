"""Offline, local-only snapshots of manually obtained Pine source text."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, Mapping

from tidelab.domain import canonical_json
from tidelab.strategy_intake import validate_record


MAX_SOURCE_BYTES = 1024 * 1024


def _paths(store: Path, candidate_id: str, digest: str) -> tuple[Path, Path]:
    return store / f"{digest}.pine", store / f"{candidate_id}-{digest}.json"


def _write_once(path: Path, content: bytes) -> None:
    try:
        with path.open("xb") as target:
            target.write(content)
            target.flush()
            os.fsync(target.fileno())
    except FileExistsError:
        if path.read_bytes() != content:
            raise ValueError(f"existing Pine snapshot differs: {path.name}") from None


def capture_pine(record: Mapping[str, Any], source_file: str | Path,
                 store: str | Path) -> dict[str, Any]:
    """Retain exact input bytes; the caller must verify publication provenance."""
    item = validate_record(dict(record))
    if item["source"]["kind"] != "tradingview_script" or item["stage"] != "captured":
        raise ValueError("Pine capture requires a captured TradingView intake record")
    content = Path(source_file).read_bytes()
    if not content or len(content) > MAX_SOURCE_BYTES or b"\x00" in content:
        raise ValueError("Pine source must be nonempty text of at most 1 MiB")
    try:
        content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Pine source must be UTF-8; bytes are never normalized") from exc
    digest = sha256(content).hexdigest()
    destination = Path(store)
    destination.mkdir(parents=True, exist_ok=True)
    snapshot, receipt = _paths(destination, item["candidate_id"], digest)
    _write_once(snapshot, content)
    if receipt.exists():
        result = json.loads(receipt.read_text(encoding="utf-8"))
        if (result.get("candidate_id") != item["candidate_id"]
                or result.get("source_locator") != item["source"]["locator"]
                or result.get("content_sha256") != digest
                or result.get("byte_count") != len(content)):
            raise ValueError("existing Pine receipt differs")
    else:
        result = {
            "schema_version": 1,
            "candidate_id": item["candidate_id"],
            "source_locator": item["source"]["locator"],
            "capture_record_version": item["version"],
            "capture_method": "manual_local_file",
            "captured_utc": datetime.now(timezone.utc).isoformat(),
            "content_sha256": digest,
            "byte_count": len(content),
        }
        _write_once(receipt, (canonical_json(result) + "\n").encode("utf-8"))
    return {"candidate_id": item["candidate_id"], "content_sha256": digest,
            "source_revision": f"sha256:{digest}", "byte_count": len(content),
            "snapshot": str(snapshot), "receipt": str(receipt),
            "provenance": "manual_claim_not_independently_verified"}


def verify_pine(record: Mapping[str, Any], store: str | Path) -> dict[str, Any]:
    """Check retained bytes and receipt against a candidate record."""
    item = validate_record(dict(record))
    source = item["source"]
    if source["kind"] != "tradingview_script" or source["content_sha256"] is None:
        raise ValueError("record has no TradingView Pine content hash")
    digest = source["content_sha256"]
    if source["revision"] != f"sha256:{digest}":
        raise ValueError("Pine source revision must equal its content hash")
    snapshot, receipt = _paths(Path(store), item["candidate_id"], digest)
    content = snapshot.read_bytes()
    if not content or len(content) > MAX_SOURCE_BYTES or sha256(content).hexdigest() != digest:
        raise ValueError("Pine snapshot hash mismatch")
    saved = json.loads(receipt.read_text(encoding="utf-8"))
    if (saved.get("schema_version") != 1
            or saved.get("candidate_id") != item["candidate_id"]
            or saved.get("source_locator") != source["locator"]
            or saved.get("content_sha256") != digest
            or saved.get("byte_count") != len(content)
            or saved.get("capture_method") != "manual_local_file"):
        raise ValueError("Pine receipt does not match intake record and snapshot")
    return {"candidate_id": item["candidate_id"], "content_sha256": digest,
            "byte_count": len(content), "local_snapshot": "verified",
            "publication_provenance": "manual_claim_not_independently_verified"}
