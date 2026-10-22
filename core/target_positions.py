"""目标持仓计算 - 再平衡的纯计算层

将优化器输出的目标权重与当前持仓求并集，推导每只标的的目标数量。
被调出组合的标的会以 ``target_quantity=0`` / ``is_exit=True`` 的形式出现，
使引擎能够为其生成清仓订单——修复"调出持仓永不卖出"的 CRITICAL 缺陷。

本模块只做纯计算：不建订单、不读配置、不判断交易可行性、不做 I/O。
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Mapping, Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TargetPosition:
    """单只标的的目标持仓（再平衡输入）

    Attributes:
        stock: 股票代码
        current_quantity: 调仓前持仓（股）
        target_quantity: 调仓后目标持仓（股），0 表示退出
        price: 调仓日复权收盘价；退出标的可为 None
        weight: 目标权重；退出标的为 0.0
        is_exit: True 表示不在目标权重中、需要清仓
    """

    stock: str
    current_quantity: int
    target_quantity: int
    price: Optional[float]
    weight: float
    is_exit: bool


def build_target_positions(
    target_weights: pd.Series,
    current_positions: Mapping[str, int],
    prices: pd.Series,
    total_value: float,
    *,
    round_lot: bool = True,
    lot_size: int = 100,
    value_buffer: float = 0.985,
) -> dict[str, TargetPosition]:
    """由目标权重、当前持仓与价格推导目标持仓（含调出标的的清仓项）。

    Args:
        target_weights: 优化器输出，索引为股票代码，值为目标权重（非负）。
            允许权重和小于 1（余额留作现金）。
        current_positions: 当前持仓 {股票: 股数}，仅应包含股数 > 0 的标的。
        prices: 调仓日复权收盘价，索引为股票代码；缺失或非正视为不可定价。
        total_value: 组合总市值（现金 + 持仓市值），必须为有限正数。
        round_lot: 是否按整手取整。
        lot_size: 每手股数（A股为 100）。
        value_buffer: 买入现金缓冲系数，沿用引擎既有的 0.985 语义。

    Returns:
        {股票: TargetPosition}，覆盖 target_weights 与 current_positions 的并集；
        仅当调仓前后均为 0 股（无持仓且无法定价或未入选）时省略该股票。

    Raises:
        ValueError: total_value 非有限正数；或 target_weights 含负权重。

    Note:
        退出标的（is_exit=True）不要求价格有效：清仓数量由 ``current_quantity``
        决定，成交价在次日开盘获取。在场标的若无法定价则维持现状、不产生订单。
    """
    if not math.isfinite(total_value) or total_value <= 0:
        raise ValueError(f"total_value 必须为有限正数，当前为 {total_value!r}")

    if len(target_weights) > 0 and bool((target_weights < 0).any()):
        raise ValueError("目标权重不允许为负（A股不做空）")

    weight_map: dict[str, float] = {
        str(stock): float(weight) for stock, weight in target_weights.items()
    }
    holding_map: dict[str, int] = {
        str(stock): int(quantity) for stock, quantity in current_positions.items()
    }

    total_weight = sum(weight_map.values())
    if total_weight > 1.0 + 1e-6:
        logger.warning("目标权重之和 %.4f 超过 1.0，将产生隐性杠杆", total_weight)

    targets: dict[str, TargetPosition] = {}

    for stock in sorted(set(weight_map) | set(holding_map)):
        current = holding_map.get(stock, 0)
        weight = weight_map.get(stock, 0.0)
        price = _resolve_price(prices, stock)

        # 情形 4/8：未入选或权重为 0 → 有持仓则清仓，空仓则不输出
        if weight <= 0.0:
            if current > 0:
                targets[stock] = TargetPosition(
                    stock=stock,
                    current_quantity=current,
                    target_quantity=0,
                    price=price,
                    weight=0.0,
                    is_exit=True,
                )
            continue

        # 情形 6/9：无法定价
        if price is None:
            if current > 0:
                logger.warning("%s 缺少有效价格，维持现有持仓 %d 股", stock, current)
                targets[stock] = TargetPosition(
                    stock=stock,
                    current_quantity=current,
                    target_quantity=current,
                    price=None,
                    weight=weight,
                    is_exit=False,
                )
            else:
                logger.debug("%s 缺少有效价格且当前空仓，跳过建仓", stock)
            continue

        # 情形 1/2/3/5：按权重与缓冲系数计算目标数量
        raw_quantity = weight * total_value * value_buffer / price
        if round_lot:
            target_quantity = int(math.floor(raw_quantity / lot_size) * lot_size)
        else:
            target_quantity = int(raw_quantity)

        targets[stock] = TargetPosition(
            stock=stock,
            current_quantity=current,
            target_quantity=target_quantity,
            price=price,
            weight=weight,
            is_exit=target_quantity == 0 and current > 0,
        )

    return targets


def compute_portfolio_value(
    cash: float,
    current_positions: Mapping[str, int],
    prices: pd.Series,
    market_values: Optional[Mapping[str, float]] = None,
) -> float:
    """以最新价格重算组合总价值（现金 + Σ 数量 × 价格）。

    ``tracker.get_total_value()`` 在"开盘成交后、日终盯市前"不可信
    （``Position.execute_trade`` 不维护 ``market_value``），因此调仓估值
    一律用价格重算，``market_values`` 仅作为价格缺失时的兜底。

    Args:
        cash: 现金余额。
        current_positions: 当前持仓 {股票: 股数}。
        prices: 最新价格；缺失或非正时回退到 market_values。
        market_values: 可选，tracker 记录的市值（仅在价格缺失时使用）。

    Returns:
        组合总价值；无有效估值信息的标的按 0 计入。
    """
    total = float(cash)

    for stock_key, quantity in current_positions.items():
        stock = str(stock_key)
        qty = int(quantity)
        if qty <= 0:
            continue

        price = _resolve_price(prices, stock)
        if price is not None:
            total += qty * price
            continue

        fallback = None if market_values is None else market_values.get(stock)
        if fallback is not None and math.isfinite(float(fallback)) and float(fallback) > 0:
            total += float(fallback)
        else:
            logger.debug("%s 既无有效价格也无市值，估值时跳过", stock)

    return total


def _resolve_price(prices: pd.Series, stock: str) -> Optional[float]:
    """取出有效价格；缺失、NaN 或非正数返回 None"""
    raw = prices.get(stock)
    if raw is None or pd.isna(raw):
        return None
    value = float(raw)
    return value if value > 0 else None
