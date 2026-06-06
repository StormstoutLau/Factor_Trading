"""
实盘交易桥接模块 (Live Trading Bridge)

P3.1: 将回测系统产生的信号转换为实际交易订单发送给券商。

架构设计:
    - LiveTradingBridge: 抽象基类，定义统一接口
    - MockLiveBridge: 模拟实现，用于回测验证和接口测试
    - 子类化: 实现具体券商接口 (RuiqiBridge, VTKBridge, etc.)

职责划分:
    - 信号层 → [回测/实盘共享] 生成 OrderIntent
    - 桥接层 → 将 OrderIntent 转换为券商订单并发送
    - 执行层 → 券商 API 执行订单

与现有系统集成:
    - 接入 execution_policy.OrderIntent 统一订单意图
    - HOLD 意图自动过滤，不产生订单
    - 支持多资产类型 (STOCK, FUTURE, OPTION)
"""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from core.execution_policy import OrderIntent

logger = logging.getLogger(__name__)


# ============================================================================
# 数据类
# ============================================================================


@dataclass
class LiveOrder:
    """实盘订单记录"""

    order_id: str
    asset: str
    asset_type: str
    side: str  # BUY / SELL / SELL_SHORT / BUY_TO_COVER
    quantity: float
    price: float | None = None
    status: str = "pending"  # pending / filled / partial / cancelled / rejected
    filled_qty: float = 0.0
    avg_price: float | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime | None = None
    broker_order_id: str | None = None


# ============================================================================
# 抽象基类
# ============================================================================


class LiveTradingBridge(ABC):
    """实盘交易桥接抽象基类

    子类实现具体券商接口。

    Subclassing:
        需要实现:
        - place_intents()
        - cancel_orders()
        - sync_positions()
        - query_order_status()
        可选重写:
        - get_broker_info()
    """

    @abstractmethod
    def place_intents(
        self, intents: list[OrderIntent], date: pd.Timestamp
    ) -> list[str]:
        """将订单意图转换为实盘订单并发送

        Args:
            intents: OrderIntent 列表
            date: 交易日期

        Returns:
            订单ID列表 (仅非 HOLD 意图产生订单)
        """
        ...

    @abstractmethod
    def cancel_orders(self, asset: str | None = None) -> int:
        """取消订单

        Args:
            asset: 指定标的取消，None 则取消所有未成交订单

        Returns:
            取消的订单数
        """
        ...

    @abstractmethod
    def sync_positions(self) -> dict[str, dict]:
        """同步实盘持仓

        Returns:
            {asset: {quantity, avg_cost, market_value, ...}}
        """
        ...

    @abstractmethod
    def query_order_status(self, order_id: str) -> dict:
        """查询订单状态

        Args:
            order_id: 订单ID

        Returns:
            {status, filled, avg_price, ...}
        """
        ...

    def get_broker_info(self) -> dict:
        """获取券商信息 (默认实现，子类可重写)"""
        return {
            "name": self.__class__.__name__,
            "is_mock": False,
            "version": "1.0.0",
        }


# ============================================================================
# Mock 实现
# ============================================================================


class MockLiveBridge(LiveTradingBridge):
    """模拟实盘桥接实现

    不实际发送订单，仅记录订单用于验证。
    用于回测验证和接口测试。

    Example:
        bridge = MockLiveBridge()
        order_ids = bridge.place_intents(intents, date)
        orders = bridge.get_placed_orders()
        bridge.clear()
    """

    def __init__(self):
        self._orders: list[LiveOrder] = []
        self._positions: dict[str, dict] = {}
        self._order_counter = 0

    # ── 抽象方法实现 ──────────────────────────────────────────

    def place_intents(
        self, intents: list[OrderIntent], date: pd.Timestamp
    ) -> list[str]:
        order_ids: list[str] = []
        for intent in intents:
            if intent.action == "HOLD":
                continue

            self._order_counter += 1
            order_id = f"mock_{self._order_counter:06d}"

            order = LiveOrder(
                order_id=order_id,
                asset=intent.asset,
                asset_type=str(intent.asset_type.value),
                side=intent.action,
                quantity=intent.trade_quantity,
                status="pending",
                filled_qty=0.0,
            )
            self._orders.append(order)
            order_ids.append(order_id)

        return order_ids

    def cancel_orders(self, asset: str | None = None) -> int:
        cancelled = 0
        for order in self._orders:
            if order.status in ("pending", "partial"):
                if asset is None or order.asset == asset:
                    order.status = "cancelled"
                    cancelled += 1
        return cancelled

    def sync_positions(self) -> dict[str, dict]:
        return {**self._positions}

    def query_order_status(self, order_id: str) -> dict:
        for order in self._orders:
            if order.order_id == order_id:
                return {
                    "status": order.status,
                    "filled": order.filled_qty,
                    "avg_price": order.avg_price,
                    "order_id": order.order_id,
                }
        return {"status": "unknown", "filled": 0.0, "avg_price": None, "order_id": order_id}

    # ── Mock 专用方法 ─────────────────────────────────────────

    def get_placed_orders(self) -> list[dict]:
        """获取已放置的订单记录 (测试用)"""
        return [
            {
                "order_id": o.order_id,
                "asset": o.asset,
                "asset_type": o.asset_type,
                "action": o.side,
                "quantity": o.quantity,
                "status": o.status,
                "filled": o.filled_qty,
            }
            for o in self._orders
        ]

    def clear(self):
        """重置所有状态 (测试用)"""
        self._orders.clear()
        self._positions.clear()
        self._order_counter = 0

    def get_broker_info(self) -> dict:
        return {
            "name": "MockLiveBridge",
            "is_mock": True,
            "version": "1.0.0",
        }