"""Export the TL-001A synthetic selection trial's portable identity.

Run after committing the tested probe so the TideLab code revision is exact.
The generated manifest belongs in ignored local artifacts, not in source.
"""

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
    parser.add_argument("output", type=Path, help="new local JSON path; existing files are preserved")
    args = parser.parse_args()
    working_changes = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=ROOT, text=True, encoding="utf-8"
    )
    if working_changes.strip():
        parser.error("commit the tested source before exporting its exact code revision")
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()
    inputs = ROOT / "scripts" / "lean_fallback"
    identity = build_experiment_identity(
        engine={
            "name": "lean",
            "version": "pinned-source",
            "source_revision": "88bce0fc6fe282378ee73c54cef1090d0d7a73ee",
        },
        code={"repository": "Loothore907:tidelab", "revision": revision},
        configuration={
            "id": "tl001a-selection-rules-v1",
            "sha256": digest(inputs / "fixtures" / "selection_rules_v1.json"),
        },
        data={
            "source_id": "tl001a-invented-quote-v1",
            "revision": "v1",
            "sha256": digest(inputs / "fixtures" / "selection_quote_v1.json"),
            "kind": "synthetic",
            "rights_reference": "TideLab-authored",
        },
        cost={
            "model_id": "tl001a-conservative-fill-policy",
            "revision": "v1",
            "sha256": digest(inputs / "TideLabConservativePaperFillProbe.cs"),
        },
        trial={
            "strategy_id": "tl001a-selection-compatibility",
            "strategy_version": "v1",
            "trial_id": "joined-selection-gate-v1",
            "sequence": 1,
            "origin": "human",
            "parent_trial_id": None,
        },
    )
    export_experiment_identity(identity, args.output, public_synthetic=True)
    print(f"{args.output.resolve()} identity_sha256={identity['identity_sha256']}")


if __name__ == "__main__":
    main()
