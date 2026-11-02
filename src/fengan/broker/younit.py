"""Live adapter on the official Younit SDK (`younit-sdk`, by EFG Hermes Data Science).

Install the SDK, set TRADING_ID and API_KEY, and set YOUNIT_MODE=live.
Simulation (paper) mode is ON unless YOUNIT_REAL_MONEY=true is set explicitly.

Mapping notes, from reading the SDK source (v0.1.0):
  - Only market and limit orders exist for stocks. Stop orders are refused here.
  - Quote has no daily change or volume, so both come from the last two daily candles.
  - Client.list_orders() rows carry no symbol or side, so this adapter tracks
    the orders it placed and refreshes their status from list_orders().
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from ..config import Settings
from ..models import (
    Account,
    Bar,
    Order,
    OrderRequest,
    OrderStatus,
    OrderType,
    Position,
    Quote,
    Side,
)
from .base import BrokerClient

# Status text from list_orders() -> our status. Unknown text stays "pending".
_STATUS = {
    "filled": OrderStatus.FILLED,
    "executed": OrderStatus.FILLED,
    "fully executed": OrderStatus.FILLED,
    "cancelled": OrderStatus.CANCELLED,
    "canceled": OrderStatus.CANCELLED,
    "rejected": OrderStatus.REJECTED,
}


def _status(text: object) -> OrderStatus:
    return _STATUS.get(str(text or "").strip().lower(), OrderStatus.PENDING)


class YounitClient(BrokerClient):
    name = "younit"

    def __init__(self, settings: Settings, sdk_client: object | None = None) -> None:
        if sdk_client is None:
            try:
                from younit import Client
            except ImportError as e:  # pragma: no cover - depends on install
                raise RuntimeError(
                    "The Younit SDK is not installed. Install it from source: "
                    "pip install <path-to>/younit-python-master"
                ) from e
            # Credentials come from TRADING_ID / API_KEY (env or .env), read by the SDK itself.
            sdk_client = Client(simulation=not settings.real_money)
        self._c = sdk_client
        self._settings = settings
        self._placed: dict[str, Order] = {}

    # reads

    def get_account(self) -> Account:
        p = self._c.portfolio()
        return Account(
            account_id=str(getattr(self._c, "profile_id", None) or "younit"),
            currency=p.currency or "EGP",
            cash=round(p.total_cash, 2),
            equity=round(p.total_balance, 2),
            buying_power=round(p.total_cash, 2),
        )

    def get_positions(self) -> list[Position]:
        out = []
        for p in self._c.positions():
            if p.is_fund or not p.symbol or p.quantity <= 0:
                continue
            out.append(
                Position(
                    symbol=p.symbol,
                    quantity=p.quantity,
                    avg_cost=round(p.average_price, 4),
                    last_price=p.market_price,
                    market_value=round(p.market_value, 2),
                    unrealized_pnl=round(p.unrealized_pnl, 2),
                    unrealized_pnl_pct=round(p.unrealized_pnl_pct, 2),
                )
            )
        return out

    def list_symbols(self) -> dict[str, str]:
        return {s.symbol: (s.name or s.symbol) for s in self._c.list_stocks() if s.symbol}

    def get_quote(self, symbol: str) -> Quote:
        s = symbol.strip().upper()
        q = self._c.quote(s)
        recent = self.get_bars(s, date.today() - timedelta(days=14), date.today())
        change = 0.0
        volume = 0
        if len(recent) >= 2 and recent[-2].close:
            change = 100 * (q.last / recent[-2].close - 1)
        if recent:
            volume = recent[-1].volume
        return Quote(
            symbol=s,
            name=q.name or s,
            last=q.last,
            change_pct=round(change, 2),
            volume=volume,
            as_of=datetime.now(timezone.utc),
        )

    def get_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        from younit import ChartPeriod

        candles = self._c.historical_prices(
            symbol.strip().upper(),
            period=ChartPeriod.DAY,
            date_from=start.isoformat(),
            date_to=end.isoformat(),
        )
        bars = [
            Bar(
                day=c.timestamp.date(),
                open=c.open,
                high=c.high,
                low=c.low,
                close=c.close,
                volume=int(c.volume),
            )
            for c in candles
            if c.timestamp is not None and c.close > 0
        ]
        bars.sort(key=lambda b: b.day)
        return bars

    # writes

    def submit_order(self, request: OrderRequest) -> Order:
        if request.order_type == OrderType.STOP:
            raise ValueError("The Younit API supports market and limit orders only. Use a limit order.")
        limit = request.limit_price if request.order_type == OrderType.LIMIT else None
        place = self._c.buy if request.side == Side.BUY else self._c.sell
        sdk_order = place(request.symbol, request.quantity, limit=limit)
        order_id = str(getattr(sdk_order, "order_id", None) or f"pending-{len(self._placed) + 1}")
        order = Order(
            order_id=order_id,
            request=request,
            status=_status(getattr(sdk_order, "status_text", None)),
            created_at=datetime.now(timezone.utc),
        )
        self._placed[order_id] = order
        return order

    def get_orders(self) -> list[Order]:
        if self._placed:
            try:
                rows = {str(r.get("OrderId")): r for r in self._c.list_orders()}
            except Exception:
                rows = {}
            for oid, order in self._placed.items():
                row = rows.get(oid)
                if row is not None:
                    order.status = _status(row.get("Status"))
        return sorted(self._placed.values(), key=lambda o: o.created_at, reverse=True)

    def cancel_order(self, order_id: str) -> Order:
        if not order_id.isdigit():
            raise ValueError(f"'{order_id}' is not a Younit order id.")
        if not self._c.cancel_order(int(order_id)):
            raise ValueError(f"Younit did not cancel order {order_id}.")
        order = self._placed.get(order_id)
        if order is None:
            raise ValueError(f"Order {order_id} was cancelled, but it was not placed from this session.")
        order.status = OrderStatus.CANCELLED
        return order
