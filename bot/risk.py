import os
from dataclasses import dataclass


@dataclass
class PositionParams:
    entry_price: float
    stop_loss: float
    take_profit: float
    units: float
    risk_amount: float
    broker: str


def calculate_position(
    direction: str,
    entry_price: float,
    account_balance: float,
    broker: str,
    risk_pct: float | None = None,
    target_pct: float | None = None,
) -> PositionParams:
    """
    BUY:  SL = entry * (1 - risk_pct),  TP = entry * (1 + target_pct)
    SELL: SL = entry * (1 + risk_pct),  TP = entry * (1 - target_pct)
    units = (balance * risk_pct) / abs(entry - stop_loss)
    """
    if risk_pct is None:
        risk_pct = float(os.getenv("BOT_RISK_PCT", "0.01"))
    if target_pct is None:
        target_pct = float(os.getenv("BOT_TARGET_PCT", "0.01"))

    if direction == "BUY":
        stop_loss = entry_price * (1 - risk_pct)
        take_profit = entry_price * (1 + target_pct)
    else:
        stop_loss = entry_price * (1 + risk_pct)
        take_profit = entry_price * (1 - target_pct)

    risk_amount = account_balance * risk_pct
    price_risk = abs(entry_price - stop_loss)
    units = risk_amount / price_risk if price_risk > 0 else 0.0

    # OANDA uses integer units; Binance uses 4 decimal places
    if broker == "OANDA":
        units = round(units)
    else:
        units = round(units, 4)

    return PositionParams(
        entry_price=entry_price,
        stop_loss=round(stop_loss, 5),
        take_profit=round(take_profit, 5),
        units=units,
        risk_amount=round(risk_amount, 2),
        broker=broker,
    )


def validate_position(params: PositionParams, min_units: float = 1.0) -> bool:
    """Returns False if the position is too small to place."""
    return params.units >= min_units and params.risk_amount > 0
