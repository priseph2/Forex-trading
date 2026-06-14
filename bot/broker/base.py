from abc import ABC, abstractmethod


class BrokerError(Exception):
    """Raised when a broker API call fails."""


class BaseBroker(ABC):

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable broker name, e.g. 'OANDA' or 'BINANCE'."""

    supports_short: bool = True

    @abstractmethod
    def get_balance(self) -> float:
        """Return available cash balance in USD."""

    @abstractmethod
    def get_price(self, pair: str) -> float:
        """Return current mid-price for a pair (using internal pair format)."""

    @abstractmethod
    def place_order(
        self,
        pair: str,
        direction: str,
        units: float,
        stop_loss: float,
        take_profit: float,
    ) -> str:
        """Place a market order with SL/TP. Returns broker-assigned trade_id."""

    @abstractmethod
    def get_open_trades(self) -> list[dict]:
        """
        Return list of open positions, each with keys:
        trade_id, pair, direction, units, entry_price, current_price, unrealised_pnl
        """

    @abstractmethod
    def close_trade(self, trade_id: str) -> dict:
        """
        Close a specific trade. Returns dict with:
        trade_id, exit_price, realised_pnl, closed_at (ISO-8601 UTC)
        """
