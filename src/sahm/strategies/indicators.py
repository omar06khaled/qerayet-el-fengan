"""Technical indicators, dependency-free.

Every function returns a list the same length as its input, with None until
enough history exists. Each value at index i uses only inputs up to and
including i, so indicators never look ahead.
"""

from __future__ import annotations

from math import sqrt
from typing import Optional

Series = list[Optional[float]]


def sma(values: list[float], n: int) -> Series:
    out: Series = [None] * len(values)
    s = 0.0
    for i, v in enumerate(values):
        s += v
        if i >= n:
            s -= values[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def ema(values: list[float], n: int) -> Series:
    """Exponential moving average, seeded with the SMA of the first n values."""
    out: Series = [None] * len(values)
    if len(values) < n:
        return out
    k = 2 / (n + 1)
    prev = sum(values[:n]) / n
    out[n - 1] = prev
    for i in range(n, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def rsi(values: list[float], n: int) -> Series:
    """Wilder's relative strength index, 0 to 100."""
    out: Series = [None] * len(values)
    if len(values) <= n:
        return out
    gains = losses = 0.0
    for i in range(1, n + 1):
        d = values[i] - values[i - 1]
        gains += max(d, 0)
        losses += max(-d, 0)
    g, l = gains / n, losses / n
    out[n] = 100.0 if l == 0 else 100 - 100 / (1 + g / l)
    for i in range(n + 1, len(values)):
        d = values[i] - values[i - 1]
        g = (g * (n - 1) + max(d, 0)) / n
        l = (l * (n - 1) + max(-d, 0)) / n
        out[i] = 100.0 if l == 0 else 100 - 100 / (1 + g / l)
    return out


def stdev(values: list[float], n: int) -> Series:
    """Rolling population standard deviation."""
    out: Series = [None] * len(values)
    for i in range(n - 1, len(values)):
        window = values[i - n + 1 : i + 1]
        m = sum(window) / n
        out[i] = sqrt(sum((v - m) ** 2 for v in window) / n)
    return out


def bollinger(values: list[float], n: int, k: float) -> tuple[Series, Series, Series]:
    """(middle, upper, lower) bands."""
    mid, sd = sma(values, n), stdev(values, n)
    upper = [m + k * s if m is not None and s is not None else None for m, s in zip(mid, sd)]
    lower = [m - k * s if m is not None and s is not None else None for m, s in zip(mid, sd)]
    return mid, upper, lower


def macd(values: list[float], fast: int, slow: int, signal: int) -> tuple[Series, Series]:
    """(macd line, signal line)."""
    f, s = ema(values, fast), ema(values, slow)
    line: Series = [a - b if a is not None and b is not None else None for a, b in zip(f, s)]
    start = next((i for i, v in enumerate(line) if v is not None), None)
    sig: Series = [None] * len(values)
    if start is not None:
        tail = ema([v for v in line[start:] if v is not None], signal)
        sig[start:] = tail
    return line, sig


def highest(values: list[float], n: int) -> Series:
    """Highest value of the PREVIOUS n bars, excluding today (for breakouts)."""
    out: Series = [None] * len(values)
    for i in range(n, len(values)):
        out[i] = max(values[i - n : i])
    return out


def lowest(values: list[float], n: int) -> Series:
    """Lowest value of the PREVIOUS n bars, excluding today."""
    out: Series = [None] * len(values)
    for i in range(n, len(values)):
        out[i] = min(values[i - n : i])
    return out


def rate_of_change(values: list[float], n: int) -> Series:
    """Percent change over n bars."""
    out: Series = [None] * len(values)
    for i in range(n, len(values)):
        if values[i - n]:
            out[i] = 100 * (values[i] / values[i - n] - 1)
    return out
