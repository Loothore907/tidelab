from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import sys
from typing import Any

from tidelab.coinbase import CoinbasePublicClient
from tidelab.config import AppConfig, load_config
from tidelab.domain import isoformat_utc, parse_utc, utc_now
from tidelab.lean_hourly_export import export_lean_hourly_closes
from tidelab.okx_archive import import_okx_archive
from tidelab.service import refresh_product, sync_closed_bars
from tidelab.storage import TideStore
from tidelab.stream import capture_public_stream_sync


def _json_print(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def _hour_boundary(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def _parse_hour(value: str) -> datetime:
    parsed = parse_utc(value)
    if parsed != _hour_boundary(parsed):
        raise argparse.ArgumentTypeError("timestamp must be aligned to an exact UTC hour")
    return parsed


def _runtime(config_path: str) -> tuple[AppConfig, TideStore, CoinbasePublicClient]:
    config = load_config(config_path)
    store = TideStore(config.storage.path)
    store.initialize()
    return config, store, CoinbasePublicClient(config.coinbase)


def _add_bounds(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--start", required=True, type=_parse_hour, help="inclusive UTC hour")
    parser.add_argument("--end", required=True, type=_parse_hour, help="exclusive UTC hour")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tidelab", description="TideLab TL-001 public-data recorder")
    parser.add_argument("--config", default="config.toml", help="TOML configuration path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="initialize the local SQLite schema")
    subparsers.add_parser("metadata", help="refresh public product metadata")

    okx_parser = subparsers.add_parser("import-okx", help="import a local OKX daily or monthly archive")
    okx_parser.add_argument("--file", required=True, help="downloaded OKX candlestick ZIP")
    okx_parser.add_argument("--symbol", required=True, help="spot symbol, for example BTC-USDT")
    okx_parser.add_argument("--period", required=True, help="archive period, YYYY-MM or YYYY-MM-DD")
    okx_parser.add_argument("--database", required=True, help="local SQLite path")

    lean_parser = subparsers.add_parser("export-lean-h1", help="export complete local hourly closes for LEAN's signal reader")
    lean_parser.add_argument("--database", required=True, help="existing local SQLite path")
    lean_parser.add_argument("--venue", required=True, help="exact venue identifier")
    lean_parser.add_argument("--instrument", required=True, help="exact canonical instrument identifier")
    lean_parser.add_argument("--source", required=True, help="exact recorded bar source")
    lean_parser.add_argument("--output", required=True, help="new ignored local directory for daily CSV files")
    _add_bounds(lean_parser)

    sync_parser = subparsers.add_parser("sync", help="synchronize closed hourly bars")
    _add_bounds(sync_parser)

    report_parser = subparsers.add_parser("report", help="report gaps, freshness, and duplicate attempts")
    _add_bounds(report_parser)

    stream_parser = subparsers.add_parser("stream", help="capture the public WebSocket feed")
    stream_parser.add_argument("--seconds", type=float, default=10.0)

    smoke_parser = subparsers.add_parser("smoke", help="run bounded public REST/WebSocket validation")
    smoke_parser.add_argument("--hours", type=int, default=24)
    smoke_parser.add_argument("--stream-seconds", type=float, default=10.0)
    return parser


def run(args: argparse.Namespace) -> int:
    if args.command == "import-okx":
        store = TideStore(args.database)
        result = import_okx_archive(args.file, symbol=args.symbol, period=args.period, store=store)
        _json_print(result.as_dict())
        return 0
    if args.command == "export-lean-h1":
        result = export_lean_hourly_closes(
            TideStore(args.database), venue=args.venue, instrument_id=args.instrument,
            source=args.source, start=args.start, end=args.end, output_dir=args.output,
        )
        _json_print(result.as_dict())
        return 0
    config, store, client = _runtime(args.config)
    if args.command == "init":
        _json_print({"database": str(config.storage.path), "status": "initialized"})
        return 0
    if args.command == "metadata":
        _json_print(refresh_product(client, store))
        return 0
    if args.command == "sync":
        metadata = refresh_product(client, store)
        result = sync_closed_bars(client, store, start=args.start, end=args.end)
        _json_print({"metadata": metadata, "sync": result.as_dict()})
        return 0
    if args.command == "report":
        report = store.hourly_report(
            venue=config.coinbase.venue,
            instrument_id=f"{config.coinbase.venue}:{config.coinbase.product_id}",
            start=args.start,
            end=args.end,
            stale_after_seconds=config.report.stale_after_seconds,
        )
        _json_print(report.as_dict())
        return 1 if report.missing_bars else 0
    if args.command == "stream":
        result = capture_public_stream_sync(
            config.coinbase,
            config.stream,
            store,
            duration_seconds=args.seconds,
        )
        _json_print(result.as_dict())
        return 0
    if args.command == "smoke":
        if args.hours < 1:
            raise ValueError("hours must be positive")
        end = _hour_boundary(utc_now())
        start = end - timedelta(hours=args.hours)
        metadata = refresh_product(client, store)
        first_sync = sync_closed_bars(client, store, start=start, end=end)
        restart_sync = sync_closed_bars(client, store, start=start, end=end)
        stream_result = capture_public_stream_sync(
            config.coinbase,
            config.stream,
            store,
            duration_seconds=args.stream_seconds,
        )
        report = store.hourly_report(
            venue=config.coinbase.venue,
            instrument_id=f"{config.coinbase.venue}:{config.coinbase.product_id}",
            start=start,
            end=end,
            stale_after_seconds=config.report.stale_after_seconds,
        )
        output = {
            "window": {"start": isoformat_utc(start), "end": isoformat_utc(end)},
            "metadata": metadata,
            "first_sync": first_sync.as_dict(),
            "restart_sync": restart_sync.as_dict(),
            "stream": stream_result.as_dict(),
            "report": report.as_dict(),
        }
        _json_print(output)
        return 1 if report.missing_bars or stream_result.message_count == 0 else 0
    raise AssertionError(f"unhandled command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except Exception as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
