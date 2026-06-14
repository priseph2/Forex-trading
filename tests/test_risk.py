import pytest
from bot.risk import PositionParams, calculate_position, validate_position


def test_buy_position_levels():
    params = calculate_position("BUY", entry_price=1.10000, account_balance=10_000, broker="OANDA")
    assert params.stop_loss < params.entry_price < params.take_profit
    assert abs(params.stop_loss - 1.10000 * 0.99) < 0.0001
    assert abs(params.take_profit - 1.10000 * 1.01) < 0.0001


def test_sell_position_levels():
    params = calculate_position("SELL", entry_price=1.10000, account_balance=10_000, broker="OANDA")
    assert params.take_profit < params.entry_price < params.stop_loss
    assert abs(params.stop_loss - 1.10000 * 1.01) < 0.0001
    assert abs(params.take_profit - 1.10000 * 0.99) < 0.0001


def test_units_formula():
    # units = (balance * 0.01) / (entry * 0.01) = balance / entry
    params = calculate_position("BUY", entry_price=1.0, account_balance=10_000, broker="OANDA")
    # risk_amount=100, price_risk=0.01, units=10000
    assert params.units == 10_000
    assert params.risk_amount == 100.0


def test_oanda_units_are_integer():
    params = calculate_position("BUY", entry_price=1.10000, account_balance=10_000, broker="OANDA")
    assert params.units == int(params.units)


def test_binance_units_have_decimals():
    params = calculate_position("BUY", entry_price=30_000.0, account_balance=10_000, broker="BINANCE")
    # For BTC at 30k, units should be a small decimal
    assert params.units > 0


def test_validate_position_ok():
    params = calculate_position("BUY", entry_price=1.0, account_balance=10_000, broker="OANDA")
    assert validate_position(params) is True


def test_validate_position_too_small():
    # Tiny balance → risk_amount is negligible, units rounds to 0
    params = calculate_position("BUY", entry_price=1.0, account_balance=0.001, broker="OANDA")
    assert validate_position(params) is False


def test_custom_risk_pct():
    params = calculate_position(
        "BUY", entry_price=100.0, account_balance=10_000, broker="OANDA",
        risk_pct=0.02, target_pct=0.02
    )
    assert abs(params.stop_loss - 98.0) < 0.001
    assert abs(params.take_profit - 102.0) < 0.001
    assert params.risk_amount == 200.0
