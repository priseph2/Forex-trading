import logging
from dataclasses import dataclass

from src.data.fetcher import CRYPTO_PAIRS, FOREX_PAIRS, DataFetchError, fetch_ohlcv
from src.signals.aggregator import aggregate_signals
from src.signals.models import Direction, PairResult
from src.strategies.bollinger_strategy import BollingerStrategy
from src.strategies.ema_crossover import EMACrossoverStrategy
from src.strategies.macd_strategy import MACDStrategy
from src.strategies.rsi_strategy import RSIStrategy

logger = logging.getLogger(__name__)

# Pairs the bot actively trades (subset of full lists — most liquid)
BOT_FOREX_PAIRS = list(FOREX_PAIRS.keys())          # all 7 major pairs → OANDA
BOT_CRYPTO_PAIRS = ["BTC/USD", "ETH/USD", "SOL/USD", "BNB/USD", "XRP/USD"]

PAIR_BROKER_MAP: dict[str, str] = {
    **{p: "OANDA" for p in BOT_FOREX_PAIRS},
    **{p: "BINANCE" for p in BOT_CRYPTO_PAIRS},
}

_STRATEGIES = [
    EMACrossoverStrategy(),
    RSIStrategy(),
    MACDStrategy(),
    BollingerStrategy(),
]

MIN_CONFIDENCE = 0.60


@dataclass
class ScanResult:
    pair: str
    broker: str
    direction: str          # "BUY" or "SELL"
    confidence: float
    pair_result: PairResult


def _scan_single_pair(pair: str) -> ScanResult | None:
    try:
        ohlcv = fetch_ohlcv(pair, period_days=60, timeframe="1d")
        signals = [s.generate(pair, ohlcv) for s in _STRATEGIES]
        result = aggregate_signals(pair, signals, _STRATEGIES)
    except DataFetchError as e:
        logger.warning("Scan failed for %s: %s", pair, e)
        return None
    except Exception as e:
        logger.warning("Unexpected error scanning %s: %s", pair, e)
        return None

    if result.combined == Direction.HOLD:
        return None
    if result.combined_confidence < MIN_CONFIDENCE:
        return None

    broker = PAIR_BROKER_MAP.get(pair, "OANDA")

    # Binance Spot cannot short
    if result.combined == Direction.SELL and broker == "BINANCE":
        logger.debug("Skipping SELL signal for %s — Binance Spot does not support shorting", pair)
        return None

    return ScanResult(
        pair=pair,
        broker=broker,
        direction=result.combined.value,
        confidence=result.combined_confidence,
        pair_result=result,
    )


def scan_all_pairs(exclude_pairs: set[str] | None = None) -> list[ScanResult]:
    """Scan all bot pairs and return qualifying signals sorted by confidence."""
    exclude = exclude_pairs or set()
    all_pairs = BOT_FOREX_PAIRS + BOT_CRYPTO_PAIRS
    results = []
    for pair in all_pairs:
        if pair in exclude:
            continue
        result = _scan_single_pair(pair)
        if result:
            results.append(result)
    return sorted(results, key=lambda r: r.confidence, reverse=True)


def get_top_candidates(
    max_candidates: int = 2,
    exclude_pairs: set[str] | None = None,
) -> list[ScanResult]:
    """Return the top N highest-confidence signals. Empty list means skip today."""
    return scan_all_pairs(exclude_pairs=exclude_pairs)[:max_candidates]
