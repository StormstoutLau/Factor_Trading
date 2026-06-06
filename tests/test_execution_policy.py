"""
Phase 1 TDD: 执行策略抽象层测试

测试范围:
1. OrderIntent - 统一订单意图数据结构
2. ExecutionResult - 执行结果
3. ExecutionPolicy - 抽象基类
4. T1StockPolicy - A股 T+1 策略实现
5. SignalTranslator - 信号翻译器 (from_weights)
6. 多态性测试 - 不同策略可互换使用
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest

import numpy as np
import pandas as pd

# ============================================================================
# 模块 1: OrderIntent 测试
# ============================================================================


class TestOrderIntent(unittest.TestCase):
    """测试 OrderIntent 数据结构"""

    def test_create_basic(self):
        """创建基本 OrderIntent"""
        from core.execution_policy import OrderIntent

        intent = OrderIntent(
            asset="000001.SZ",
            asset_type="stock",
            target_quantity=1000.0,
            current_quantity=500.0,
        )

        self.assertEqual(intent.asset, "000001.SZ")
        self.assertEqual(intent.asset_type, "stock")
        self.assertEqual(intent.target_quantity, 1000.0)
        self.assertEqual(intent.current_quantity, 500.0)
        self.assertEqual(intent.urgency, 1.0)  # 默认值

    def test_trade_quantity_buy(self):
        """trade_quantity = target - current (加仓)"""
        from core.execution_policy import OrderIntent

        intent = OrderIntent(
            asset="000001.SZ",
            asset_type="stock",
            target_quantity=1000.0,
            current_quantity=200.0,
        )
        self.assertEqual(intent.trade_quantity, 800.0)

    def test_trade_quantity_sell(self):
        """trade_quantity = target - current (减仓)"""
        from core.execution_policy import OrderIntent

        intent = OrderIntent(
            asset="000001.SZ",
            asset_type="stock",
            target_quantity=0.0,
            current_quantity=500.0,
        )
        self.assertEqual(intent.trade_quantity, -500.0)

    def test_trade_quantity_hold(self):
        """trade_quantity = 0 (不变)"""
        from core.execution_policy import OrderIntent

        intent = OrderIntent(
            asset="000001.SZ",
            asset_type="stock",
            target_quantity=500.0,
            current_quantity=500.0,
        )
        self.assertEqual(intent.trade_quantity, 0.0)

    def test_action_buy(self):
        """加多仓 → BUY"""
        from core.execution_policy import OrderIntent

        intent = OrderIntent(
            asset="000001.SZ",
            asset_type="stock",
            target_quantity=1000.0,
            current_quantity=0.0,
        )
        self.assertEqual(intent.action, "BUY")

    def test_action_sell(self):
        """减多仓 → SELL"""
        from core.execution_policy import OrderIntent

        intent = OrderIntent(
            asset="000001.SZ",
            asset_type="stock",
            target_quantity=0.0,
            current_quantity=500.0,
        )
        self.assertEqual(intent.action, "SELL")

    def test_action_hold(self):
        """不变 → HOLD"""
        from core.execution_policy import OrderIntent

        intent = OrderIntent(
            asset="000001.SZ",
            asset_type="stock",
            target_quantity=500.0,
            current_quantity=500.0,
        )
        self.assertEqual(intent.action, "HOLD")

    def test_action_sell_short(self):
        """加空仓 (target < current ≤ 0) → SELL_SHORT"""
        from core.execution_policy import OrderIntent

        intent = OrderIntent(
            asset="IF2406",
            asset_type="future",
            target_quantity=-2.0,
            current_quantity=0.0,
        )
        self.assertEqual(intent.action, "SELL_SHORT")

    def test_action_buy_to_cover(self):
        """减空仓 (target > current, current < 0) → BUY_TO_COVER"""
        from core.execution_policy import OrderIntent

        intent = OrderIntent(
            asset="IF2406",
            asset_type="future",
            target_quantity=0.0,
            current_quantity=-2.0,
        )
        self.assertEqual(intent.action, "BUY_TO_COVER")

    def test_action_flip_long_to_short(self):
        """多头翻空 (target < 0, current > 0) → SELL"""
        from core.execution_policy import OrderIntent

        intent = OrderIntent(
            asset="IF2406",
            asset_type="future",
            target_quantity=-2.0,
            current_quantity=3.0,
        )
        # 先平多仓 → SELL
        self.assertEqual(intent.action, "SELL")

    def test_action_flip_short_to_long(self):
        """空头翻多 (target > 0, current < 0) → BUY_TO_COVER"""
        from core.execution_policy import OrderIntent

        intent = OrderIntent(
            asset="IF2406",
            asset_type="future",
            target_quantity=3.0,
            current_quantity=-2.0,
        )
        self.assertEqual(intent.action, "BUY_TO_COVER")

    def test_abs_trade_quantity(self):
        """abs_trade_quantity 返回绝对值"""
        from core.execution_policy import OrderIntent

        buy_intent = OrderIntent(
            asset="000001.SZ", asset_type="stock",
            target_quantity=1000.0, current_quantity=0.0,
        )
        self.assertEqual(buy_intent.abs_trade_quantity, 1000.0)

        sell_intent = OrderIntent(
            asset="000001.SZ", asset_type="stock",
            target_quantity=0.0, current_quantity=500.0,
        )
        self.assertEqual(sell_intent.abs_trade_quantity, 500.0)

    def test_urgency_custom(self):
        """自定义 urgency"""
        from core.execution_policy import OrderIntent

        intent = OrderIntent(
            asset="000001.SZ", asset_type="stock",
            target_quantity=1000.0, current_quantity=0.0,
            urgency=0.5,
        )
        self.assertEqual(intent.urgency, 0.5)


# ============================================================================
# 模块 2: ExecutionResult 测试
# ============================================================================


class TestExecutionResult(unittest.TestCase):
    """测试 ExecutionResult 数据结构"""

    def test_success_result(self):
        """成功执行的结果"""
        from core.execution_policy import ExecutionResult, OrderIntent

        intent = OrderIntent(
            asset="000001.SZ", asset_type="stock",
            target_quantity=1000.0, current_quantity=0.0,
        )
        result = ExecutionResult(
            success=True,
            intent=intent,
            executed_price=10.5,
            executed_quantity=1000.0,
            executed_date=pd.Timestamp("2024-01-15"),
        )

        self.assertTrue(result.success)
        self.assertEqual(result.executed_price, 10.5)
        self.assertEqual(result.executed_quantity, 1000.0)
        self.assertFalse(result.is_partial)

    def test_failed_result(self):
        """失败执行的结果"""
        from core.execution_policy import ExecutionResult, OrderIntent

        intent = OrderIntent(
            asset="000001.SZ", asset_type="stock",
            target_quantity=1000.0, current_quantity=0.0,
        )
        result = ExecutionResult(
            success=False,
            intent=intent,
            executed_price=0.0,
            executed_quantity=0.0,
            executed_date=pd.Timestamp("2024-01-15"),
            error_message="股票停牌",
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "股票停牌")

    def test_partial_fill(self):
        """部分成交"""
        from core.execution_policy import ExecutionResult, OrderIntent

        intent = OrderIntent(
            asset="000001.SZ", asset_type="stock",
            target_quantity=1000.0, current_quantity=0.0,
        )
        result = ExecutionResult(
            success=True,
            intent=intent,
            executed_price=10.5,
            executed_quantity=600.0,
            executed_date=pd.Timestamp("2024-01-15"),
        )

        self.assertTrue(result.success)
        self.assertTrue(result.is_partial)
        self.assertEqual(result.executed_quantity, 600.0)


# ============================================================================
# 模块 3: ExecutionPolicy 基类 + T1StockPolicy 测试
# ============================================================================


class TestExecutionPolicy(unittest.TestCase):
    """测试 ExecutionPolicy 抽象基类 + T1StockPolicy"""

    def test_policy_is_abstract(self):
        """ExecutionPolicy 是抽象类，不能直接实例化"""
        from core.execution_policy import ExecutionPolicy

        with self.assertRaises(TypeError):
            ExecutionPolicy()  # type: ignore

    def test_t1_policy_timing(self):
        """T1StockPolicy 的 timing 属性"""
        from core.execution_policy import T1StockPolicy, ExecutionTiming

        policy = T1StockPolicy()
        self.assertEqual(policy.timing, ExecutionTiming.NEXT_OPEN)

    def test_t1_policy_needs_pending_queue(self):
        """T1StockPolicy 需要待执行队列"""
        from core.execution_policy import T1StockPolicy

        policy = T1StockPolicy()
        self.assertTrue(policy.needs_pending_queue)

    def test_t1_policy_no_intraday(self):
        """T1StockPolicy 不支持日内交易"""
        from core.execution_policy import T1StockPolicy

        policy = T1StockPolicy()
        self.assertFalse(policy.supports_intraday)

    def test_t1_create_orders_buy(self):
        """T1StockPolicy: 买入意图 → PendingOrder(BUY)"""
        from core.execution_policy import T1StockPolicy, OrderIntent

        policy = T1StockPolicy()
        intent = OrderIntent(
            asset="000001.SZ", asset_type="stock",
            target_quantity=1000.0, current_quantity=0.0,
        )
        date = pd.Timestamp("2024-01-15")

        orders = policy.create_orders(intent, date)

        self.assertEqual(len(orders), 1)
        order = orders[0]
        self.assertEqual(order.stock, "000001.SZ")
        self.assertEqual(order.quantity, 1000)
        self.assertEqual(order.side.name, "BUY")
        self.assertEqual(order.create_date, date)

    def test_t1_create_orders_sell(self):
        """T1StockPolicy: 卖出意图 → PendingOrder(SELL)"""
        from core.execution_policy import T1StockPolicy, OrderIntent

        policy = T1StockPolicy()
        intent = OrderIntent(
            asset="000001.SZ", asset_type="stock",
            target_quantity=0.0, current_quantity=500.0,
        )
        date = pd.Timestamp("2024-01-15")

        orders = policy.create_orders(intent, date)

        self.assertEqual(len(orders), 1)
        order = orders[0]
        self.assertEqual(order.stock, "000001.SZ")
        self.assertEqual(order.quantity, 500)
        self.assertEqual(order.side.name, "SELL")
        self.assertEqual(order.create_date, date)

    def test_t1_create_orders_hold(self):
        """T1StockPolicy: 不变 → 空订单列表"""
        from core.execution_policy import T1StockPolicy, OrderIntent

        policy = T1StockPolicy()
        intent = OrderIntent(
            asset="000001.SZ", asset_type="stock",
            target_quantity=500.0, current_quantity=500.0,
        )
        date = pd.Timestamp("2024-01-15")

        orders = policy.create_orders(intent, date)
        self.assertEqual(len(orders), 0)

    def test_t1_create_orders_add_position(self):
        """T1StockPolicy: 加仓 → PendingOrder(BUY)"""
        from core.execution_policy import T1StockPolicy, OrderIntent

        policy = T1StockPolicy()
        intent = OrderIntent(
            asset="000001.SZ", asset_type="stock",
            target_quantity=1000.0, current_quantity=300.0,
        )
        date = pd.Timestamp("2024-01-15")

        orders = policy.create_orders(intent, date)
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].quantity, 700)
        self.assertEqual(orders[0].side.name, "BUY")

    def test_t1_create_orders_reduce_position(self):
        """T1StockPolicy: 减仓 → PendingOrder(SELL)"""
        from core.execution_policy import T1StockPolicy, OrderIntent

        policy = T1StockPolicy()
        intent = OrderIntent(
            asset="000001.SZ", asset_type="stock",
            target_quantity=200.0, current_quantity=1000.0,
        )
        date = pd.Timestamp("2024-01-15")

        orders = policy.create_orders(intent, date)
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].quantity, 800)
        self.assertEqual(orders[0].side.name, "SELL")


# ============================================================================
# 模块 4: SignalTranslator 测试
# ============================================================================


class TestSignalTranslator(unittest.TestCase):
    """测试 SignalTranslator"""

    def test_from_weights_basic(self):
        """权重 → OrderIntent 基本转换"""
        from core.execution_policy import SignalTranslator

        target_weights = pd.Series(
            [0.5, 0.3, 0.2],
            index=["000001.SZ", "000002.SZ", "000003.SZ"],
        )
        current_positions = {}  # 空仓
        prices = pd.Series(
            [10.0, 20.0, 50.0],
            index=["000001.SZ", "000002.SZ", "000003.SZ"],
        )
        total_value = 1_000_000.0

        intents = SignalTranslator.from_weights(
            target_weights, current_positions, prices, total_value
        )

        self.assertEqual(len(intents), 3)

        # 验证第一只股票
        intent_0 = next(i for i in intents if i.asset == "000001.SZ")
        self.assertEqual(intent_0.asset_type, "stock")
        self.assertEqual(intent_0.current_quantity, 0.0)
        expected_qty = 0.5 * 1_000_000 / 10.0
        self.assertAlmostEqual(intent_0.target_quantity, expected_qty)
        self.assertEqual(intent_0.action, "BUY")

    def test_from_weights_partial_existing(self):
        """部分已有持仓，部分新建"""
        from core.execution_policy import SignalTranslator

        target_weights = pd.Series(
            [0.4, 0.6],
            index=["000001.SZ", "000002.SZ"],
        )
        current_positions = {"000001.SZ": 5000.0}
        prices = pd.Series(
            [10.0, 20.0],
            index=["000001.SZ", "000002.SZ"],
        )
        total_value = 1_000_000.0

        intents = SignalTranslator.from_weights(
            target_weights, current_positions, prices, total_value
        )

        self.assertEqual(len(intents), 2)

        intent_1 = next(i for i in intents if i.asset == "000001.SZ")
        expected_target = 0.4 * 1_000_000 / 10.0  # 40000
        self.assertAlmostEqual(intent_1.target_quantity, expected_target)
        self.assertEqual(intent_1.current_quantity, 5000.0)
        # target > current → BUY
        self.assertEqual(intent_1.action, "BUY")

    def test_from_weights_sell_all(self):
        """清仓（权重为0）"""
        from core.execution_policy import SignalTranslator

        target_weights = pd.Series(
            [0.5, 0.5],
            index=["000001.SZ", "000002.SZ"],
        )
        current_positions = {"000001.SZ": 10000.0, "000003.SZ": 5000.0}
        prices = pd.Series(
            [10.0, 20.0, 30.0],
            index=["000001.SZ", "000002.SZ", "000003.SZ"],
        )
        total_value = 1_000_000.0

        intents = SignalTranslator.from_weights(
            target_weights, current_positions, prices, total_value
        )

        # 000003.SZ 不在目标权重中 → 应清仓
        intent_3 = next(i for i in intents if i.asset == "000003.SZ")
        self.assertEqual(intent_3.target_quantity, 0.0)
        self.assertEqual(intent_3.current_quantity, 5000.0)
        self.assertEqual(intent_3.action, "SELL")

    def test_from_weights_empty(self):
        """空输入"""
        from core.execution_policy import SignalTranslator

        target_weights = pd.Series(dtype=float)
        current_positions = {}
        prices = pd.Series(dtype=float)
        total_value = 1_000_000.0

        intents = SignalTranslator.from_weights(
            target_weights, current_positions, prices, total_value
        )
        self.assertEqual(len(intents), 0)

    def test_from_weights_no_change_skipped(self):
        """无变化时跳过"""
        from core.execution_policy import SignalTranslator

        target_weights = pd.Series(
            [0.5],
            index=["000001.SZ"],
        )
        prices = pd.Series([10.0], index=["000001.SZ"])
        total_value = 1_000_000.0
        target_qty = 0.5 * 1_000_000 / 10.0  # 50000

        current_positions = {"000001.SZ": target_qty}

        intents = SignalTranslator.from_weights(
            target_weights, current_positions, prices, total_value
        )
        # 仓位无变化 → 跳过
        self.assertEqual(len(intents), 0)

    def test_from_weights_custom_asset_type(self):
        """自定义 asset_type"""
        from core.execution_policy import SignalTranslator

        target_weights = pd.Series(
            [1.0],
            index=["IF2406"],
        )
        prices = pd.Series([3500.0], index=["IF2406"])
        total_value = 1_000_000.0

        intents = SignalTranslator.from_weights(
            target_weights, current_positions={}, prices=prices,
            total_value=total_value, asset_type="future",
        )

        self.assertEqual(len(intents), 1)
        self.assertEqual(intents[0].asset_type, "future")
        self.assertEqual(intents[0].action, "BUY")


# ============================================================================
# 模块 5: 多态性测试
# ============================================================================


class TestPolicyPolymorphism(unittest.TestCase):
    """测试 ExecutionPolicy 多态性"""

    def test_policies_share_interface(self):
        """不同策略实现相同的接口"""
        from core.execution_policy import (
            ExecutionPolicy, T1StockPolicy, ExecutionTiming,
        )

        # 验证 T1StockPolicy 实现了所有抽象方法
        policy = T1StockPolicy()
        self.assertIsInstance(policy, ExecutionPolicy)
        self.assertIsInstance(policy.timing, ExecutionTiming)
        self.assertIsInstance(policy.needs_pending_queue, bool)
        self.assertIsInstance(policy.supports_intraday, bool)

    def test_policy_dispatch_based_on_asset_type(self):
        """根据资产类型分派不同策略"""
        from core.execution_policy import T1StockPolicy, OrderIntent

        policies = {
            "stock": T1StockPolicy(),
            # "future": T0FuturesPolicy(),  # Phase 2 实现
        }

        intent = OrderIntent(
            asset="000001.SZ", asset_type="stock",
            target_quantity=1000.0, current_quantity=0.0,
        )

        policy = policies[intent.asset_type]
        orders = policy.create_orders(intent, pd.Timestamp("2024-01-15"))

        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].stock, "000001.SZ")

    def test_all_intent_actions_coverage(self):
        """覆盖所有 action 类型的意图"""
        from core.execution_policy import OrderIntent

        # BUY: 买入开仓
        buy = OrderIntent("A", "stock", 100, 0)
        self.assertEqual(buy.action, "BUY")

        # SELL: 卖出平仓
        sell = OrderIntent("A", "stock", 0, 100)
        self.assertEqual(sell.action, "SELL")

        # HOLD: 不变
        hold = OrderIntent("A", "stock", 100, 100)
        self.assertEqual(hold.action, "HOLD")

        # SELL_SHORT: 开空仓
        short = OrderIntent("A", "future", -2, 0)
        self.assertEqual(short.action, "SELL_SHORT")

        # BUY_TO_COVER: 平空仓
        cover = OrderIntent("A", "future", 0, -2)
        self.assertEqual(cover.action, "BUY_TO_COVER")


# ============================================================================
# 模块 6: 与现有系统兼容性测试
# ============================================================================


class TestBackwardCompatibility(unittest.TestCase):
    """确保新抽象层与现有代码兼容"""

    def test_t1_policy_uses_existing_pending_order(self):
        """T1StockPolicy 生成的订单使用现有 PendingOrder 类型"""
        from core.execution_policy import T1StockPolicy, OrderIntent
        from core.pending import PendingOrder, OrderSide

        policy = T1StockPolicy()
        intent = OrderIntent(
            asset="000001.SZ", asset_type="stock",
            target_quantity=1000.0, current_quantity=0.0,
        )

        orders = policy.create_orders(intent, pd.Timestamp("2024-01-15"))

        self.assertIsInstance(orders[0], PendingOrder)
        self.assertEqual(orders[0].side, OrderSide.BUY)

    def test_signal_translator_output_compatible_with_t1_policy(self):
        """SignalTranslator 输出可直接消费于 T1StockPolicy"""
        from core.execution_policy import SignalTranslator, T1StockPolicy

        target_weights = pd.Series([0.5, 0.5], index=["000001.SZ", "000002.SZ"])
        prices = pd.Series([10.0, 20.0], index=["000001.SZ", "000002.SZ"])

        intents = SignalTranslator.from_weights(
            target_weights, {}, prices, 1_000_000.0
        )

        policy = T1StockPolicy()
        date = pd.Timestamp("2024-01-15")

        for intent in intents:
            orders = policy.create_orders(intent, date)
            self.assertGreaterEqual(len(orders), 0)
            for order in orders:
                self.assertIsNotNone(order.stock)
                self.assertGreater(order.quantity, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)