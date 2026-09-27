"""Offline synthetic historical batches and artifact-only recovery."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tidelab.historical_batch import run, recover
from tidelab.historical_batch_demo import create_demo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo")
    demo.add_argument("--output", type=Path, required=True)
    modes = demo.add_mutually_exclusive_group()
    modes.add_argument("--scale", action="store_true")
    modes.add_argument("--channel", action="store_true")
    modes.add_argument("--monday", action="store_true")
    launch = commands.add_parser("run")
    for field in ("plan", "snapshot", "database", "registry", "output"):
        launch.add_argument("--" + field, type=Path, required=True)
    launch.add_argument("--retry-of")
    recovery = commands.add_parser("recover")
    recovery.add_argument("--output", type=Path, required=True)
    recovery.add_argument("--registry", type=Path, required=True)
    recovery.add_argument("--abort", action="store_true")
    args = parser.parse_args()
    if args.command == "demo":
        args.output.mkdir(parents=True, exist_ok=False)
        plan, snapshot, database = create_demo(args.output / "fixture", scale=args.scale, channel=args.channel, monday=args.monday)
        result = run(plan, snapshot, database, args.output / "trials.sqlite3", args.output / "attempt")
        if args.channel:
            from tidelab.channel_breakout import review_artifacts
            from tidelab.historical_batch import write
            write(args.output / "review.json", review_artifacts(args.output / "attempt"))
    elif args.command == "run":
        result = run(args.plan, args.snapshot, args.database, args.registry, args.output, retry_of=args.retry_of)
    else:
        result = recover(args.output, args.registry, abort=args.abort)
    print(json.dumps({key: value for key, value in result.items() if key != "jobs"}, indent=2))
    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
