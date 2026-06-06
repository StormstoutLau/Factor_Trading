"""
订单执行策略实现

包含 TWAP、VWAP、ICEBERG 等策略，
以及市场冲击模型。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Order:
    """订单信息"""

    symbol: str
    side: str  # 'BUY' or 'SELL'
    total_qty: int
    remaining_qty: int
    filled_qty: int = 0
    avg_price: float = 0.0
    fill_timestamps: list = None

    def __post_init__(self):
        if self.fill_timestamps is None:
            self.fill_timestamps = []


@dataclass
class TradeExecution:
    """交易执行结果"""

    timestamp: Any
    symbol: str
    side: str
    qty: int
    price: float
    amount: float
    impact: float  # 市场冲击成本


class BaseOrderStrategy(ABC):
    """订单策略基类"""

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.orders: dict[str, Order] = {}

    @abstractmethod
    def execute(
        self,
        symbol: str,
        side: str,
        qty: int,
        timestamp: Any,
        market_data: dict,
    ) -> list[TradeExecution]:
        """执行订单

        Args:
            symbol: 标的代码
            side: 方向 'BUY' or 'SELL'
            qty: 数量
            timestamp: 时间戳
            market_data: 市场数据

        Returns:
            成交列表
        """
        pass


class MarketOrderStrategy(BaseOrderStrategy):
    """市价单策略 - 一次全部成交"""

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self.impact_model = MarketImpactModel(config)

    def execute(
        self,
        symbol: str,
        side: str,
        qty: int,
        timestamp: Any,
        market_data: dict,
    ) -> list[TradeExecution]:
        price = market_data.get("price", market_data.get("close", 0.0))
        impact = self.impact_model.calculate_impact(qty, market_data)

        if side == "BUY":
            price *= 1 + impact
        else:
            price *= 1 - impact

        amount = qty * price
        return [
            TradeExecution(
                timestamp=timestamp,
                symbol=symbol,
                side=side,
                qty=qty,
                price=price,
                amount=amount,
                impact=impact * amount,
            )
        ]


class TWAPStrategy(BaseOrderStrategy):
    """时间加权平均价格策略 (TWAP)

    在固定时间间隔内均分订单。
    """

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self.intervals = self.config.get("intervals", 10)
        self.current_interval = 0
        self.impact_model = MarketImpactModel(config)

    def execute(
        self,
        symbol: str,
        side: str,
        qty: int,
        timestamp: Any,
        market_data: dict,
    ) -> list[TradeExecution]:
        order_key = f"{symbol}_{side}"

        if order_key not in self.orders:
            self.orders[order_key] = Order(
                symbol=symbol, side=side, total_qty=qty, remaining_qty=qty
            )
            self.current_interval = 0

        order = self.orders[order_key]
        if order.remaining_qty <= 0:
            return []

        qty_per_interval = order.total_qty // self.intervals
        qty_this_time = min(qty_per_interval, order.remaining_qty)
        if qty_this_time <= 0:
            return []

        price = market_data.get("price", market_data.get("close", 0.0))
        impact = self.impact_model.calculate_impact(qty_this_time, market_data)

        if side == "BUY":
            trade_price = price * (1 + impact)
        else:
            trade_price = price * (1 - impact)

        order.filled_qty += qty_this_time
        order.remaining_qty -= qty_this_time
        order.avg_price = (order.avg_price * (order.filled_qty - qty_this_time) + trade_price * qty_this_time) / order.filled_qty
        order.fill_timestamps.append(timestamp)

        amount = qty_this_time * trade_price
        logger.debug(
            f"TWAP执行: {symbol} {side} {qty_this_time}/{order.total_qty} @ {trade_price:.2f}"
        )

        return [
            TradeExecution(
                timestamp=timestamp,
                symbol=symbol,
                side=side,
                qty=qty_this_time,
                price=trade_price,
                amount=amount,
                impact=impact * amount,
            )
        ]


class VWAPStrategy(BaseOrderStrategy):
    """成交量加权平均价格策略 (VWAP)

    根据成交量分布动态分配订单。
    """

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self.volume_profile = self.config.get(
            "volume_profile",
            np.array([1.0 / 10] * 10),  # 默认均匀分布
        )
        self.current_idx = 0
        self.impact_model = MarketImpactModel(config)

    def execute(
        self,
        symbol: str,
        side: str,
        qty: int,
        timestamp: Any,
        market_data: dict,
    ) -> list[TradeExecution]:
        order_key = f"{symbol}_{side}"

        if order_key not in self.orders:
            self.orders[order_key] = Order(
                symbol=symbol, side=side, total_qty=qty, remaining_qty=qty
            )
            self.current_idx = 0

        order = self.orders[order_key]
        if order.remaining_qty <= 0:
            return []

        # 根据成交量分布计算当前时段下单量
        weight = self.volume_profile[self.current_idx % len(self.volume_profile)]
        qty_this_time = int(order.total_qty * weight)
        qty_this_time = min(qty_this_time, order.remaining_qty)
        if qty_this_time <= 0:
            qty_this_time = order.remaining_qty

        # 如果有实时成交量，结合起来调整
        if "volume" in market_data:
            vol = market_data["volume"]
            # 可以结合实时成交量进一步调整权重
            pass

        price = market_data.get("price", market_data.get("close", 0.0))
        impact = self.impact_model.calculate_impact(qty_this_time, market_data)

        if side == "BUY":
            trade_price = price * (1 + impact)
        else:
            trade_price = price * (1 - impact)

        order.filled_qty += qty_this_time
        order.remaining_qty -= qty_this_time
        order.avg_price = (order.avg_price * (order.filled_qty - qty_this_time) + trade_price * qty_this_time) / order.filled_qty
        order.fill_timestamps.append(timestamp)
        self.current_idx += 1

        amount = qty_this_time * trade_price
        logger.debug(
            f"VWAP执行: {symbol} {side} {qty_this_time}/{order.total_qty} @ {trade_price:.2f}"
        )

        return [
            TradeExecution(
                timestamp=timestamp,
                symbol=symbol,
                side=side,
                qty=qty_this_time,
                price=trade_price,
                amount=amount,
                impact=impact * amount,
            )
        ]


class IcebergStrategy(BaseOrderStrategy):
    """冰山策略 (ICEBERG)

    只显示一小部分订单，隐藏真实规模。
    """

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self.visible_size = self.config.get("visible_size", 1000)
        self.iceberg_ratio = self.config.get("iceberg_ratio", 0.1)
        self.impact_model = MarketImpactModel(config)

    def execute(
        self,
        symbol: str,
        side: str,
        qty: int,
        timestamp: Any,
        market_data: dict,
    ) -> list[TradeExecution]:
        order_key = f"{symbol}_{side}"

        if order_key not in self.orders:
            self.orders[order_key] = Order(
                symbol=symbol, side=side, total_qty=qty, remaining_qty=qty
            )

        order = self.orders[order_key]
        if order.remaining_qty <= 0:
            return []

        # 冰山单每次只成交可见部分
        visible_qty = min(self.visible_size, int(order.total_qty * self.iceberg_ratio))
        qty_this_time = min(visible_qty, order.remaining_qty)
        if qty_this_time <= 0:
            return []

        price = market_data.get("price", market_data.get("close", 0.0))
        impact = self.impact_model.calculate_impact(qty_this_time, market_data)

        if side == "BUY":
            trade_price = price * (1 + impact)
        else:
            trade_price = price * (1 - impact)

        order.filled_qty += qty_this_time
        order.remaining_qty -= qty_this_time
        order.avg_price = (order.avg_price * (order.filled_qty - qty_this_time) + trade_price * qty_this_time) / order.filled_qty
        order.fill_timestamps.append(timestamp)

        amount = qty_this_time * trade_price
        logger.debug(
            f"Iceberg执行: {symbol} {side} {qty_this_time}/{order.total_qty} @ {trade_price:.2f}"
        )

        return [
            TradeExecution(
                timestamp=timestamp,
                symbol=symbol,
                side=side,
                qty=qty_this_time,
                price=trade_price,
                amount=amount,
                impact=impact * amount,
            )
        ]


class MarketImpactModel:
    """市场冲击模型

    基于 Almgren-Chriss 或类似框架，
    计算订单对市场价格的冲击。
    """

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.temporary_impact_coef = self.config.get("temporary_coef", 0.001)
        self.permanent_impact_coef = self.config.get("permanent_coef", 0.0001)
        self.market_volatility = self.config.get("volatility", 0.02)

    def calculate_impact(self, qty: int, market_data: dict) -> float:
        """计算市场冲击

        Args:
            qty: 下单数量
            market_data: 市场数据，包含 volume/price 等

        Returns:
            冲击比例 (frac)
        """
        if qty <= 0:
            return 0.0

        volume = market_data.get("volume", 1000000)
        normalized_qty = qty / volume

        # 临时冲击和永久冲击结合
        temporary_impact = self.temporary_impact_coef * np.sqrt(normalized_qty)
        permanent_impact = self.permanent_impact_coef * normalized_qty

        total_impact = temporary_impact + permanent_impact
        return min(total_impact, 0.1)  # 上限 10%

