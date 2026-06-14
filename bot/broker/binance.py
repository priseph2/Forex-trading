import logging
import os
from datetime import datetime, timezone

from bot.broker.base import BaseBroker, BrokerError

logger = logging.getLogger(__name__)

# Cached LOT_SIZE step sizes per symbol to avoid repeated API calls
_LOT_SIZE_CACHE: dict[str, float] = {}


def _to_binance_symbol(pair: str) -> str:
    """'X:BTCUSD' or 'BTC/USD' → 'BTCUSDT'"""
    raw = pair.replace("X:", "").replace("/", "")
    if raw.endswith("USD") and not raw.endswith("USDT"):
        raw = raw + "T"
    return raw


def _round_step(quantity: float, step: float) -> float:
    """Round quantity down to the nearest step size."""
    return round(quantity - (quantity % step), 8)


class BinanceBroker(BaseBroker):
    supports_short: bool = False  # Spot only — no shorting

    def __init__(self):
        try:
            from binance.client import Client
            from binance.exceptions import BinanceAPIException
            self._Client = Client
            self._BinanceAPIException = BinanceAPIException
        except ImportError as e:
            raise ImportError("python-binance is required: pip install python-binance") from e

        testnet = os.getenv("BINANCE_TESTNET", "true").lower() == "true"
        api_key = os.getenv("BINANCE_API_KEY")
        secret = os.getenv("BINANCE_SECRET_KEY")
        if not api_key or not secret:
            raise EnvironmentError("BINANCE_API_KEY and BINANCE_SECRET_KEY must be set")
        self._client = self._Client(api_key=api_key, api_secret=secret, testnet=testnet)
        self._mode = "testnet" if testnet else "live"
        logger.info("Binance broker initialised (%s)", self._mode)

    @property
    def name(self) -> str:
        return "BINANCE"

    def _get_step_size(self, symbol: str) -> float:
        if symbol not in _LOT_SIZE_CACHE:
            try:
                info = self._client.get_symbol_info(symbol)
                for f in info["filters"]:
                    if f["filterType"] == "LOT_SIZE":
                        _LOT_SIZE_CACHE[symbol] = float(f["stepSize"])
                        break
            except Exception:
                _LOT_SIZE_CACHE[symbol] = 0.0001
        return _LOT_SIZE_CACHE[symbol]

    def get_balance(self) -> float:
        try:
            account = self._client.get_account()
            for asset in account["balances"]:
                if asset["asset"] == "USDT":
                    return float(asset["free"])
            return 0.0
        except Exception as e:
            raise BrokerError(f"Binance get_balance failed: {e}") from e

    def get_price(self, pair: str) -> float:
        symbol = _to_binance_symbol(pair)
        try:
            ticker = self._client.get_symbol_ticker(symbol=symbol)
            return float(ticker["price"])
        except Exception as e:
            raise BrokerError(f"Binance get_price failed for {pair}: {e}") from e

    def place_order(
        self, pair: str, direction: str, units: float, stop_loss: float, take_profit: float
    ) -> str:
        if direction == "SELL":
            raise BrokerError("Binance Spot does not support short selling")

        symbol = _to_binance_symbol(pair)
        step = self._get_step_size(symbol)
        qty = _round_step(units, step) if step > 0 else round(units, 4)

        if qty <= 0:
            raise BrokerError(f"Quantity too small after rounding for {symbol}")

        try:
            # 1. Market buy
            self._client.order_market_buy(symbol=symbol, quantity=qty)

            # 2. OCO sell order (take-profit + stop-loss)
            oco = self._client.create_oco_order(
                symbol=symbol,
                side="SELL",
                quantity=qty,
                price=f"{take_profit:.4f}",
                stopPrice=f"{stop_loss:.4f}",
                stopLimitPrice=f"{stop_loss * 0.999:.4f}",
                stopLimitTimeInForce="GTC",
            )
            order_list_id = str(oco["orderListId"])
            logger.info("Binance OCO order placed for %s qty=%s → orderListId=%s", symbol, qty, order_list_id)
            return order_list_id
        except Exception as e:
            raise BrokerError(f"Binance place_order failed for {pair}: {e}") from e

    def get_open_trades(self) -> list[dict]:
        try:
            oco_orders = self._client.get_open_orders()
            # Group by symbol, return one entry per active OCO
            seen: set[str] = set()
            trades = []
            for o in oco_orders:
                symbol = o["symbol"]
                if symbol in seen:
                    continue
                seen.add(symbol)
                price = float(self._client.get_symbol_ticker(symbol=symbol)["price"])
                trades.append({
                    "trade_id": str(o.get("orderListId", o["orderId"])),
                    "pair": symbol,
                    "direction": "BUY",
                    "units": float(o["origQty"]),
                    "entry_price": price,
                    "current_price": price,
                    "unrealised_pnl": 0.0,
                })
            return trades
        except Exception as e:
            raise BrokerError(f"Binance get_open_trades failed: {e}") from e

    def close_trade(self, trade_id: str) -> dict:
        """Cancel OCO and market sell remaining position."""
        try:
            # Find the OCO to get symbol and quantity
            open_orders = self._client.get_open_orders()
            symbol = None
            qty = None
            for o in open_orders:
                if str(o.get("orderListId")) == trade_id:
                    symbol = o["symbol"]
                    qty = float(o["origQty"])
                    break

            if not symbol:
                raise BrokerError(f"OCO order {trade_id} not found — may already be filled")

            # Cancel OCO
            self._client.cancel_order_list(symbol=symbol, orderListId=int(trade_id))

            # Market sell
            result = self._client.order_market_sell(symbol=symbol, quantity=qty)
            exit_price = float(result.get("fills", [{}])[0].get("price", 0))

            return {
                "trade_id": trade_id,
                "exit_price": exit_price,
                "realised_pnl": 0.0,  # Binance doesn't return PnL directly
                "closed_at": datetime.now(timezone.utc).isoformat(),
            }
        except BrokerError:
            raise
        except Exception as e:
            raise BrokerError(f"Binance close_trade failed: {e}") from e
