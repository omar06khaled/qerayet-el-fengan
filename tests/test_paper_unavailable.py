"""younit 0.1.1 disables simulation. Fengan must fall back to read-only, never to real orders."""

import pytest

from fengan.broker.younit import YounitClient, _connect
from fengan.config import Settings
from fengan.models import OrderRequest, OrderType, Side
from fengan.orders import OrderDesk, OrderSafetyError


class _Client011:
    """Mimics younit 0.1.1: simulation=True refuses to start."""

    def __init__(self, simulation=None):
        if simulation:
            raise ValueError("EFG_SIMULATION is temporarily disabled in this version while simulation mode is being verified.")
        self.simulation = simulation
        self.buys = 0

    def buy(self, *a, **k):
        self.buys += 1


class _Client010:
    def __init__(self, simulation=None):
        self.simulation = simulation


def test_paper_request_on_011_connects_read_only(monkeypatch):
    monkeypatch.delenv("EFG_SIMULATION", raising=False)
    c, unavailable = _connect(_Client011, Settings(mode="live"))
    assert unavailable and c.simulation is None


def test_paper_works_on_010():
    c, unavailable = _connect(_Client010, Settings(mode="live"))
    assert not unavailable and c.simulation is True


def test_real_money_never_asks_for_simulation():
    c, unavailable = _connect(_Client011, Settings(mode="live", real_money=True))
    assert not unavailable and c.simulation is None


def test_efg_simulation_env_gives_clear_error(monkeypatch):
    monkeypatch.setenv("EFG_SIMULATION", "true")
    with pytest.raises(RuntimeError, match="Remove EFG_SIMULATION"):
        _connect(_Client011, Settings(mode="live"))


def test_unrelated_errors_still_raise(monkeypatch):
    class Broken:
        def __init__(self, simulation=None):
            raise ValueError("bad API_KEY")

    with pytest.raises(ValueError, match="API_KEY"):
        _connect(Broken, Settings(mode="live"))


def test_read_only_blocks_every_write():
    sdk = _Client011()
    yc = YounitClient(Settings(mode="live", trading_enabled=True), sdk_client=sdk)
    yc.read_only = True
    req = OrderRequest(symbol="COMI", side=Side.BUY, quantity=1, order_type=OrderType.LIMIT, limit_price=1.0)
    with pytest.raises(ValueError, match="read-only"):
        yc.submit_order(req)
    with pytest.raises(ValueError, match="read-only"):
        yc.cancel_order("123")
    with pytest.raises(OrderSafetyError, match="read-only"):
        OrderDesk(yc, Settings(mode="live", trading_enabled=True)).preview(req)
    assert sdk.buys == 0
