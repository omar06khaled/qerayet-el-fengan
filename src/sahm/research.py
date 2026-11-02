"""Strategy research helpers shared by the dashboard API and the MCP server."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from . import strategies
from .backtest import run_backtest
from .broker.base import BrokerClient
from .config import Settings
from .strategies.checks import report_card


def check_universe(client: BrokerClient, settings: Settings) -> list[str]:
    """Stocks a strategy is checked on: the demo universe, or the live watchlist."""
    return list(client.list_symbols()) if client.name == "mock" else list(settings.watchlist)


def backtest(client: BrokerClient, symbol: str, strategy: str, params: Optional[dict], days: int,
             commission_pct: float = 0.15):
    end = date.today()
    bars = client.get_bars(symbol, end - timedelta(days=max(60, min(days, 1500))), end)
    return run_backtest(symbol.upper(), bars, strategy, params, commission_pct)


def check(client: BrokerClient, settings: Settings, strategy: str, params: Optional[dict],
          symbols: Optional[list[str]] = None, days: int = 730, commission_pct: float = 0.15):
    strategies.load_all()
    spec = strategies.get(strategy)
    end = date.today()
    start = end - timedelta(days=max(240, min(days, 1500)))
    bars = {}
    for s in symbols or check_universe(client, settings):
        try:
            bars[s.upper()] = client.get_bars(s, start, end)
        except Exception:
            continue  # a stock the broker cannot serve is left out of the report
    return report_card(spec, bars, params, commission_pct=commission_pct, synthetic=client.name == "mock")


def catalog() -> dict:
    strategies.load_all()
    return {
        "strategies": [s.to_dict() for s in strategies.REGISTRY.values()],
        "load_errors": list(strategies.LOAD_ERRORS),
    }
