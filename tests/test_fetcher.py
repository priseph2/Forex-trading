from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.data.fetcher import (
    CRYPTO_PAIRS,
    FOREX_PAIRS,
    DataFetchError,
    fetch_ohlcv,
    get_pairs_for_market,
)


def _make_mock_agg(close: float, ts: int) -> MagicMock:
    agg = MagicMock()
    agg.open = close * 0.9999
    agg.high = close * 1.001
    agg.low = close * 0.999
    agg.close = close
    agg.volume = 1000.0
    agg.timestamp = ts
    return agg


def _make_aggs(n: int) -> list[MagicMock]:
    base_ts = 1704067200000  # 2024-01-01 UTC in milliseconds
    day_ms = 86_400 * 1_000
    return [_make_mock_agg(1.1000 + i * 0.0001, base_ts + i * day_ms) for i in range(n)]


def test_unknown_pair_raises():
    with pytest.raises(DataFetchError, match="Unknown pair"):
        fetch_ohlcv("FOO/BAR")


@patch("src.data.fetcher.RESTClient")
def test_successful_fetch_returns_dataframe(mock_cls):
    mock_cls.return_value.get_aggs.return_value = _make_aggs(100)
    with patch.dict("os.environ", {"POLYGON_API_KEY": "test_key"}):
        df = fetch_ohlcv("EUR/USD", period_days=80)
    assert isinstance(df, pd.DataFrame)
    assert set(df.columns) == {"Open", "High", "Low", "Close", "Volume"}
    assert len(df) >= 60


@patch("src.data.fetcher.RESTClient")
def test_empty_response_raises(mock_cls):
    mock_cls.return_value.get_aggs.return_value = []
    with patch.dict("os.environ", {"POLYGON_API_KEY": "test_key"}):
        with pytest.raises(DataFetchError, match="Empty response"):
            fetch_ohlcv("EUR/USD")


@patch("src.data.fetcher.RESTClient")
def test_short_response_raises(mock_cls):
    mock_cls.return_value.get_aggs.return_value = _make_aggs(30)
    with patch.dict("os.environ", {"POLYGON_API_KEY": "test_key"}):
        with pytest.raises(DataFetchError, match="Insufficient data"):
            fetch_ohlcv("EUR/USD")


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("POLYGON_API_KEY", raising=False)
    with pytest.raises(EnvironmentError, match="POLYGON_API_KEY"):
        fetch_ohlcv("EUR/USD")


# --- Crypto pair tests ---

def test_crypto_unknown_pair_raises():
    with pytest.raises(DataFetchError, match="Unknown pair"):
        fetch_ohlcv("FOO/BAR")


@patch("src.data.fetcher.RESTClient")
def test_crypto_fetch_returns_dataframe(mock_cls):
    mock_cls.return_value.get_aggs.return_value = _make_aggs(100)
    with patch.dict("os.environ", {"POLYGON_API_KEY": "test_key"}):
        df = fetch_ohlcv("BTC/USD", period_days=80)
    assert isinstance(df, pd.DataFrame)
    assert set(df.columns) == {"Open", "High", "Low", "Close", "Volume"}
    assert len(df) >= 60


def test_get_pairs_for_market_forex():
    pairs = get_pairs_for_market("forex")
    assert pairs == FOREX_PAIRS
    assert all(v.startswith("C:") for v in pairs.values())


def test_get_pairs_for_market_crypto():
    pairs = get_pairs_for_market("crypto")
    assert pairs == CRYPTO_PAIRS
    assert all(v.startswith("X:") for v in pairs.values())


def test_get_pairs_for_market_all():
    pairs = get_pairs_for_market("all")
    assert len(pairs) == len(FOREX_PAIRS) + len(CRYPTO_PAIRS)
    assert "EUR/USD" in pairs
    assert "BTC/USD" in pairs


def test_crypto_pairs_have_correct_ticker_format():
    for friendly, ticker in CRYPTO_PAIRS.items():
        assert ticker.startswith("X:"), f"{friendly} ticker '{ticker}' should start with 'X:'"
