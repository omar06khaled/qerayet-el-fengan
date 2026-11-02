"""Example user strategy. Copy this file, rename it, and change the rule.

Every .py file in this folder is loaded when Sahm starts, and shows up in the
dashboard, the API and the MCP tools next to the built-in strategies.

The rule: after a streak of down closes, buy, then sell after a fixed number of days.
"""

from sahm.strategies import Param, strategy


@strategy(
    id="three_red_days",
    name="Three red days",
    summary="Buy after a streak of down closes, sell after a fixed number of days.",
    how="A short-term bounce rule: several down days in a row often overshoot. Exits on time, not on price.",
    params=[
        Param("streak", "Down days in a row", 3, 1, 10),
        Param("hold", "Days to hold", 5, 1, 60),
    ],
    author="Omar Nassar",
)
def three_red_days(bars, p):
    targets = []
    down_streak = 0
    days_held = 0
    for i, bar in enumerate(bars):
        # Only today's and earlier closes are used: bars[i] and bars[i - 1].
        if i > 0 and bar.close < bars[i - 1].close:
            down_streak += 1
        else:
            down_streak = 0

        if days_held > 0:
            days_held += 1
            if days_held > p["hold"]:
                days_held = 0
        elif down_streak >= p["streak"]:
            days_held = 1

        targets.append(1 if days_held > 0 else 0)
    return targets
