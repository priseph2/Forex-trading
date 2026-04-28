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


def get_pairs_for_market(market: Market) -> dict[str, str]:
    if market == "forex":
        return FOREX_PAIRS
    if market == "crypto":
        return CRYPTO_PAIRS
    return ALL_PAIRS


class DataFetchError(RuntimeError):
    pass


def _get_client() -> RESTClient:
    api_key = os.environ.get("POLYGON_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "POLYGON_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return RESTClient(api_key=api_key)


def fetch_ohlcv(pair: str, period_days: int = 100) -> pd.DataFrame:
    """
    Fetch daily OHLCV bars for a forex or crypto pair from Polygon.io.

    Returns a DataFrame with DatetimeIndex and columns [Open, High, Low, Close, Volume].
    Raises DataFetchError if the pair is unknown, data is empty, or fewer than 60 bars returned.
    """
    if pair not in ALL_PAIRS:
        raise DataFetchError(
            f"Unknown pair '{pair}'. Supported: {list(ALL_PAIRS.keys())}"
        )

    ticker = ALL_PAIRS[pair]
    to_date = datetime.now(timezone.utc).date()
    # Extra buffer for weekends and holidays so we always get enough trading days
    from_date = to_date - timedelta(days=period_days + 40)

    client = _get_client()
    try:
        aggs = list(
            client.get_aggs(
                ticker,
                1,
                "day",
                from_date.strftime("%Y-%m-%d"),
                to_date.strftime("%Y-%m-%d"),
                limit=500,
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
    df = df.tail(period_days)

    if len(df) < 60:
        raise DataFetchError(
            f"Insufficient data for {pair}: got {len(df)} rows, need at least 60"
        )

    return df


def fetch_all_pairs(
    market: Market = "forex",
    period_days: int = 100,
    rate_limit_delay: float = 13.0,
) -> dict[str, pd.DataFrame]:
    """Fetch pairs for the given market with a delay to respect the free-tier rate limit."""
    results: dict[str, pd.DataFrame] = {}
    pairs = list(get_pairs_for_market(market).keys())
    for i, pair in enumerate(pairs):
        try:
            results[pair] = fetch_ohlcv(pair, period_days)
        except DataFetchError as e:
            warnings.warn(str(e))
        if i < len(pairs) - 1:
            time.sleep(rate_limit_delay)
    return results
