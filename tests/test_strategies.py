"""Strategy library tests. Every registered strategy, including contributed files in
strategies/, must pass these, so they double as the gate for open-source contributions."""

from datetime import date

import pytest

from fengan import strategies
from fengan.broker.mock import MockYounitClient
from fengan.strategies import Param, Strategy, indicators as ind
from fengan.strategies.checks import chance_of_luck, lookahead_check, report_card
from fengan.strategies.loader import load_file

strategies.load_all()
CLIENT = MockYounitClient()
BARS = CLIENT.get_bars("COMI", date(2025, 6, 1), date(2026, 11, 1))
ALL_BARS = {s: CLIENT.get_bars(s, date(2025, 6, 1), date(2026, 11, 1)) for s in CLIENT.list_symbols()}


@pytest.mark.parametrize("sid", sorted(strategies.REGISTRY))
def test_every_strategy_runs_and_has_no_lookahead(sid):
    spec = strategies.get(sid)
    out = spec.run(BARS)
    assert len(out) == len(BARS) and set(out) <= {0, 1}
    result = lookahead_check(spec, BARS)
    assert result.passed, f"{sid}: {result.detail}"


@pytest.mark.parametrize("sid", sorted(strategies.REGISTRY))
def test_every_strategy_is_documented(sid):
    spec = strategies.get(sid)
    assert spec.name and spec.summary and spec.author
    for p in spec.params:
        assert p.min <= p.default <= p.max, f"{sid}.{p.key} default outside its range"


def test_builtin_library_is_present():
    expected = {"buy_and_hold", "sma_cross", "ema_cross", "macd_signal", "rsi_reversion",
                "bollinger_reversion", "donchian_breakout", "momentum"}
    assert expected <= set(strategies.REGISTRY)


def test_example_user_strategy_is_loaded_from_folder():
    spec = strategies.get("three_red_days")
    assert spec.source == "your file: three_red_days.py"


def test_lookahead_guard_catches_a_cheat():
    cheat = Strategy(
        id="cheat", name="Peeks at tomorrow", summary="Buys if tomorrow closes higher.",
        signals=lambda b, p: [1 if i + 1 < len(b) and b[i + 1].close > b[i].close else 0 for i in range(len(b))],
    )
    result = lookahead_check(cheat, BARS)
    assert not result.passed and result.first_bad_day
    card = report_card(cheat, ALL_BARS)
    assert card.verdict == "invalid"


def test_param_validation():
    sma = strategies.get("sma_cross")
    assert sma.resolve({}) == {"fast": 20, "slow": 50}
    with pytest.raises(ValueError, match="shorter"):
        sma.resolve({"fast": 60, "slow": 50})
    with pytest.raises(ValueError, match="between"):
        sma.resolve({"fast": 1})
    with pytest.raises(ValueError, match="Unknown parameter"):
        sma.resolve({"fats": 10})
    with pytest.raises(ValueError, match="whole number"):
        sma.resolve({"fast": 10.5})
    assert strategies.get("bollinger_reversion").resolve({"width": 2.5})["width"] == 2.5


def test_bad_output_is_rejected():
    short = Strategy(id="short", name="Short", summary="", signals=lambda b, p: [1])
    with pytest.raises(ValueError, match="signals for"):
        short.run(BARS)
    weird = Strategy(id="weird", name="Weird", summary="", signals=lambda b, p: [2] * len(b))
    with pytest.raises(ValueError, match="only 0"):
        weird.run(BARS)


def test_broken_user_file_is_reported_not_fatal(tmp_path):
    bad = tmp_path / "broken.py"
    bad.write_text("raise RuntimeError('oops')\n")
    before = len(strategies.LOAD_ERRORS)
    load_file(bad)
    assert len(strategies.LOAD_ERRORS) == before + 1
    assert strategies.LOAD_ERRORS[-1]["file"] == "broken.py"


def test_duplicate_id_is_rejected(tmp_path):
    dup = tmp_path / "dup.py"
    dup.write_text(
        "from fengan.strategies import strategy\n"
        "@strategy(id='sma_cross', name='x', summary='x')\n"
        "def f(b, p):\n    return [0] * len(b)\n"
    )
    load_file(dup)
    assert "already exists" in strategies.LOAD_ERRORS[-1]["error"]
    assert strategies.get("sma_cross").source == "built-in"


def test_synthetic_data_never_gets_a_verdict():
    card = report_card(strategies.get("bollinger_reversion"), ALL_BARS, synthetic=True)
    assert card.verdict == "demo_data"
    assert any("random" in n for n in card.notes)


def test_report_card_splits_history():
    card = report_card(strategies.get("sma_cross"), ALL_BARS)
    s = card.symbols[0]
    assert card.split_pct == 70 and len(card.symbols) == 8
    assert s.out_sample_start > BARS[0].day.isoformat()


def test_chance_of_luck():
    assert chance_of_luck(0, 8) == 1.0
    assert chance_of_luck(8, 8) == pytest.approx(1 / 256)
    assert chance_of_luck(7, 8) == pytest.approx(9 / 256)


def test_indicators_match_hand_calculations():
    v = [1.0, 2, 3, 4, 5]
    assert ind.sma(v, 3) == [None, None, 2.0, 3.0, 4.0]
    assert ind.highest(v, 2) == [None, None, 2.0, 3.0, 4.0]  # previous bars only
    assert ind.rate_of_change(v, 1)[1] == pytest.approx(100.0)
    e = ind.ema(v, 3)
    assert e[2] == pytest.approx(2.0) and e[3] == pytest.approx(3.0)
    r = ind.rsi([1.0, 2, 3, 4, 5, 6], 3)
    assert r[3] == 100.0  # only gains


def test_new_strategy_with_param_object():
    p = Param("n", "N", 5, 1, 10)
    assert p.coerce("7") == 7
