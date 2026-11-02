"""Small, dependency-free daily backtester for long-only strategies.

Signals are computed on day t's close and executed at day t+1's open, so a
strategy cannot trade on information it would not have had. A flat fee is
charged on every buy and every sell.

`start` lets you measure only part of the history (for out-of-sample tests)
while the strategy still sees all earlier days to warm up its indicators.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt
from typing import Optional

from . import strategies
from .models import Bar

EGX_SESSIONS_PER_YEAR = 245  # approximate


@dataclass
class BacktestResult:
    strategy: str
    strategy_name: str
    symbol: str
    params: dict
    start: str
    end: str
    trading_days: int
    total_return_pct: float
    buy_and_hold_return_pct: float
    max_drawdown_pct: float
    sharpe: float
    trades: int
    win_rate_pct: float
    exposure_pct: float  # share of days spent holding the stock
    trade_log: list[dict] = field(default_factory=list)
    # Growth of 100 EGP, strategy vs buy and hold, one point per trading day.
    equity_curve: list[dict] = field(default_factory=list)


def run_backtest(
    symbol: str,
    bars: list[Bar],
    strategy: "str | strategies.Strategy",
    params: Optional[dict] = None,
    commission_pct: float = 0.15,
    start: int = 0,
    targets: Optional[list[int]] = None,
) -> BacktestResult:
    strategies.load_all()
    spec = strategy if isinstance(strategy, strategies.Strategy) else strategies.get(strategy)
    resolved = spec.resolve(params)
    if len(bars) - start < 30:
        raise ValueError("Need at least 30 trading days of data to backtest.")
    target = targets if targets is not None else spec.run(bars, resolved)
    fee = commission_pct / 100
    window = bars[start:]

    equity = 1.0
    curve = [1.0]
    pos = 0
    entry_price = 0.0
    entry_day = ""
    log: list[dict] = []
    daily_rets: list[float] = []
    held = 0

    for t in range(start + 1, len(bars)):
        bar, prev = bars[t], bars[t - 1]
        want = target[t - 1]  # decided at yesterday's close
        start_eq = equity
        if want != pos:
            if want == 1:
                equity *= 1 - fee
                entry_price, entry_day = bar.open, bar.day.isoformat()
                equity *= bar.close / bar.open
            else:
                equity *= bar.open / prev.close
                equity *= 1 - fee
                log.append({
                    "entry": entry_day, "exit": bar.day.isoformat(),
                    "return_pct": round(100 * (bar.open / entry_price - 1), 2),
                })
            pos = want
        elif pos == 1:
            equity *= bar.close / prev.close
        held += pos
        daily_rets.append(equity / start_eq - 1)
        curve.append(equity)

    if pos == 1:
        log.append({
            "entry": entry_day, "exit": "open",
            "return_pct": round(100 * (bars[-1].close / entry_price - 1), 2),
        })

    peak, mdd = curve[0], 0.0
    for v in curve:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)

    mean = sum(daily_rets) / len(daily_rets)
    var = sum((r - mean) ** 2 for r in daily_rets) / max(1, len(daily_rets) - 1)
    sharpe = (mean / sqrt(var)) * sqrt(EGX_SESSIONS_PER_YEAR) if var > 0 else 0.0

    closed = [x for x in log if x["exit"] != "open"]
    wins = sum(1 for x in closed if x["return_pct"] > 0)
    first = window[0].close

    return BacktestResult(
        strategy=spec.id,
        strategy_name=spec.name,
        symbol=symbol,
        params=resolved,
        start=window[0].day.isoformat(),
        end=window[-1].day.isoformat(),
        trading_days=len(window),
        total_return_pct=round(100 * (equity - 1), 2),
        buy_and_hold_return_pct=round(100 * (window[-1].close / first - 1), 2),
        max_drawdown_pct=round(100 * mdd, 2),
        sharpe=round(sharpe, 2),
        trades=len(log),
        win_rate_pct=round(100 * wins / len(closed), 1) if closed else 0.0,
        exposure_pct=round(100 * held / max(1, len(window) - 1), 1),
        trade_log=log[-20:],
        equity_curve=[
            {"day": b.day.isoformat(), "strategy": round(100 * eq, 2), "buy_hold": round(100 * b.close / first, 2)}
            for b, eq in zip(window, curve)
        ],
    )
