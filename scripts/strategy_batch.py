"""Batch-test normalized strategy packages on TideLab-authored synthetic bars.

Raw papers, repositories and Pine are intake sources, not executable packages.
This command neither translates them with AI nor reads market data or orders.
"""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from tidelab.domain import canonical_json
from tidelab.strategy_batch import evaluate_batch, load_json, parse_synthetic_bars
from tidelab.strategy_intake import IntakeRegistry, load_record, record_digest


ROOT = Path(__file__).resolve().parents[1]
MAX_PACKAGES = 10000


def run(package_dir: Path, record_paths: list[Path], fixture_path: Path,
        output_path: Path) -> dict:
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
    fixture_bytes = fixture_path.read_bytes()
    bars = parse_synthetic_bars(load_json(fixture_path, max_bytes=2 * 1024 * 1024))
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
                          "file_sha256": sha256(path.read_bytes()).hexdigest(),
                          "reason": type(exc).__name__})
    tested = evaluate_batch(packages, records, bars)
    for item in tested:
        item["index"] = original_indices[item["index"]]
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
            "engine": "tidelab-strategy-batch-v1", "cost": {"fee_rate": "0.0025",
            "adverse_rate": "0.001", "initial_cash": "10000", "quantity_unit": "0.00000001"},
            "fixture_sha256": sha256(fixture_bytes).hexdigest(),
            "source_record_sha256": {f"{key[0]}:{key[1]}": record_digest(record)
                                     for key, record in sorted(records.items())},
            "package_count": len(files), "outcomes": outcomes, "summary": summary,
            "scope": "synthetic_contract_only_no_market_claim"}
    raw = (canonical_json(body) + "\n").encode("utf-8")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("xb") as output:
        output.write(raw)
    return {"package_count": len(files), "summary": summary,
            "artifact_sha256": sha256(raw).hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packages", type=Path, required=True)
    parser.add_argument("--record", type=Path, action="append", required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(canonical_json(run(args.packages, args.record, args.fixture, args.output)))


if __name__ == "__main__":
    main()
