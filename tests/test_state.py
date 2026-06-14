import pytest
from datetime import datetime, timezone
from bot.state import TradeState

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")


@pytest.fixture
def state(tmp_path):
    db = tmp_path / "test.db"
    return TradeState(db_path=str(db))


def _insert(state, pair="EUR/USD", broker="OANDA", direction="BUY",
            entry=1.1, sl=1.089, tp=1.111, units=1000, tid="T1"):
    return state.insert_trade(pair, broker, direction, entry, sl, tp, units, tid)


def test_insert_and_get_open(state):
    _insert(state)
    trades = state.get_open_trades()
    assert len(trades) == 1
    assert trades[0]["pair"] == "EUR/USD"
    assert trades[0]["status"] == "open"


def test_open_count(state):
    assert state.get_open_trade_count() == 0
    _insert(state, pair="EUR/USD", tid="T1")
    _insert(state, pair="BTC/USD", broker="BINANCE", tid="T2")
    assert state.get_open_trade_count() == 2


def test_is_pair_already_open(state):
    assert state.is_pair_already_open("EUR/USD") is False
    _insert(state)
    assert state.is_pair_already_open("EUR/USD") is True
    assert state.is_pair_already_open("GBP/USD") is False


def test_close_trade(state):
    trade_id = _insert(state)
    now = datetime.now(timezone.utc).isoformat()
    state.close_trade(trade_id, exit_price=1.115, pnl=50.0, closed_at=now)
    trades = state.get_open_trades()
    assert len(trades) == 0


def test_upsert_daily_summary(state):
    # opened_at is set to now() by insert_trade, so use today's real date
    trade_id = _insert(state, tid="TXX")
    closed_at = datetime.now(timezone.utc).isoformat()
    state.close_trade(trade_id, 1.115, 50.0, closed_at)
    state.upsert_daily_summary(TODAY)
    summary = state.get_daily_summary(TODAY)
    assert summary is not None
    assert summary["total_trades"] == 1
    assert summary["wins"] == 1
    assert summary["gross_pnl"] == 50.0


def test_get_all_trades_for_date(state):
    _insert(state, tid="TYY")
    trades = state.get_all_trades_for_date(TODAY)
    assert len(trades) == 1
    assert trades[0]["pair"] == "EUR/USD"


def test_summary_win_loss_count(state):
    for i, pnl in enumerate([100.0, -30.0, 50.0], start=1):
        tid = state.insert_trade("P"+str(i), "OANDA", "BUY", 1.1, 1.089, 1.111, 1000, f"T{i}")
        closed_at = datetime.now(timezone.utc).isoformat()
        state.close_trade(tid, 1.115, pnl, closed_at)
    state.upsert_daily_summary(TODAY)
    s = state.get_daily_summary(TODAY)
    assert s["wins"] == 2
    assert s["losses"] == 1
    assert abs(s["gross_pnl"] - 120.0) < 0.01
