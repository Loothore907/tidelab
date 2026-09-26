"""Shared registered replay; synthetic default, explicit private policy, no promotion."""
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sqlite3
from time import perf_counter
from uuid import uuid4

from tidelab.domain import canonical_json, parse_utc
from tidelab.experiment_identity import build_experiment_identity
from tidelab.historical_input import HOUR, SOURCE, read_partition
from tidelab.package_lean_parity import validate_package_domain
from tidelab.strategy_batch import parse_json_bytes, replay_package, validate_cost, UnsupportedPackage
from tidelab.trial_registry import TrialRegistry

ROOT = Path(__file__).resolve().parents[2]
TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
AUTHORITY = "issue-95-synthetic-foundation"
METRICS = ["net_return", "max_drawdown", "fill_count", "round_trips", "fees", "turnover", "exposure"]
SOURCES = ["historical_batch.py", "historical_input.py", "strategy_batch.py", "trial_registry.py",
           "experiment_identity.py", "package_lean_parity.py", "strategy_intake.py", "domain.py",
           "rsi_private.py"]


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_raw(path: Path, raw: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def write(path: Path, value) -> None:
    write_raw(path, (canonical_json(value) + "\n").encode())


def read(path: Path):
    return parse_json_bytes(path.read_bytes(), max_bytes=16 * 1024 * 1024)


@contextmanager
def exclusive(output: Path):
    """OS releases this nonblocking lock on process death; never infer from age."""
    with (output / ".lock").open("a+b") as handle:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            if handle.read(1) == b"":
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def finalize(directory: Path, name: str = "manifest.json") -> str:
    files = {str(p.relative_to(directory)).replace("\\", "/"): digest(p.read_bytes())
             for p in sorted(directory.rglob("*")) if p.is_file()
             and p.name != ".lock" and p != directory / name and not p.name.endswith(".pending")}
    pending = directory / (name + ".pending")
    if pending.exists():
        if read(pending) != {"files": files}:
            raise ValueError("incomplete_manifest_changed")
    else:
        write(pending, {"files": files})
    os.link(pending, directory / name)  # atomic, exclusive publication
    pending.unlink()
    return digest((directory / name).read_bytes())


def verify(directory: Path, name: str = "manifest.json") -> str:
    manifest = read(directory / name)
    actual = {str(p.relative_to(directory)).replace("\\", "/") for p in directory.rglob("*")
              if p.is_file() and p.name != ".lock" and p != directory / name and not p.name.endswith(".pending")}
    if actual != set(manifest["files"]):
        raise ValueError("artifact_file_set_mismatch")
    for relative, expected in manifest["files"].items():
        path = (directory / relative).resolve()
        if not path.is_relative_to(directory.resolve()) or digest(path.read_bytes()) != expected:
            raise ValueError("artifact_digest_mismatch")
    return digest((directory / name).read_bytes())


def freeze(path: Path, target: Path, limit: int = 65536) -> bytes:
    if path.stat().st_size > limit:
        raise ValueError("input_size_limit")
    raw = path.read_bytes()
    write_raw(target, raw)
    return raw


def preflight(plan: dict, descriptor: dict) -> None:
    expected = {"schema_version", "kind", "family", "generation", "parent_experiment", "phase", "issue",
                "authority", "markets", "partitions", "packages", "jobs", "costs", "budget", "max_bars",
                "benchmark_allocation", "metrics", "selection", "retention", "snapshot_sha256"}
    if set(plan) != expected or type(plan["schema_version"]) is not int or plan["schema_version"] != 1:
        raise ValueError("invalid_plan_fields")
    if plan["kind"] != "synthetic" or descriptor.get("kind") != "synthetic":
        raise ValueError("real_data_not_enabled")
    if plan["phase"] != "development":
        raise ValueError("phase_not_enabled")
    if plan["issue"] != 95 or plan["authority"] != AUTHORITY:
        raise ValueError("missing_synthetic_authority")
    for field in ("family", "generation"):
        if not isinstance(plan[field], str) or not TOKEN.fullmatch(plan[field]):
            raise ValueError("invalid_experiment_id")
    if plan["parent_experiment"] is not None and not TOKEN.fullmatch(plan["parent_experiment"]):
        raise ValueError("invalid_parent")
    if (plan["selection"] != "none" or plan["retention"] != "retain_all_local"
            or plan["metrics"] != METRICS):
        raise ValueError("unsupported_review_policy")
    if (set(plan["costs"]) != {"baseline", "stress"} or not plan["markets"]
            or len(plan["markets"]) != len(set(plan["markets"]))):
        raise ValueError("invalid_comparison_scope")
    for cost in plan["costs"].values():
        validate_cost(cost)
    allocation = Decimal(plan["benchmark_allocation"])
    if not allocation.is_finite() or not 0 < allocation <= 1 or allocation.as_tuple().exponent < -8:
        raise ValueError("invalid_benchmark_allocation")
    if (not isinstance(plan["jobs"], list) or not isinstance(plan["packages"], list)
            or not 1 <= len(plan["packages"]) <= 10000):
        raise ValueError("invalid_inventory")
    if (type(plan["budget"]) is not int or not 1 <= len(plan["jobs"]) <= plan["budget"] <= 10000
            or type(plan["max_bars"]) is not int or not 3 <= plan["max_bars"] <= 10000):
        raise ValueError("budget_or_bar_limit")
    if set(plan["partitions"]) != {"development", "validation", "untouched"}:
        raise ValueError("invalid_partitions")
    ranges = []
    for phase in ("development", "validation", "untouched"):
        part = plan["partitions"][phase]
        if set(part) != {"start", "end"}:
            raise ValueError("invalid_partition_fields")
        start, end = parse_utc(part["start"]), parse_utc(part["end"])
        if (start >= end or any(x.minute or x.second or x.microsecond for x in (start, end))
                or not all(part[k].endswith("Z") for k in ("start", "end"))
                or (ranges and start < ranges[-1][1])):
            raise ValueError("invalid_partition_order")
        ranges.append((start, end))
    if (set(descriptor) != {"schema_version", "kind", "source", "venue", "interval_seconds", "rights_reference", "receipt", "partitions"}
            or descriptor["schema_version"] != 1 or descriptor["source"] != SOURCE
            or descriptor["venue"] != "tidelab" or descriptor["interval_seconds"] != 3600
            or descriptor["rights_reference"] != "TideLab-authored"
            or descriptor["receipt"] != "tidelab-synthetic-generator-v1"
            or set(descriptor["partitions"]) != set(plan["markets"])):
        raise ValueError("unsupported_snapshot")
    for market, part in descriptor["partitions"].items():
        if (not TOKEN.fullmatch(market) or set(part) != {"start", "end", "warmup_bars", "sha256"}
                or not DIGEST.fullmatch(part["sha256"])
                or type(part["warmup_bars"]) is not int or part["warmup_bars"] < 1
                or {k: part[k] for k in ("start", "end")} != plan["partitions"]["development"]
                or int((ranges[0][1] - ranges[0][0]) / HOUR) + part["warmup_bars"] > plan["max_bars"]):
            raise ValueError("invalid_snapshot_partition")


def prepare_jobs(plan: dict, descriptor: dict, packages: dict, package_validator=validate_package_domain) -> list[dict]:
    inventory, seen = [], {}
    for index, job in enumerate(plan["jobs"]):
        item = {"index": index, "job": job, "status": "admitted"}
        try:
            if not isinstance(job, dict) or set(job) != {"package", "market", "cost", "benchmark"}:
                raise ValueError("invalid_job_fields")
            if job["market"] not in plan["markets"] or job["cost"] not in plan["costs"]:
                raise ValueError("unknown_job_input")
            if job["benchmark"] not in (None, "cash", "passive"):
                raise UnsupportedPackage("unsupported_benchmark")
            source = packages[job["package"]]
            item["inputs"] = {key: source[key] for key in ("package_sha256", "record_sha256")}
            if source.get("error"):
                raise ValueError(source["error"])
            parsed = package_validator(source["package"], source["record"])
            if parsed.warmup > descriptor["partitions"][job["market"]]["warmup_bars"]:
                raise UnsupportedPackage("insufficient_declared_warmup")
            semantic = {"rule": source["package"]["rule"], "requirements": source["package"]["requirements"]}
            if job["benchmark"]:
                semantic = {"benchmark": job["benchmark"], "allocation": plan["benchmark_allocation"]}
            key = digest(canonical_json({"semantic": semantic, "market": job["market"], "cost": job["cost"]}).encode())
            item["configuration_key"] = key
            if key in seen:
                item.update(status="duplicate", reason="duplicate_configuration", duplicate_of=seen[key])
            else:
                seen[key] = index
        except UnsupportedPackage as exc:
            item.update(status="unsupported", reason=str(exc))
        except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
            item.update(status="invalid", reason=type(exc).__name__)
        inventory.append(item)
    return inventory


class Metrics:
    def __init__(self, initial: Decimal, stream):
        self.initial = self.peak = self.final = initial
        self.drawdown = self.fees = self.notional = Decimal(0)
        self.fills = self.round_trips = self.held = self.count = 0
        self.units = Decimal(0)
        self.stream = stream

    def emit(self, row):
        self.stream.write(canonical_json(row) + "\n")
        self.count += 1
        self.final, self.units = Decimal(row["equity"]), Decimal(row["units"])
        self.held += self.units > 0
        self.peak = max(self.peak, self.final)
        self.drawdown = max(self.drawdown, (self.peak - self.final) / self.peak)
        if row["fill"]:
            fill = row["fill"]
            self.fills += 1
            self.round_trips += fill["side"] == "sell"
            self.fees += Decimal(fill["fee"])
            self.notional += Decimal(fill["quantity"]) * Decimal(fill["price"])

    def result(self, *, kind="synthetic"):
        return {"net_return": str(self.final / self.initial - 1), "max_drawdown": str(self.drawdown),
                "fill_count": self.fills, "round_trips": self.round_trips, "fees": str(self.fees),
                "turnover": str(self.notional / self.initial), "exposure": str(Decimal(self.held) / self.count),
                "terminal_units": str(self.units), "terminal_equity": str(self.final),
                "scored_bars": self.count, "evidence": ("descriptive_synthetic_scenario" if kind == "synthetic"
                    else "descriptive_private_historical_scenario")}


def complete_job(registry, batch_id, item, directory):
    artifact_hash = verify(directory)
    result = read(directory / "result.json")
    if (result["index"] != item["index"] or result["attempt_id"] != item.get("attempt_id")
            or result.get("identity_sha256") != item.get("identity", {}).get("identity_sha256")):
        raise ValueError("job_identity_mismatch")
    attempt = item.get("attempt_id")
    if attempt and registry.status(attempt) is None and result["status"] != "aborted":
        raise ValueError("missing_trial_start")
    if attempt and registry.status(attempt) is not None:
        registry.finish(attempt, result["status"], datetime.fromisoformat(result["finished_utc"]),
                        reason_code=result.get("reason"), artifact_sha256=artifact_hash)
    registry.finish_job(batch_id, item["index"], {**result, "artifact_sha256": artifact_hash,
                                               "artifact_directory": directory.name})


def close_batch(registry, batch_id, output, status):
    state = registry.batch(batch_id)
    summary = {"batch_id": batch_id, "status": status, "jobs": list(state["jobs"].values()),
               "submitted_jobs": len(state["inventory"]),
               "distinct_configurations": len({x["configuration_key"] for x in state["inventory"] if x.get("configuration_key")}),
               "reserved_executable_jobs": sum("attempt_id" in x for x in state["inventory"]),
               "attempt_count": len(state["attempt_statuses"]),
               "terminal_attempt_count": sum(value != "open" for value in state["attempt_statuses"].values()),
               "strategy_jobs": sum(x["job"].get("benchmark") is None for x in state["inventory"] if isinstance(x["job"], dict)),
               "benchmark_jobs": sum(x["job"].get("benchmark") is not None for x in state["inventory"] if isinstance(x["job"], dict))}
    if not (output / "summary.json").exists():
        write(output / "summary.json", summary)
    elif read(output / "summary.json") != summary:
        raise ValueError("summary_registry_mismatch")
    artifact = verify(output) if (output / "manifest.json").exists() else finalize(output)
    registry.finish_batch(batch_id, status, artifact)
    return summary


def run(plan_path: Path, descriptor_path: Path, database: Path, registry_path: Path,
        output: Path, *, retry_of: str | None = None, checkpoint=lambda _: None, _policy=None) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    with exclusive(output):
        return _run(plan_path, descriptor_path, database, registry_path, output, retry_of, checkpoint, _policy)


def _run(plan_path, descriptor_path, database, registry_path, output, retry_of, checkpoint, policy=None):
    check_plan = policy.preflight if policy else preflight
    package_validator = policy.package if policy else validate_package_domain
    reader = policy.read_partition if policy else read_partition
    started = perf_counter()
    batch_id = "batch-" + uuid4().hex
    write(output / "attempt.json", {"batch_id": batch_id, "started_utc": now()})
    inputs = output / "inputs"
    inputs.mkdir()
    try:
        raw = freeze(plan_path, inputs / "plan.json", 4 * 1024 * 1024)
        plan_hash = digest(raw)
        plan = parse_json_bytes(raw, max_bytes=4 * 1024 * 1024)
        desc_raw = freeze(descriptor_path, inputs / "snapshot.json", 1024 * 1024)
        descriptor = parse_json_bytes(desc_raw, max_bytes=1024 * 1024)
        check_plan(plan, descriptor)
        if digest(desc_raw) != plan["snapshot_sha256"]:
            raise ValueError("descriptor_digest_mismatch")
        packages = {}
        for index, ref in enumerate(plan["packages"]):
            if set(ref) != {"id", "package", "record", "package_sha256", "record_sha256"} or ref["id"] in packages:
                raise ValueError("invalid_package_reference")
            package_raw = freeze(plan_path.parent / ref["package"], inputs / f"package-{index}.json")
            record_raw = freeze(plan_path.parent / ref["record"], inputs / f"record-{index}.json")
            source = {"package_sha256": digest(package_raw), "record_sha256": digest(record_raw)}
            try:
                if any(source[k] != ref[k] for k in source):
                    raise ValueError("source_bytes_changed")
                source.update(package=parse_json_bytes(package_raw), record=parse_json_bytes(record_raw))
            except (ValueError, UnicodeError) as exc:
                source["error"] = type(exc).__name__
            packages[ref["id"]] = source
        inventory = prepare_jobs(plan, descriptor, packages, package_validator)
        revision = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
        runtime = {"code_revision": revision, "python": platform.python_version(),
                   "sources": {name: digest((ROOT / "src/tidelab" / name).read_bytes()) for name in SOURCES}}
        write(inputs / "runtime.json", runtime)
        inputs_hash = finalize(inputs)
        for item in inventory:
            item["inputs_sha256"] = inputs_hash
            if item["status"] != "admitted":
                continue
            job = item["job"]
            item["attempt_id"] = f"{batch_id}.{item['index']}"
            item["identity"] = build_experiment_identity(
                engine={"name": "tidelab-package-replay", "version": "v2", "source_revision": revision},
                code={"repository": "Loothore907:tidelab", "revision": revision},
                configuration={"id": f"{plan['family']}.{plan['generation']}.{item['index']}",
                               "sha256": digest(canonical_json({"plan": plan, "job": job, "inputs": inputs_hash}).encode())},
                data={"source_id": descriptor["source"], "revision": plan["generation"], "sha256": descriptor["partitions"][job["market"]]["sha256"],
                      "kind": descriptor["kind"], "rights_reference": descriptor["rights_reference"]},
                cost={"model_id": job["cost"], "revision": "v1", "sha256": digest(canonical_json(plan["costs"][job["cost"]]).encode())},
                trial={"strategy_id": f"{plan['family']}.{item['configuration_key']}", "strategy_version": plan["generation"],
                       "trial_id": f"{plan['family']}.{plan['generation']}.{item['index']}", "sequence": item["index"] + 1,
                       "origin": "human", "parent_trial_id": None})
        write(output / "admission.json", {"batch_id": batch_id, "plan_sha256": plan_hash,
                                         "inputs_sha256": inputs_hash, "inventory": inventory})
    except (ValueError, KeyError, TypeError, ArithmeticError, OSError) as exc:
        result = {"status": "blocked", "reason": str(exc), "batch_id": batch_id,
                  "jobs": [{"index": i, "status": "blocked"} for i, _ in enumerate(
                      plan["jobs"] if isinstance(locals().get("plan"), dict) and isinstance(plan.get("jobs"), list) else [])]}
        write(output / "rejection.json", result)
        finalize(output)
        return result
    registry = TrialRegistry(registry_path)
    registry.initialize()
    reason = registry.reserve_batch(batch_id, family=plan["family"], generation=plan["generation"],
                                    phase=plan["phase"], plan_sha256=plan_hash, inventory=inventory, retry_of=retry_of)
    if reason:
        result = {"status": "blocked", "reason": reason, "batch_id": batch_id}
        write(output / "rejection.json", result)
        finalize(output)
        return result
    checkpoint("reserved")
    for item in inventory:
        if item["status"] == "admitted":
            registry.start(item["attempt_id"], item["identity"], "development", datetime.now(timezone.utc))
    checkpoint("started")
    cache, failed_markets = {}, set()
    for item in inventory:
        index, job = item["index"], item["job"]
        directory = output / f"job-{index}"
        directory.mkdir()
        result = {"index": index, "attempt_id": item.get("attempt_id"), "status": item["status"],
                  "identity_sha256": item.get("identity", {}).get("identity_sha256")}
        if item["status"] == "admitted":
            try:
                if job["market"] in failed_markets:
                    raise ValueError("partition_previously_failed")
                if job["market"] not in cache:
                    try:
                        cache[job["market"]] = reader(database, descriptor, job["market"],
                            capture=lambda rows: write(output / f"market-{plan['markets'].index(job['market'])}.json", {"rows": rows}))
                    except (ValueError, ArithmeticError, OSError, sqlite3.Error) as exc:
                        failed_markets.add(job["market"])
                        raise ValueError("partition_read_failed") from exc
                source = packages[job["package"]]
                strategy = package_validator(source["package"], source["record"])
                if job["benchmark"]:
                    strategy = replace(strategy, target_fraction=Decimal(plan["benchmark_allocation"]))
                cost = validate_cost(plan["costs"][job["cost"]])
                with (directory / "trace.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
                    metrics = Metrics(cost["initial_cash"], stream)
                    replay_package(strategy, cache[job["market"]], **cost,
                                   score_start=descriptor["partitions"][job["market"]]["warmup_bars"],
                                   benchmark=job["benchmark"], emit=metrics.emit)
                    stream.flush()
                    os.fsync(stream.fileno())
                result.update(status="completed", metrics=metrics.result(kind=descriptor["kind"]))
            except (ValueError, ArithmeticError, OSError) as exc:
                result.update(status="failed", reason="evaluation_failed")
                write(directory / "failure.json", {"exception": type(exc).__name__, "reason": str(exc),
                                                     "cause": str(exc.__cause__) if exc.__cause__ else None})
        else:
            result["reason"] = item.get("reason", item["status"])
        result["finished_utc"] = now()
        write(directory / "result.json", result)
        finalize(directory)
        checkpoint("artifact")
        complete_job(registry, batch_id, item, directory)
    write(output / "timing.json", {"elapsed_seconds": perf_counter() - started,
                                   "markets_read": len(cache), "failed_markets": sorted(failed_markets)})
    state = registry.batch(batch_id)
    status = "failed" if any(x["status"] == "failed" for x in state["jobs"].values()) else "completed"
    return close_batch(registry, batch_id, output, status)


def recover(output: Path, registry_path: Path, *, abort: bool = False) -> dict:
    """Complete verified artifact metadata or explicitly abort; never read prices."""
    registry = TrialRegistry(registry_path)
    with exclusive(output):
        admission = read(output / "admission.json")
        batch_id = admission["batch_id"]
        state = registry.batch(batch_id)
        if (admission["inventory"] != state["inventory"] or admission["plan_sha256"] != state["plan_sha256"]
                or verify(output / "inputs") != admission["inputs_sha256"]
                or any(x["inputs_sha256"] != admission["inputs_sha256"] for x in state["inventory"])):
            raise ValueError("admission_identity_mismatch")
        if state["terminal"]:
            if verify(output) != state["terminal"]["artifact_sha256"]:
                raise ValueError("batch_artifact_mismatch")
            return read(output / "summary.json")
        # Precheck all unfinished jobs so a missing artifact cannot cause partial recovery.
        if not abort and any(not (output / f"job-{x['index']}" / "manifest.json").exists()
                             for x in state["inventory"] if x["index"] not in state["jobs"]):
            raise ValueError("unfinished_execution_requires_explicit_abort")
        for item in state["inventory"]:
            directory = output / f"job-{item['index']}"
            if item["index"] in state["jobs"]:
                directory = output / state["jobs"][item["index"]]["artifact_directory"]
                if verify(directory) != state["jobs"][item["index"]]["artifact_sha256"]:
                    raise ValueError("job_artifact_mismatch")
                continue
            prior_abort = output / f"abort-{item['index']}"
            if (prior_abort / "manifest.json").exists():
                complete_job(registry, batch_id, item, prior_abort)
                continue
            if (directory / "manifest.json").exists():
                complete_job(registry, batch_id, item, directory)
                continue
            directory.mkdir(exist_ok=True)
            # Preserve a partial result as-is; abort metadata has its own artifact directory.
            abort_dir = output / f"abort-{item['index']}"
            abort_dir.mkdir(exist_ok=True)
            result = {"index": item["index"], "attempt_id": item.get("attempt_id"),
                      "status": "aborted", "reason": "operator_aborted", "finished_utc": now(),
                      "identity_sha256": item.get("identity", {}).get("identity_sha256")}
            if not (abort_dir / "result.json").exists():
                write(abort_dir / "result.json", result)
            finalize(abort_dir)
            complete_job(registry, batch_id, item, abort_dir)
        state = registry.batch(batch_id)
        status = "aborted" if any(x["status"] == "aborted" for x in state["jobs"].values()) else (
            "failed" if any(x["status"] == "failed" for x in state["jobs"].values()) else "completed")
        return close_batch(registry, batch_id, output, status)
