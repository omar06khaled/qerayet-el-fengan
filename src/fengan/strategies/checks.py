"""Checks that any strategy, built-in or contributed, must pass.

1. Look-ahead guard: a signal for day t may only use days up to t. We rerun the
   strategy on histories cut short at many points; if any past signal changes
   when future days are removed, the strategy is peeking at the future.

2. Report card: the history is split in two. The earlier part (in-sample) is
   where a strategy is usually tuned; the later part (out-of-sample) is data it
   has not seen. A rule that only beats buy and hold in-sample is likely overfit.

A backtest cannot prove a strategy will work. It can show whether a rule would
have beaten simply holding, after fees, on data it was not tuned on.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from statistics import median
from typing import Optional

from ..backtest import run_backtest
from ..models import Bar
from .base import Strategy

MIN_TRADES_PER_STOCK = 2  # on the out-of-sample data, averaged across stocks


def chance_of_luck(beat: int, n: int) -> float:
    """Chance a coin-flip rule beats buy and hold on at least `beat` of `n` stocks."""
    from math import comb

    return sum(comb(n, k) for k in range(beat, n + 1)) / 2**n


@dataclass
class LookaheadResult:
    passed: bool
    cuts_tested: int
    detail: str
    first_bad_day: Optional[str] = None


def lookahead_check(spec: Strategy, bars: list[Bar], params: Optional[dict] = None, cuts: int = 15) -> LookaheadResult:
    full = spec.run(bars, params)
    n = len(bars)
    lo = max(2, n // 5)
    points = sorted({lo + (n - 2 - lo) * i // max(1, cuts - 1) for i in range(cuts)})
    for k in points:
        try:
            partial = spec.run(bars[: k + 1], params)
        except Exception as e:
            return LookaheadResult(False, len(points), f"Crashed on a shorter history ({k + 1} days): {e}")
        if partial != full[: k + 1]:
            bad = next(i for i, (a, b) in enumerate(zip(partial, full)) if a != b)
            day = bars[bad].day.isoformat()
            return LookaheadResult(
                False, len(points),
                f"The signal for {day} changed when later days were removed, so it uses future prices.",
                day,
            )
    return LookaheadResult(True, len(points), f"Signals stayed the same across {len(points)} shortened histories.")


@dataclass
class SymbolScore:
    symbol: str
    in_sample_pct: float
    in_sample_hold_pct: float
    out_sample_pct: float
    out_sample_hold_pct: float
    out_sample_trades: int
    out_sample_drawdown_pct: float
    out_sample_start: str
    beat_in_sample: bool
    beat_out_sample: bool


@dataclass
class ReportCard:
    strategy: str
    strategy_name: str
    params: dict
    split_pct: int
    lookahead: LookaheadResult
    verdict: str  # holds_up | mixed | does_not_hold_up | too_few_trades | baseline | invalid | demo_data
    headline: str
    notes: list[str] = field(default_factory=list)
    symbols: list[SymbolScore] = field(default_factory=list)
    beat_count: int = 0
    median_excess_pct: float = 0.0
    total_trades: int = 0
    luck_chance_pct: float = 100.0

    def to_dict(self) -> dict:
        return asdict(self)


def report_card(
    spec: Strategy,
    bars_by_symbol: dict[str, list[Bar]],
    params: Optional[dict] = None,
    split: float = 0.7,
    commission_pct: float = 0.15,
    synthetic: bool = False,
) -> ReportCard:
    resolved = spec.resolve(params)
    usable = {s: b for s, b in bars_by_symbol.items() if len(b) >= 120}
    if not usable:
        raise ValueError("Need at least 120 trading days per stock to split into in-sample and out-of-sample.")

    # Look-ahead check on the longest history available.
    longest = max(usable.values(), key=len)
    la = lookahead_check(spec, longest, resolved)

    scores: list[SymbolScore] = []
    for sym, bars in usable.items():
        cut = int(len(bars) * split)
        targets = spec.run(bars, resolved)
        ins = run_backtest(sym, bars[:cut], spec, resolved, commission_pct, targets=targets[:cut])
        oos = run_backtest(sym, bars, spec, resolved, commission_pct, start=cut, targets=targets)
        scores.append(SymbolScore(
            symbol=sym,
            in_sample_pct=ins.total_return_pct,
            in_sample_hold_pct=ins.buy_and_hold_return_pct,
            out_sample_pct=oos.total_return_pct,
            out_sample_hold_pct=oos.buy_and_hold_return_pct,
            out_sample_trades=oos.trades,
            out_sample_drawdown_pct=oos.max_drawdown_pct,
            out_sample_start=oos.start,
            beat_in_sample=ins.total_return_pct > ins.buy_and_hold_return_pct,
            beat_out_sample=oos.total_return_pct > oos.buy_and_hold_return_pct,
        ))

    n = len(scores)
    beat = sum(s.beat_out_sample for s in scores)
    beat_in = sum(s.beat_in_sample for s in scores)
    excess = median(s.out_sample_pct - s.out_sample_hold_pct for s in scores)
    trades = sum(s.out_sample_trades for s in scores)
    luck = chance_of_luck(beat, n)
    notes: list[str] = []

    if not la.passed:
        verdict, headline = "invalid", "Fails the look-ahead check, so its results cannot be trusted."
        notes.append(la.detail)
    elif spec.id == "buy_and_hold":
        verdict, headline = "baseline", "This is the baseline the other strategies are measured against."
    elif synthetic:
        verdict = "demo_data"
        headline = "The code works. Demo prices are random, so they cannot tell you whether the idea does."
    elif trades < MIN_TRADES_PER_STOCK * n:
        verdict = "too_few_trades"
        headline = f"Only {trades} trades on the later data: too few to tell skill from luck."
    elif beat * 3 >= n * 2 and excess > 0:
        verdict = "holds_up"
        headline = f"Beat buy and hold on {beat} of {n} stocks on data it was not tuned on."
    elif beat * 3 <= n:
        verdict = "does_not_hold_up"
        headline = f"Beat buy and hold on only {beat} of {n} stocks on the later data."
    else:
        verdict = "mixed"
        headline = f"Beat buy and hold on {beat} of {n} stocks on the later data: no clear edge."

    if la.passed and beat_in * 3 >= n * 2 and verdict in ("does_not_hold_up", "mixed"):
        notes.append(
            f"It beat buy and hold on {beat_in} of {n} stocks on the earlier data but not on the later data. "
            "That pattern usually means the rule fits past noise (overfitting)."
        )
    if la.passed and verdict in ("holds_up", "mixed"):
        notes.append(
            f"A rule that picks at random would beat buy and hold on {beat} or more of {n} stocks "
            f"about {100 * luck:.0f}% of the time. Stocks tend to move together, so the true chance is higher."
        )
    if synthetic:
        notes.append(
            "Demo prices are synthetic random walks with no real patterns, so any edge shown here is luck. "
            "Use live mode for real EGX history before drawing conclusions."
        )
    notes.append(f"Fees of {commission_pct:g}% are charged on every buy and every sell. Past results do not predict future returns.")

    return ReportCard(
        strategy=spec.id, strategy_name=spec.name, params=resolved, split_pct=round(split * 100),
        lookahead=la, verdict=verdict, headline=headline, notes=notes, symbols=scores,
        beat_count=beat, median_excess_pct=round(excess, 2), total_trades=trades,
        luck_chance_pct=round(100 * luck, 1),
    )
