"""P-051b R 组：mean_reversion z-score 闭式。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from _p051b_common import make_view


def _window(k: int) -> np.ndarray:
    """20 行：前 20−k 行 10.0（H），末 k 行 9.0（L）→ latest=L。"""
    values = np.concatenate([np.full(20 - k, 10.0), np.full(k, 9.0)])
    return values.reshape(-1, 1)


def _signals(values: np.ndarray, *, positions: dict[str, float] | None = None):
    from strategies.mean_reversion import MeanReversionConfig, MeanReversionStrategy

    strategy = MeanReversionStrategy(MeanReversionConfig())
    view, state = make_view(closes=values, positions=positions, codes=["000001"])
    return strategy.generate_signals(view, state)


def test_r1_k3_z_below_entry_selects():
    # z = −2.3202 ≤ −2.0
    assert _signals(_window(3)).to_dict() == {"000001": 1.0}


def test_r2_k4_z_above_entry_rejects():
    # z = −1.9494 > −2.0
    assert _signals(_window(4)).empty


def test_r3_single_spike_invariant():
    # z = −(n−1)/√n = −4.24853
    assert _signals(_window(1)).to_dict() == {"000001": 1.0}


def test_r4_holding_exits_when_z_reverts():
    # k=16 → z = −0.4873 ≥ −0.5 → 出场
    assert _signals(_window(16), positions={"000001": 0.5}).empty


def test_r5_holding_keeps_while_z_stays_low():
    # k=15 → z = −0.5627 < −0.5 → 保持
    assert _signals(_window(15), positions={"000001": 0.5}).to_dict() == {"000001": 1.0}


def test_r6_flat_window_zero_z():
    flat = np.full((20, 1), 10.0)
    assert _signals(flat).empty
    assert _signals(flat, positions={"000001": 0.5}).empty


def test_r7_pure_function():
    from strategies.mean_reversion import MeanReversionConfig, MeanReversionStrategy

    strategy = MeanReversionStrategy(MeanReversionConfig())
    view, state = make_view(closes=_window(3), codes=["000001"])
    first = strategy.generate_signals(view, state)
    second = strategy.generate_signals(view, state)
    pd.testing.assert_series_equal(first, second)
