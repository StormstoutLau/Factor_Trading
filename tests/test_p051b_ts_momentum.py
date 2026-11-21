"""P-051b M 组：ts_momentum 多周期投票。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from _p051b_common import CODES, make_view


def test_m1_votes_sample_from_section_18_3_1():
    from strategies.momentum import TSMomentumConfig, TSMomentumStrategy

    # 120 行窗口（W = max(lookbacks)）；锚点行索引：
    #   iloc[-120]=0 → t−120, iloc[-60]=60 → t−60, iloc[-20]=100 → t−20, iloc[-1]=119 → t−1
    closes = np.full((120, 3), 100.0)
    closes[0, :] = [100.0, 50.0, 100.0]
    closes[60, :] = [60.0, 60.0, 80.0]
    closes[100, :] = [80.0, 70.0, 70.0]
    closes[119, :] = [90.0, 80.0, 75.0]
    # A: 2 票；B: 3 票；C: 1 票 → min_votes=2 → {A, B}
    strategy = TSMomentumStrategy(TSMomentumConfig())
    view, state = make_view(closes=closes)
    weights = strategy.generate_signals(view, state)
    assert weights.round(12).to_dict() == {"000001": 0.5, "600000": 0.5}
    assert "000002" not in weights.index


def test_m2_min_votes_three_selects_only_b():
    from strategies.momentum import TSMomentumConfig, TSMomentumStrategy

    closes = np.full((120, 3), 100.0)
    closes[0, :] = [100.0, 50.0, 100.0]
    closes[60, :] = [60.0, 60.0, 80.0]
    closes[100, :] = [80.0, 70.0, 70.0]
    closes[119, :] = [90.0, 80.0, 75.0]
    strategy = TSMomentumStrategy(TSMomentumConfig(min_votes=3))
    view, state = make_view(closes=closes)
    weights = strategy.generate_signals(view, state)
    assert weights.to_dict() == {"600000": 1.0}


def test_m3_flat_prices_zero_votes_not_selected():
    from strategies.momentum import TSMomentumConfig, TSMomentumStrategy

    strategy = TSMomentumStrategy(TSMomentumConfig())
    view, state = make_view(closes=np.full((120, 3), 100.0))
    weights = strategy.generate_signals(view, state)
    assert weights.empty
    assert float(weights.dtype == "float64")


def test_m4_no_codes_returns_empty_float():
    from strategies.momentum import TSMomentumConfig, TSMomentumStrategy

    strategy = TSMomentumStrategy(TSMomentumConfig())
    view, state = make_view(closes=np.full((120, 0), 100.0), codes=[])
    weights = strategy.generate_signals(view, state)
    assert weights.empty
    assert float(weights.dtype == "float64")


def test_m5_weights_non_negative_and_bounded():
    from strategies.momentum import TSMomentumConfig, TSMomentumStrategy

    closes = np.array([np.linspace(50.0, 100.0 + 20.0 * j, 120) for j in range(3)]).T
    strategy = TSMomentumStrategy(TSMomentumConfig(min_votes=1))
    view, state = make_view(closes=closes)
    weights = strategy.generate_signals(view, state)
    assert bool((weights >= 0).all())
    assert float(weights.sum()) <= 1.0 + 1e-9
    assert set(weights.index).issubset(set(CODES))


def test_m6_pure_function_repeatable():
    from strategies.momentum import TSMomentumConfig, TSMomentumStrategy

    closes = np.full((120, 3), 100.0)
    closes[119, :] = [120.0, 90.0, 100.0]
    strategy = TSMomentumStrategy(TSMomentumConfig())
    view, state = make_view(closes=closes)
    pd.testing.assert_series_equal(
        strategy.generate_signals(view, state),
        strategy.generate_signals(view, state),
    )


def test_m7_no_lookahead_reads_history_only():
    from strategies.momentum import TSMomentumConfig, TSMomentumStrategy

    strategy = TSMomentumStrategy(TSMomentumConfig(min_votes=1))
    base = np.full((120, 1), 100.0)
    base[119, 0] = 110.0
    view_a, state = make_view(closes=base, codes=["000001"], prices={"000001": 1.0})
    weights_a = strategy.generate_signals(view_a, state)

    changed = base.copy()
    changed[119, 0] = 90.0  # 改 t−1 → 结果应变
    view_b, _ = make_view(closes=changed, codes=["000001"], prices={"000001": 999.0})
    weights_b = strategy.generate_signals(view_b, state)

    assert weights_a.to_dict() != weights_b.to_dict()
    view_c, _ = make_view(closes=base, codes=["000001"], prices={"000001": 42.0})
    assert strategy.generate_signals(view_c, state).to_dict() == weights_a.to_dict()


def test_m8_insufficient_rows_raises():
    from strategies.base import StrategyConfigError
    from strategies.momentum import TSMomentumConfig, TSMomentumStrategy

    strategy = TSMomentumStrategy(TSMomentumConfig())
    view, state = make_view(closes=np.full((119, 3), 100.0))
    with pytest.raises(StrategyConfigError):
        strategy.generate_signals(view, state)
