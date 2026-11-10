"""P-011 参考实现（DESIGN §4；按公式独立编写，不复制被测代码）。

本文件不以 ``test_`` 开头，不会被 pytest 收集。
"""

from __future__ import annotations

import math
from typing import Mapping, Optional

import numpy as np
import pandas as pd


def _seq_sum(values: np.ndarray) -> float:
    """按索引顺序累加（对齐 ``@njit`` 下 ``np.sum`` 的归约顺序）。"""
    total = 0.0
    for i in range(len(values)):
        total += float(values[i])
    return total


def ref_rebalance_kernel(
    positions: np.ndarray,
    cash: float,
    last_portfolio_value: float,
    signal: np.ndarray,
    prices: np.ndarray,
    buyable_mask: np.ndarray,
    sellable_mask: np.ndarray,
    top_n: int,
    cost_rate: float,
) -> tuple[np.ndarray, float]:
    """V3 再平衡内核的参考实现（DESIGN §4.2 语义）。

    归约顺序与内核保持一致（成本逐元素累加、现金净额按索引顺序累加），
    以保证浮点结果比特一致：``@njit`` 下 ``np.sum`` 为顺序累加，
    而 NumPy 的 ``np.sum`` 采用 pairwise 归约（实测 200 组中约半数末位不同），
    故此处显式顺序累加。
    """
    n_stocks = len(signal)
    signal_clean = np.nan_to_num(signal, nan=0.0)

    if n_stocks <= top_n:
        selected = signal_clean > 0
    else:
        abs_signal = np.abs(signal_clean)
        threshold = np.partition(abs_signal, -top_n)[-top_n]
        selected = abs_signal >= threshold

    selected = selected & buyable_mask
    n_selected = np.sum(selected)
    if n_selected == 0:
        return positions.copy(), float(cash)

    target_value_per_stock = last_portfolio_value * (1.0 / n_selected)
    target = np.zeros(n_stocks, dtype=np.float64)
    for i in range(n_stocks):
        if selected[i] and prices[i] > 0:
            target[i] = target_value_per_stock / prices[i]

    for i in range(n_stocks):
        if (not sellable_mask[i]) and positions[i] > 0:
            target[i] = 0.0

    trade_positions = target - positions
    trade_costs = 0.0
    for i in range(n_stocks):
        trade_costs += abs(trade_positions[i]) * prices[i] * cost_rate

    new_cash = cash - _seq_sum(trade_positions * prices) - trade_costs
    return target, float(new_cash)


def ref_build_target_positions(
    target_weights: pd.Series,
    current_positions: Mapping[str, int],
    prices: pd.Series,
    total_value: float,
    *,
    round_lot: bool = True,
    lot_size: int = 100,
    value_buffer: float = 0.985,
) -> dict[str, tuple[int, int, Optional[float], float, bool]]:
    """V2 目标持仓的参考实现（DESIGN §4.5 / target_positions 文档语义）。

    Returns:
        ``{stock: (current_quantity, target_quantity, price, weight, is_exit)}``
    """
    if not math.isfinite(total_value) or total_value <= 0:
        raise ValueError(f"total_value 必须为有限正数，当前为 {total_value!r}")
    if len(target_weights) > 0 and bool((target_weights < 0).any()):
        raise ValueError("目标权重不允许为负（A股不做空）")

    weight_map = {str(stock): float(weight) for stock, weight in target_weights.items()}
    holding_map = {str(stock): int(quantity) for stock, quantity in current_positions.items()}

    out: dict[str, tuple[int, int, Optional[float], float, bool]] = {}
    for stock in sorted(set(weight_map) | set(holding_map)):
        current = holding_map.get(stock, 0)
        weight = weight_map.get(stock, 0.0)

        raw_price = prices.get(stock)
        if raw_price is None or pd.isna(raw_price):
            price: Optional[float] = None
        else:
            price = float(raw_price) if float(raw_price) > 0 else None

        if weight <= 0.0:
            if current > 0:
                out[stock] = (current, 0, price, 0.0, True)
            continue

        if price is None:
            if current > 0:
                out[stock] = (current, current, None, weight, False)
            continue

        raw_quantity = weight * total_value * value_buffer / price
        if round_lot:
            target_quantity = int(math.floor(raw_quantity / lot_size) * lot_size)
        else:
            target_quantity = int(raw_quantity)
        out[stock] = (current, target_quantity, price, weight, target_quantity == 0 and current > 0)
    return out


def ref_calculate_cost(
    amount: float,
    is_buy: bool,
    *,
    commission_rate: float,
    commission_min: float,
    stamp_tax_rate: float,
    slippage_pct: float,
    exchange_fee: float = 0.0,
) -> float:
    """V2 成本函数的参考实现（加总顺序与被测实现一致）。"""
    cost = 0.0
    commission = amount * commission_rate
    commission = max(commission, commission_min)
    cost += commission
    if exchange_fee > 0:
        cost += amount * exchange_fee
    if (not is_buy) and stamp_tax_rate > 0:
        cost += amount * stamp_tax_rate
    cost += amount * slippage_pct
    return cost


def ref_v3_nav(cash: float, positions: np.ndarray, prices: np.ndarray) -> float:
    """V3 组合价值参考：``cash + Σ positions * prices``。"""
    return float(cash) + _seq_sum(positions * prices)
