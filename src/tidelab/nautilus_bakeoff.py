"""Isolated TL-001A compatibility probe; not a production engine adapter.

The optional NautilusTrader dependency is imported only when the probe runs.
No venue connection, market-data download, account access, or order submission occurs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Sequence

from tidelab.domain import MarketEvent, isoformat_utc, stable_id


HOUR = timedelta(hours=1)


@dataclass(frozen=True)
class AdmittedBars:
    bars: tuple[object, ...]
    source_event_ids: tuple[str, ...]
    fixture_id: str


def admit_hourly_bars(events: Sequence[MarketEvent], *, instrument_id: object) -> AdmittedBars:
    """Map only complete, consecutive synthetic bars to Nautilus close timestamps.

    Rejecting rather than silently filling a gap makes an incomplete experiment
    unmistakable. The original TideLab event IDs remain separate from engine data.
    """
    from nautilus_trader.model import Bar, BarAggregation, BarSpecification, BarType
    from nautilus_trader.model import Price, PriceType, Quantity

    if not events:
        raise ValueError("at least one hourly bar is required")
    if str(instrument_id) != "BTC-USDT.SIM":
        raise ValueError("unexpected engine instrument")
    bar_type = BarType(
        instrument_id,
        BarSpecification(1, BarAggregation.HOUR, PriceType.LAST),
    )
    bars = []
    event_ids = []
    previous_start = None
    for event in events:
        if event.source != "synthetic.fixture":
            raise ValueError("the bakeoff accepts only synthetic fixtures")
        if event.event_type != "bar" or event.interval_seconds != 3600 or not event.closed:
            raise ValueError("a closed hourly bar is required")
        if event.instrument_id != "SIM:BTC-USDT":
            raise ValueError("unexpected synthetic instrument")
        if event.event_time.utcoffset() != timedelta(0):
            raise ValueError("bar start must be UTC")
        if event.event_time.minute or event.event_time.second or event.event_time.microsecond:
            raise ValueError("bar start must align to an hour")
        if previous_start is not None and event.event_time != previous_start + HOUR:
            raise ValueError("duplicate, unordered, or missing hourly bar")
        close_time = event.event_time + HOUR
        if event.received_at < close_time:
            raise ValueError("bar was received before closure")
        values = {key: Decimal(str(event.payload[key])) for key in
                  ("open", "high", "low", "close", "volume")}
        if any(not value.is_finite() for value in values.values()):
            raise ValueError("bar values must be finite")
        if any(values[key] <= 0 for key in ("open", "high", "low", "close")):
            raise ValueError("invalid OHLCV bar")
        if values["volume"] < 0 or values["low"] > min(values["open"], values["close"]):
            raise ValueError("invalid OHLCV bar")
        if values["high"] < max(values["open"], values["close"]):
            raise ValueError("invalid OHLCV bar")
        if values["high"] < values["low"]:
            raise ValueError("invalid OHLCV bar")
        if any(value.as_tuple().exponent < -2 for key, value in values.items()
               if key != "volume"):
            raise ValueError("price exceeds synthetic instrument precision")
        if values["volume"].as_tuple().exponent < -3:
            raise ValueError("volume exceeds synthetic instrument precision")
        close_ns = int(close_time.timestamp()) * 1_000_000_000
        bars.append(Bar(
            bar_type=bar_type,
            open=Price.from_str(f"{values['open']:.2f}"),
            high=Price.from_str(f"{values['high']:.2f}"),
            low=Price.from_str(f"{values['low']:.2f}"),
            close=Price.from_str(f"{values['close']:.2f}"),
            volume=Quantity.from_str(f"{values['volume']:.3f}"),
            ts_event=close_ns,
            ts_init=close_ns,
        ))
        event_ids.append(event.event_id)
        previous_start = event.event_time
    return AdmittedBars(
        bars=tuple(bars),
        source_event_ids=tuple(event_ids),
        fixture_id=stable_id(*event_ids),
    )


def trend_signal(closes: Sequence[Decimal]) -> str:
    """Unoptimized H1 skeleton shared by sequential and engine-clock probes."""
    if len(closes) < 3:
        return "warming"
    fast = sum(closes[-2:]) / 2
    slow = sum(closes[-3:]) / 3
    return "long" if fast > slow else "cash"


def run_probe(events: Sequence[MarketEvent]) -> dict[str, object]:
    """Replay synthetic bars and return deterministic signal/provenance evidence."""
    import nautilus_trader
    from nautilus_trader.backtest import BacktestEngine, BacktestEngineConfig
    from nautilus_trader.model import AccountType, Currency, CurrencyPair, InstrumentId
    from nautilus_trader.model import Money, OmsType, Price, Quantity, Symbol, Venue
    from nautilus_trader.trading import Strategy

    if nautilus_trader.__version__ != "2.0.0rc5":
        raise RuntimeError("TL-001A probe requires NautilusTrader 2.0.0rc5")

    venue = Venue("SIM")
    instrument_id = InstrumentId(Symbol("BTC-USDT"), venue)
    admitted = admit_hourly_bars(events, instrument_id=instrument_id)
    instrument = CurrencyPair(
        instrument_id=instrument_id,
        raw_symbol=Symbol("BTC-USDT"),
        base_currency=Currency.from_str("BTC"),
        quote_currency=Currency.from_str("USDT"),
        price_precision=2,
        size_precision=3,
        price_increment=Price.from_str("0.01"),
        size_increment=Quantity.from_str("0.001"),
        ts_event=0,
        ts_init=0,
        min_quantity=Quantity.from_str("0.001"),
        min_notional=Money(1, Currency.from_str("USDT")),
        maker_fee=Decimal("0.001"),
        taker_fee=Decimal("0.001"),
    )

    class SignalObserver(Strategy):
        def __init__(self) -> None:
            super().__init__()
            self.closes: list[Decimal] = []
            self.signals: list[str] = []
            self.timestamps: list[int] = []

        def on_start(self) -> None:
            self.subscribe_bars(admitted.bars[0].bar_type)

        def on_bar(self, bar: object) -> None:
            self.closes.append(Decimal(str(bar.close)))
            self.signals.append(trend_signal(self.closes))
            self.timestamps.append(bar.ts_event)

    observer = SignalObserver()
    engine = BacktestEngine(BacktestEngineConfig(bypass_logging=True, run_analysis=False))
    try:
        engine.add_venue(
            venue=venue,
            oms_type=OmsType.NETTING,
            account_type=AccountType.CASH,
            starting_balances=[Money(10_000, Currency.from_str("USDT"))],
            base_currency=None,
        )
        engine.add_instrument(instrument)
        engine.add_strategy(observer)
        engine.add_data(admitted.bars)
        engine.run()
        expected = [trend_signal([Decimal(str(bar.close)) for bar in admitted.bars[:n]])
                    for n in range(1, len(admitted.bars) + 1)]
        if observer.signals != expected:
            raise AssertionError("engine and sequential strategy semantics diverged")
        if observer.timestamps != [bar.ts_event for bar in admitted.bars]:
            raise AssertionError("engine callback order or timing diverged")
        return {
            "engine": "nautilus_trader",
            "engine_version": nautilus_trader.__version__,
            "fixture_id": admitted.fixture_id,
            "source_event_ids": admitted.source_event_ids,
            "first_close": isoformat_utc(events[0].event_time + HOUR),
            "last_close": isoformat_utc(events[-1].event_time + HOUR),
            "signals": tuple(observer.signals),
            "orders_submitted": 0,
        }
    finally:
        engine.dispose()
