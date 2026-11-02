from datetime import date

import pytest

from sahm.backtest import run_backtest
from sahm.broker.mock import MockYounitClient
from sahm.config import Settings
from sahm.models import OrderRequest, OrderStatus, Side
from sahm.orders import OrderDesk, OrderSafetyError


@pytest.fixture
def client():
    return MockYounitClient()


def test_mock_data_is_deterministic_and_skips_weekend():
    a, b = MockYounitClient(), MockYounitClient()
    assert a.get_quote("COMI") == b.get_quote("COMI")
    bars = a.get_bars("COMI", date(2026, 1, 1), date(2026, 3, 1))
    assert bars and all(bar.day.weekday() not in (4, 5) for bar in bars)


def test_account_equity_matches_positions(client):
    acct = client.get_account()
    mv = sum(p.market_value for p in client.get_positions())
    assert acct.equity == pytest.approx(acct.cash + mv, abs=0.05)


def test_unknown_symbol_raises(client):
    with pytest.raises(ValueError):
        client.get_quote("AAPL")


@pytest.mark.parametrize("strategy", ["buy_and_hold", "sma_cross", "rsi_reversion"])
def test_backtests_run(client, strategy):
    bars = client.get_bars("SWDY", date(2025, 11, 1), date(2026, 11, 1))
    r = run_backtest("SWDY", bars, strategy)
    assert r.trading_days == len(bars)
    assert r.max_drawdown_pct <= 0


def test_buy_and_hold_matches_baseline_minus_fee(client):
    bars = client.get_bars("COMI", date(2025, 11, 1), date(2026, 11, 1))
    r = run_backtest("COMI", bars, "buy_and_hold", commission_pct=0)
    # enters at day-2 open, so it is close to (not equal to) close-to-close baseline
    assert abs(r.total_return_pct - r.buy_and_hold_return_pct) < 5


def test_preview_does_not_place_order(client):
    desk = OrderDesk(client, Settings(trading_enabled=True, max_order_egp=1e9))
    desk.preview(OrderRequest(symbol="FWRY", side=Side.BUY, quantity=10))
    assert client.get_orders() == []


def test_confirm_blocked_when_trading_disabled(client):
    desk = OrderDesk(client, Settings(trading_enabled=False, max_order_egp=1e9))
    token = desk.preview(OrderRequest(symbol="FWRY", side=Side.BUY, quantity=10))["confirmation_token"]
    with pytest.raises(OrderSafetyError):
        desk.confirm(token)
    assert client.get_orders() == []


def test_order_cap_enforced(client):
    desk = OrderDesk(client, Settings(trading_enabled=True, max_order_egp=100))
    with pytest.raises(OrderSafetyError):
        desk.preview(OrderRequest(symbol="COMI", side=Side.BUY, quantity=100))


def test_token_is_single_use(client):
    desk = OrderDesk(client, Settings(trading_enabled=True, max_order_egp=1e9))
    token = desk.preview(OrderRequest(symbol="FWRY", side=Side.BUY, quantity=10))["confirmation_token"]
    order = desk.confirm(token)
    assert order.status == OrderStatus.FILLED
    with pytest.raises(OrderSafetyError):
        desk.confirm(token)


def test_cannot_sell_more_than_held(client):
    desk = OrderDesk(client, Settings(trading_enabled=True, max_order_egp=1e9))
    token = desk.preview(OrderRequest(symbol="COMI", side=Side.SELL, quantity=10_000))["confirmation_token"]
    assert desk.confirm(token).status == OrderStatus.REJECTED
