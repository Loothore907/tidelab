"""CLI boundary used only by the pinned LEAN synthetic integration probe."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tidelab.lean_paper_join import LeanSyntheticPaperJoin  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "claim", "reconcile",
                                           "prepare-sell", "claim-sell", "reconcile-sell"))
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
    elif args.action == "reconcile":
        print(join.reconcile())
    elif args.action == "prepare-sell":
        print("sell_prepared" if join.prepare_sell() else "sell_existing")
    elif args.action == "claim-sell":
        if not join.claim_sell():
            raise RuntimeError("durable sell intent already claimed")
        print("sell_claimed")
    else:
        print(join.reconcile_sell())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
