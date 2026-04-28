#!/usr/bin/env python3
"""
Forex & Crypto Signal Generator — powered by Polygon.io

Usage:
  python main.py                         # Forex majors (~90s on free tier)
  python main.py --market crypto         # Top altcoins (~3min on free tier)
  python main.py --market all            # Forex + crypto (~4.5min on free tier)
  python main.py --pair BTC/USD          # Single pair (no rate-limit delay)
  python main.py --export                # Also write signals_output.json
  python main.py --period 150            # Use more historical data
"""
import argparse
import time

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.data.fetcher import ALL_PAIRS, DataFetchError, Timeframe, fetch_ohlcv, get_pairs_for_market
from src.signals.aggregator import aggregate_signals
from src.signals.output import export_json, print_signals
from src.strategies.bollinger_strategy import BollingerStrategy
from src.strategies.ema_crossover import EMACrossoverStrategy
from src.strategies.macd_strategy import MACDStrategy
from src.strategies.rsi_strategy import RSIStrategy

STRATEGIES = [
    EMACrossoverStrategy(),
    RSIStrategy(),
    MACDStrategy(),
    BollingerStrategy(),
]

_RATE_LIMIT_DELAY = 13.0  # seconds between requests on Polygon free tier (5 req/min)


def run(pairs: list[str], period_days: int, export: bool, market: str, timeframe: Timeframe, console: Console) -> None:
    results = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Starting…", total=len(pairs))

        for i, pair in enumerate(pairs):
            progress.update(task, description=f"Fetching {pair}…")
            try:
                ohlcv = fetch_ohlcv(pair, period_days, timeframe)
                signals = [s.generate(pair, ohlcv) for s in STRATEGIES]
                result = aggregate_signals(pair, signals, STRATEGIES)
                results.append(result)
            except DataFetchError as e:
                console.print(f"[yellow]Warning:[/yellow] Skipping {pair}: {e}")
            finally:
                progress.advance(task)

            if i < len(pairs) - 1:
                time.sleep(_RATE_LIMIT_DELAY)

    if results:
        print_signals(results, console, market=market)
    else:
        console.print(
            "[red]No signals generated — check your POLYGON_API_KEY and network connection.[/red]"
        )

    if export and results:
        export_json(results)
        console.print("[green]Signals exported to signals_output.json[/green]")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Forex & crypto trading signal generator using Polygon.io data"
    )
    parser.add_argument("--export", action="store_true", help="Export signals to JSON")
    parser.add_argument(
        "--market",
        choices=["forex", "crypto", "all"],
        default="forex",
        help="Market to analyze: forex (default), crypto, or all",
    )
    parser.add_argument("--pair", type=str, help="Analyze a single pair, e.g. EUR/USD or BTC/USD")
    parser.add_argument(
        "--timeframe",
        choices=["1d", "4h", "1h"],
        default="1d",
        help="Bar size: 1d=daily (default), 4h=4-hour, 1h=1-hour",
    )
    parser.add_argument(
        "--period",
        type=int,
        default=None,
        help="Calendar days of history (default: 100 for 1d, 30 for 4h, 14 for 1h)",
    )
    args = parser.parse_args()

    console = Console()

    if args.pair and args.pair not in ALL_PAIRS:
        console.print(
            f"[red]Unknown pair '{args.pair}'. "
            f"Valid pairs: {', '.join(ALL_PAIRS.keys())}[/red]"
        )
        raise SystemExit(1)

    from src.data.fetcher import default_period_for
    period = args.period if args.period is not None else default_period_for(args.timeframe)

    if args.pair:
        pairs = [args.pair]
        market_label = "forex" if args.pair in list(ALL_PAIRS.keys())[:7] else "crypto"
    else:
        pairs = list(get_pairs_for_market(args.market).keys())
        market_label = args.market

    run(pairs, period, args.export, market_label, args.timeframe, console)


if __name__ == "__main__":
    main()
