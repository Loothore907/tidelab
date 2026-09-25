"""Record a local trial launch and terminal status around one command."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from tidelab.trial_registry import TrialRegistry


ROOT = Path(__file__).resolve().parents[1]


def local_data_path(value: str, parser: argparse.ArgumentParser) -> Path:
    path = Path(value).resolve()
    if not path.is_relative_to((ROOT / "data").resolve()):
        parser.error("trial identity, registry and log must stay under ignored data/")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--identity", required=True)
    parser.add_argument("--phase", required=True,
                        choices=("development", "validation", "untouched"))
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--log", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("a trial command is required after --")
    registry_path = local_data_path(args.registry, parser)
    identity_path = local_data_path(args.identity, parser)
    log_path = local_data_path(args.log, parser)
    if log_path.exists():
        parser.error("trial log already exists")
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    registry = TrialRegistry(registry_path)
    registry.initialize()
    registry.start(args.attempt_id, identity, args.phase, datetime.now(timezone.utc))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with log_path.open("xb") as output:
            result = subprocess.run(command, cwd=ROOT, stdout=output,
                                    stderr=subprocess.STDOUT, check=False)
        log_digest = sha256(log_path.read_bytes()).hexdigest()
        registry.finish(args.attempt_id,
                        "completed" if result.returncode == 0 else "failed",
                        datetime.now(timezone.utc),
                        reason_code=None if result.returncode == 0 else
                        f"exit-{result.returncode}", artifact_sha256=log_digest)
    except BaseException:
        if registry.status(args.attempt_id) == "open":
            registry.finish(args.attempt_id, "aborted", datetime.now(timezone.utc),
                            reason_code="runner-interrupted",
                            artifact_sha256=sha256(log_path.read_bytes()).hexdigest()
                            if log_path.exists() else None)
        raise
    print(f"attempt={args.attempt_id} outcome={registry.status(args.attempt_id)} "
          f"log_sha256={log_digest}")
    if result.returncode:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
