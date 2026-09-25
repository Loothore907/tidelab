"""Audit one ignored H1 result and print only its verification hash."""

from __future__ import annotations

import argparse
from pathlib import Path

from tidelab.h1_trial_review import review_bundle


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--attempt-id", required=True)
    args = parser.parse_args()
    data = (ROOT / "data").resolve()
    bundle = Path(args.bundle).resolve()
    registry = Path(args.registry).resolve()
    if not bundle.is_relative_to(data) or not registry.is_relative_to(data):
        parser.error("private H1 paths must remain under ignored data/")
    digest = review_bundle(bundle, registry, args.attempt_id)
    print(f"H1_PRIVATE_REVIEW status=pass result_sha256={digest}")


if __name__ == "__main__":
    main()
