"""Built-in library of well-known technical strategies.

All long-only (hold the stock or hold cash), daily bars, EGX defaults.
"""

from __future__ import annotations

from . import indicators as ind
from .base import Param, closes, enter_exit, hold_while, strategy


@strategy(
    id="buy_and_hold",
    name="Buy and hold",
    summary="Buy on the first day and never sell. The baseline every other rule must beat.",
    how="Holds the stock every day. Any strategy that trades should earn more than this after fees.",
)
def buy_and_hold(bars, p):
    return [1] * len(bars)


@strategy(
    id="sma_cross",
    name="Moving-average crossover",
    summary="Hold while the fast simple moving average is above the slow one.",
    how="A classic trend filter. The 50/200 version is the 'golden cross'; shorter windows react faster but trade more.",
    params=[
        Param("fast", "Fast average (days)", 20, 2, 100),
        Param("slow", "Slow average (days)", 50, 5, 250),
    ],
    check=lambda p: "The fast average must be shorter than the slow one." if p["fast"] >= p["slow"] else None,
    reference="https://en.wikipedia.org/wiki/Moving_average_crossover",
)
def sma_cross(bars, p):
    c = closes(bars)
    f, s = ind.sma(c, p["fast"]), ind.sma(c, p["slow"])
    return hold_while([a is not None and b is not None and a > b for a, b in zip(f, s)])


@strategy(
    id="ema_cross",
    name="Exponential average crossover",
    summary="Like the moving-average crossover, but recent prices count more.",
    how="Exponential averages react faster to new prices than simple ones, so signals come earlier.",
    params=[
        Param("fast", "Fast average (days)", 12, 2, 100),
        Param("slow", "Slow average (days)", 26, 5, 250),
    ],
    check=lambda p: "The fast average must be shorter than the slow one." if p["fast"] >= p["slow"] else None,
)
def ema_cross(bars, p):
    c = closes(bars)
    f, s = ind.ema(c, p["fast"]), ind.ema(c, p["slow"])
    return hold_while([a is not None and b is not None and a > b for a, b in zip(f, s)])


@strategy(
    id="macd_signal",
    name="MACD signal line",
    summary="Hold while the MACD line is above its signal line.",
    how="MACD is the gap between a 12-day and 26-day exponential average; its 9-day average is the signal line. Crossings mark momentum turning.",
    params=[
        Param("fast", "Fast average (days)", 12, 2, 50),
        Param("slow", "Slow average (days)", 26, 5, 100),
        Param("signal", "Signal line (days)", 9, 2, 50),
    ],
    check=lambda p: "The fast average must be shorter than the slow one." if p["fast"] >= p["slow"] else None,
    reference="https://en.wikipedia.org/wiki/MACD",
)
def macd_signal(bars, p):
    line, sig = ind.macd(closes(bars), p["fast"], p["slow"], p["signal"])
    return hold_while([a is not None and b is not None and a > b for a, b in zip(line, sig)])


@strategy(
    id="rsi_reversion",
    name="RSI mean reversion",
    summary="Buy when RSI shows the stock oversold, sell when it shows it overbought.",
    how="RSI measures recent gains against losses on a 0 to 100 scale. Below 30 is commonly read as oversold, above 70 as overbought.",
    params=[
        Param("period", "RSI period (days)", 14, 2, 50),
        Param("lower", "Buy below", 30, 1, 50),
        Param("upper", "Sell above", 70, 50, 99),
    ],
    reference="https://en.wikipedia.org/wiki/Relative_strength_index",
)
def rsi_reversion(bars, p):
    r = ind.rsi(closes(bars), p["period"])
    return enter_exit(
        [v is not None and v < p["lower"] for v in r],
        [v is not None and v > p["upper"] for v in r],
    )


@strategy(
    id="bollinger_reversion",
    name="Bollinger band bounce",
    summary="Buy when the price closes below the lower band, sell when it returns to the middle.",
    how="The bands sit a set number of standard deviations around a moving average. A close outside them is unusual, and this rule bets it snaps back.",
    params=[
        Param("period", "Average (days)", 20, 5, 100),
        Param("width", "Band width (std. devs)", 2, 0.5, 4, step=0.5, integer=False),
    ],
    reference="https://en.wikipedia.org/wiki/Bollinger_Bands",
)
def bollinger_reversion(bars, p):
    c = closes(bars)
    mid, _, lower = ind.bollinger(c, p["period"], p["width"])
    return enter_exit(
        [lo is not None and price < lo for price, lo in zip(c, lower)],
        [m is not None and price >= m for price, m in zip(c, mid)],
    )


@strategy(
    id="donchian_breakout",
    name="Donchian breakout (Turtle)",
    summary="Buy when the price breaks above its recent high, sell when it breaks below a shorter recent low.",
    how="The rule the 1980s Turtle traders made famous: follow breakouts and cut losers on a shorter channel.",
    params=[
        Param("entry", "Breakout high (days)", 20, 5, 100),
        Param("exit", "Exit low (days)", 10, 2, 100),
    ],
    reference="https://en.wikipedia.org/wiki/Donchian_channel",
)
def donchian_breakout(bars, p):
    hi = ind.highest([b.high for b in bars], p["entry"])
    lo = ind.lowest([b.low for b in bars], p["exit"])
    c = closes(bars)
    return enter_exit(
        [h is not None and price > h for price, h in zip(c, hi)],
        [low is not None and price < low for price, low in zip(c, lo)],
    )


@strategy(
    id="momentum",
    name="Time-series momentum",
    summary="Hold while the stock is up over the lookback period, hold cash while it is down.",
    how="Trend following at its simplest: stocks that have risen tend to keep rising for a while.",
    params=[Param("lookback", "Lookback (days)", 60, 5, 250)],
    reference="https://en.wikipedia.org/wiki/Momentum_investing",
)
def momentum(bars, p):
    roc = ind.rate_of_change(closes(bars), p["lookback"])
    return hold_while([v is not None and v > 0 for v in roc])
