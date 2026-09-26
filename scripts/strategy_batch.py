"""Batch-test normalized strategy packages on TideLab-authored synthetic bars.

Raw papers, repositories and Pine are intake sources, not executable packages.
This command neither translates them with AI nor reads market data or orders.
"""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import file_digest, sha256
import json
from pathlib import Path

from tidelab.domain import canonical_json
from tidelab.strategy_batch import (SYNTHETIC_COST, SYNTHETIC_ENGINE,
                                    evaluate_batch, load_json, parse_json_bytes,
                                    parse_synthetic_bars)
from tidelab.strategy_intake import IntakeRegistry, load_record, record_digest
from tidelab.synthetic_batch_ledger import SyntheticBatchLedger


ROOT = Path(__file__).resolve().parents[1]
MAX_PACKAGES = 10000


def _file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def run(package_dir: Path, record_paths: list[Path], fixture_path: Path,
        output_path: Path, ledger_path: Path | None = None) -> dict:
    package_dir = package_dir.resolve()
    fixture_path = fixture_path.resolve()
    output_path = output_path.resolve()
    if (not package_dir.is_dir()
            or not fixture_path.is_relative_to((ROOT / "research" / "examples").resolve())
            or not output_path.is_relative_to((ROOT / "data").resolve())):
        raise ValueError("packages need a directory; synthetic fixture and private output need approved roots")
    files = sorted(package_dir.glob("*.json"))
    if not files or len(files) > MAX_PACKAGES:
        raise ValueError("batch needs 1 to 10000 JSON packages")
    if output_path.exists():
        raise FileExistsError(output_path)
    ledger_path = (ledger_path or ROOT / "data" / "strategy_batch" / "synthetic_trials.sqlite3").resolve()
    if not ledger_path.is_relative_to((ROOT / "data").resolve()) or ledger_path == output_path:
        raise ValueError("synthetic ledger must stay under private data")
    fixture_bytes = fixture_path.read_bytes()
    file_hashes = [_file_sha256(path) for path in files]
    ledger = SyntheticBatchLedger(ledger_path)
    ledger.initialize()
    output_key = output_path.relative_to((ROOT / "data").resolve()).as_posix()
    run_id = ledger.begin(output_key, "synthetic_strategy_batch",
                          sha256(fixture_bytes).hexdigest(),
                          list(zip(file_hashes, (path.name for path in files))))
    bars = parse_synthetic_bars(parse_json_bytes(fixture_bytes, max_bytes=2 * 1024 * 1024))
    records = {}
    for path in record_paths:
        record = load_record(path)
        if record["source"]["kind"] != "synthetic_example":
            IntakeRegistry(ROOT / "data" / "strategy_intake" / "intake.sqlite3").check_implementation_record(record)
        key = (record["candidate_id"], record["version"])
        if key in records and record_digest(records[key]) != record_digest(record):
            raise ValueError("source record identity duplicated with different bytes")
        records[key] = record
    packages, original_indices, early = [], [], []
    for index, path in enumerate(files):
        try:
            packages.append(load_json(path))
            original_indices.append(index)
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            early.append({"index": index, "status": "rejected_before_test",
                          "file_sha256": file_hashes[index],
                          "reason": type(exc).__name__})
    tested = evaluate_batch(packages, records, bars)
    for item in tested:
        item["index"] = original_indices[item["index"]]
    for item in tested:
        item["file_sha256"] = file_hashes[item["index"]]
    outcomes = sorted(early + tested, key=lambda item: item["index"])
    used = {(package["source"]["candidate_id"], package["source"]["version"])
            for package in packages if isinstance(package.get("source"), dict)
            and "candidate_id" in package["source"] and "version" in package["source"]
            and isinstance(package["source"]["candidate_id"], str)
            and type(package["source"]["version"]) is int}
    for key, record in sorted(records.items()):
        if key not in used:
            outcomes.append({"source_candidate_id": key[0], "source_version": key[1],
                             "source_sha256": record_digest(record),
                             "status": "needs_source_parser"})
    summary = dict(sorted(Counter(item["status"] for item in outcomes).items()))
    body = {"schema_version": 1, "kind": "synthetic_strategy_batch",
            "engine": SYNTHETIC_ENGINE, "cost": SYNTHETIC_COST,
            "fixture_sha256": sha256(fixture_bytes).hexdigest(),
            "source_record_sha256": {f"{key[0]}:{key[1]}": record_digest(record)
                                     for key, record in sorted(records.items())},
            "package_count": len(files), "outcomes": outcomes, "summary": summary,
            "scope": "synthetic_contract_only_no_market_claim"}
    raw = (canonical_json(body) + "\n").encode("utf-8")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("xb") as output:
        output.write(raw)
    completion = ledger.complete(output_key, raw)
    return {"package_count": len(files), "summary": summary,
            "artifact_sha256": sha256(raw).hexdigest(),
            "ledger_run_id": run_id, "ledger_recorded": completion["new_completion"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packages", type=Path, required=True)
    parser.add_argument("--record", type=Path, action="append", required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ledger", type=Path)
    args = parser.parse_args()
    print(canonical_json(run(args.packages, args.record, args.fixture,
                             args.output, args.ledger)))


if __name__ == "__main__":
    main()
