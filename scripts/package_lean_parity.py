"""Run one retained synthetic package-to-LEAN comparison. See the frozen contract."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tidelab.package_lean_parity import run_parity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("package", "record", "fixture", "lean-root", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--dotnet", default="dotnet")
    args = parser.parse_args()
    result = run_parity(args.package, args.record, args.fixture,
                        args.lean_root, args.dotnet, args.output)
    print(f"{result['status']}: {args.output / 'result.json'}")
    return 0 if result["status"] == "matched" else 1


if __name__ == "__main__":
    raise SystemExit(main())
