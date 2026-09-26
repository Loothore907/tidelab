"""Run one phase of the private, frozen five-market TL-003 screen.

This reads existing ignored OKX history only. Real-data outputs and the trial
registry stay under ignored data/tl003_screen_v1/. No orders or feeds exist here.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from tidelab.candidate_screen import (BASE, END, FAMILIES, PARTITIONS, SOURCE,
                                      STRESS, passes, preflight, read_bars, replay)
from tidelab.domain import canonical_json
from tidelab.experiment_identity import build_experiment_identity
from tidelab.trial_registry import TrialRegistry


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "tl003_screen_v1"
DATABASE = ROOT / "data" / "okx" / "research.sqlite3"
PLAN = ROOT / "research" / "first-pass-universe-v1.json"
PREREG = ROOT / "docs" / "experiments" / "FIVE-MARKET-SCREEN-V1-PREREGISTRATION.md"
TERMS_URL = "https://www.okx.com/en-us/help/historicaldata-terms-and-conditions"


def _command(*args: str) -> str:
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def integrated_head() -> str:
    """Refuse real-data reads from an unintegrated or unchecked source head."""
    if _command("git", "status", "--porcelain") or _command("git", "branch", "--show-current") != "main":
        raise RuntimeError("private screen requires clean integrated main")
    head = _command("git", "rev-parse", "HEAD")
    if head != _command("git", "rev-parse", "origin/main"):
        raise RuntimeError("main and origin/main differ")
    remote = _command("git", "ls-remote", "origin", "refs/heads/main").split()[0]
    if head != remote:
        raise RuntimeError("origin/main is not fresh")
    runs = json.loads(_command("gh", "run", "list", "--repo", "Loothore907/tidelab",
                               "--commit", head, "--json", "headSha,workflowName,status,conclusion",
                               "--limit", "20"))
    if not any(run["headSha"] == head and run["workflowName"] == "CI"
               and run["status"] == "completed" and run["conclusion"] == "success"
               for run in runs):
        raise RuntimeError("exact-head remote CI has not passed")
    return head


def _write_new(path: Path, payload: dict[str, object]) -> str:
    raw = (canonical_json(payload) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as output:
        output.write(raw)
    return sha256(raw).hexdigest()


def _read_decision(phase: str, code_revision: str, config_hash: str) -> dict:
    path = DATA / f"{phase}-decision.json"
    decision = json.loads(path.read_text(encoding="utf-8"))
    if decision["code_revision"] != code_revision or decision["configuration_sha256"] != config_hash:
        raise RuntimeError("selection belongs to a different integrated source or configuration")
    selected = decision["selected"]
    if selected is not None:
        result_path = DATA / "attempts" / f"{selected['attempt_id']}.json"
        raw = result_path.read_bytes()
        result = json.loads(raw)
        if (sha256(raw).hexdigest() != selected["artifact_sha256"]
                or result["decision"] != "survived"
                or (result["instrument"], result["family"]) !=
                    (selected["instrument"], selected["family"])
                or TrialRegistry(DATA / "trials.sqlite3").status(selected["attempt_id"]) != "completed"):
            raise RuntimeError("prior selected trial evidence differs")
    return decision


def _trial_identity(instrument: str, family: str, phase: str,
                    data_hash: str, plan_hash: str, code_revision: str,
                    config_hash: str, cost_hash: str, reviewed: date,
                    parent_attempt: str | None) -> dict:
    suffix = instrument.replace(":", "-")
    return build_experiment_identity(
        engine={"name": "tidelab-offline-screen", "version": "v1",
                "source_revision": code_revision},
        code={"repository": "Loothore907:tidelab", "revision": code_revision},
        configuration={"id": "five-market-screen-v1", "sha256": config_hash},
        data={"source_id": SOURCE, "revision": f"{plan_hash[:12]}-{phase}",
              "sha256": data_hash, "kind": "third_party",
              "rights_reference": f"okx-historical-personal-{reviewed.isoformat()}"},
        cost={"model_id": "five-market-screen-cost", "revision": "v1",
              "sha256": cost_hash},
        trial={"strategy_id": f"{family}.{suffix}", "strategy_version": "v1",
               "trial_id": f"{phase}.{family}.{suffix}", "sequence": 1,
               "origin": "human", "parent_trial_id": parent_attempt},
    )


def _run_one(registry: TrialRegistry, instrument: str, family: str, phase: str,
             bars: list, data_hash: str, plan_hash: str, code_revision: str,
             config_hash: str, cost_hash: str, reviewed: date,
             parent_attempt: str | None) -> dict:
    suffix = instrument.replace(":", "-")
    attempt = f"screen-v1-{phase}-{suffix}-{family}"
    if registry.status(attempt) is not None:
        raise RuntimeError("screen attempt already launched; do not rerun an opened result")
    identity = _trial_identity(instrument, family, phase, data_hash, plan_hash,
                               code_revision, config_hash, cost_hash, reviewed,
                               parent_attempt)
    registry.start(attempt, identity, phase, datetime.now(timezone.utc))
    try:
        base = replay(bars, family, BASE)
        stress = replay(bars, family, STRESS)
        primary = replay(bars, family, BASE, benchmark=True)
        primary_stress = replay(bars, family, STRESS, benchmark=True)
        full = replay(bars, family, BASE, allocation=Decimal(1), benchmark=True)
        full_stress = replay(bars, family, STRESS, allocation=Decimal(1), benchmark=True)
        status = passes(base, stress, primary)
        result = {"schema_version": 1, "attempt_id": attempt, "phase": phase,
                  "instrument": instrument, "family": family,
                  "identity": identity, "parent_attempt_id": parent_attempt,
                  "partition_start_utc": PARTITIONS[phase][0].isoformat(),
                  "partition_end_utc": PARTITIONS[phase][1].isoformat(),
                  "source_plan_sha256": plan_hash, "data_sha256": data_hash,
                  "terms_url": TERMS_URL, "terms_reviewed_utc_date": reviewed.isoformat(),
                  "cash_net_return": "0", "base": base, "stress": stress,
                  "primary_25pct": primary, "primary_stress": primary_stress,
                  "full_buy_hold": full, "full_buy_hold_stress": full_stress,
                  "margin_over_primary": str(Decimal(base["net_return"])
                                             - Decimal(primary["net_return"])),
                  "decision": status, "warnings": ["hourly-full-fill-scenario",
                                                    "historical-archive-is-delayed"]}
        artifact_hash = _write_new(DATA / "attempts" / f"{attempt}.json", result)
        registry.finish(attempt, "completed", datetime.now(timezone.utc),
                        artifact_sha256=artifact_hash)
        return {"instrument": instrument, "family": family,
                "attempt_id": attempt, "artifact_sha256": artifact_hash,
                "decision": status, "margin_over_primary": result["margin_over_primary"],
                "max_drawdown": base["max_drawdown"]}
    except BaseException:
        if registry.status(attempt) == "open":
            registry.finish(attempt, "failed", datetime.now(timezone.utc),
                            reason_code="screen-evaluation-error")
        raise


def run(phase: str, reviewed: date) -> dict:
    if reviewed != datetime.now(timezone.utc).date():
        raise ValueError("review the current official OKX terms on the UTC run date")
    code_revision = integrated_head()
    if (DATA / f"{phase}-decision.json").exists():
        raise RuntimeError("phase decision already recorded")
    instruments, plan_hash = preflight(DATABASE, PLAN)
    config_hash = sha256(PREREG.read_bytes()).hexdigest()
    cost_hash = sha256(canonical_json({
        "base": {key: str(value) for key, value in BASE.items()},
        "stress": {key: str(value) for key, value in STRESS.items()},
    }).encode("utf-8")).hexdigest()
    selected = None
    parent_attempt = None
    if phase != "development":
        prior = _read_decision("development" if phase == "validation" else "validation",
                               code_revision, config_hash)
        selected = prior["selected"]
        if selected is None or (phase == "untouched" and prior["outcome"] != "survived"):
            raise RuntimeError("prior phase did not nominate a candidate")
        parent_attempt = selected["attempt_id"]
    registry = TrialRegistry(DATA / "trials.sqlite3")
    registry.initialize()
    outcomes = []
    for instrument in instruments:
        for family in FAMILIES:
            if selected is not None and (instrument, family) != (selected["instrument"], selected["family"]):
                continue
            bars, data_hash = read_bars(DATABASE, instrument, phase)
            outcomes.append(_run_one(registry, instrument, family, phase, bars, data_hash,
                                     plan_hash, code_revision, config_hash, cost_hash,
                                     reviewed, parent_attempt))
    if phase == "development":
        survivors = [item for item in outcomes if item["decision"] == "survived"]
        survivors.sort(key=lambda item: (-Decimal(item["margin_over_primary"]),
                                         Decimal(item["max_drawdown"]),
                                         instruments.index(item["instrument"]),
                                         FAMILIES.index(item["family"])))
        selected = survivors[0] if survivors else None
        outcome = "survived" if selected else "no_development_survivor"
    else:
        selected = outcomes[0] if outcomes[0]["decision"] == "survived" else None
        outcome = outcomes[0]["decision"]
    decision = {"schema_version": 1, "phase": phase, "code_revision": code_revision,
                "configuration_sha256": config_hash, "source_plan_sha256": plan_hash,
                "cost_sha256": cost_hash, "terms_reviewed_utc_date": reviewed.isoformat(),
                "selected": selected, "outcome": outcome, "outcomes": outcomes}
    _write_new(DATA / f"{phase}-decision.json", decision)
    return {"phase": phase, "attempts": len(outcomes), "outcome": outcome,
            "selected": selected is not None}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=tuple(PARTITIONS), required=True)
    parser.add_argument("--terms-reviewed-utc-date", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    print(canonical_json(run(args.phase, args.terms_reviewed_utc_date)))


if __name__ == "__main__":
    main()
