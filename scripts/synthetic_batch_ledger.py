"""Inspect or repair the ignored synthetic batch ledger without rerunning inputs."""

from __future__ import annotations

import argparse
from pathlib import Path

from tidelab.domain import canonical_json
from tidelab.synthetic_batch_ledger import SyntheticBatchLedger


ROOT = Path(__file__).resolve().parents[1]
DATA = (ROOT / "data").resolve()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("summary", "recover"))
    parser.add_argument("--ledger", type=Path,
                        default=DATA / "strategy_batch" / "synthetic_trials.sqlite3")
    parser.add_argument("--artifact", type=Path)
    args = parser.parse_args()
    ledger_path = args.ledger.resolve()
    if not ledger_path.is_relative_to(DATA):
        raise ValueError("synthetic ledger must stay under private data")
    ledger = SyntheticBatchLedger(ledger_path)
    ledger.initialize()
    if args.action == "summary":
        if args.artifact is not None:
            raise ValueError("summary does not take an artifact")
        print(canonical_json(ledger.summary()))
        return
    if args.artifact is None:
        raise ValueError("recover needs an existing artifact")
    artifact = args.artifact.resolve()
    if not artifact.is_relative_to(DATA) or artifact.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("artifact must be a bounded private synthetic output")
    print(canonical_json(ledger.complete(artifact.relative_to(DATA).as_posix(),
                                         artifact.read_bytes())))


if __name__ == "__main__":
    main()
