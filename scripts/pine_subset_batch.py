"""Compile pinned TideLab-authored Pine examples and run synthetic contract checks."""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import file_digest, sha256
import json
from pathlib import Path

from tidelab.domain import canonical_json
from tidelab.pine_subset import (GRAMMAR_VERSION, MAX_SOURCE_BYTES,
                                 PineFrontendError, compile_pine)
from tidelab.strategy_batch import (SYNTHETIC_COST, SYNTHETIC_ENGINE,
                                    evaluate_batch, load_json, parse_json_bytes,
                                    parse_package, parse_synthetic_bars, signal_trace)
from tidelab.strategy_intake import load_record
from tidelab.synthetic_batch_ledger import SyntheticBatchLedger


ROOT = Path(__file__).resolve().parents[1]


def _source_input(path: Path) -> tuple[str, bytes]:
    with path.open("rb") as stream:
        raw = stream.read(MAX_SOURCE_BYTES + 1)
    with path.open("rb") as stream:
        digest = file_digest(stream, "sha256").hexdigest()
    return digest, raw


def run(source_dir: Path, record_paths: list[Path], fixture_path: Path,
        output_path: Path, ledger_path: Path | None = None) -> dict:
    examples = (ROOT / "research" / "examples").resolve()
    source_dir, fixture_path, output_path = (source_dir.resolve(), fixture_path.resolve(),
                                             output_path.resolve())
    if (not source_dir.is_relative_to(examples) or not source_dir.is_dir()
            or not fixture_path.is_relative_to(examples)
            or not output_path.is_relative_to((ROOT / "data").resolve())):
        raise ValueError("source and fixture must be public examples; output must be under data")
    files = sorted(source_dir.glob("*.pine"))
    if not 1 <= len(files) <= 10000:
        raise ValueError("batch needs 1 to 10000 Pine files")
    if any(not path.resolve().is_relative_to(examples) for path in files):
        raise ValueError("Pine source path escapes public examples")
    if output_path.exists():
        raise FileExistsError(output_path)
    ledger_path = (ledger_path or ROOT / "data" / "strategy_batch" / "synthetic_trials.sqlite3").resolve()
    if not ledger_path.is_relative_to((ROOT / "data").resolve()) or ledger_path == output_path:
        raise ValueError("synthetic ledger must stay under private data")
    if fixture_path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("synthetic fixture exceeds size limit")
    fixture_bytes = fixture_path.read_bytes()
    source_inputs = [_source_input(path) for path in files]
    ledger = SyntheticBatchLedger(ledger_path)
    ledger.initialize()
    output_key = output_path.relative_to((ROOT / "data").resolve()).as_posix()
    run_id = ledger.begin(output_key, "synthetic_pine_subset_batch",
                          sha256(fixture_bytes).hexdigest(),
                          [(digest, path.name)
                           for (digest, _), path in zip(source_inputs, files)])
    bars = parse_synthetic_bars(parse_json_bytes(fixture_bytes, max_bytes=2 * 1024 * 1024))
    records = {}
    for path in record_paths:
        if not path.resolve().is_relative_to(examples):
            raise ValueError("only TideLab-authored synthetic example records are accepted")
        record = load_record(path)
        if record["source"]["kind"] != "synthetic_example":
            raise ValueError("only synthetic example records are accepted")
        digest = record["source"]["content_sha256"]
        if digest in records:
            raise ValueError("duplicate source digest record")
        records[digest] = record
    compiled, record_map, indices, outcomes, source_hashes = [], {}, [], [], {}
    for index, path in enumerate(files):
        source_sha, raw = source_inputs[index]
        source_hashes[index] = source_sha
        identity = {"index": index, "file": path.name, "source_sha256": source_sha,
                    "grammar_version": GRAMMAR_VERSION}
        try:
            record = records.get(source_sha)
            if record is None:
                raise PineFrontendError("source_record_missing")
            package = compile_pine(raw, record)
            parsed = parse_package(package, record)
            if not path.with_suffix(".trace.json").is_file():
                raise PineFrontendError("conformance_trace_missing")
            trace = load_json(path.with_suffix(".trace.json"))
            expected = {"schema_version": 1, "grammar_version": GRAMMAR_VERSION,
                        "source_sha256": source_sha, "signals": signal_trace(parsed, bars)}
            if trace != expected:
                raise PineFrontendError("conformance_trace_mismatch")
            key = (record["candidate_id"], record["version"])
            if key in record_map and record_map[key] != record:
                raise PineFrontendError("duplicate_record_identity")
            record_map[key] = record
            compiled.append(package)
            indices.append(index)
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            code = exc.code if isinstance(exc, PineFrontendError) else type(exc).__name__
            status = ("unsupported_pine" if code.startswith("unsupported_") else
                      "conformance_failed" if code.startswith("conformance_") else
                      "rejected_before_test")
            outcomes.append({**identity, "status": status, "reason": code})
    evaluated = evaluate_batch(compiled, record_map, bars)
    for item in evaluated:
        index = indices[item.pop("index")]
        item.update({"index": index, "file": files[index].name,
                     "source_sha256": source_hashes[index],
                     "grammar_version": GRAMMAR_VERSION,
                     "conformance": "matched"})
        outcomes.append(item)
    outcomes.sort(key=lambda item: item["index"])
    body = {"schema_version": 1, "kind": "synthetic_pine_subset_batch",
            "grammar_version": GRAMMAR_VERSION, "engine": SYNTHETIC_ENGINE,
            "cost": SYNTHETIC_COST,
            "fixture_sha256": sha256(fixture_bytes).hexdigest(),
            "source_count": len(files), "outcomes": outcomes,
            "summary": dict(sorted(Counter(item["status"] for item in outcomes).items())),
            "scope": "synthetic_contract_only_no_tradingview_or_market_claim"}
    raw = (canonical_json(body) + "\n").encode("utf-8")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("xb") as output:
        output.write(raw)
    completion = ledger.complete(output_key, raw)
    return {"source_count": len(files), "summary": body["summary"],
            "artifact_sha256": sha256(raw).hexdigest(),
            "ledger_run_id": run_id, "ledger_recorded": completion["new_completion"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--record", type=Path, action="append", required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ledger", type=Path)
    args = parser.parse_args()
    print(canonical_json(run(args.sources, args.record, args.fixture,
                             args.output, args.ledger)))


if __name__ == "__main__":
    main()
