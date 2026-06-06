"""
执行策略抽象层 - 统一多资产交易执行

Phase 1: 基础抽象
- ExecutionTiming: 执行时机枚举
- OrderIntent: 统一订单意图（信号层和执行层的中间表示）
- ExecutionResult: 执行结果
- ExecutionPolicy: 抽象执行策略基类
- T1StockPolicy: A股 T+1 策略实现
- SignalTranslator: 信号翻译器 (from_weights)

设计原则:
    1. 最小侵入: 纯新增模块，不修改现有引擎代码
    2. 多态: 不同资产类型使用不同策略，但共享相同接口
    3. 兼容: T1StockPolicy 生成的 PendingOrder 与现有系统完全兼容
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import pandas as pd

from core.config import AssetType
from core.pending import OrderSide, PendingOrder, create_pending_order


# ============================================================================
# Module 1: ExecutionTiming - 执行时机
# ============================================================================


class ExecutionTiming(Enum):
    """执行时机枚举

    不同资产类型的执行时效差异:
        - 股票 A股: T+1, 当日信号→次日开盘执行
        - 期货: T+0, 当日信号→当日执行
        - 期权: T+1, 类似股票
    """
    IMMEDIATE_OPEN = "immediate_open"       # T+0 当日开盘执行
    IMMEDIATE_CLOSE = "immediate_close"     # T+0 当日收盘执行
    NEXT_OPEN = "next_open"                # T+1 次日开盘执行 (当前A股默认)
    NEXT_CLOSE = "next_close"              # T+1 次日收盘执行
    CUSTOM = "custom"                      # 自定义时机


# ============================================================================
# Module 2: OrderIntent - 统一订单意图
# ============================================================================


@dataclass
class OrderIntent:
    """统一订单意图 - 信号层和执行层的中间表示

    将"权重信号"和"事件信号"统一为此数据结构，
    再由 ExecutionPolicy 决定如何执行。

    Attributes:
        asset: 资产代码
        asset_type: 资产类型 ("stock" | "future" | "option")
        target_quantity: 目标仓位 (有符号: >0 多头, <0 空头)
        current_quantity: 当前仓位 (有符号)
        urgency: 紧急程度 (0-1, 1=最高优先级)
    """

    asset: str
    asset_type: str | AssetType
    target_quantity: float
    current_quantity: float
    urgency: float = 1.0

    @property
    def trade_quantity(self) -> float:
        """需要交易的数量 = target - current"""
        return self.target_quantity - self.current_quantity

    @property
    def abs_trade_quantity(self) -> float:
        """需要交易的绝对数量"""
        return abs(self.trade_quantity)

    @property
    def action(self) -> str:
        """推导交易动作

        Returns:
            "BUY" | "SELL" | "SELL_SHORT" | "BUY_TO_COVER" | "HOLD"
        """
        tq = self.trade_quantity
        cq = self.current_quantity
        if abs(tq) < 1e-10:
            return "HOLD"
        if tq > 0 and cq >= 0:
            return "BUY"
        if tq < 0 and cq > 0:
            return "SELL"
        if tq < 0 and cq <= 0:
            return "SELL_SHORT"
        if tq > 0 and cq < 0:
            return "BUY_TO_COVER"
        return "HOLD"


# ============================================================================
# Module 3: ExecutionResult - 执行结果
# ============================================================================


@dataclass
class ExecutionResult:
    """执行结果

    Attributes:
        success: 是否成功执行
        intent: 原始订单意图
        executed_price: 执行价格
        executed_quantity: 实际成交数量
        executed_date: 执行日期
        error_message: 失败原因
    """

    success: bool
    intent: OrderIntent
    executed_price: float
    executed_quantity: float
    executed_date: pd.Timestamp
    error_message: str = ""

    @property
    def is_partial(self) -> bool:
        """是否部分成交"""
        return self.success and self.executed_quantity < self.intent.abs_trade_quantity


# ============================================================================
# Module 4: ExecutionPolicy - 抽象基类
# ============================================================================


class ExecutionPolicy(ABC):
    """执行策略抽象基类

    定义"如何将 OrderIntent 转换为实际订单"的接口。
    不同资产类型实现不同的策略。

    子类必须实现:
        - timing: 执行时机
        - needs_pending_queue: 是否需要待执行队列
        - supports_intraday: 是否支持日内交易
        - create_orders: 将 OrderIntent 转换为 PendingOrder 列表
    """

    @property
    @abstractmethod
    def timing(self) -> ExecutionTiming:
        """执行时机"""
        ...

    @property
    @abstractmethod
    def needs_pending_queue(self) -> bool:
        """是否需要待执行订单队列"""
        ...

    @property
    @abstractmethod
    def supports_intraday(self) -> bool:
        """是否支持日内交易"""
        ...

    @abstractmethod
    def create_orders(
        self, intent: OrderIntent, date: pd.Timestamp
    ) -> list[PendingOrder]:
        """将 OrderIntent 转换为 PendingOrder 列表

        Args:
            intent: 订单意图
            date: 创建日期

        Returns:
            PendingOrder 列表 (可能为空)
        """
        ...


# ============================================================================
# Module 5: T1StockPolicy - A股 T+1 策略
# ============================================================================


class T1StockPolicy(ExecutionPolicy):
    """A股 T+1 执行策略

    特征:
        - 当日信号→次日开盘执行
        - 需要待执行队列（处理涨停/停牌失败重试）
        - 不支持日内交易
        - 仅做多（stock 类型默认）
    """

    @property
    def timing(self) -> ExecutionTiming:
        return ExecutionTiming.NEXT_OPEN

    @property
    def needs_pending_queue(self) -> bool:
        return True

    @property
    def supports_intraday(self) -> bool:
        return False

    def create_orders(
        self, intent: OrderIntent, date: pd.Timestamp
    ) -> list[PendingOrder]:
        """将 OrderIntent 转换为 PendingOrder

        T+1 规则:
            - BUY → PendingOrder(BUY), 次日开盘执行
            - SELL → PendingOrder(SELL), 次日开盘执行
            - HOLD → 空列表
            - SELL_SHORT / BUY_TO_COVER → 空列表 (A股不支持做空)
        """
        tq = intent.trade_quantity
        if abs(tq) < 1e-10:
            return []

        action = intent.action
        if action == "HOLD":
            return []

        # A股仅支持做多方向
        if action in ("SELL_SHORT", "BUY_TO_COVER"):
            return []

        if action == "BUY":
            side = OrderSide.BUY
        elif action == "SELL":
            side = OrderSide.SELL
        else:
            return []

        order = create_pending_order(
            stock=intent.asset,
            side=side,
            quantity=int(abs(tq)),
            create_date=date,
        )
        return [order]


# ============================================================================
# Module 6: T0FuturesPolicy - 期货 T+0 策略
# ============================================================================


class T0FuturesPolicy(ExecutionPolicy):
    """期货 T+0 执行策略

    特征:
        - 当日信号→当日执行 (IMMEDIATE_OPEN)
        - 不需要待执行队列（期货流动性好，无需延迟）
        - 支持日内交易
        - 支持多空双向交易
        - 翻仓时拆分为两个订单（先平后开）
    """

    @property
    def timing(self) -> ExecutionTiming:
        return ExecutionTiming.IMMEDIATE_OPEN

    @property
    def needs_pending_queue(self) -> bool:
        return False

    @property
    def supports_intraday(self) -> bool:
        return True

    def create_orders(
        self, intent: OrderIntent, date: pd.Timestamp
    ) -> list[PendingOrder]:
        """将 OrderIntent 转换为 PendingOrder

        T+0 规则:
            - BUY → PendingOrder(BUY) 立即执行
            - SELL → PendingOrder(SELL) 立即执行
            - SELL_SHORT → PendingOrder(SELL_SHORT) 立即执行
            - BUY_TO_COVER → PendingOrder(BUY_TO_COVER) 立即执行
            - 翻仓: 多→空 = SELL(平多) + SELL_SHORT(开空)
            - 翻仓: 空→多 = BUY_TO_COVER(平空) + BUY(开多)
            - HOLD → 空列表
        """
        tq = intent.trade_quantity
        if abs(tq) < 1e-10:
            return []

        action = intent.action
        orders: list[PendingOrder] = []

        if action == "HOLD":
            return []

        elif action == "BUY":
            # 纯加多仓
            orders.append(create_pending_order(
                stock=intent.asset,
                side=OrderSide.BUY,
                quantity=int(abs(tq)),
                create_date=date,
            ))

        elif action == "SELL":
            if intent.target_quantity < 0 and intent.current_quantity > 0:
                # 翻仓: 多头→空头
                # 先平多仓
                orders.append(create_pending_order(
                    stock=intent.asset,
                    side=OrderSide.SELL,
                    quantity=int(abs(intent.current_quantity)),
                    create_date=date,
                ))
                # 再开空仓
                open_qty = int(abs(intent.target_quantity))
                if open_qty > 0:
                    orders.append(create_pending_order(
                        stock=intent.asset,
                        side=OrderSide.SELL_SHORT,
                        quantity=open_qty,
                        create_date=date,
                    ))
            else:
                # 纯减多仓
                orders.append(create_pending_order(
                    stock=intent.asset,
                    side=OrderSide.SELL,
                    quantity=int(abs(tq)),
                    create_date=date,
                ))

        elif action == "SELL_SHORT":
            # 纯加空仓（不处理翻仓，翻仓已在 SELL 分支处理）
            orders.append(create_pending_order(
                stock=intent.asset,
                side=OrderSide.SELL_SHORT,
                quantity=int(abs(tq)),
                create_date=date,
            ))

        elif action == "BUY_TO_COVER":
             if intent.target_quantity > 0 and intent.current_quantity < 0:
                 # 翻仓: 空头→多头
                 # 先平空仓
                 orders.append(create_pending_order(
                     stock=intent.asset,
                     side=OrderSide.BUY_TO_COVER,
                     quantity=int(abs(intent.current_quantity)),
                     create_date=date,
                 ))
                 # 再开多仓
                 open_qty = int(abs(intent.target_quantity))
                 if open_qty > 0:
                     orders.append(create_pending_order(
                         stock=intent.asset,
                         side=OrderSide.BUY,
                         quantity=open_qty,
                         create_date=date,
                     ))
             else:
                 # 纯减空仓
                 orders.append(create_pending_order(
                     stock=intent.asset,
                     side=OrderSide.BUY_TO_COVER,
                     quantity=int(abs(tq)),
                     create_date=date,
                 ))

        return orders


# ============================================================================
# Module 7: SignalTranslator - 信号翻译器
# ============================================================================


class SignalTranslator:
    """信号翻译器 - 将不同信号格式统一为 OrderIntent

    支持:
        - from_weights: 权重信号 → OrderIntent (当前实现)
        - from_signals: vbt 风格信号 → OrderIntent (Phase 4)
    """

    @staticmethod
    def from_weights(
        target_weights: pd.Series,
        current_positions: dict[str, float],
        prices: pd.Series,
        total_value: float,
        asset_type: str | AssetType = AssetType.STOCK,
    ) -> list[OrderIntent]:
        """权重信号 → OrderIntent 列表

        将优化器输出的目标权重转换为 OrderIntent 列表。
        只返回需要交易的资产（target ≠ current）。

        Args:
            target_weights: 目标权重 (asset → weight)
            current_positions: 当前持仓 (asset → quantity)
            prices: 当前价格 (asset → price)
            total_value: 组合总价值
            asset_type: 资产类型

        Returns:
            OrderIntent 列表
        """
        intents: list[OrderIntent] = []

        # 收集所有涉及的资产
        all_assets = set(target_weights.index) | set(current_positions.keys())

        for asset in all_assets:
            asset_str = str(asset)
            target_w = float(target_weights.get(asset, 0.0))
            current_qty = float(current_positions.get(asset_str, 0.0))

            # 计算目标数量
            if target_w > 0 and asset_str in prices.index:
                price = float(prices[asset_str])
                if price > 0:
                    target_qty = target_w * total_value / price
                else:
                    target_qty = 0.0
            else:
                target_qty = 0.0

            # 跳过无变化的持仓
            if abs(target_qty - current_qty) < 1e-10:
                continue

            intents.append(OrderIntent(
                asset=asset_str,
                asset_type=asset_type,
                target_quantity=target_qty,
                current_quantity=current_qty,
            ))

        return intents

    @staticmethod
    def from_signals(
        buy_signal: pd.Series,
        sell_signal: pd.Series,
        current_positions: dict[str, float],
        prices: pd.Series,
        total_value: float,
        short_signal: pd.Series | None = None,
        short_exit_signal: pd.Series | None = None,
        asset_type: str | AssetType = AssetType.FUTURE,
    ) -> list[OrderIntent]:
        """vbt 风格信号 → OrderIntent 列表

        将 buy_signal / sell_signal / short_signal / short_exit_signal
        转换为统一的 OrderIntent 列表。

        Args:
            buy_signal: 买入信号 (asset → bool)
            sell_signal: 卖出信号 (asset → bool)
            current_positions: 当前持仓 (asset → quantity)
            prices: 当前价格 (asset → price)
            total_value: 组合总价值
            short_signal: 做空信号 (asset → bool), 可选
            short_exit_signal: 平空信号 (asset → bool), 可选
            asset_type: 资产类型 (默认 "future")

        Returns:
            OrderIntent 列表
        """
        if short_signal is None:
            short_signal = pd.Series(dtype=bool)
        if short_exit_signal is None:
            short_exit_signal = pd.Series(dtype=bool)

        intents: list[OrderIntent] = []

        # 收集所有涉及的资产
        all_assets = (
            set(buy_signal.index)
            | set(sell_signal.index)
            | set(short_signal.index)
            | set(short_exit_signal.index)
            | set(current_positions.keys())
        )

        for asset in all_assets:
            asset_str = str(asset)

            # 获取价格
            if asset_str not in prices.index:
                continue
            price = float(prices[asset_str])
            if price <= 0:
                continue

            current_qty = float(current_positions.get(asset_str, 0.0))
            position_qty = total_value / price

            # 1. 买入信号 (开多仓)
            buy = bool(buy_signal.get(asset, False))
            if buy and current_qty <= 0:
                intents.append(OrderIntent(
                    asset=asset_str,
                    asset_type=asset_type,
                    target_quantity=position_qty,
                    current_quantity=current_qty,
                ))
                continue

            # 2. 卖出信号 (平多仓)
            sell = bool(sell_signal.get(asset, False))
            if sell and current_qty > 0:
                intents.append(OrderIntent(
                    asset=asset_str,
                    asset_type=asset_type,
                    target_quantity=0.0,
                    current_quantity=current_qty,
                ))
                continue

            # 3. 做空信号 (开空仓)
            short = bool(short_signal.get(asset, False))
            if short and current_qty >= 0:
                intents.append(OrderIntent(
                    asset=asset_str,
                    asset_type=asset_type,
                    target_quantity=-position_qty,
                    current_quantity=current_qty,
                ))
                continue

            # 4. 平空信号 (平空仓)
            short_exit = bool(short_exit_signal.get(asset, False))
            if short_exit and current_qty < 0:
                intents.append(OrderIntent(
                    asset=asset_str,
                    asset_type=asset_type,
                    target_quantity=0.0,
                    current_quantity=current_qty,
                ))
                continue

        return intents