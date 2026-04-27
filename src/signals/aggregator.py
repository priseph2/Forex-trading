from datetime import datetime, timezone

from src.signals.models import Direction, PairResult, Signal
from src.strategies.base import BaseStrategy


def aggregate_signals(
    pair: str,
    signals: list[Signal],
    strategies: list[BaseStrategy],
) -> PairResult:
    """
    Weighted voting: sum confidence * strategy_weight per direction.
    If BUY and SELL scores are within 10% of total, override to HOLD to avoid razor-thin calls.
    """
    weight_map = {s.name: s.weight for s in strategies}
    scores: dict[Direction, float] = {
        Direction.BUY: 0.0,
        Direction.SELL: 0.0,
        Direction.HOLD: 0.0,
    }

    for sig in signals:
        w = weight_map.get(sig.strategy, 1.0)
        scores[sig.direction] += sig.confidence * w

    total_score = sum(scores.values())

    buy_score = scores[Direction.BUY]
    sell_score = scores[Direction.SELL]

    if total_score > 0 and abs(buy_score - sell_score) / total_score < 0.10:
        combined = Direction.HOLD
        combined_confidence = 0.5
    else:
        combined = max(scores, key=lambda d: scores[d])
        combined_confidence = scores[combined] / total_score if total_score > 0 else 0.5

    combined_confidence = max(0.0, min(1.0, combined_confidence))

    return PairResult(
        pair=pair,
        timestamp=datetime.now(timezone.utc),
        signals=signals,
        combined=combined,
        combined_confidence=combined_confidence,
    )
