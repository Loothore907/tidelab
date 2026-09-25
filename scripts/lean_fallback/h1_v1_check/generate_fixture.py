"""Generate TideLab-authored hourly values for the H1 v1 LEAN decision probe."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from zoneinfo import ZoneInfo


def main(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    first_start = datetime(2026, 1, 1, 5, tzinfo=timezone.utc)
    closes = [100] * 168 + [102, 98, 110]
    days: dict[str, list[str]] = {}
    for offset, close in enumerate(closes):
        start = first_start + timedelta(hours=offset)
        # LEAN requests each custom-data file by the subscription's New York
        # date, while each line retains its UTC bar start.
        local_day = start.astimezone(ZoneInfo("America/New_York"))
        days.setdefault(local_day.strftime("%Y%m%d"), []).append(
            f"{start:%Y-%m-%d %H:%M:%S},{close},"
            f"{closes[offset - 1] if offset else 100}\n"
        )
    for day, lines in days.items():
        (destination / f"{day}.csv").write_text("".join(lines), encoding="ascii")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
