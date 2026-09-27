"""One manifest to authored synthetic results, or existing artifact-only recovery."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tidelab.source_workflow import run, recover


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    launch = commands.add_parser("run")
    launch.add_argument("--manifest", type=Path, required=True)
    launch.add_argument("--output", type=Path, required=True)
    launch.add_argument("--lean-root", type=Path, default=os.environ.get("TIDELAB_LEAN_ROOT"))
    launch.add_argument("--dotnet", default=os.environ.get("TIDELAB_DOTNET", "dotnet"))
    recovery = commands.add_parser("recover")
    recovery.add_argument("--output", type=Path, required=True)
    recovery.add_argument("--abort", action="store_true")
    args = parser.parse_args()
    if args.command == "run":
        if args.lean_root is None:
            parser.error("--lean-root or TIDELAB_LEAN_ROOT is required for the pinned comparison")
        result = run(args.manifest, args.output, lean_root=args.lean_root, dotnet=args.dotnet)
    else:
        result = recover(args.output, abort=args.abort)
    print(json.dumps({"status": result["status"], "compilation": result["compilation_counts"],
        "jobs": result["job_counts"], "parity": result["parity"]["status"],
        "semantic_sha256": result["semantic_sha256"], "results": str(args.output / "results.json")}, indent=2))
    return 0 if result["status"] == "accounted" and result["parity"]["status"] == "matched" else 1


if __name__ == "__main__":
    raise SystemExit(main())
