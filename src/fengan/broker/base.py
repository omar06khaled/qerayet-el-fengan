"""The adapter interface. Everything above this line is broker-agnostic.

When the real Younit SDK docs are available, only a new implementation of this
class is needed (see broker/younit.py). Tools, safety checks and the backtester
stay unchanged.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from ..models import Account, Bar, Order, OrderRequest, Position, Quote


class BrokerClient(ABC):
    name: str = "base"

    @abstractmethod
    def get_account(self) -> Account: ...

    @abstractmethod
    def get_positions(self) -> list[Position]: ...

    @abstractmethod
    def list_symbols(self) -> dict[str, str]:
        """Ticker -> company name for tradable instruments."""

    @abstractmethod
    def get_quote(self, symbol: str) -> Quote: ...

    @abstractmethod
    def get_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        """Daily OHLCV bars, oldest first."""

    @abstractmethod
    def submit_order(self, request: OrderRequest) -> Order: ...

    @abstractmethod
    def get_orders(self) -> list[Order]: ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> Order: ...
