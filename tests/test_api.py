from fastapi.testclient import TestClient

from sahm.api import app

api = TestClient(app)


def test_status_and_reads():
    assert api.get("/api/status").json()["synthetic"] is True
    assert api.get("/api/account").json()["currency"] == "EGP"
    assert len(api.get("/api/symbols").json()) == 8
    bars = api.get("/api/history/comi?days=90").json()["bars"]
    assert bars and {"day", "close"} <= set(bars[0])


def test_unknown_symbol_is_400():
    assert api.get("/api/history/AAPL").status_code == 400


def test_backtest_has_equity_curve():
    r = api.post("/api/backtest", json={"symbol": "SWDY", "strategy": "sma_cross"}).json()
    curve = r["equity_curve"]
    assert len(curve) == r["trading_days"]
    assert curve[0]["strategy"] == 100 and curve[0]["buy_hold"] == 100


def test_strategy_catalog_and_check():
    cat = api.get("/api/strategies").json()
    ids = {s["id"] for s in cat["strategies"]}
    assert {"macd_signal", "three_red_days"} <= ids
    card = api.post("/api/check", json={"strategy": "donchian_breakout"}).json()
    assert card["lookahead"]["passed"] and card["verdict"] == "demo_data"
    assert len(card["symbols"]) == 8
    assert api.post("/api/check", json={"strategy": "sma_cross", "params": {"fast": 99, "slow": 20}}).status_code == 400


def test_bad_strategy_is_400():
    assert api.post("/api/backtest", json={"symbol": "SWDY", "strategy": "moon"}).status_code == 400


def test_preview_then_confirm_blocked_when_trading_disabled():
    p = api.post("/api/orders/preview", json={"symbol": "FWRY", "side": "buy", "quantity": 10})
    assert p.status_code == 200
    c = api.post("/api/orders/confirm", json={"confirmation_token": p.json()["confirmation_token"]})
    assert c.status_code == 409 and "disabled" in c.json()["detail"]


def test_order_over_cap_is_409():
    r = api.post("/api/orders/preview", json={"symbol": "COMI", "side": "buy", "quantity": 1000})
    assert r.status_code == 409
