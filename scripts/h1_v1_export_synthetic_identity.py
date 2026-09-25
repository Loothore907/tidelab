"""Export a local identity for the fixed H1 v1 invented-input check."""

from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path
import subprocess

from tidelab.experiment_identity import build_experiment_identity, export_experiment_identity


ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="new manifest path under ignored data/")
    args = parser.parse_args()
    destination = args.output.resolve()
    if not destination.is_relative_to((ROOT / "data").resolve()):
        parser.error("synthetic trial manifest must stay under ignored data/")
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT,
                                    text=True, encoding="utf-8")
    if dirty.strip():
        parser.error("commit tested source before recording its code revision")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                       text=True, encoding="utf-8").strip()
    input_path = ROOT / "scripts/lean_fallback/h1_v1_check/synthetic_input.json"
    identity = build_experiment_identity(
        engine={"name": "lean", "version": "pinned-source",
                "source_revision": "88bce0fc6fe282378ee73c54cef1090d0d7a73ee"},
        code={"repository": "Loothore907:tidelab", "revision": revision},
        configuration={"id": "h1-v1-frozen-preregistration",
                       "sha256": digest(ROOT / "docs/experiments/H1-V1-PREREGISTRATION.md")},
        data={"source_id": "h1-v1-invented-input", "revision": "v1",
              "sha256": digest(input_path), "kind": "synthetic",
              "rights_reference": "TideLab-authored"},
        cost={"model_id": "h1-v1-research-cost", "revision": "v1",
              "sha256": digest(ROOT / "scripts/lean_fallback/TideLabH1V1ResearchReplay.cs")},
        trial={"strategy_id": "h1", "strategy_version": "v1",
               "trial_id": "h1-v1-synthetic-accounting", "sequence": 1,
               "origin": "human", "parent_trial_id": None},
    )
    export_experiment_identity(identity, destination, public_synthetic=True)
    print(f"identity_sha256={identity['identity_sha256']} code={revision}")


if __name__ == "__main__":
    main()
