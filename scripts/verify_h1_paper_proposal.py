"""Consume one invented C# H1 proposal through the local SQLite paper barrier."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from tidelab.h1_paper_bridge import H1SyntheticPaperBridge
from tidelab.paper_intent import PaperProductRules
from tidelab.synthetic_paper import SyntheticLocalPaperSource


def main(path: Path) -> None:
    payload = path.read_text(encoding="utf-8")
    proposal = json.loads(payload)
    opening = datetime.fromisoformat(proposal["ObservedOpenUtc"].replace("Z", "+00:00"))
    rules = PaperProductRules(proposal["InstrumentId"], "synthetic-h1-rules-1",
                              "0.00000001", "0.01", "0.00000001", "1")
    with TemporaryDirectory() as directory:
        db = Path(directory) / "paper.sqlite3"
        bridge = H1SyntheticPaperBridge(db)
        bridge.initialize()
        intent = bridge.prepare(payload, observed_at=opening,
                                source_revision=proposal["SourceRevision"], rules=rules)
        assert bridge.claim_once(intent.client_id, observed_at=opening,
                                 opening_utc=opening,
                                 source_revision=proposal["SourceRevision"], rules=rules)
        restarted = H1SyntheticPaperBridge(db)
        assert not restarted.claim_once(intent.client_id, observed_at=opening,
                                        opening_utc=opening,
                                        source_revision=proposal["SourceRevision"], rules=rules)
        source = SyntheticLocalPaperSource(db)
        source.initialize()
        assert source.submit(intent.client_id, proposal["SourceRevision"])
        assert source.reconcile(intent.client_id) == "present_hold"
        assert source.order_count(intent.client_id) == 1
        print("H1V1_PAPER_BRIDGE policy=shared intent=durable "
              "restart_claim=blocked local_order=one unresolved=hold")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
