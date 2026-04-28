import os
import time
import warnings
from datetime import datetime, timedelta, timezone
from typing import Literal

import pandas as pd
from dotenv import load_dotenv
from polygon import RESTClient

load_dotenv()

FOREX_PAIRS: dict[str, str] = {
    "EUR/USD": "C:EURUSD",
    "GBP/USD": "C:GBPUSD",
    "USD/JPY": "C:USDJPY",
    "AUD/USD": "C:AUDUSD",
    "USD/CHF": "C:USDCHF",
    "USD/CAD": "C:USDCAD",
    "NZD/USD": "C:NZDUSD",
}

# Top altcoins by market cap (BTC + ETH as benchmarks + liquid altcoins)
CRYPTO_PAIRS: dict[str, str] = {
    "BTC/USD": "X:BTCUSD",
    "ETH/USD": "X:ETHUSD",
    "SOL/USD": "X:SOLUSD",
    "XRP/USD": "X:XRPUSD",
    "ADA/USD": "X:ADAUSD",
    "AVAX/USD": "X:AVAXUSD",
    "DOGE/USD": "X:DOGEUSD",
    "DOT/USD": "X:DOTUSD",
    "LINK/USD": "X:LINKUSD",
    "LTC/USD": "X:LTCUSD",
    "MATIC/USD": "X:MATICUSD",
    "ATOM/USD": "X:ATOMUSD",
}

ALL_PAIRS: dict[str, str] = {**FOREX_PAIRS, **CRYPTO_PAIRS}

Market = Literal["forex", "crypto", "all"]
Timeframe = Literal["1d", "4h", "1h"]

# Maps our timeframe labels to Polygon (multiplier, timespan) and a sensible default period
_TIMEFRAME_CONFIG: dict[str, tuple[int, str, int]] = {
    "1d": (1, "day",  100),  # ~100 daily bars
    "4h": (4, "hour",  30),  # ~180 4h bars over 30 calendar days
    "1h": (1, "hour",  14),  # ~336 1h bars over 14 calendar days
}

TIMEFRAME_LABELS: dict[str, str] = {
    "1d": "Daily (1D)",
    "4h": "4-Hour",
    "1h": "1-Hour",
}


def get_pairs_for_market(market: Market) -> dict[str, str]:
    if market == "forex":
        return FOREX_PAIRS
    if market == "crypto":
        return CRYPTO_PAIRS
    return ALL_PAIRS


def default_period_for(timeframe: Timeframe) -> int:
    return _TIMEFRAME_CONFIG[timeframe][2]


class DataFetchError(RuntimeError):
    pass


def _get_client() -> RESTClient:
    api_key = os.environ.get("POLYGON_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "POLYGON_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return RESTClient(api_key=api_key)


def fetch_ohlcv(
    pair: str,
    period_days: int = 100,
    timeframe: Timeframe = "1d",
) -> pd.DataFrame:
    """
    Fetch OHLCV bars for a forex or crypto pair from Polygon.io.

    Parameters
    ----------
    pair        : friendly name, e.g. "EUR/USD" or "BTC/USD"
    period_days : calendar days of history to request
    timeframe   : bar size -- "1d" (daily), "4h" (4-hour), or "1h" (1-hour)

    Returns a DataFrame with DatetimeIndex and columns [Open, High, Low, Close, Volume].
    Raises DataFetchError if the pair is unknown, data is empty, or fewer than 60 bars returned.
    """
    if pair not in ALL_PAIRS:
        raise DataFetchError(
            f"Unknown pair '{pair}'. Supported: {list(ALL_PAIRS.keys())}"
        )
    if timeframe not in _TIMEFRAME_CONFIG:
        raise DataFetchError(f"Unknown timeframe '{timeframe}'. Use: {list(_TIMEFRAME_CONFIG)}")

    multiplier, timespan, _ = _TIMEFRAME_CONFIG[timeframe]
    ticker = ALL_PAIRS[pair]
    to_date = datetime.now(timezone.utc).date()
    # Extra buffer ensures we always get enough bars after weekends/holidays
    from_date = to_date - timedelta(days=period_days + 40)

    client = _get_client()
    try:
        aggs = list(
            client.get_aggs(
                ticker,
                multiplier,
                timespan,
                from_date.strftime("%Y-%m-%d"),
                to_date.strftime("%Y-%m-%d"),
                limit=5000,
            )
        )
    except Exception as e:
        raise DataFetchError(f"Failed to fetch data for {pair}: {e}") from e

    if not aggs:
        raise DataFetchError(f"Empty response for {pair}")

    records = [
        {
            "Open": agg.open,
            "High": agg.high,
            "Low": agg.low,
            "Close": agg.close,
            "Volume": agg.volume,
            "timestamp": agg.timestamp,
        }
        for agg in aggs
    ]

    df = pd.DataFrame(records)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("timestamp").sort_index()

    # For intraday, tail by bar count rather than calendar days
    if timeframe == "1d":
        df = df.tail(period_days)
    else:
        bars_per_day = 6 if timeframe == "4h" else 24
        df = df.tail(period_days * bars_per_day)

    if len(df) < 60:
        raise DataFetchError(
            f"Insufficient data for {pair} ({timeframe}): got {len(df)} bars, need at least 60"
        )

    return df


def fetch_all_pairs(
    market: Market = "forex",
    period_days: int = 100,
    timeframe: Timeframe = "1d",
    rate_limit_delay: float = 13.0,
) -> dict[str, pd.DataFrame]:
    """Fetch pairs for the given market with a delay to respect the free-tier rate limit."""
    results: dict[str, pd.DataFrame] = {}
    pairs = list(get_pairs_for_market(market).keys())
    for i, pair in enumerate(pairs):
        try:
            results[pair] = fetch_ohlcv(pair, period_days, timeframe)
        except DataFetchError as e:
            warnings.warn(str(e))
        if i < len(pairs) - 1:
            time.sleep(rate_limit_delay)
    return results
