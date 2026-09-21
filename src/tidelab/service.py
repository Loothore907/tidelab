from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from tidelab.coinbase import CoinbasePublicClient
from tidelab.domain import isoformat_utc, utc_now
from tidelab.storage import TideStore


@dataclass(frozen=True)
class SyncResult:
    run_id: int
    requested_start: str
    requested_end: str
    fetched: int
    inserted: int
    duplicates: int
    incomplete_skipped: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def refresh_product(client: CoinbasePublicClient, store: TideStore) -> dict[str, Any]:
    received_at = utc_now()
    instrument = client.fetch_product(received_at)
    store.upsert_instrument(instrument)
    return {
        "instrument_id": instrument.instrument_id,
        "product_class": instrument.product_class,
        "status": instrument.status,
        "base_increment": instrument.base_increment,
        "quote_increment": instrument.quote_increment,
        "base_min_size": instrument.base_min_size,
        "quote_min_size": instrument.quote_min_size,
        "fetched_at": isoformat_utc(instrument.fetched_at),
    }


def sync_closed_bars(
    client: CoinbasePublicClient,
    store: TideStore,
    *,
    start: datetime,
    end: datetime,
) -> SyncResult:
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("sync bounds must be timezone-aware")
    start = start.astimezone(timezone.utc)
    end = end.astimezone(timezone.utc)
    if end <= start:
        raise ValueError("sync end must be after start")

    instrument_id = f"{client.config.venue}:{client.config.product_id}"
    run_id = store.start_ingestion_run(
        "coinbase.public_rest.candles",
        client.config.venue,
        instrument_id,
        start,
        end,
    )
    fetched = inserted = duplicates = incomplete = 0
    try:
        for window_start, window_end in client.candle_windows(start, end):
            received_at = utc_now()
            raw_candles = client.fetch_candle_window(window_start, window_end)
            fetched += len(raw_candles)
            events = []
            for raw in raw_candles:
                event, closed = client.parse_candle(raw, received_at=received_at)
                if event.event_time < window_start or event.event_time >= window_end:
                    continue
                if not closed:
                    incomplete += 1
                    continue
                events.append(event)
            result = store.insert_events(events)
            inserted += result.inserted
            duplicates += result.duplicates
    except BaseException as exc:
        status = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        store.finish_ingestion_run(
            run_id,
            fetched=fetched,
            inserted=inserted,
            duplicate_attempts=duplicates,
            incomplete_skipped=incomplete,
            status=status,
            error=f"{type(exc).__name__}: {exc}",
        )
        raise

    store.finish_ingestion_run(
        run_id,
        fetched=fetched,
        inserted=inserted,
        duplicate_attempts=duplicates,
        incomplete_skipped=incomplete,
        status="complete",
    )
    return SyncResult(
        run_id=run_id,
        requested_start=isoformat_utc(start),
        requested_end=isoformat_utc(end),
        fetched=fetched,
        inserted=inserted,
        duplicates=duplicates,
        incomplete_skipped=incomplete,
    )
