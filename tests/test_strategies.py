import pandas as pd
import pytest

from src.signals.models import Direction
from src.strategies.bollinger_strategy import BollingerStrategy
from src.strategies.ema_crossover import EMACrossoverStrategy
from src.strategies.macd_strategy import MACDStrategy
from src.strategies.rsi_strategy import RSIStrategy

PAIR = "EUR/USD"
ALL_STRATEGIES = [EMACrossoverStrategy(), RSIStrategy(), MACDStrategy(), BollingerStrategy()]


def test_signal_has_correct_pair(sample_ohlcv):
    for strategy in ALL_STRATEGIES:
        sig = strategy.generate(PAIR, sample_ohlcv)
        assert sig.pair == PAIR


def test_signal_has_correct_strategy_name(sample_ohlcv):
    for strategy in ALL_STRATEGIES:
        sig = strategy.generate(PAIR, sample_ohlcv)
        assert sig.strategy == strategy.name


def test_confidence_bounds(sample_ohlcv, flat_ohlcv, oversold_ohlcv):
    for ohlcv in [sample_ohlcv, flat_ohlcv, oversold_ohlcv]:
        for strategy in ALL_STRATEGIES:
            sig = strategy.generate(PAIR, ohlcv)
            assert 0.0 <= sig.confidence <= 1.0, (
                f"{strategy.name} confidence={sig.confidence} out of [0,1]"
            )


def test_rsi_hold_on_flat(flat_ohlcv):
    sig = RSIStrategy().generate(PAIR, flat_ohlcv)
    assert sig.direction == Direction.HOLD


def test_rsi_buy_on_oversold(oversold_ohlcv):
    sig = RSIStrategy().generate(PAIR, oversold_ohlcv)
    assert sig.direction == Direction.BUY


def test_rsi_sell_on_overbought(overbought_ohlcv):
    sig = RSIStrategy().generate(PAIR, overbought_ohlcv)
    assert sig.direction == Direction.SELL


def test_nan_guard_short_data():
    """All strategies must return HOLD with insufficient_data when fewer than min rows."""
    from datetime import datetime, timezone

    closes = pd.Series([1.1] * 10, dtype=float)
    dates = pd.date_range("2024-01-01", periods=10, freq="B")
    short_df = pd.DataFrame(
        {
            "Open": closes,
            "High": closes,
            "Low": closes,
            "Close": closes,
            "Volume": [1.0] * 10,
        },
        index=dates,
    )
    for strategy in ALL_STRATEGIES:
        sig = strategy.generate(PAIR, short_df)
        assert sig.direction == Direction.HOLD, f"{strategy.name} did not return HOLD"
        assert sig.metadata.get("reason") == "insufficient_data", (
            f"{strategy.name} missing 'insufficient_data' reason"
        )
