import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np

from bot.scanner import get_top_candidates, scan_all_pairs, ScanResult


def _make_ohlcv(n=100, trend="up") -> pd.DataFrame:
    """Synthetic OHLCV data with a clear trend for deterministic signals."""
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    if trend == "up":
        close = np.linspace(1.0, 1.15, n)
    else:
        close = np.linspace(1.15, 1.0, n)
    df = pd.DataFrame({
        "open": close * 0.999,
        "high": close * 1.002,
        "low": close * 0.998,
        "close": close,
        "volume": np.ones(n) * 1000,
    }, index=dates)
    return df


@patch("bot.scanner.fetch_ohlcv")
def test_get_top_candidates_returns_results(mock_fetch):
    mock_fetch.return_value = _make_ohlcv(100, trend="up")
    results = get_top_candidates(max_candidates=2)
    # At least some pairs should produce signals on a strong uptrend
    assert isinstance(results, list)
    assert len(results) <= 2
    for r in results:
        assert isinstance(r, ScanResult)
        assert r.direction in ("BUY", "SELL")
        assert 0.0 <= r.confidence <= 1.0


@patch("bot.scanner.fetch_ohlcv")
def test_get_top_candidates_excludes_pairs(mock_fetch):
    mock_fetch.return_value = _make_ohlcv(100, trend="up")
    from bot.scanner import BOT_FOREX_PAIRS, BOT_CRYPTO_PAIRS
    all_pairs = set(BOT_FOREX_PAIRS + BOT_CRYPTO_PAIRS)
    results = get_top_candidates(max_candidates=5, exclude_pairs=all_pairs)
    assert results == []


@patch("bot.scanner.fetch_ohlcv")
def test_scan_handles_fetch_error(mock_fetch):
    from src.data.fetcher import DataFetchError
    mock_fetch.side_effect = DataFetchError("API down")
    results = scan_all_pairs()
    # Should return empty list gracefully, not raise
    assert results == []


@patch("bot.scanner.fetch_ohlcv")
def test_no_binance_sell_signals(mock_fetch):
    mock_fetch.return_value = _make_ohlcv(100, trend="down")
    from bot.scanner import BOT_FOREX_PAIRS
    results = scan_all_pairs(exclude_pairs=set(BOT_FOREX_PAIRS))
    # Any crypto results must be BUY only
    for r in results:
        if r.broker == "BINANCE":
            assert r.direction == "BUY", f"BINANCE SELL found for {r.pair}"


@patch("bot.scanner.fetch_ohlcv")
def test_results_sorted_by_confidence(mock_fetch):
    mock_fetch.return_value = _make_ohlcv(100, trend="up")
    results = get_top_candidates(max_candidates=10)
    confidences = [r.confidence for r in results]
    assert confidences == sorted(confidences, reverse=True)
