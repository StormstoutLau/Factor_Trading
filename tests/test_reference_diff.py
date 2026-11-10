"""P-011 B1/B2：参考实现差分（V3 内核 / V2 目标持仓与成本 / NAV 递推）。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core.config import CostConfig
from core.engine_v3_vector import _rebalance_kernel
from core.execution import ExecutionSimulator
from core.pending import OrderSide
from core.target_positions import build_target_positions
from _reference_impl import (
    ref_build_target_positions,
    ref_calculate_cost,
    ref_rebalance_kernel,
    ref_v3_nav,
)


def _kernel_cases():
    rng = np.random.default_rng(20261110)
    cases = []
    for n in (1, 2, 5, 20, 40):
        for top_n in sorted({1, max(1, n // 2), n}):
            for variant in (0, 1):
                signal = rng.normal(0.0, 1.0, n)
                if variant == 0:
                    signal[::7] = np.nan
                else:
                    signal = np.abs(signal)
                prices = rng.uniform(5.0, 50.0, n)
                prices[::11] = 0.0
                buyable = rng.random(n) > 0.2
                sellable = rng.random(n) > 0.2
                positions = rng.uniform(0.0, 100.0, n)
                if variant == 0:
                    positions[::5] = 0.0
                cases.append(
                    {
                        "positions": positions,
                        "cash": 1_000_000.0,
                        "last_pv": 1_000_000.0,
                        "signal": signal,
                        "prices": prices,
                        "buyable": buyable,
                        "sellable": sellable,
                        "top_n": top_n,
                        "cost_rate": 0.001,
                    }
                )
    cases.append(
        {
            "positions": np.array([1.0]),
            "cash": 500.0,
            "last_pv": 500.0,
            "signal": np.array([np.nan]),
            "prices": np.array([10.0]),
            "buyable": np.array([True]),
            "sellable": np.array([True]),
            "top_n": 1,
            "cost_rate": 0.0,
        }
    )
    cases.append(
        {
            "positions": np.array([0.0]),
            "cash": 500.0,
            "last_pv": 500.0,
            "signal": np.array([1.0]),
            "prices": np.array([0.0]),
            "buyable": np.array([True]),
            "sellable": np.array([True]),
            "top_n": 1,
            "cost_rate": 0.0,
        }
    )
    return cases


def _run_kernel(case, kernel):
    return kernel(
        case["positions"].copy(),
        case["cash"],
        case["last_pv"],
        case["signal"],
        case["prices"],
        case["buyable"],
        case["sellable"],
        case["top_n"],
        case["cost_rate"],
    )


def test_rebalance_kernel_matches_reference():
    for case in _kernel_cases():
        positions, cash = _run_kernel(case, _rebalance_kernel)
        ref_positions, ref_cash = _run_kernel(case, ref_rebalance_kernel)
        assert np.array_equal(positions, ref_positions), f"positions mismatch: {case}"
        assert cash == ref_cash, f"cash mismatch: {cash} != {ref_cash}"


def test_rebalance_kernel_python_fallback_matches():
    """``py_func`` 回退与参考公式数值等价（非比特一致，见 DESIGN §4.2 注）。

    回退路径在 CPython 下执行 ``np.sum``（NumPy pairwise 归约），而 JIT 路径
    为顺序累加，末位可差 1 ulp；故此处按 ``rtol=1e-12`` 判定，持仓数组仍要求
    比特一致。
    """
    fallback = getattr(_rebalance_kernel, "py_func", _rebalance_kernel)
    for case in _kernel_cases():
        positions, cash = _run_kernel(case, fallback)
        ref_positions, ref_cash = _run_kernel(case, ref_rebalance_kernel)
        assert np.array_equal(positions, ref_positions)
        assert np.isclose(cash, ref_cash, rtol=1e-12, atol=1e-9), f"{cash} != {ref_cash}"


def test_rebalance_kernel_all_nan_signal():
    case = {
        "positions": np.array([1.0, 2.0]),
        "cash": 500.0,
        "last_pv": 500.0,
        "signal": np.array([np.nan, np.nan]),
        "prices": np.array([10.0, 20.0]),
        "buyable": np.array([True, True]),
        "sellable": np.array([True, True]),
        "top_n": 2,
        "cost_rate": 0.0,
    }
    positions, cash = _run_kernel(case, _rebalance_kernel)
    ref_positions, ref_cash = _run_kernel(case, ref_rebalance_kernel)
    assert np.array_equal(positions, np.array([1.0, 2.0]))
    assert cash == 500.0
    assert np.array_equal(positions, ref_positions) and cash == ref_cash


def test_rebalance_kernel_zero_price():
    case = {
        "positions": np.array([0.0]),
        "cash": 500.0,
        "last_pv": 500.0,
        "signal": np.array([1.0]),
        "prices": np.array([0.0]),
        "buyable": np.array([True]),
        "sellable": np.array([True]),
        "top_n": 1,
        "cost_rate": 0.0,
    }
    positions, cash = _run_kernel(case, _rebalance_kernel)
    assert positions[0] == 0.0
    assert cash == 500.0
    ref_positions, ref_cash = _run_kernel(case, ref_rebalance_kernel)
    assert np.array_equal(positions, ref_positions) and cash == ref_cash


def test_target_positions_matches_reference():
    prices = pd.Series({"A": 10.0, "B": 20.0, "C": 0.0, "D": np.nan})
    weights = pd.Series({"A": 0.5, "B": 0.3, "E": 0.0})
    current = {"B": 100, "C": 50, "D": 10, "F": 20}
    for round_lot in (True, False):
        for total_value in (1_000_000.0, 987_654.321):
            actual = build_target_positions(
                weights, current, prices, total_value, round_lot=round_lot
            )
            expected = ref_build_target_positions(
                weights, current, prices, total_value, round_lot=round_lot
            )
            assert set(actual) == set(expected)
            for stock, target in actual.items():
                exp = expected[stock]
                assert (
                    target.current_quantity,
                    target.target_quantity,
                    target.price,
                    target.weight,
                    target.is_exit,
                ) == exp, f"{stock} mismatch: {target} != {exp}"


def test_cost_matches_reference():
    cfg = CostConfig(
        commission_rate=0.0003,
        commission_min=5.0,
        stamp_tax_rate=0.001,
        slippage_pct=0.001,
    )
    sim = ExecutionSimulator(cfg)
    cases = [
        (1_000.0, OrderSide.BUY),
        (100_000.0, OrderSide.BUY),
        (100_000.0, OrderSide.SELL),
        (2_000_000.0, OrderSide.SELL),
    ]
    for amount, side in cases:
        actual = sim._calculate_cost(amount, side)
        expected = ref_calculate_cost(
            amount,
            side == OrderSide.BUY,
            commission_rate=cfg.commission_rate,
            commission_min=cfg.commission_min,
            stamp_tax_rate=cfg.stamp_tax_rate,
            slippage_pct=cfg.slippage_pct,
        )
        assert actual == expected, f"{amount} {side}: {actual} != {expected}"


def test_v3_nav_matches_reference():
    cash = 123_456.789
    positions = np.array([100.0, 0.0, 250.5])
    prices = np.array([10.5, 20.0, 3.25])
    expected = ref_v3_nav(cash, positions, prices)
    assert cash + float(np.sum(positions * prices)) == expected


def test_determinism_metamorphic():
    for case in _kernel_cases():
        first = _run_kernel(case, _rebalance_kernel)
        second = _run_kernel(case, _rebalance_kernel)
        assert np.array_equal(first[0], second[0]) and first[1] == second[1]


def test_price_scaling_metamorphic():
    rng = np.random.default_rng(7)
    n = 10
    case = {
        "positions": np.zeros(n),
        "cash": 1_000_000.0,
        "last_pv": 1_000_000.0,
        "signal": rng.normal(size=n),
        "prices": rng.uniform(5.0, 50.0, n),
        "buyable": np.ones(n, dtype=bool),
        "sellable": np.ones(n, dtype=bool),
        "top_n": 5,
        "cost_rate": 0.0,
    }
    base_positions, base_cash = _run_kernel(case, _rebalance_kernel)
    scaled = dict(case)
    scaled["prices"] = case["prices"] * 2.0
    scaled_positions, scaled_cash = _run_kernel(scaled, _rebalance_kernel)
    assert np.allclose(scaled_positions, base_positions / 2.0, rtol=1e-12, atol=1e-12)
    assert abs(scaled_cash - base_cash) <= 1e-9
    base_nav = ref_v3_nav(base_cash, base_positions, case["prices"])
    scaled_nav = ref_v3_nav(scaled_cash, scaled_positions, scaled["prices"])
    assert abs(scaled_nav - base_nav) <= 1e-6
