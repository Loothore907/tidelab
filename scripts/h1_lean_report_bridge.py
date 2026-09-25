"""Cross-process SQLite gate for the pinned LEAN synthetic H1 report probe."""

from __future__ import annotations

import argparse
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tidelab.h1_local_report_join import H1LocalReportJoin, _digest  # noqa: E402
from tidelab.h1_paper_bridge import H1SyntheticPaperBridge  # noqa: E402
from tidelab.paper_intent import PaperProductRules  # noqa: E402


def complete_report(path: Path) -> str:
    candidate = path.with_name(path.name + ".next")
    if candidate.exists():
        raise RuntimeError("torn H1 report candidate; hold")
    payload = path.read_text(encoding="utf-8")
    if candidate.exists():
        raise RuntimeError("torn H1 report candidate; hold")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "claim", "reconcile",
                                           "state", "revision", "handoff"))
    parser.add_argument("database", type=Path)
    parser.add_argument("proposal", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("next_proposal", type=Path, nargs="?")
    args = parser.parse_args()
    payload = args.proposal.read_text(encoding="utf-8")
    proposal = json.loads(payload)
    opening = datetime.fromisoformat(proposal["ObservedOpenUtc"].replace("Z", "+00:00"))
    rules = PaperProductRules(proposal["InstrumentId"], "synthetic-h1-rules-1",
                              "0.00000001", "0.01", "0.00000001", "1")
    bridge = H1SyntheticPaperBridge(args.database)
    bridge.initialize()
    join = H1LocalReportJoin(args.database)
    join.initialize()
    if args.action == "prepare":
        intent = bridge.prepare(payload, observed_at=opening,
                                source_revision=proposal["SourceRevision"], rules=rules)
        print(f"prepared client={intent.client_id} quantity={intent.quantity}")
    elif args.action == "claim":
        if not bridge.claim_once(proposal["ClientId"], observed_at=opening,
                                 opening_utc=opening,
                                 source_revision=proposal["SourceRevision"], rules=rules):
            raise RuntimeError("H1 intent is not claimable")
        print("claimed")
    elif args.action == "reconcile":
        print(join.reconcile(payload, complete_report(args.report)))
    elif args.action == "revision":
        report = json.loads(complete_report(args.report),
                            parse_float=Decimal)
        print("h1-report-v1:" + _digest(report))
    elif args.action == "handoff":
        if args.next_proposal is None:
            parser.error("handoff requires next_proposal")
        print(join.handoff(payload, complete_report(args.report),
                           args.next_proposal.read_text(encoding="utf-8"), rules))
    else:
        print(bridge.intents.state(proposal["ClientId"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
