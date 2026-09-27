"""Finite authored-source compilation and orchestration of existing synthetic replay.

No source execution, discovery, private admission, or new strategy semantics.
Input accounting is independent of historical job reservation and execution.
"""
from collections import Counter
from datetime import timedelta
import json
from pathlib import Path
import sqlite3
from time import perf_counter

from tidelab import historical_batch as batch
from tidelab.domain import canonical_json, isoformat_utc
from tidelab.historical_input import FIELDS, SOURCE, row_digest
from tidelab.package_lean_parity import run_parity, validate_package_domain
from tidelab.pine_subset import GRAMMAR_VERSION, compile_pine, PineFrontendError
from tidelab.storage import TideStore
from tidelab.strategy_batch import (SYNTHETIC_COST, SYNTHETIC_ENGINE, UnsupportedPackage,
    parse_json_bytes, parse_synthetic_bars, signal_trace, validate_cost)
from tidelab.strategy_intake import validate_record
from tidelab.synthetic_batch_ledger import SyntheticBatchLedger

KIND = "synthetic_source_workflow"
SCOPE = "synthetic_compilation_only_no_research_authority"
EXAMPLES = batch.ROOT / "research/examples"
DATA = batch.ROOT / "data/source_workflow"


def _ref(ref):
    if (not isinstance(ref, dict) or set(ref) != {"path", "sha256"}
            or not isinstance(ref["path"], str) or not batch.DIGEST.fullmatch(ref["sha256"])):
        raise ValueError("invalid_file_reference")


def _capture(root, ref, target):
    path = (root / ref["path"]).resolve()
    if not path.is_relative_to(EXAMPLES.resolve()):
        raise ValueError("source_outside_authored_examples")
    raw = batch.freeze(path, target, 4 * 1024 * 1024)
    if batch.digest(raw) != ref["sha256"]:
        raise ValueError("input_identity_mismatch")
    return raw


def _manifest(path):
    path = path.resolve()
    if not path.is_relative_to(EXAMPLES.resolve()):
        raise ValueError("manifest_outside_authored_examples")
    raw = path.read_bytes()
    manifest = parse_json_bytes(raw, max_bytes=4 * 1024 * 1024)
    if (set(manifest) != {"schema_version", "kind", "corpus", "inputs", "history",
                          "warmup_bars", "costs", "benchmark_allocation"}
            or manifest["schema_version"] != 1 or manifest["kind"] != "tidelab_authored_synthetic"
            or not batch.TOKEN.fullmatch(manifest["corpus"])):
        raise ValueError("invalid_source_manifest")
    if not isinstance(manifest["inputs"], list) or not 1 <= len(manifest["inputs"]) <= 1000:
        raise ValueError("finite_input_inventory_required")
    seen = set()
    for item in manifest["inputs"]:
        if (set(item) - {"grammar_version"} != {"id", "format", "source", "record", "trace"}
                or not batch.TOKEN.fullmatch(item["id"]) or item["id"] in seen
                or item["format"] not in ("normalized_json", "pine_subset", "prose")
                or ("grammar_version" in item and (item["format"] != "pine_subset"
                    or not isinstance(item["grammar_version"], str)))):
            raise ValueError("invalid_source_inventory")
        seen.add(item["id"])
        for name in ("source", "record"):
            _ref(item[name])
        if item["trace"] is not None:
            _ref(item["trace"])
    _ref(manifest["history"])
    if (type(manifest["warmup_bars"]) is not int or manifest["warmup_bars"] < 0
            or set(manifest["costs"]) != {"baseline", "stress"}):
        raise ValueError("invalid_common_configuration")
    for cost in manifest["costs"].values():
        validate_cost(cost)
    return raw, manifest


def structure(package):
    """Operator topology only: sizes/thresholds/windows are not broad coverage."""
    def shape(node):
        if isinstance(node, dict):
            return {k: shape(v) for k, v in node.items()
                    if k in ("op", "args", "arg", "left", "right")}
        if isinstance(node, list):
            return [shape(v) for v in node]
        return node
    return {key: shape(package["rule"][key]) for key in ("entry", "exit")}


def _compile(manifest_path, raw, manifest, output, ledger):
    captured = output / "sources"
    captured.mkdir()
    batch.write_raw(captured / "submission.json", raw)
    batch.write(captured / "runtime.json", {name: batch.digest((Path(__file__).parent / name).read_bytes())
        for name in ("source_workflow.py", "pine_subset.py", "synthetic_batch_ledger.py", "storage.py")})
    # Register the complete declared source denominator before opening any source.
    ledger.begin("compilation", KIND, manifest["history"]["sha256"],
                 [(x["source"]["sha256"], x["id"]) for x in manifest["inputs"]])
    root = manifest_path.resolve().parent
    history_error = None
    try:
        history = parse_json_bytes(_capture(root, manifest["history"], captured / "history.json"),
                                   max_bytes=4 * 1024 * 1024)
        bars = parse_synthetic_bars(history)
        if not 3 <= len(bars) <= 10000 or manifest["warmup_bars"] >= len(bars):
            raise ValueError("invalid_history_bounds")
    except (ValueError, OSError) as exc:
        history_error = str(exc)
    outcomes, refs, records = [], [], {}
    for index, item in enumerate(manifest["inputs"]):
        outcome = {"index": index, "id": item["id"], "format": item["format"],
                   "file_sha256": item["source"]["sha256"],
                   "record_sha256": item["record"]["sha256"], "jobs": []}
        outcomes.append(outcome)
        if "grammar_version" in item:
            outcome["grammar_version"] = item["grammar_version"]
        try:
            source = _capture(root, item["source"], captured / f"source-{index}.raw")
            record_raw = _capture(root, item["record"], captured / f"record-{index}.json")
            record = validate_record(parse_json_bytes(record_raw))
            if record["source"]["kind"] != "synthetic_example" or record["source"]["authors"] != ["TideLab"]:
                raise ValueError("authored_synthetic_record_required")
            identity = (record["candidate_id"], record["version"])
            if identity in records and records[identity] != record:
                raise ValueError("conflicting_record_identity")
            records[identity] = record
            outcome["intake"] = {"candidate_id": identity[0], "version": identity[1]}
            if history_error:
                raise ValueError("history_identity_or_format: " + history_error)
            if item["format"] == "prose":
                outcome.update(status="needs_source_parser", reason="prose_requires_interpretation")
                continue
            package = (compile_pine(source, record, grammar_version=item.get("grammar_version", GRAMMAR_VERSION))
                       if item["format"] == "pine_subset"
                       else parse_json_bytes(source))
            parsed = validate_package_domain(package, record)
            if parsed.preceding_warmup > manifest["warmup_bars"]:
                raise UnsupportedPackage("insufficient_declared_warmup")
            package_raw = (canonical_json(package) + "\n").encode()
            batch.write_raw(captured / f"package-{index}.json", package_raw)
            outcome.update(package_sha256=batch.digest(package_raw), structure=structure(package))
            if item["trace"] is None:
                raise PineFrontendError("conformance_trace_missing")
            trace = parse_json_bytes(_capture(root, item["trace"], captured / f"trace-{index}.json"))
            if trace != {"source_sha256": item["source"]["sha256"],
                         "history_sha256": manifest["history"]["sha256"],
                         "signals": signal_trace(parsed, bars)}:
                raise PineFrontendError("conformance_trace_mismatch")
            outcome.update(status="compiled", conformance="matched")
            refs.append({"id": item["id"], "package": f"package-{index}.json",
                         "record": f"record-{index}.json", "package_sha256": batch.digest(package_raw),
                         "record_sha256": item["record"]["sha256"]})
        except UnsupportedPackage as exc:
            outcome.update(status="unsupported", reason=str(exc))
        except PineFrontendError as exc:
            outcome.update(status="conformance_failed" if exc.code.startswith("conformance_") else
                           "unsupported" if exc.code.startswith("unsupported_") else "invalid", reason=exc.code)
        except (ValueError, OSError, KeyError, TypeError, ArithmeticError) as exc:
            outcome.update(status="invalid", reason=str(exc))
    body = {"schema_version": 1, "kind": KIND, "scope": SCOPE, "engine": SYNTHETIC_ENGINE,
            "cost": SYNTHETIC_COST, "fixture_sha256": manifest["history"]["sha256"],
            "source_count": len(outcomes), "outcomes": outcomes,
            "summary": dict(sorted(Counter(x["status"] for x in outcomes).items()))}
    batch.write(captured / "packages.json", {"packages": refs})
    body["captured_files"] = {p.name: batch.digest(p.read_bytes()) for p in sorted(captured.iterdir())}
    batch.write(captured / "compilation.json", body)
    batch.finalize(captured)
    ledger.complete("compilation", (captured / "compilation.json").read_bytes())
    return refs


def _assemble(output, manifest, refs):
    """Materialize only the supplied invented bars in a new isolated store."""
    sources = output / "sources"
    bars = parse_synthetic_bars(batch.read(sources / "history.json"))
    warmup = manifest["warmup_bars"]
    market = "synthetic:CORPUS-USD"
    database = output / "history.sqlite3"
    TideStore(database).initialize()
    rows = []
    with sqlite3.connect(database) as db:
        for index, bar in enumerate(bars):
            timestamp = isoformat_utc(bar.start)
            payload = {"open": str(bar.open), "close": str(bar.close),
                       "high": str(bar.high if bar.high is not None else max(bar.open, bar.close)),
                       "low": str(bar.low if bar.low is not None else min(bar.open, bar.close)), "volume": "1000"}
            row = dict(zip(FIELDS, [f"corpus-{index}", 1, "tidelab", market, "bar", timestamp,
                timestamp, SOURCE, 3600, 1, canonical_json(payload),
                canonical_json({"kind": "tidelab_synthetic", "author": "TideLab"})]))
            db.execute(f"INSERT INTO market_events ({','.join(FIELDS)}) VALUES ({','.join('?' for _ in FIELDS)})", tuple(row.values()))
            rows.append(row)
    start, end = bars[warmup].start, bars[-1].start + timedelta(hours=1)
    descriptor = {"schema_version": 1, "kind": "synthetic", "source": SOURCE, "venue": "tidelab",
        "interval_seconds": 3600, "rights_reference": "TideLab-authored", "receipt": "tidelab-synthetic-generator-v1",
        "partitions": {market: {"start": isoformat_utc(start), "end": isoformat_utc(end),
                                "warmup_bars": warmup, "sha256": row_digest(rows)}}}
    batch.write(output / "snapshot.json", descriptor)
    jobs = [{"package": ref["id"], "market": market, "cost": cost, "benchmark": None}
            for ref in refs for cost in ("baseline", "stress")]
    jobs.extend({"package": refs[0]["id"], "market": market, "cost": cost, "benchmark": benchmark}
                for benchmark in ("cash", "passive") for cost in ("baseline", "stress"))
    plan = {"schema_version": 1, "kind": "synthetic", "family": manifest["corpus"], "generation": "v1",
        "parent_experiment": None, "phase": "development", "issue": 95, "authority": batch.AUTHORITY,
        "markets": [market], "partitions": {
            "development": {"start": isoformat_utc(start), "end": isoformat_utc(end)},
            "validation": {"start": isoformat_utc(end), "end": isoformat_utc(end + timedelta(hours=1))},
            "untouched": {"start": isoformat_utc(end + timedelta(hours=1)), "end": isoformat_utc(end + timedelta(hours=2))}},
        "packages": [{**ref, "package": "sources/" + ref["package"], "record": "sources/" + ref["record"]} for ref in refs],
        "jobs": jobs, "costs": manifest["costs"], "budget": len(jobs), "max_bars": len(bars),
        "benchmark_allocation": manifest["benchmark_allocation"], "metrics": batch.METRICS,
        "selection": "none", "retention": "retain_all_local",
        "snapshot_sha256": batch.digest((output / "snapshot.json").read_bytes())}
    batch.preflight(plan, descriptor)
    batch.write(output / "plan.json", plan)


def _report(output, historical):
    source_hash = batch.verify(output / "sources")
    compilation = batch.read(output / "sources/compilation.json")
    actual = {p.name: batch.digest(p.read_bytes()) for p in (output / "sources").iterdir()
              if p.name not in ("compilation.json", "manifest.json")}
    if actual != compilation["captured_files"]:
        raise ValueError("compiled_source_artifact_mismatch")
    inputs = compilation["outcomes"]
    plan = batch.read(output / "attempt/inputs/plan.json") if (output / "attempt/inputs/plan.json").exists() else None
    jobs = historical.get("jobs", []) if historical else []
    traces = {str(j["index"]): batch.digest(path.read_bytes()) for j in jobs
              if (path := output / "attempt" / j.get("artifact_directory", "") / "trace.jsonl").exists()}
    for item in inputs:
        item["jobs"] = [j["index"] for j in jobs if plan and plan["jobs"][j["index"]]["package"] == item["id"]
                        and plan["jobs"][j["index"]]["benchmark"] is None]
    parity = batch.read(output / "parity.json") if (output / "parity.json").exists() else {"status": "not_run", "cases": []}
    result = {"schema_version": 1, "sources_manifest_sha256": source_hash,
        "inputs": inputs, "compilation_counts": compilation["summary"],
        "distinct_rule_structures": len({canonical_json(x["structure"]) for x in inputs if x["status"] == "compiled"}),
        "historical": historical, "job_counts": dict(Counter(x["status"] for x in jobs)), "parity": parity,
        "trace_sha256": traces,
        "semantic_sha256": batch.digest(canonical_json({"inputs": inputs, "traces": traces,
            "jobs": [{k: j[k] for k in ("index", "status", "reason", "metrics") if k in j} for j in jobs]}).encode()),
        "status": "accounted" if plan and len(jobs) == len(plan["jobs"]) else "rejected"}
    if plan:
        result["ordered_jobs"] = plan["jobs"]
        result["costs"] = plan["costs"]
        if (output / "attempt/admission.json").exists():
            result["admission"] = batch.read(output / "attempt/admission.json")["inventory"]
    if (output / "timing.json").exists():
        result["measurement"] = batch.read(output / "timing.json")
    if parity["status"] != "not_run":
        if batch.verify(output / "parity") != parity["artifact_sha256"]:
            raise ValueError("parity_artifact_mismatch")
    if (output / "results.json").exists():
        if batch.read(output / "results.json") != result:
            raise ValueError("consolidated_result_mismatch")
    else:
        batch.write(output / "results.json", result)
    return result


def run(manifest_path: Path, output: Path, *, lean_root: Path | None = None,
        dotnet: str = "dotnet", checkpoint=lambda _: None):
    """New isolated submission. CLI requires LEAN; tests may inspect compilation alone."""
    started = perf_counter()
    raw, manifest = _manifest(manifest_path)
    output = output.resolve()
    if not output.is_relative_to(DATA.resolve()) or output == DATA.resolve():
        raise ValueError("dedicated_synthetic_output_required")
    output.mkdir(parents=True, exist_ok=False)
    with batch.exclusive(output):
        ledger = SyntheticBatchLedger(output / "sources.sqlite3")
        ledger.initialize()
        refs = _compile(manifest_path, raw, manifest, output, ledger)
        checkpoint("compiled")
        historical = None
        if refs:
            _assemble(output, manifest, refs)
            checkpoint("assembled")
            historical = batch.run(output / "plan.json", output / "snapshot.json", output / "history.sqlite3",
                                   output / "trials.sqlite3", output / "attempt", checkpoint=checkpoint)
            checkpoint("historical_complete")
            if lean_root is not None and historical.get("status") in ("completed", "failed"):
                parity_dir = output / "parity"
                parity_dir.mkdir()
                plan = batch.read(output / "attempt/inputs/plan.json")
                cases = []
                # Each executed non-benchmark configuration/cost; duplicates and failed
                # jobs remain accounted by the backend, never replayed for parity.
                for job in historical["jobs"]:
                    spec = plan["jobs"][job["index"]]
                    if job["status"] != "completed" or spec["benchmark"] is not None:
                        continue
                    ref_index = next(i for i, r in enumerate(plan["packages"]) if r["id"] == spec["package"])
                    captured = output / "attempt/inputs"
                    result = run_parity(captured / f"package-{ref_index}.json", captured / f"record-{ref_index}.json",
                        output / "sources/history.json", lean_root, dotnet, parity_dir / f"job-{job['index']}",
                        cost=plan["costs"][spec["cost"]], score_start=manifest["warmup_bars"])
                    if result["status"] == "matched":
                        historical_trace = [json.loads(line) for line in
                            (output / "attempt" / job["artifact_directory"] / "trace.jsonl").read_text().splitlines()]
                        if historical_trace != batch.read(parity_dir / f"job-{job['index']}" / "python.json")["trace"]:
                            result = {**result, "status": "mismatch", "reason": "historical_trace_differs"}
                    cases.append({"job_index": job["index"], **result})
                artifact = batch.finalize(parity_dir)
                batch.write(output / "parity.json", {"status": "matched" if cases and all(
                    x["status"] == "matched" for x in cases) else "failed", "cases": cases, "artifact_sha256": artifact})
        batch.write(output / "timing.json", {"elapsed_seconds": perf_counter() - started,
            "source_count": len(manifest["inputs"]), "commands_submitted": 1,
            "per_candidate_manual_steps_after_submission": 0})
        return _report(output, historical)


def recover(output: Path, *, abort=False):
    """Use existing ledgers/manifests; no source recompile, data read or replay."""
    output = output.resolve()
    if not output.is_relative_to(DATA.resolve()) or output == DATA.resolve():
        raise ValueError("dedicated_synthetic_output_required")
    with batch.exclusive(output):
        batch.verify(output / "sources")
        ledger = SyntheticBatchLedger(output / "sources.sqlite3")
        ledger.complete("compilation", (output / "sources/compilation.json").read_bytes())
        if not batch.read(output / "sources/packages.json")["packages"]:
            return _report(output, None)
        historical = batch.recover(output / "attempt", output / "trials.sqlite3", abort=abort)
        return _report(output, historical)
