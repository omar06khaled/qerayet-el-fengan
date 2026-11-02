"""Live adapter against the REAL Younit SDK models, with a fake transport-free client.

Builds the SDK's own pydantic models from raw API-shaped JSON (the same aliases the
production API returns), so a field rename in the SDK breaks these tests.
"""

from datetime import date

import pytest

younit = pytest.importorskip("younit")
from younit.models.market_data import HistoricalCandle, Quote as YQuote, StockInfo  # noqa: E402
from younit.models.portfolio import PortfolioSummary, Position as YPosition  # noqa: E402

from fengan.broker.younit import YounitClient  # noqa: E402
from fengan.config import Settings  # noqa: E402
from fengan.models import OrderRequest, OrderStatus, OrderType, Side  # noqa: E402
from fengan.orders import OrderDesk, OrderSafetyError  # noqa: E402


class _FakeOrder:
    def __init__(self, oid):
        self.order_id = oid
        self.status_text = "Accepted"


class FakeSDK:
    profile_id = 4242

    def __init__(self):
        self.calls = []

    def portfolio(self):
        return PortfolioSummary.model_validate(
            {"totalCash": 5000.5, "totalBalance": 12000.25, "currencyShortName": "EGP"}
        )

    def positions(self):
        return [
            YPosition.model_validate({
                "securityID": 1, "symbol": "COMI.CA", "shortNameE": "CIB", "quantity": 50,
                "averageCost": 80.0, "marketPrice": 90.0, "holdingValue": 4500.0,
                "unRealizedProfit": 500.0, "unRealizedProfitPercentage": 12.5, "isFund": False,
            }),
            YPosition.model_validate({"securityID": 2, "symbol": "AZG.CA", "quantity": 10, "isFund": True}),
        ]

    def list_stocks(self):
        return [StockInfo.model_validate({"stockId": 1, "symbol": "COMI", "stockName": "CIB"})]

    def quote(self, symbol):
        return YQuote.model_validate({"stockId": 1, "symbol": symbol, "stockName": "CIB", "price": 90.0})

    def historical_prices(self, symbol, period, date_from, date_to):
        raw = [
            {"dateTime": "2026-10-28T00:00:00", "openPrice": 85, "highPrice": 88, "lowPrice": 84, "price": 87.0, "volume": 1000},
            {"dateTime": "2026-10-29T00:00:00", "openPrice": 87, "highPrice": 91, "lowPrice": 86, "price": 88.0, "volume": 2500.0},
        ]
        return [HistoricalCandle.model_validate(r) for r in raw]

    def buy(self, symbol, qty, limit=None):
        self.calls.append(("buy", symbol, qty, limit))
        return _FakeOrder(9001)

    def sell(self, symbol, qty, limit=None):
        self.calls.append(("sell", symbol, qty, limit))
        return _FakeOrder(9002)

    def list_orders(self):
        return [{"OrderId": 9001, "Status": "Filled"}]

    def cancel_order(self, order_id):
        return True


@pytest.fixture
def live():
    return YounitClient(Settings(mode="live"), sdk_client=FakeSDK())


def test_account_and_positions_map_sdk_fields(live):
    a = live.get_account()
    assert (a.cash, a.equity, a.account_id) == (5000.5, 12000.25, "4242")
    pos = live.get_positions()
    assert [p.symbol for p in pos] == ["COMI"]  # suffix stripped by SDK, fund excluded
    assert pos[0].unrealized_pnl_pct == 12.5


def test_bars_and_quote_change(live):
    bars = live.get_bars("comi", date(2026, 10, 1), date(2026, 10, 31))
    assert [b.day.isoformat() for b in bars] == ["2026-10-28", "2026-10-29"]
    q = live.get_quote("comi")
    assert q.symbol == "COMI" and q.volume == 2500
    assert q.change_pct == round(100 * (90 / 87 - 1), 2)  # last vs previous close


def test_market_and_limit_orders_route_to_sdk(live):
    live.submit_order(OrderRequest(symbol="COMI", side=Side.BUY, quantity=5))
    live.submit_order(OrderRequest(symbol="COMI", side=Side.SELL, quantity=2,
                                   order_type=OrderType.LIMIT, limit_price=95))
    assert live._c.calls == [("buy", "COMI", 5, None), ("sell", "COMI", 2, 95)]
    assert {o.order_id: o.status for o in live.get_orders()}["9001"] == OrderStatus.FILLED


def test_stop_orders_refused(live):
    with pytest.raises(ValueError, match="market and limit"):
        live.submit_order(OrderRequest(symbol="COMI", side=Side.BUY, quantity=1,
                                       order_type=OrderType.STOP, stop_price=80))


def test_market_order_is_capped(live):
    """Unlike a cap that skips market orders, ours prices them at the last price."""
    desk = OrderDesk(live, Settings(mode="live", trading_enabled=True, max_order_egp=1000))
    with pytest.raises(OrderSafetyError):
        desk.preview(OrderRequest(symbol="COMI", side=Side.BUY, quantity=1_000_000))
    assert live._c.calls == []


def test_simulation_is_default():
    assert Settings.from_env().real_money is False
