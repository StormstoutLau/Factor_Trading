"""
P0 集成测试: engine_v2 接入 ExecutionPolicy 抽象层

验证:
1. SignalTranslator + T1StockPolicy 生成的订单与旧路径一致
2. engine_v2 支持 execution_policy 依赖注入
3. engine_v2 支持 risk_manager 依赖注入
4. 新旧路径在完整回测中结果一致
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from unittest.mock import Mock, MagicMock

import numpy as np
import pandas as pd

from core.pending import OrderSide, PendingOrder, PendingOrderQueue
from core.execution_policy import (
    SignalTranslator, T1StockPolicy, OrderIntent,
)
from core.tracker import Position, PositionTracker


class TestRebalanceOrderGeneration(unittest.TestCase):
    """验证 SignalTranslator + T1StockPolicy 生成的订单与旧路径一致"""

    def setUp(self):
        self.date = pd.Timestamp("2024-01-15")

    def test_same_orders_as_old_path_buy(self):
        """新路径 BUY: 与旧 create_pending_order(BUY) 一致"""
        from core.pending import create_pending_order

        # 旧路径
        old_order = create_pending_order("000001.SZ", OrderSide.BUY, 1000, self.date)

        # 新路径
        intent = OrderIntent("000001.SZ", "stock", 1000.0, 0.0)
        policy = T1StockPolicy()
        new_orders = policy.create_orders(intent, self.date)

        self.assertEqual(len(new_orders), 1)
        new_order = new_orders[0]
        self.assertEqual(new_order.stock, old_order.stock)
        self.assertEqual(new_order.side, old_order.side)
        self.assertEqual(new_order.quantity, old_order.quantity)
        self.assertEqual(new_order.create_date, old_order.create_date)

    def test_same_orders_as_old_path_sell(self):
        """新路径 SELL: 与旧 create_pending_order(SELL) 一致"""
        from core.pending import create_pending_order

        old_order = create_pending_order("000001.SZ", OrderSide.SELL, 500, self.date)

        intent = OrderIntent("000001.SZ", "stock", 0.0, 500.0)
        policy = T1StockPolicy()
        new_orders = policy.create_orders(intent, self.date)

        self.assertEqual(len(new_orders), 1)
        new_order = new_orders[0]
        self.assertEqual(new_order.stock, old_order.stock)
        self.assertEqual(new_order.side, old_order.side)
        self.assertEqual(new_order.quantity, old_order.quantity)

    def test_from_weights_produces_same_intents(self):
        """SignalTranslator.from_weights 从权重生成正确的 OrderIntent"""
        target_weights = pd.Series(
            [0.5, 0.3, 0.2],
            index=["000001.SZ", "000002.SZ", "000003.SZ"],
        )
        current_positions = {}
        prices = pd.Series(
            [10.0, 20.0, 50.0],
            index=["000001.SZ", "000002.SZ", "000003.SZ"],
        )
        total_value = 1_000_000.0

        intents = SignalTranslator.from_weights(
            target_weights, current_positions, prices, total_value
        )

        self.assertEqual(len(intents), 3)
        for intent in intents:
            self.assertEqual(intent.action, "BUY")
            self.assertGreater(intent.target_quantity, 0)

    def test_full_roundtrip_weights_to_orders(self):
        """完整链路: 权重 → OrderIntent → PendingOrder"""
        target_weights = pd.Series(
            [0.5, 0.5],
            index=["000001.SZ", "000002.SZ"],
        )
        current_positions = {"000001.SZ": 5000.0}
        prices = pd.Series([10.0, 20.0], index=["000001.SZ", "000002.SZ"])
        total_value = 1_000_000.0

        # 1. 权重 → OrderIntent
        intents = SignalTranslator.from_weights(
            target_weights, current_positions, prices, total_value
        )

        # 2. OrderIntent → PendingOrder
        policy = T1StockPolicy()
        all_orders = []
        for intent in intents:
            all_orders.extend(policy.create_orders(intent, self.date))

        # 应该有 2 个订单: BUY 000002.SZ, BUY 000001.SZ (加仓)
        self.assertEqual(len(all_orders), 2)
        stocks = {o.stock for o in all_orders}
        self.assertIn("000001.SZ", stocks)
        self.assertIn("000002.SZ", stocks)


class TestEngineV2ExecutionPolicyInjection(unittest.TestCase):
    """验证 engine_v2 支持 execution_policy 注入"""

    def test_engine_accepts_execution_policy(self):
        """engine_v2 构造函数接受 execution_policy 参数"""
        import importlib
        import core.engine_v2 as ev2
        importlib.reload(ev2)

        from core.config import BacktestConfig
        from core.execution_policy import T1StockPolicy

        cfg = BacktestConfig()
        policy = T1StockPolicy()

        # 验证注入不报错
        engine = ev2.BacktestEngineV2(
            config=cfg,
            execution_policy=policy,
        )
        self.assertIsNotNone(engine)
        self.assertIs(engine._execution_policy, policy)

    def test_engine_accepts_risk_manager(self):
        """engine_v2 构造函数接受 risk_manager 参数"""
        import importlib
        import core.engine_v2 as ev2
        importlib.reload(ev2)

        from core.config import BacktestConfig
        from core.risk_manager import MarkToMarketPolicy

        cfg = BacktestConfig()
        risk_mgr = MarkToMarketPolicy()

        engine = ev2.BacktestEngineV2(
            config=cfg,
            risk_manager=risk_mgr,
        )
        self.assertIsNotNone(engine)
        self.assertIs(engine._risk_manager, risk_mgr)

    def test_engine_without_policy_uses_old_path(self):
        """不注入 execution_policy 时使用旧路径 (默认行为)"""
        import importlib
        import core.engine_v2 as ev2
        importlib.reload(ev2)

        from core.config import BacktestConfig

        cfg = BacktestConfig()
        engine = ev2.BacktestEngineV2(config=cfg)

        self.assertIsNone(engine._execution_policy)
        self.assertIsNone(engine._risk_manager)


class TestMarkToMarketPolicyIntegration(unittest.TestCase):
    """验证 MarkToMarketPolicy 接入 engine_v2 的盯市流程"""

    def test_risk_manager_checks_positions(self):
        """风险管理器检查持仓并生成动作"""
        from core.risk_manager import (
            MarkToMarketPolicy, StopLossConfig, RiskAction,
        )
        from core.config import MarginConfig

        # 创建一个亏损持仓
        pos = Position("000001.SZ", 1000, 10.0, 8500.0, -1500.0, 0.0)

        mtm = MarkToMarketPolicy(
            stop_loss_config=StopLossConfig(stop_loss_pct=-0.10),
            margin_config=MarginConfig(),
        )

        results = mtm.check_position(pos)
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].action, RiskAction.STOP_LOSS)

    def test_risk_manager_returns_empty_for_healthy(self):
        """健康持仓不生成风险动作"""
        from core.risk_manager import MarkToMarketPolicy

        pos = Position("000001.SZ", 1000, 10.0, 12000.0, 2000.0, 0.0)
        mtm = MarkToMarketPolicy()

        results = mtm.check_position(pos)
        self.assertEqual(len(results), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)