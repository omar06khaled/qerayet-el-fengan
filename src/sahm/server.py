"""Sahm MCP server (FastMCP, stdio transport).

Run:  sahm-mcp              (after `pip install -e .`)
  or: python -m sahm.server
Inspect: npx @modelcontextprotocol/inspector sahm-mcp

For full account access (funds, streaming, 30 tools), use the official SDK's
`younit-mcp`. This server adds rule backtesting and runs on synthetic data offline.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, timedelta
from typing import Optional

from mcp.server.fastmcp import FastMCP

from . import research
from .backtest import run_backtest
from .broker import make_client
from .config import Settings
from .models import OrderRequest, OrderType, Side
from .orders import OrderDesk

settings = Settings.from_env()
client = make_client(settings)
desk = OrderDesk(client, settings)

mcp = FastMCP(
    "sahm",
    instructions=(
        "Tools for Younit by EFG Hermes (Egyptian Exchange, prices in EGP). "
        f"Data source: {client.name}"
        + (" (SYNTHETIC demo data, not real prices)" if client.name == "mock" else "")
        + ". Orders are two-step: call preview_order, show the summary to the user, "
        "and call confirm_order only after the user explicitly approves."
    ),
)


def _parse_day(value: Optional[str], default: date) -> date:
    return date.fromisoformat(value) if value else default


# Read-only tools

@mcp.tool()
def get_account() -> dict:
    """Cash, equity and buying power for the connected account (EGP)."""
    return client.get_account().model_dump()


@mcp.tool()
def get_positions() -> list[dict]:
    """Open positions with cost basis, market value and unrealized P&L."""
    return [p.model_dump() for p in client.get_positions()]


@mcp.tool()
def list_symbols() -> dict[str, str]:
    """Tradable EGX tickers and company names."""
    return client.list_symbols()


@mcp.tool()
def get_quote(symbol: str) -> dict:
    """Latest price, daily change and volume for one EGX ticker, e.g. COMI."""
    return client.get_quote(symbol).model_dump(mode="json")


@mcp.tool()
def get_price_history(symbol: str, start: Optional[str] = None, end: Optional[str] = None) -> dict:
    """Daily OHLCV bars for a ticker. Dates are YYYY-MM-DD; defaults to the last 6 months.
    Returns a summary plus at most 130 bars to keep responses small."""
    end_d = _parse_day(end, date.today())
    start_d = _parse_day(start, end_d - timedelta(days=182))
    bars = client.get_bars(symbol, start_d, end_d)
    if not bars:
        return {"symbol": symbol.upper(), "bars": [], "note": "No data in that range."}
    closes = [b.close for b in bars]
    return {
        "symbol": symbol.upper(),
        "start": bars[0].day.isoformat(),
        "end": bars[-1].day.isoformat(),
        "return_pct": round(100 * (closes[-1] / closes[0] - 1), 2),
        "high": max(b.high for b in bars),
        "low": min(b.low for b in bars),
        "bars": [b.model_dump(mode="json") for b in bars[-130:]],
    }


@mcp.tool()
def get_orders() -> list[dict]:
    """Recent orders and their status."""
    return [o.model_dump(mode="json") for o in client.get_orders()]


# Research tools

@mcp.tool()
def list_strategies() -> dict:
    """All strategies (built-in and the user's own files) with their parameters, defaults and ranges."""
    return research.catalog()


@mcp.tool()
def backtest_strategy(
    symbol: str,
    strategy: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    params: Optional[dict] = None,
    commission_pct: float = 0.15,
) -> dict:
    """Backtest a long-only rule strategy on daily bars (signals at close, fills at next open).
    strategy: one of list_strategies(). Dates YYYY-MM-DD, default last 12 months.
    Results are historical simulations, not predictions."""
    end_d = _parse_day(end, date.today())
    start_d = _parse_day(start, end_d - timedelta(days=365))
    bars = client.get_bars(symbol, start_d, end_d)
    result = asdict(run_backtest(symbol.upper(), bars, strategy, params, commission_pct))
    result.pop("equity_curve")  # chart data is for the dashboard; keep AI responses small
    return result


@mcp.tool()
def check_strategy(strategy: str, params: Optional[dict] = None, symbols: Optional[list[str]] = None) -> dict:
    """Report card for a strategy: a look-ahead check, then a test on data it was not tuned on.
    Splits about 2 years of history 70/30 per stock and compares the later 30% against buy and hold.
    Report the verdict and the notes to the user as written; never call it proof the strategy will work."""
    return research.check(client, settings, strategy, params, symbols).to_dict()


# Trading tools (two-step, guarded)

@mcp.tool()
def preview_order(
    symbol: str,
    side: str,
    quantity: int,
    order_type: str = "market",
    limit_price: Optional[float] = None,
    stop_price: Optional[float] = None,
) -> dict:
    """Step 1 of 2. Validate and price an order WITHOUT placing it.
    side: buy|sell. order_type: market|limit|stop (stop = conditional trigger).
    Returns a confirmation_token. Show the summary to the user before anything else."""
    request = OrderRequest(
        symbol=symbol.upper(),
        side=Side(side.lower()),
        quantity=quantity,
        order_type=OrderType(order_type.lower()),
        limit_price=limit_price,
        stop_price=stop_price,
    )
    return desk.preview(request)


@mcp.tool()
def confirm_order(confirmation_token: str) -> dict:
    """Step 2 of 2. Place a previously previewed order.
    Call ONLY after the user has explicitly approved that exact preview in this conversation."""
    return desk.confirm(confirmation_token).model_dump(mode="json")


@mcp.tool()
def cancel_order(order_id: str) -> dict:
    """Cancel a pending order by id."""
    return client.cancel_order(order_id).model_dump(mode="json")


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
