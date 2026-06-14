import logging
import os
from datetime import datetime, timezone

from bot.broker.base import BaseBroker, BrokerError

logger = logging.getLogger(__name__)


def _to_oanda_pair(pair: str) -> str:
    """'C:EURUSD' or 'EUR/USD' → 'EUR_USD'"""
    raw = pair.replace("C:", "").replace("/", "")
    return raw[:3] + "_" + raw[3:]


def _is_forex_market_open() -> bool:
    """Forex closes Friday 22:00 UTC, reopens Sunday 22:00 UTC."""
    now = datetime.now(timezone.utc)
    if now.weekday() == 5:  # Saturday
        return False
    if now.weekday() == 6 and now.hour < 22:  # Sunday before open
        return False
    return True


class OANDABroker(BaseBroker):
    supports_short: bool = True

    def __init__(self):
        try:
            from oandapyV20 import API
            import oandapyV20.endpoints.accounts as accounts_ep
            import oandapyV20.endpoints.orders as orders_ep
            import oandapyV20.endpoints.pricing as pricing_ep
            import oandapyV20.endpoints.trades as trades_ep
            self._API = API
            self._accounts_ep = accounts_ep
            self._orders_ep = orders_ep
            self._pricing_ep = pricing_ep
            self._trades_ep = trades_ep
        except ImportError as e:
            raise ImportError("oandapyV20 is required: pip install oandapyV20") from e

        practice = os.getenv("OANDA_PRACTICE", "true").lower() == "true"
        self._account_id = os.getenv("OANDA_ACCOUNT_ID")
        api_key = os.getenv("OANDA_API_KEY")
        if not self._account_id or not api_key:
            raise EnvironmentError("OANDA_ACCOUNT_ID and OANDA_API_KEY must be set")
        self._api = self._API(
            access_token=api_key,
            environment="practice" if practice else "live",
        )
        self._mode = "practice" if practice else "live"
        logger.info("OANDA broker initialised (%s)", self._mode)

    @property
    def name(self) -> str:
        return "OANDA"

    def _request(self, endpoint):
        try:
            from oandapyV20.exceptions import V20Error
            return self._api.request(endpoint)
        except Exception as e:
            raise BrokerError(f"OANDA API error: {e}") from e

    def get_balance(self) -> float:
        r = self._request(self._accounts_ep.AccountDetails(self._account_id))
        return float(r["account"]["balance"])

    def get_price(self, pair: str) -> float:
        instrument = _to_oanda_pair(pair)
        params = {"instruments": instrument}
        r = self._request(self._pricing_ep.PricingInfo(self._account_id, params=params))
        price = r["prices"][0]
        return (float(price["bids"][0]["price"]) + float(price["asks"][0]["price"])) / 2

    def place_order(
        self, pair: str, direction: str, units: float, stop_loss: float, take_profit: float
    ) -> str:
        if not _is_forex_market_open():
            raise BrokerError("Forex market is closed (weekend)")

        instrument = _to_oanda_pair(pair)
        signed_units = str(int(units)) if direction == "BUY" else str(-int(units))

        data = {
            "order": {
                "type": "MARKET",
                "instrument": instrument,
                "units": signed_units,
                "takeProfitOnFill": {"price": f"{take_profit:.5f}"},
                "stopLossOnFill": {"price": f"{stop_loss:.5f}"},
                "timeInForce": "FOK",
            }
        }
        r = self._request(self._orders_ep.OrderCreate(self._account_id, data=data))
        trade_id = r["orderFillTransaction"]["tradeOpened"]["tradeID"]
        logger.info("OANDA order placed: %s %s %s units → trade_id=%s", direction, pair, units, trade_id)
        return str(trade_id)

    def get_open_trades(self) -> list[dict]:
        r = self._request(self._trades_ep.TradesList(self._account_id))
        trades = []
        for t in r.get("trades", []):
            direction = "BUY" if float(t["currentUnits"]) > 0 else "SELL"
            trades.append({
                "trade_id": t["id"],
                "pair": t["instrument"].replace("_", ""),
                "direction": direction,
                "units": abs(float(t["currentUnits"])),
                "entry_price": float(t["price"]),
                "current_price": float(t.get("currentUnits", t["price"])),
                "unrealised_pnl": float(t.get("unrealizedPL", 0)),
            })
        return trades

    def close_trade(self, trade_id: str) -> dict:
        endpoint = self._trades_ep.TradeClose(self._account_id, trade_id)
        r = self._request(endpoint)
        txn = r.get("orderFillTransaction", {})
        return {
            "trade_id": trade_id,
            "exit_price": float(txn.get("price", 0)),
            "realised_pnl": float(txn.get("pl", 0)),
            "closed_at": txn.get("time", datetime.now(timezone.utc).isoformat()),
        }
