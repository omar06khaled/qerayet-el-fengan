"""Strategy plugin interface and registry.

A strategy is a function that, given daily bars and parameters, returns a target
position for each day: 1 = hold the stock, 0 = hold cash. The backtester decides
on day t's close and trades at day t+1's open, so a strategy may use day t's
close but nothing after it. `checks.lookahead_check` verifies this automatically.

    from sahm.strategies import Param, strategy

    @strategy(
        id="three_red_days",
        name="Three red days",
        summary="Buy after three down closes in a row, sell after a few days.",
        params=[Param("streak", "Down days in a row", 3, 1, 10),
                Param("hold", "Days to hold", 5, 1, 60)],
        author="Your name",
    )
    def three_red_days(bars, p):
        ...
        return targets  # list of 0/1, same length as bars
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from ..models import Bar

SignalFn = Callable[[list[Bar], dict], list[int]]
CheckFn = Callable[[dict], Optional[str]]


@dataclass(frozen=True)
class Param:
    key: str
    label: str
    default: float
    min: float
    max: float
    step: float = 1
    integer: bool = True
    help: str = ""

    def coerce(self, raw: object) -> float:
        try:
            value = float(raw)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            raise ValueError(f"{self.label} must be a number.")
        if self.integer:
            if value != int(value):
                raise ValueError(f"{self.label} must be a whole number.")
            value = int(value)
        if not (self.min <= value <= self.max):
            raise ValueError(f"{self.label} must be between {self.min:g} and {self.max:g}.")
        return value

    def to_dict(self) -> dict:
        return {
            "key": self.key, "label": self.label, "default": self.default, "min": self.min,
            "max": self.max, "step": self.step, "integer": self.integer, "help": self.help,
        }


@dataclass
class Strategy:
    id: str
    name: str
    summary: str
    signals: SignalFn
    params: list[Param] = field(default_factory=list)
    how: str = ""
    author: str = "Sahm"
    source: str = "built-in"
    reference: str = ""
    check: Optional[CheckFn] = None  # cross-parameter rule, returns an error message or None

    def resolve(self, raw: Optional[dict]) -> dict:
        """Defaults + validation. Unknown keys are rejected so typos never pass silently."""
        raw = dict(raw or {})
        unknown = set(raw) - {p.key for p in self.params}
        if unknown:
            raise ValueError(f"Unknown parameter(s) for {self.name}: {', '.join(sorted(unknown))}.")
        values = {p.key: p.coerce(raw.get(p.key, p.default)) for p in self.params}
        if self.check:
            problem = self.check(values)
            if problem:
                raise ValueError(problem)
        return values

    def run(self, bars: list[Bar], raw_params: Optional[dict] = None) -> list[int]:
        p = self.resolve(raw_params)
        out = list(self.signals(bars, p))
        if len(out) != len(bars):
            raise ValueError(f"{self.name} returned {len(out)} signals for {len(bars)} days.")
        if any(v not in (0, 1) for v in out):
            raise ValueError(f"{self.name} must return only 0 (cash) or 1 (hold) for each day.")
        return out

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "summary": self.summary, "how": self.how,
            "author": self.author, "source": self.source, "reference": self.reference,
            "params": [p.to_dict() for p in self.params],
        }


REGISTRY: dict[str, Strategy] = {}
LOAD_ERRORS: list[dict] = []


def strategy(
    *,
    id: str,
    name: str,
    summary: str,
    params: Optional[list[Param]] = None,
    how: str = "",
    author: str = "Sahm",
    reference: str = "",
    check: Optional[CheckFn] = None,
    source: str = "built-in",
) -> Callable[[SignalFn], SignalFn]:
    """Register a strategy. Used as a decorator on its signal function."""

    def register(fn: SignalFn) -> SignalFn:
        if not id.replace("_", "").isalnum() or not id.islower():
            raise ValueError(f"Strategy id '{id}' must be lowercase letters, digits and underscores.")
        if id in REGISTRY:
            raise ValueError(f"A strategy with id '{id}' already exists ({REGISTRY[id].source}).")
        REGISTRY[id] = Strategy(
            id=id, name=name, summary=summary, signals=fn, params=list(params or []),
            how=how, author=author, source=source, reference=reference, check=check,
        )
        return fn

    return register


def get(strategy_id: str) -> Strategy:
    try:
        return REGISTRY[strategy_id]
    except KeyError:
        raise ValueError(f"Unknown strategy '{strategy_id}'. Options: {', '.join(REGISTRY)}") from None


def closes(bars: list[Bar]) -> list[float]:
    return [b.close for b in bars]


def hold_while(conditions: list[Optional[bool]]) -> list[int]:
    """1 on days the condition is True, 0 otherwise (None counts as not yet known)."""
    return [1 if c else 0 for c in conditions]


def enter_exit(enter: list[Optional[bool]], exit_: list[Optional[bool]]) -> list[int]:
    """Stateful helper: go long when `enter` fires, go flat when `exit_` fires."""
    out, pos = [], 0
    for e, x in zip(enter, exit_):
        if pos == 0 and e:
            pos = 1
        elif pos == 1 and x:
            pos = 0
        out.append(pos)
    return out
