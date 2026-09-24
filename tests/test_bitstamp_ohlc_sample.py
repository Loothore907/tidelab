from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


_SPEC = spec_from_file_location("bitstamp_ohlc_sample", Path(__file__).resolve().parents[1] / "scripts" / "bitstamp_ohlc_sample.py")
assert _SPEC and _SPEC.loader
sample = module_from_spec(_SPEC)
_SPEC.loader.exec_module(sample)


def test_collect_rejects_missing_hour(monkeypatch):
    monkeypatch.setattr(sample, "fetch_page", lambda _start, _limit: [
        {"timestamp": "1704067200", "open": "1", "high": "2", "low": "1", "close": "2", "volume": "1"},
        {"timestamp": "1704074400", "open": "2", "high": "2", "low": "1", "close": "1", "volume": "1"},
    ])
    with pytest.raises(ValueError, match="missing, duplicate, or out-of-window hour"):
        sample.collect(datetime(2024, 1, 1, tzinfo=timezone.utc), datetime(2024, 1, 1, 3, tzinfo=timezone.utc))


def test_collect_rejects_invalid_price(monkeypatch):
    monkeypatch.setattr(sample, "fetch_page", lambda _start, _limit: [
        {"timestamp": "1704067200", "open": "3", "high": "2", "low": "1", "close": "2", "volume": "1"},
    ])
    with pytest.raises(ValueError, match="invalid OHLCV"):
        sample.collect(datetime(2024, 1, 1, tzinfo=timezone.utc), datetime(2024, 1, 1, 1, tzinfo=timezone.utc))
