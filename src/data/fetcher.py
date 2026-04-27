import os
import time
import warnings
from datetime import datetime, timedelta, timezone

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
    Fetch daily OHLCV bars for a forex pair from Polygon.io.

    Returns a DataFrame with DatetimeIndex and columns [Open, High, Low, Close, Volume].
    Raises DataFetchError if the pair is unknown, data is empty, or fewer than 60 bars returned.
    """
    if pair not in FOREX_PAIRS:
        raise DataFetchError(
            f"Unknown pair '{pair}'. Supported: {list(FOREX_PAIRS.keys())}"
        )

    ticker = FOREX_PAIRS[pair]
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
    period_days: int = 100, rate_limit_delay: float = 13.0
) -> dict[str, pd.DataFrame]:
    """Fetch all pairs with a delay between requests to respect the free-tier rate limit."""
    results: dict[str, pd.DataFrame] = {}
    pairs = list(FOREX_PAIRS.keys())
    for i, pair in enumerate(pairs):
        try:
            results[pair] = fetch_ohlcv(pair, period_days)
        except DataFetchError as e:
            warnings.warn(str(e))
        if i < len(pairs) - 1:
            time.sleep(rate_limit_delay)
    return results
