"""Selected BTC Monday UTC adaptation; no private admission or trial.

Attribution: Caporale and Plastun, DOI10.1016/j.frl.2018.11.012, CC BY4.0.
Source PDF SHA256:4b6ed61e7150d1a4250e27636c9195d323e88218c3a51a33047f5e37737902ff.
Independently written UTC/spot/cash-budget/next-open adaptation, not replication.
Source/license/changes: docs/evidence/TL-003-BTC-MONDAY-SYNTHETIC.md.
"""
from tidelab.strategy_intake import record_digest

CANDIDATE = "caporale-plastun-btc-monday-utc"


def package(record):
    if record["source"]["kind"] != "synthetic_example" and record["candidate_id"] != CANDIDATE:
        raise ValueError("outside_selected_monday_candidate")
    return {"schema_version": 4, "strategy_id": CANDIDATE, "version": 1,
        "source": {"candidate_id": record["candidate_id"], "version": record["version"],
                   "record_sha256": record_digest(record)},
        "requirements": {"interval_seconds": 3600, "product_class": "spot", "position_mode": "long_cash"},
        "rule": {"entry": {"op": "utc_calendar", "weekday": 1, "hour": 0},
                 "exit": {"op": "utc_calendar", "weekday": 2, "hour": 0}, "target_fraction": "0.25"}}


class UnapprovedMondayPolicy:
    @staticmethod
    def preflight(*args, **kwargs):
        raise ValueError("monday_trial_authority_ungranted")

    package = preflight
    read_partition = preflight


def prepare_private(*args, **kwargs):
    UnapprovedMondayPolicy.preflight()


def execute_private(*args, **kwargs):
    UnapprovedMondayPolicy.preflight()
