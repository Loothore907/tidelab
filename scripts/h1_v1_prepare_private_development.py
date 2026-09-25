"""Prepare one ignored H1 development bundle after manually reviewing OKX terms."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import subprocess

from tidelab.h1_private_trial import prepare_development


ROOT = Path(__file__).resolve().parents[1]


def private_path(value: str, parser: argparse.ArgumentParser) -> Path:
    path = Path(value).resolve()
    if not path.is_relative_to((ROOT / "data").resolve()):
        parser.error("all market input and output paths must stay under ignored data/")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--archive-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--terms-reviewed-utc-date", type=date.fromisoformat,
                        required=True)
    args = parser.parse_args()
    database = private_path(args.database, parser)
    archives = private_path(args.archive_dir, parser)
    output = private_path(args.output_dir, parser)
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT).strip():
        parser.error("commit tested source before preparing a real-data trial")
    if subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT).decode().strip() != "main":
        parser.error("prepare private source only from integrated main")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    upstream = subprocess.check_output(["git", "rev-parse", "origin/main"], cwd=ROOT).decode().strip()
    if revision != upstream:
        parser.error("main and the fetched origin/main must be even")
    result = prepare_development(ROOT, database, archives, output, revision,
                                 args.terms_reviewed_utc_date)
    print("prepared private development input " + " ".join(
        f"{name}={value}" for name, value in result.items()))


if __name__ == "__main__":
    main()
