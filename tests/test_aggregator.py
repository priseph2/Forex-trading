from datetime import datetime, timezone

import pytest

from src.signals.aggregator import aggregate_signals
from src.signals.models import Direction, Signal
from src.strategies.bollinger_strategy import BollingerStrategy
from src.strategies.ema_crossover import EMACrossoverStrategy
from src.strategies.macd_strategy import MACDStrategy
from src.strategies.rsi_strategy import RSIStrategy

PAIR = "EUR/USD"
STRATEGIES = [EMACrossoverStrategy(), RSIStrategy(), MACDStrategy(), BollingerStrategy()]
_NOW = datetime.now(timezone.utc)


def _sig(strategy_name: str, direction: Direction, confidence: float) -> Signal:
    return Signal(
        pair=PAIR,
        strategy=strategy_name,
        direction=direction,
        confidence=confidence,
        timestamp=_NOW,
    )


def test_unanimous_buy():
    signals = [
        _sig("EMA Crossover", Direction.BUY, 0.9),
        _sig("RSI", Direction.BUY, 0.8),
        _sig("MACD", Direction.BUY, 0.85),
        _sig("Bollinger Bands", Direction.BUY, 0.8),
    ]
    result = aggregate_signals(PAIR, signals, STRATEGIES)
    assert result.combined == Direction.BUY
    assert result.combined_confidence > 0.5


def test_unanimous_sell():
    signals = [
        _sig("EMA Crossover", Direction.SELL, 0.9),
        _sig("RSI", Direction.SELL, 0.8),
        _sig("MACD", Direction.SELL, 0.85),
        _sig("Bollinger Bands", Direction.SELL, 0.8),
    ]
    result = aggregate_signals(PAIR, signals, STRATEGIES)
    assert result.combined == Direction.SELL


def test_all_hold():
    signals = [
        _sig("EMA Crossover", Direction.HOLD, 0.5),
        _sig("RSI", Direction.HOLD, 0.5),
        _sig("MACD", Direction.HOLD, 0.5),
        _sig("Bollinger Bands", Direction.HOLD, 0.5),
    ]
    result = aggregate_signals(PAIR, signals, STRATEGIES)
    assert result.combined == Direction.HOLD


def test_confidence_always_in_bounds():
    for directions in [
        [Direction.BUY, Direction.SELL, Direction.HOLD, Direction.BUY],
        [Direction.SELL, Direction.HOLD, Direction.BUY, Direction.SELL],
    ]:
        signals = [
            _sig(s.name, d, 0.7) for s, d in zip(STRATEGIES, directions)
        ]
        result = aggregate_signals(PAIR, signals, STRATEGIES)
        assert 0.0 <= result.combined_confidence <= 1.0


def test_pair_result_has_all_signals():
    signals = [
        _sig("EMA Crossover", Direction.BUY, 0.9),
        _sig("RSI", Direction.HOLD, 0.5),
        _sig("MACD", Direction.BUY, 0.8),
        _sig("Bollinger Bands", Direction.HOLD, 0.5),
    ]
    result = aggregate_signals(PAIR, signals, STRATEGIES)
    assert len(result.signals) == 4
    assert result.pair == PAIR
