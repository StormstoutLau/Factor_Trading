"""
P3.1 TDD: 实盘交易桥接接口测试

验证:
1. LiveTradingBridge 抽象基类契约
2. MockLiveBridge 模拟实现
3. 订单意图→实盘订单转换
4. 订单状态管理
5. 持仓同步
6. 与现有 OrderIntent 兼容
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from unittest.mock import MagicMock, patch

import pandas as pd


# ============================================================================
# P3.1.1: LiveTradingBridge 抽象基类
# ============================================================================


class TestLiveTradingBridgeInterface(unittest.TestCase):
    """LiveTradingBridge 抽象基类契约"""

    def test_bridge_is_abstract(self):
        """LiveTradingBridge 是抽象基类，不能直接实例化"""
        from core.live_bridge import LiveTradingBridge

        with self.assertRaises(TypeError):
            LiveTradingBridge()  # 抽象类不能直接实例化

    def test_bridge_defines_place_intents(self):
        """定义 place_intents 抽象方法"""
        from core.live_bridge import LiveTradingBridge

        self.assertTrue(hasattr(LiveTradingBridge, "place_intents"))
        self.assertTrue(
            getattr(LiveTradingBridge.place_intents, "__isabstractmethod__", False)
        )

    def test_bridge_defines_cancel_orders(self):
        """定义 cancel_orders 抽象方法"""
        from core.live_bridge import LiveTradingBridge

        self.assertTrue(hasattr(LiveTradingBridge, "cancel_orders"))
        self.assertTrue(
            getattr(LiveTradingBridge.cancel_orders, "__isabstractmethod__", False)
        )

    def test_bridge_defines_sync_positions(self):
        """定义 sync_positions 抽象方法"""
        from core.live_bridge import LiveTradingBridge

        self.assertTrue(hasattr(LiveTradingBridge, "sync_positions"))
        self.assertTrue(
            getattr(LiveTradingBridge.sync_positions, "__isabstractmethod__", False)
        )

    def test_bridge_defines_query_order_status(self):
        """定义 query_order_status 抽象方法"""
        from core.live_bridge import LiveTradingBridge

        self.assertTrue(hasattr(LiveTradingBridge, "query_order_status"))
        self.assertTrue(
            getattr(LiveTradingBridge.query_order_status, "__isabstractmethod__", False)
        )

    def test_bridge_defines_get_broker_info(self):
        """定义 get_broker_info 非抽象方法 (提供默认实现)"""
        from core.live_bridge import LiveTradingBridge

        self.assertTrue(hasattr(LiveTradingBridge, "get_broker_info"))


# ============================================================================
# P3.1.2: MockLiveBridge 模拟实现
# ============================================================================


class TestMockLiveBridge(unittest.TestCase):
    """MockLiveBridge 模拟实现验证"""

    def setUp(self):
        from core.live_bridge import MockLiveBridge

        self.bridge = MockLiveBridge()

    def test_mock_bridge_is_instance(self):
        """MockLiveBridge 是 LiveTradingBridge 的实例"""
        from core.live_bridge import LiveTradingBridge, MockLiveBridge

        self.assertIsInstance(self.bridge, LiveTradingBridge)

    def test_place_intents_returns_order_ids(self):
        """place_intents 返回订单ID列表"""
        from core.execution_policy import OrderIntent
        from core.config import AssetType

        intents = [
            OrderIntent(
                asset="000001.SZ",
                asset_type=AssetType.STOCK,
                target_quantity=1000.0,
                current_quantity=0.0,
            ),
            OrderIntent(
                asset="600000.SH",
                asset_type=AssetType.STOCK,
                target_quantity=500.0,
                current_quantity=200.0,
            ),
        ]

        order_ids = self.bridge.place_intents(intents, date=pd.Timestamp("2024-01-15"))
        self.assertEqual(len(order_ids), 2)
        self.assertIsInstance(order_ids[0], str)
        self.assertTrue(order_ids[0].startswith("mock_"))

    def test_place_intents_records_orders(self):
        """place_intents 记录订单到内部日志"""
        from core.execution_policy import OrderIntent
        from core.config import AssetType

        intents = [
            OrderIntent(
                asset="000001.SZ",
                asset_type=AssetType.STOCK,
                target_quantity=1000.0,
                current_quantity=0.0,
            ),
        ]

        self.bridge.place_intents(intents, date=pd.Timestamp("2024-01-15"))
        orders = self.bridge.get_placed_orders()

        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]["asset"], "000001.SZ")
        self.assertEqual(orders[0]["action"], "BUY")

    def test_cancel_orders_returns_count(self):
        """cancel_orders 返回取消的订单数"""
        from core.execution_policy import OrderIntent
        from core.config import AssetType

        intents = [
            OrderIntent(
                asset="000001.SZ",
                asset_type=AssetType.STOCK,
                target_quantity=1000.0,
                current_quantity=0.0,
            ),
        ]

        self.bridge.place_intents(intents, date=pd.Timestamp("2024-01-15"))
        cancelled = self.bridge.cancel_orders("000001.SZ")

        self.assertEqual(cancelled, 1)

    def test_sync_positions_returns_positions(self):
        """sync_positions 返回当前持仓字典"""
        positions = self.bridge.sync_positions()

        self.assertIsInstance(positions, dict)

    def test_query_order_status_returns_status(self):
        """query_order_status 返回订单状态"""
        from core.execution_policy import OrderIntent
        from core.config import AssetType

        intents = [
            OrderIntent(
                asset="000001.SZ",
                asset_type=AssetType.STOCK,
                target_quantity=1000.0,
                current_quantity=0.0,
            ),
        ]

        order_ids = self.bridge.place_intents(intents, date=pd.Timestamp("2024-01-15"))
        status = self.bridge.query_order_status(order_ids[0])

        self.assertIsInstance(status, dict)
        self.assertIn("status", status)
        self.assertIn("filled", status)

    def test_get_broker_info_returns_dict(self):
        """get_broker_info 返回券商信息"""
        info = self.bridge.get_broker_info()
        self.assertIsInstance(info, dict)
        self.assertIn("name", info)
        self.assertIn("is_mock", info)
        self.assertTrue(info["is_mock"])

    def test_mock_bridge_clear_resets_state(self):
        """clear() 重置所有记录"""
        from core.execution_policy import OrderIntent
        from core.config import AssetType

        intents = [
            OrderIntent(
                asset="000001.SZ",
                asset_type=AssetType.STOCK,
                target_quantity=1000.0,
                current_quantity=0.0,
            ),
        ]

        self.bridge.place_intents(intents, date=pd.Timestamp("2024-01-15"))
        self.bridge.clear()

        orders = self.bridge.get_placed_orders()
        self.assertEqual(len(orders), 0)


# ============================================================================
# P3.1.3: 与现有系统集成
# ============================================================================


class TestBridgeIntegrationWithOrderIntent(unittest.TestCase):
    """LiveTradingBridge 与 OrderIntent 集成"""

    def test_intent_action_mapping(self):
        """OrderIntent 的 action 正确映射到订单方向"""
        from core.execution_policy import OrderIntent
        from core.config import AssetType

        # BUY: target > current
        intent_buy = OrderIntent(
            asset="000001.SZ",
            asset_type=AssetType.STOCK,
            target_quantity=1000.0,
            current_quantity=0.0,
        )
        self.assertEqual(intent_buy.action, "BUY")

        # SELL: target < current
        intent_sell = OrderIntent(
            asset="000001.SZ",
            asset_type=AssetType.STOCK,
            target_quantity=0.0,
            current_quantity=1000.0,
        )
        self.assertEqual(intent_sell.action, "SELL")

        # HOLD: target == current
        intent_hold = OrderIntent(
            asset="000001.SZ",
            asset_type=AssetType.STOCK,
            target_quantity=500.0,
            current_quantity=500.0,
        )
        self.assertEqual(intent_hold.action, "HOLD")

    def test_bridge_filters_hold_intents(self):
        """HOLD 意图不产生订单"""
        from core.live_bridge import MockLiveBridge
        from core.execution_policy import OrderIntent
        from core.config import AssetType

        bridge = MockLiveBridge()
        intents = [
            OrderIntent(
                asset="000001.SZ",
                asset_type=AssetType.STOCK,
                target_quantity=500.0,
                current_quantity=500.0,  # HOLD
            ),
            OrderIntent(
                asset="600000.SH",
                asset_type=AssetType.STOCK,
                target_quantity=1000.0,
                current_quantity=0.0,  # BUY
            ),
        ]

        order_ids = bridge.place_intents(intents, date=pd.Timestamp("2024-01-15"))
        self.assertEqual(len(order_ids), 1)  # 只有 BUY 产生订单

    def test_multi_asset_intents(self):
        """支持多资产类型意图"""
        from core.live_bridge import MockLiveBridge
        from core.execution_policy import OrderIntent
        from core.config import AssetType

        bridge = MockLiveBridge()
        intents = [
            OrderIntent(
                asset="000001.SZ",
                asset_type=AssetType.STOCK,
                target_quantity=1000.0,
                current_quantity=0.0,
            ),
            OrderIntent(
                asset="IF2406",
                asset_type=AssetType.FUTURE,
                target_quantity=2.0,
                current_quantity=0.0,
            ),
        ]

        order_ids = bridge.place_intents(intents, date=pd.Timestamp("2024-01-15"))
        self.assertEqual(len(order_ids), 2)

        orders = bridge.get_placed_orders()
        asset_types = {o["asset_type"] for o in orders}
        self.assertIn(AssetType.STOCK, asset_types)
        self.assertIn(AssetType.FUTURE, asset_types)


if __name__ == "__main__":
    unittest.main(verbosity=2)