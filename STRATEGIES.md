# Writing a strategy

A strategy is one Python function that looks at daily prices and says, for each day, whether to hold the stock (1) or hold cash (0). Sahm handles the rest: backtesting, the dashboard form, the AI tools, and the checks.

## The built-in library

| Strategy | Idea | Settings (defaults) |
|---|---|---|
| Buy and hold | The baseline every rule must beat | None |
| Moving-average crossover | Hold while the fast average is above the slow one | fast 20, slow 50 |
| Exponential average crossover | The same, weighting recent prices more | fast 12, slow 26 |
| MACD signal line | Hold while MACD is above its signal line | 12, 26, 9 |
| RSI mean reversion | Buy oversold, sell overbought | period 14, buy below 30, sell above 70 |
| Bollinger band bounce | Buy below the lower band, sell at the middle | 20 days, 2 std. devs |
| Donchian breakout (Turtle) | Buy a breakout above the recent high, sell below a shorter recent low | 20 / 10 days |
| Time-series momentum | Hold while the stock is up over the lookback | 60 days |

## Add your own in three steps

1. Copy `strategies/three_red_days.py` to a new file in the same folder, for example `strategies/my_rule.py`.
2. Change the `@strategy(...)` details and the rule inside the function.
3. Restart `sahm-dashboard`. Your strategy appears under **Your strategies** in the lab, and in the MCP tools.

```python
from sahm.strategies import Param, closes, hold_while, indicators as ind, strategy


@strategy(
    id="price_above_average",          # lowercase, digits, underscores; must be unique
    name="Price above its average",
    summary="Hold while the close is above its moving average.",
    params=[Param("days", "Average (days)", 50, 5, 250)],
    author="Your name",
)
def price_above_average(bars, p):
    c = closes(bars)
    avg = ind.sma(c, p["days"])
    return hold_while([a is not None and price > a for price, a in zip(c, avg)])
```

**What you get:**
- `bars`: daily bars, oldest first, each with `day`, `open`, `high`, `low`, `close`, `volume`.
- `p`: your settings, already checked against each `Param`'s range.

**What you return:** a list of 0s and 1s, one per bar.

**Helpers:**
- `hold_while(conditions)`: 1 on every day a condition is true.
- `enter_exit(enter, exit)`: buy when `enter` fires, sell when `exit` fires.

**Indicators:** `sma`, `ema`, `rsi`, `stdev`, `bollinger`, `macd`, `highest` and `lowest` (previous N days, excluding today), and `rate_of_change`. Each returns `None` until it has enough history.

**Cross-setting rules:** to reject combinations that make no sense, pass `check=lambda p: "message" if bad else None`.

## The one rule: never use the future

The decision for day *t* is made at day *t*'s close and traded at day *t+1*'s open. Your function may use `bars[i]` and anything earlier, never `bars[i + 1]`.

You don't have to take this on trust. **Check this strategy** in the dashboard, the `check_strategy` MCP tool, and the test suite all run the **look-ahead guard**. It reruns your strategy on histories cut short at 15 points and fails if any past signal changes when future days are removed.

## What the report card tells you, and what it doesn't

The report card splits each stock's history 70/30. You usually tune a rule on the earlier part, so only the later part shows whether it holds up. It compares the strategy to simply holding the stock, after a 0.15% fee each way, on every stock in your watchlist.

| Verdict | Meaning |
|---|---|
| Holds up on unseen data | Beat holding on at least two thirds of stocks on the later data |
| Mixed results | No clear edge either way |
| Does not hold up | Beat holding on a third of stocks or fewer |
| Too few trades to judge | Fewer than 2 trades per stock on the later data |
| Uses future prices | Failed the look-ahead guard; ignore its numbers |
| No verdict on demo data | Demo prices are random walks, so nothing can be learned about the idea |

The report also says how often a random rule would do as well. **A backtest cannot prove a strategy will work.** It can only show that a rule would have beaten holding on data it wasn't tuned on. Treat a good result as a reason to keep testing, not a reason to trade.

## Contributing a strategy to the project

1. Add your file to `strategies/`, with your name as `author` and a link in `reference` if the idea has a source.
2. Run `pytest -q`. Every strategy, yours included, must pass the look-ahead guard and the documentation checks.
3. Open a pull request with the report card from live mode (real EGX history) pasted in the description.

Strategy files are Python and run with full permissions. Contributed files may only import from `sahm.strategies`, `math`, `statistics`, `typing`, `dataclasses` and `__future__`, with no `open`, `eval`, `exec` or `__import__`. A test enforces this, but it is a first filter, not a sandbox: every pull request is also read by a person. Never load strategy files you haven't read.
