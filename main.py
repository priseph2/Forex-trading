#!/usr/bin/env python3
"""
Forex Signal Generator — powered by Polygon.io

Usage:
  python main.py                   # All 7 major pairs (~90s on free tier)
  python main.py --pair EUR/USD    # Single pair (no rate-limit delay)
  python main.py --export          # Also write signals_output.json
  python main.py --period 150      # Use more historical data
"""
import argparse
import time

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.data.fetcher import FOREX_PAIRS, DataFetchError, fetch_ohlcv
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


def run(pairs: list[str], period_days: int, export: bool, console: Console) -> None:
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
                ohlcv = fetch_ohlcv(pair, period_days)
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
        print_signals(results, console)
    else:
        console.print(
            "[red]No signals generated — check your POLYGON_API_KEY and network connection.[/red]"
        )

    if export and results:
        export_json(results)
        console.print("[green]Signals exported to signals_output.json[/green]")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Forex trading signal generator using Polygon.io data"
    )
    parser.add_argument("--export", action="store_true", help="Export signals to JSON")
    parser.add_argument("--pair", type=str, help="Analyze a single pair, e.g. EUR/USD")
    parser.add_argument(
        "--period",
        type=int,
        default=100,
        help="Days of history to fetch (default: 100)",
    )
    args = parser.parse_args()

    console = Console()

    if args.pair and args.pair not in FOREX_PAIRS:
        console.print(
            f"[red]Unknown pair '{args.pair}'. "
            f"Valid pairs: {', '.join(FOREX_PAIRS.keys())}[/red]"
        )
        raise SystemExit(1)

    pairs = [args.pair] if args.pair else list(FOREX_PAIRS.keys())
    run(pairs, args.period, args.export, console)


if __name__ == "__main__":
    main()
