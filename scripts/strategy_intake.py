"""Validate and register local source-backed strategy ideas without executing them."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tidelab.domain import canonical_json
from tidelab.strategy_intake import IntakeRegistry, load_record, record_digest


DEFAULT_REGISTRY = ROOT / "data" / "strategy_intake" / "intake.sqlite3"


def _registry(value: str, parser: argparse.ArgumentParser) -> IntakeRegistry:
    target = Path(value).resolve()
    if not target.is_relative_to((ROOT / "data").resolve()):
        parser.error("the real candidate registry must remain under ignored data/")
    registry = IntakeRegistry(target)
    registry.initialize()
    return registry


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("validate", "register", "precode-check"):
        command = sub.add_parser(name)
        command.add_argument("record", type=Path)
        if name != "validate":
            command.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    listing = sub.add_parser("list")
    listing.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    args = parser.parse_args()

    if args.action == "list":
        print(canonical_json(_registry(args.registry, parser).list_latest()))
        return
    record = load_record(args.record)
    if args.action == "validate":
        print(canonical_json({"candidate_id": record["candidate_id"],
                              "version": record["version"], "stage": record["stage"],
                              "sha256": record_digest(record),
                              "meaning": "metadata_shape_only"}))
        return
    registry = _registry(args.registry, parser)
    if args.action == "register":
        added = registry.register(record)
        print(canonical_json({"candidate_id": record["candidate_id"],
                              "version": record["version"], "registered": added,
                              "sha256": record_digest(record),
                              "meaning": "local_record_only"}))
        return
    digest = registry.check_implementation_record(record)
    print(canonical_json({"candidate_id": record["candidate_id"],
                          "version": record["version"], "sha256": digest,
                          "structural_checkpoint": "passed",
                          "external_checks_still_required": [
                              "verify cited owner authority for this exact candidate and scope",
                              "verify current source rights for the proposed implementation",
                              "separately authorize and preregister any real-data trial"]}))


if __name__ == "__main__":
    main()
