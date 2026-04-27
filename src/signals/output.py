import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.text import Text

from src.signals.models import Direction, PairResult

_STRATEGY_ORDER = ["EMA Crossover", "RSI", "MACD", "Bollinger Bands"]


def _direction_cell(direction: Direction) -> Text:
    if direction == Direction.BUY:
        return Text(direction.value, style="bold green")
    if direction == Direction.SELL:
        return Text(direction.value, style="bold red")
    return Text(direction.value, style="yellow")


def _confidence_cell(confidence: float) -> Text:
    pct = f"{confidence * 100:.0f}%"
    if confidence >= 0.66:
        style = "green"
    elif confidence >= 0.40:
        style = "yellow"
    else:
        style = "red"
    return Text(pct, style=style)


def build_table(results: list[PairResult]) -> Table:
    table = Table(
        title=f"Forex Signals — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Pair", style="bold", min_width=9)
    table.add_column("EMA Cross", min_width=10)
    table.add_column("RSI", min_width=6)
    table.add_column("MACD", min_width=6)
    table.add_column("Bollinger", min_width=10)
    table.add_column("Combined", min_width=9)
    table.add_column("Confidence", min_width=10)

    for result in results:
        sig_map = {s.strategy: s for s in result.signals}
        cells: list = [result.pair]
        for name in _STRATEGY_ORDER:
            if name in sig_map:
                cells.append(_direction_cell(sig_map[name].direction))
            else:
                cells.append(Text("N/A", style="dim"))
        cells.append(_direction_cell(result.combined))
        cells.append(_confidence_cell(result.combined_confidence))
        table.add_row(*cells)

    return table


def print_signals(results: list[PairResult], console: Console | None = None) -> None:
    if console is None:
        console = Console()
    console.print(build_table(results))


def export_json(results: list[PairResult], path: str | Path = "signals_output.json") -> None:
    def _default(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Direction):
            return obj.value
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    with open(path, "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2, default=_default)
