"""P-011 B2：V2 组件差分（目标持仓 / 成本 / 成交记录字段）。

对照对象为 ``tests/_reference_impl.py`` 的独立公式实现（DESIGN §4.3-§4.4）。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from _reference_impl import ref_build_target_positions, ref_calculate_cost
from core.config import CostConfig
from core.execution import ExecutionSimulator
from core.pending import OrderSide
from core.target_positions import build_target_positions

_COST = CostConfig(
    commission_rate=0.0003,
    commission_min=5.0,
    stamp_tax_rate=0.001,
    slippage_pct=0.001,
)


def _simulator() -> ExecutionSimulator:
    return ExecutionSimulator(_COST)


def test_target_positions_matches_reference():
    """含清仓、不可定价、零权重四类分支的字段级一致。"""
    prices = pd.Series({"A": 10.0, "B": 33.0, "C": np.nan, "D": 0.0})
    weights = pd.Series({"A": 0.5, "B": 0.3, "C": 0.2})
    current = {"B": 100, "D": 10, "E": 20}
    total_value = 1_000_000.0

    actual = build_target_positions(weights, current, prices, total_value)
    expected = ref_build_target_positions(weights, current, prices, total_value)

    assert set(actual) == set(expected), "并集覆盖范围不一致"
    assert "C" not in actual, "空仓且不可定价的标的不应输出"
    for stock, target in actual.items():
        current_qty, target_qty, price, weight, is_exit = expected[stock]
        assert target.current_quantity == current_qty, stock
        assert target.target_quantity == target_qty, stock
        assert target.price == price, stock
        assert target.weight == weight, stock
        assert target.is_exit is is_exit, stock

    assert actual["A"].target_quantity == 49_200
    assert actual["B"].target_quantity == 8_900
    assert actual["D"].is_exit and actual["D"].target_quantity == 0
    assert actual["E"].is_exit and actual["E"].price is None


@pytest.mark.parametrize(
    "price, round_lot, expected_quantity",
    [
        (10.0, True, 49_200),  # 49250 → 整手向下
        (10.0, False, 49_250),
        (9.85, True, 50_000),  # 0.5*1e6*0.985/9.85 = 50000 恰好整除
        (9.85, False, 50_000),
    ],
)
def test_target_positions_round_lot_boundary(price, round_lot, expected_quantity):
    """整手边界：整除不截断、不整除按 lot_size 向下取整。"""
    weights = pd.Series({"A": 0.5})
    prices = pd.Series({"A": price})
    actual = build_target_positions(weights, {"A": 0}, prices, 1_000_000.0, round_lot=round_lot)
    expected = ref_build_target_positions(
        weights, {"A": 0}, prices, 1_000_000.0, round_lot=round_lot
    )
    assert actual["A"].target_quantity == expected_quantity
    assert actual["A"].target_quantity == expected["A"][1]


def test_calculate_cost_commision_min_binding():
    """佣金下限：小额按 ``commission_min``；大额按费率。"""
    simulator = _simulator()
    small = 1_000.0  # 1000*0.0003 = 0.3 < 5
    large = 100_000.0  # 30 > 5

    small_cost = simulator._calculate_cost(small, OrderSide.BUY)
    large_cost = simulator._calculate_cost(large, OrderSide.BUY)

    assert small_cost == pytest.approx(
        ref_calculate_cost(
            small,
            True,
            commission_rate=0.0003,
            commission_min=5.0,
            stamp_tax_rate=0.001,
            slippage_pct=0.001,
        )
    )
    assert small_cost == pytest.approx(5.0 + small * 0.001)
    assert large_cost == pytest.approx(30.0 + large * 0.001)
    assert large_cost - small_cost == pytest.approx(30.0 - 5.0 + (large - small) * 0.001)


def test_calculate_cost_stamp_only_on_sell():
    """印花税仅卖出单边（股票）。"""
    simulator = _simulator()
    amount = 100_000.0
    buy = simulator._calculate_cost(amount, OrderSide.BUY)
    sell = simulator._calculate_cost(amount, OrderSide.SELL)

    assert sell - buy == pytest.approx(amount * 0.001)
    assert buy == pytest.approx(30.0 + amount * 0.001)
    assert sell == pytest.approx(30.0 + amount * 0.001 + amount * 0.001)


def test_execute_order_trade_fields():
    """成交记录：``amount == qty*price``、``cost == 参考``、``net_amount`` 符号正确。"""
    simulator = _simulator()
    date = pd.Timestamp("2024-01-03")
    quantity = 100

    ok, buy = simulator.execute_order("000001", OrderSide.BUY, quantity, date, 10.0)
    assert ok and buy is not None
    assert buy.amount == pytest.approx(quantity * 10.0)
    assert buy.cost == pytest.approx(
        ref_calculate_cost(
            1_000.0,
            True,
            commission_rate=0.0003,
            commission_min=5.0,
            stamp_tax_rate=0.001,
            slippage_pct=0.001,
        )
    )
    assert buy.net_amount == pytest.approx(buy.amount + buy.cost)
    assert buy.net_amount > buy.amount

    ok, sell = simulator.execute_order("000001", OrderSide.SELL, quantity, date, 10.0)
    assert ok and sell is not None
    assert sell.net_amount == pytest.approx(sell.amount - sell.cost)
    assert sell.net_amount < sell.amount
    assert simulator.trade_log.get_trades() == [buy, sell]
