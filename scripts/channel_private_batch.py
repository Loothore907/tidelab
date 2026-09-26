"""Frozen channel trial, canonical store only; the run has a hard 30-minute cap."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from tidelab import channel_private as channel
from tidelab import historical_batch as batch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["authorize", "prepare", "run"])
    parser.add_argument("--terms-reviewed-utc-date", required=True)
    args = parser.parse_args()
    if args.action != "run":
        print(json.dumps(getattr(channel, args.action)(args.terms_reviewed_utc_date)))
        return
    # Child executes only the frozen function. Timeout kills it, retains its spent
    # admission/incomplete artifacts, and never invokes recovery or a retry.
    code = ("import sys,json; sys.path.insert(0, 'src'); "
            "from tidelab.channel_private import execute; print(json.dumps(execute(sys.argv[1])))")
    try:
        subprocess.run([sys.executable, "-c", code, args.terms_reviewed_utc_date], cwd=ROOT,
                       timeout=1800, check=True,
                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    except subprocess.TimeoutExpired:
        batch.write(channel.study() / "execution-timeout.json",
                    {"status": "incomplete", "limit_seconds": 1800, "no_retry": True, "utc": batch.now()})
        raise SystemExit("channel execution cap reached; retain incomplete attempt; no retry")


if __name__ == "__main__":
    main()
