"""CLI boundary used only by the pinned LEAN synthetic integration probe."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tidelab.lean_paper_join import LeanSyntheticPaperJoin  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "claim", "reconcile"))
    parser.add_argument("database", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    join = LeanSyntheticPaperJoin(args.database, args.report)
    join.initialize()
    if args.action == "prepare":
        join.prepare()
        print("prepared")
    elif args.action == "claim":
        if not join.claim():
            raise RuntimeError("durable intent already claimed")
        print("claimed")
    else:
        print(join.reconcile())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
