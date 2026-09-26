"""Bounded synthetic package comparison against actual pinned LEAN execution.

Every invocation reserves a new attempt directory before parsing or building.
The engine input contains rules and invented bars, never expected signals/fills.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Any

from tidelab.domain import canonical_json
from tidelab.strategy_batch import (SYNTHETIC_COST, UnsupportedPackage,
                                    evaluate_synthetic, parse_json_bytes,
                                    parse_package, parse_synthetic_bars)

LEAN_PIN = "88bce0fc6fe282378ee73c54cef1090d0d7a73ee"
CONTRACT = "tidelab-package-lean-synthetic-v1"
MONEY_FIELDS = {"cash", "equity", "price", "fee"}
EXACT_DECIMAL_FIELDS = {"units", "quantity"}
TOLERANCE = Decimal("1e-18")
ROOT = Path(__file__).resolve().parents[2]
RUNTIME_SOURCES = ("src/tidelab/package_lean_parity.py", "src/tidelab/strategy_batch.py",
                   "src/tidelab/strategy_intake.py", "src/tidelab/domain.py",
                   "scripts/package_lean_parity.py", "scripts/package_lean/Program.cs",
                   "scripts/package_lean/PackageLean.csproj")


def source_identity() -> dict[str, str]:
    return {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in RUNTIME_SOURCES}


def _write(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args],
                                   text=True, encoding="utf-8").strip()


def _domain(value: str) -> None:
    number = Decimal(value)
    if not number.is_finite() or abs(number) > Decimal("1e9") or number.as_tuple().exponent < -8:
        raise UnsupportedPackage("outside_cross_runtime_decimal_domain")


def validate_input(package: dict, record: dict, fixture: dict):
    strategy = parse_package(package, record)
    if record["source"]["kind"] != "synthetic_example":
        raise UnsupportedPackage("synthetic_intake_required")
    bars = parse_synthetic_bars(fixture)
    if len(bars) > 10000:
        raise UnsupportedPackage("fixture_bar_limit")
    for item in fixture["bars"]:
        _domain(item["open"])
        _domain(item["close"])
    _domain(package["rule"]["target_fraction"])

    def walk(node):
        if isinstance(node, dict):
            if node.get("op") == "number":
                _domain(node["value"])
            for item in node.values():
                walk(item)
        elif isinstance(node, list):
            for item in node:
                walk(item)
    walk(package["rule"])
    return strategy, bars


def compare_traces(expected: Any, observed: Any, path: str = "trace") -> list[dict]:
    """Return named mismatches; never coerce missing fields or nonfinite numbers."""
    differences = []

    def fail():
        differences.append({"field": path, "python": expected, "lean": observed})

    field = path.rsplit(".", 1)[-1]
    if field in MONEY_FIELDS | EXACT_DECIMAL_FIELDS:
        if not isinstance(expected, str) or not isinstance(observed, str):
            fail()
        else:
            try:
                left, right = Decimal(expected), Decimal(observed)
                tolerance = TOLERANCE if field in MONEY_FIELDS else Decimal(0)
                if not left.is_finite() or not right.is_finite() or abs(left - right) > tolerance:
                    fail()
            except ArithmeticError:
                fail()
    elif type(expected) is not type(observed):
        fail()
    elif isinstance(expected, dict):
        if expected.keys() != observed.keys():
            fail()
        else:
            for key in expected:
                differences.extend(compare_traces(expected[key], observed[key], f"{path}.{key}"))
    elif isinstance(expected, list):
        if len(expected) != len(observed):
            fail()
        else:
            for index, (left, right) in enumerate(zip(expected, observed)):
                differences.extend(compare_traces(left, right, f"{path}[{index}]"))
    elif expected != observed:
        fail()
    return differences


def run_parity(package_path: Path, record_path: Path, fixture_path: Path,
               lean_root: Path, dotnet: str, output: Path) -> dict:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    sources = source_identity()
    _write(output / "attempt.json", {
        "contract": CONTRACT, "started_utc": datetime.now(timezone.utc).isoformat(),
        "state": "started", "lean_pin": LEAN_PIN,
        "tidelab_head": _git(ROOT, "rev-parse", "HEAD"),
        "tidelab_dirty": bool(_git(ROOT, "status", "--porcelain")),
        "cost": SYNTHETIC_COST,
        "cost_sha256": sha256(canonical_json(SYNTHETIC_COST).encode()).hexdigest(),
        "runtime_sources": sources,
    })
    try:
        inputs = {}
        identities = {}
        for name, path, limit in (("package", package_path, 65536),
                                  ("record", record_path, 65536),
                                  ("fixture", fixture_path, 4 * 1024 * 1024)):
            if path.stat().st_size > limit:
                raise ValueError(f"{name} exceeds size limit")
            raw = path.read_bytes()
            with (output / f"{name}.json").open("xb") as handle:
                handle.write(raw)
            identities[name] = sha256(raw).hexdigest()
            inputs[name] = parse_json_bytes(raw, max_bytes=limit)
        _write(output / "identities.json", identities)
        strategy, bars = validate_input(inputs["package"], inputs["record"], inputs["fixture"])
        trace = []
        summary = evaluate_synthetic(strategy, bars, trace=trace)
        expected = {"trace": trace, "order_count": summary["fill_count"],
                    "fill_count": summary["fill_count"]}
        _write(output / "python.json", expected)
        lean_root = lean_root.resolve()
        if _git(lean_root, "rev-parse", "HEAD") != LEAN_PIN:
            raise ValueError("wrong_LEAN_pin")
        if _git(lean_root, "status", "--porcelain"):
            raise ValueError("modified_LEAN_source")
        sdk = subprocess.check_output([dotnet, "--version"], text=True, encoding="utf-8").strip()
        if not sdk.startswith("10."):
            raise ValueError("dotnet_10_required")
        _write(output / "runtime.json", {"dotnet_sdk": sdk, "lean_pin": LEAN_PIN})
        _write(output / "engine-input.json", {
            "package": inputs["package"], "fixture": inputs["fixture"], "cost": SYNTHETIC_COST})
        project = ROOT / "scripts/package_lean/PackageLean.csproj"
        with (output / "build.log").open("x", encoding="utf-8") as log:
            subprocess.run([dotnet, "build", str(project), "-c", "Release",
                            f"-p:LeanRoot={lean_root}", "-p:RunAnalyzers=false",
                            "-p:WarningLevel=0", "-v", "quiet"],
                           stdout=log, stderr=subprocess.STDOUT, check=True, timeout=600)
        if sources != source_identity():
            raise ValueError("source_changed_during_build")
        assembly = project.parent / "bin/Release/net10.0/PackageLean.dll"
        with (output / "engine.log").open("x", encoding="utf-8") as log:
            subprocess.run([dotnet, str(assembly), str(output / "engine-input.json"),
                            str(output / "lean.json"), str(lean_root / "Data")],
                           cwd=output, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120)
        if sources != source_identity():
            raise ValueError("source_changed_during_execution")
        observed = parse_json_bytes((output / "lean.json").read_bytes(), max_bytes=64 * 1024 * 1024)
        differences = compare_traces(expected, observed, "result")
        result = {"status": "matched" if not differences else "mismatch",
                  "contract": CONTRACT, "identities": identities, "differences": differences}
    except UnsupportedPackage as exc:
        result = {"status": "unsupported", "reason": str(exc)}
    except (ValueError, KeyError, TypeError, ArithmeticError, OSError, subprocess.SubprocessError) as exc:
        result = {"status": "failed", "reason": f"{type(exc).__name__}: {exc}"}
    _write(output / "result.json", result)
    return result
