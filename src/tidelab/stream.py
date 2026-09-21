from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from typing import Any
from uuid import uuid4

from tidelab.config import CoinbaseConfig, StreamConfig
from tidelab.domain import MarketEvent, canonical_json, decimal_text, stable_id, utc_now
from tidelab.storage import TideStore


@dataclass(frozen=True)
class StreamResult:
    session_id: str
    message_count: int
    candle_observations: int
    heartbeat_messages: int
    sequence_gap_count: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def missing_sequence_count(previous: int | None, current: int | None) -> int:
    if previous is None or current is None or current <= previous + 1:
        return 0
    return current - previous - 1


def parse_websocket_events(
    message: dict[str, Any],
    *,
    venue: str,
    product_id: str,
    received_at: datetime,
    session_id: str,
) -> list[MarketEvent]:
    if message.get("channel") != "candles":
        return []
    sequence = message.get("sequence_num")
    output: list[MarketEvent] = []
    for event_index, envelope in enumerate(message.get("events", [])):
        if not isinstance(envelope, dict):
            continue
        for candle_index, candle in enumerate(envelope.get("candles", [])):
            if not isinstance(candle, dict):
                continue
            required = ("start", "open", "high", "low", "close", "volume", "product_id")
            if any(field not in candle for field in required):
                continue
            if str(candle["product_id"]) != product_id:
                continue
            event_time = datetime.fromtimestamp(int(candle["start"]), tz=timezone.utc)
            output.append(
                MarketEvent(
                    venue=venue,
                    instrument_id=f"{venue}:{product_id}",
                    event_type="candle_observation",
                    event_time=event_time,
                    received_at=received_at,
                    source="coinbase.websocket.candles",
                    interval_seconds=300,
                    closed=False,
                    payload={
                        "open": decimal_text(candle["open"], "open"),
                        "high": decimal_text(candle["high"], "high"),
                        "low": decimal_text(candle["low"], "low"),
                        "close": decimal_text(candle["close"], "close"),
                        "volume": decimal_text(candle["volume"], "volume"),
                        "granularity": "FIVE_MINUTE_LIVE_UPDATE",
                    },
                    native=candle,
                    source_key=f"{session_id}:{sequence}:{event_index}:{candle_index}",
                )
            )
    return output


async def capture_public_stream(
    coinbase: CoinbaseConfig,
    stream: StreamConfig,
    store: TideStore,
    *,
    duration_seconds: float,
) -> StreamResult:
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")
    try:
        from websockets.asyncio.client import connect
    except ImportError as exc:
        raise RuntimeError("websockets dependency is not installed") from exc

    session_id = uuid4().hex
    instrument_id = f"{coinbase.venue}:{coinbase.product_id}"
    store.start_stream_session(session_id, coinbase.venue, instrument_id)
    message_count = candle_count = heartbeat_count = gap_count = 0
    last_sequence: int | None = None

    try:
        async with connect(
            coinbase.websocket_url,
            open_timeout=stream.open_timeout_seconds,
            close_timeout=5,
            ping_interval=20,
            ping_timeout=20,
        ) as websocket:
            for channel in stream.channels:
                request: dict[str, Any] = {"type": "subscribe", "channel": channel}
                if channel != "heartbeats":
                    request["product_ids"] = [coinbase.product_id]
                await websocket.send(json.dumps(request))

            loop = asyncio.get_running_loop()
            deadline = loop.time() + duration_seconds
            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    break
                try:
                    raw_message = await asyncio.wait_for(websocket.recv(), timeout=remaining)
                except TimeoutError:
                    break
                received_at = utc_now()
                message = json.loads(raw_message)
                if not isinstance(message, dict):
                    continue
                channel = str(message.get("channel", message.get("type", "unknown")))
                sequence_raw = message.get("sequence_num")
                sequence = int(sequence_raw) if sequence_raw is not None else None
                if sequence is not None:
                    gap_count += missing_sequence_count(last_sequence, sequence)
                    if last_sequence is None or sequence > last_sequence:
                        last_sequence = sequence
                message_time = message.get("timestamp")
                observation_id = stable_id(
                    session_id,
                    channel,
                    str(sequence),
                    str(message_time),
                    canonical_json(message),
                )
                inserted = store.insert_stream_message(
                    observation_id=observation_id,
                    session_id=session_id,
                    channel=channel,
                    sequence_num=sequence,
                    message_time=str(message_time) if message_time is not None else None,
                    received_at=received_at,
                    native=message,
                )
                if not inserted:
                    continue
                message_count += 1
                if channel == "heartbeats":
                    heartbeat_count += 1
                events = parse_websocket_events(
                    message,
                    venue=coinbase.venue,
                    product_id=coinbase.product_id,
                    received_at=received_at,
                    session_id=session_id,
                )
                if events:
                    result = store.insert_events(events)
                    candle_count += result.inserted
    except BaseException as exc:
        interrupted = isinstance(exc, (KeyboardInterrupt, asyncio.CancelledError))
        store.finish_stream_session(
            session_id,
            status="interrupted" if interrupted else "failed",
            message_count=message_count,
            sequence_gap_count=gap_count,
            error=f"{type(exc).__name__}: {exc}",
        )
        raise

    store.finish_stream_session(
        session_id,
        status="complete",
        message_count=message_count,
        sequence_gap_count=gap_count,
    )
    return StreamResult(
        session_id=session_id,
        message_count=message_count,
        candle_observations=candle_count,
        heartbeat_messages=heartbeat_count,
        sequence_gap_count=gap_count,
    )


def capture_public_stream_sync(
    coinbase: CoinbaseConfig,
    stream: StreamConfig,
    store: TideStore,
    *,
    duration_seconds: float,
) -> StreamResult:
    return asyncio.run(
        capture_public_stream(
            coinbase,
            stream,
            store,
            duration_seconds=duration_seconds,
        )
    )
