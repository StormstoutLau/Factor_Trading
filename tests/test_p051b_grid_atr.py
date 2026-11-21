"""P-051b G 组：grid_atr ATR 间距网格。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from _p051b_common import DATES
from core.strategy import MarketView, StrategyState
from strategies.base import StrategyConfigError
from strategies.grid import GridATRConfig, GridATRStrategy


def _view(closes, highs, lows, prices, codes):
    idx = DATES[: len(closes)]
    history = {
        "close": pd.DataFrame(closes, index=idx, columns=codes),
        "high": pd.DataFrame(highs, index=idx, columns=codes),
        "low": pd.DataFrame(lows, index=idx, columns=codes),
    }
    view = MarketView(
        date=idx[-1],
        signal=pd.Series(1.0, index=codes),
        tradable=pd.Series(True, index=codes),
        prices=pd.Series(prices, dtype=float),
        returns=None,
        history=history,
    )
    state = StrategyState(as_of=str(idx[-1].date()), positions={}, extras={})
    return view, state


def _flat(rows: int, cols: int, value: float) -> np.ndarray:
    return np.full((rows, cols), value)


def test_g1_atr_seed_independent():
    from core.volatility import atr

    high = _flat(15, 1, 10.5)
    low = _flat(15, 1, 9.5)
    for seed in (10.0, 10.2, 9.8):
        close = _flat(15, 1, seed)
        value = float(
            atr(pd.DataFrame(high), pd.DataFrame(low), pd.DataFrame(close), period=14).iloc[-1, 0]
        )
        assert value == pytest.approx(1.0)


def test_g2_level_weights_table():
    codes = ["000001"]
    closes = _flat(15, 1, 10.0)
    highs = _flat(15, 1, 10.5)
    lows = _flat(15, 1, 9.5)
    strategy = GridATRStrategy(GridATRConfig(base_price={"000001": 10.0}))
    expected = {10.0: 0.0, 9.0: 1 / 3, 8.0: 2 / 3, 7.0: 1.0, 6.0: 1.0}
    for price, weight in expected.items():
        view, state = _view(closes, highs, lows, {"000001": price}, codes)
        assert float(strategy.generate_signals(view, state)["000001"]) == pytest.approx(weight)


def test_g3_multi_code_scaled_to_one():
    codes = ["A", "B"]
    closes = _flat(15, 2, 10.0)
    highs = _flat(15, 2, 10.5)
    lows = _flat(15, 2, 9.5)
    strategy = GridATRStrategy(GridATRConfig(base_price={"A": 10.0, "B": 10.0}))
    view, state = _view(closes, highs, lows, {"A": 9.0, "B": 6.0}, codes)
    weights = strategy.generate_signals(view, state)
    assert float(weights["A"]) == pytest.approx(0.25)
    assert float(weights["B"]) == pytest.approx(0.75)


def test_g4_empty_base_price_raises():
    with pytest.raises(StrategyConfigError):
        GridATRConfig(base_price={})


def test_g5_missing_base_key_zero_weight():
    codes = ["A", "B"]
    closes = _flat(15, 2, 10.0)
    highs = _flat(15, 2, 10.5)
    lows = _flat(15, 2, 9.5)
    strategy = GridATRStrategy(GridATRConfig(base_price={"A": 10.0}))
    view, state = _view(closes, highs, lows, {"A": 9.0, "B": 6.0}, codes)
    weights = strategy.generate_signals(view, state)
    assert float(weights["B"]) == 0.0
    assert float(weights["A"]) == pytest.approx(1 / 3)


def test_g6_nan_atr_zero_weight():
    codes = ["000001"]
    closes = _flat(15, 1, 10.0)
    highs = _flat(15, 1, np.nan)
    lows = _flat(15, 1, np.nan)
    strategy = GridATRStrategy(GridATRConfig(base_price={"000001": 10.0}))
    view, state = _view(closes, highs, lows, {"000001": 9.0}, codes)
    weights = strategy.generate_signals(view, state)
    # grid 保留显式 0 权重（G5 同语义）；ATR 为 NaN → 该标的 0 且总和为 0
    assert float(weights.get("000001", 0.0)) == 0.0
    assert float(weights.sum()) == 0.0


def test_g7_pure_function():
    codes = ["A", "B"]
    closes = _flat(15, 2, 10.0)
    highs = _flat(15, 2, 10.5)
    lows = _flat(15, 2, 9.5)
    strategy = GridATRStrategy(GridATRConfig(base_price={"A": 10.0, "B": 10.0}))
    view, state = _view(closes, highs, lows, {"A": 9.0, "B": 6.0}, codes)
    pd.testing.assert_series_equal(
        strategy.generate_signals(view, state),
        strategy.generate_signals(view, state),
    )
