"""HTTP API for the Sahm dashboard. Shares the broker, order desk and backtester
with the MCP server, so both front doors follow the same safety rules.

Run:  sahm-dashboard        (serves the API and, if built, the web app on :8000)
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import research
from .broker import make_client
from .config import Settings
from .models import OrderRequest, OrderType, Side
from .orders import OrderDesk, OrderSafetyError

settings = Settings.from_env()
client = make_client(settings)
desk = OrderDesk(client, settings)

app = FastAPI(title="Sahm API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _day(value: Optional[str], default: date) -> date:
    try:
        return date.fromisoformat(value) if value else default
    except ValueError:
        raise HTTPException(400, f"Dates must be YYYY-MM-DD, got '{value}'.")


def _guard(fn, *args):
    try:
        return fn(*args)
    except OrderSafetyError as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/status")
def status():
    return {
        "source": client.name,
        "synthetic": client.name == "mock",
        "real_money": client.name != "mock" and settings.real_money,
        "trading_enabled": settings.trading_enabled,
        "max_order_egp": settings.max_order_egp,
    }


@app.get("/api/account")
def account():
    return client.get_account()


@app.get("/api/positions")
def positions():
    return client.get_positions()


@app.get("/api/symbols")
def symbols():
    # Live mode lists 200+ EGX stocks, so the dashboard quotes a watchlist (YOUNIT_WATCHLIST).
    tickers = list(client.list_symbols()) if client.name == "mock" else list(settings.watchlist)
    out = []
    for s in tickers:
        try:
            out.append(client.get_quote(s))
        except Exception:
            continue  # skip tickers the broker can't quote rather than failing the whole list
    return out


@app.get("/api/history/{symbol}")
def history(symbol: str, days: int = 182):
    end = date.today()
    bars = _guard(client.get_bars, symbol, end - timedelta(days=max(7, min(days, 730))), end)
    return {"symbol": symbol.upper(), "bars": bars}


@app.get("/api/strategies")
def strategies():
    return research.catalog()


class BacktestBody(BaseModel):
    symbol: str
    strategy: str
    days: int = 365
    params: dict = {}
    commission_pct: float = 0.15


@app.post("/api/backtest")
def backtest(body: BacktestBody):
    result = _guard(research.backtest, client, body.symbol, body.strategy, body.params, body.days, body.commission_pct)
    return asdict(result)


class CheckBody(BaseModel):
    strategy: str
    params: dict = {}
    symbols: Optional[list[str]] = None
    days: int = 730
    commission_pct: float = 0.15


@app.post("/api/check")
def check(body: CheckBody):
    card = _guard(research.check, client, settings, body.strategy, body.params, body.symbols, body.days,
                  body.commission_pct)
    return card.to_dict()


class OrderBody(BaseModel):
    symbol: str
    side: Side
    quantity: int
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None


@app.post("/api/orders/preview")
def preview(body: OrderBody):
    try:
        request = OrderRequest(**body.model_dump())
    except Exception as e:
        raise HTTPException(400, str(e))
    return _guard(desk.preview, request)


class ConfirmBody(BaseModel):
    confirmation_token: str


@app.post("/api/orders/confirm")
def confirm(body: ConfirmBody):
    return _guard(desk.confirm, body.confirmation_token)


@app.get("/api/orders")
def orders():
    return client.get_orders()


@app.post("/api/orders/{order_id}/cancel")
def cancel(order_id: str):
    return _guard(client.cancel_order, order_id)


# Serve the built web app (web/dist) when present.
_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"
if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        return FileResponse(_DIST / "index.html")


def main() -> None:
    import uvicorn

    uvicorn.run("sahm.api:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
