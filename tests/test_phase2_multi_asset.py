"""
Phase 2 TDD: 多空扩展测试

测试范围:
1. OrderSide 扩展 - SELL_SHORT / BUY_TO_COVER
2. Position 多空支持 - 有符号 quantity + 多空盈亏 + 保证金
3. T0FuturesPolicy - 期货 T+0 策略
4. MarginConfig - 保证金配置
5. 集成测试 - 多空完整回环 + 策略路由
6. 向后兼容 - 现有功能不受影响
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest

import numpy as np
import pandas as pd

# ============================================================================
# 模块 2.1: OrderSide 扩展测试
# ============================================================================


class TestOrderSideExtension(unittest.TestCase):
    """OrderSide 新增 SELL_SHORT / BUY_TO_COVER"""

    def test_new_enum_values_exist(self):
        """SELL_SHORT 和 BUY_TO_COVER 已添加"""
        from core.pending import OrderSide

        self.assertIn("SELL_SHORT", OrderSide.__members__)
        self.assertIn("BUY_TO_COVER", OrderSide.__members__)

    def test_buy_sell_unchanged(self):
        """原有 BUY/SELL 值不变"""
        from core.pending import OrderSide

        self.assertEqual(OrderSide.BUY.name, "BUY")
        self.assertEqual(OrderSide.SELL.name, "SELL")

    def test_sell_short_name(self):
        """SELL_SHORT 的 name 正确"""
        from core.pending import OrderSide

        self.assertEqual(OrderSide.SELL_SHORT.name, "SELL_SHORT")

    def test_enum_members_count(self):
        """OrderSide 现在有 4 个成员"""
        from core.pending import OrderSide

        self.assertEqual(len(OrderSide), 4)


# ============================================================================
# 模块 2.2: Position 多空支持测试
# ============================================================================


class TestPositionLongShort(unittest.TestCase):
    """Position 支持多空持仓"""

    def setUp(self):
        from core.tracker import Position

        self.long_pos = Position(
            stock="000001.SZ", quantity=1000, avg_cost=10.0,
            market_value=10000.0, unrealized_pnl=0.0, realized_pnl=0.0,
        )
        self.short_pos = Position(
            stock="IF2406", quantity=-2, avg_cost=3500.0,
            market_value=7000.0, unrealized_pnl=0.0, realized_pnl=0.0,
        )

    def test_direction_long(self):
        """多头 → direction = 1"""
        self.assertEqual(self.long_pos.direction, 1)

    def test_direction_short(self):
        """空头 → direction = -1"""
        self.assertEqual(self.short_pos.direction, -1)

    def test_direction_flat(self):
        """无持仓 → direction = 0"""
        from core.tracker import Position

        flat = Position("000001.SZ", 0, 0.0, 0.0, 0.0, 0.0)
        self.assertEqual(flat.direction, 0)

    def test_exposure_long(self):
        """多头暴露 = |quantity| * current_price"""
        self.long_pos.update_market_value(11.0)
        self.assertEqual(self.long_pos.exposure, 11000.0)

    def test_exposure_short(self):
        """空头暴露 = |quantity| * current_price"""
        self.short_pos.update_market_value(3400.0)
        self.assertEqual(self.short_pos.exposure, 6800.0)

    def test_margin_used_default(self):
        """margin_used 默认值为 0"""
        from core.tracker import Position

        pos = Position("000001.SZ", 1000, 10.0, 10000.0, 0.0, 0.0)
        self.assertEqual(pos.margin_used, 0.0)

    def test_margin_used_custom(self):
        """margin_used 可自定义"""
        from core.tracker import Position

        pos = Position("IF2406", -2, 3500.0, 7000.0, 0.0, 0.0, margin_used=700.0)
        self.assertEqual(pos.margin_used, 700.0)

    def test_update_market_value_long(self):
        """多头盯市: market_value = quantity * price"""
        self.long_pos.update_market_value(12.0)
        self.assertEqual(self.long_pos.market_value, 12000.0)
        self.assertEqual(self.long_pos.unrealized_pnl, 2000.0)  # (12-10)*1000

    def test_update_market_value_short(self):
        """空头盯市: PnL = quantity * (price - avg_cost)"""
        self.short_pos.update_market_value(3400.0)
        # PnL = -2 * (3400 - 3500) = -2 * (-100) = 200 (盈利)
        self.assertEqual(self.short_pos.unrealized_pnl, 200.0)
        # market_value 为绝对值
        self.assertEqual(self.short_pos.market_value, 6800.0)

    def test_update_market_value_short_loss(self):
        """空头亏损: 价格上涨"""
        self.short_pos.update_market_value(3600.0)
        # PnL = -2 * (3600 - 3500) = -2 * 100 = -200 (亏损)
        self.assertEqual(self.short_pos.unrealized_pnl, -200.0)


class TestPositionTradeExecution(unittest.TestCase):
    """Position.execute_trade 多空交易"""

    def setUp(self):
        from core.execution import Trade
        from core.pending import OrderSide
        from core.tracker import Position

        self.Trade = Trade
        self.OrderSide = OrderSide
        self.Position = Position

    def _make_trade(self, stock, side, quantity, price, amount, cost=0.0):
        """辅助: 创建 Trade"""
        from core.pending import OrderSide

        net = amount + cost if side == OrderSide.BUY else amount - cost
        return self.Trade(
            date=pd.Timestamp("2024-01-15"),
            stock=stock,
            side=side,
            quantity=quantity,
            price=price,
            amount=amount,
            cost=cost,
            net_amount=net,
        )

    def test_sell_short_new_position(self):
        """开空仓: SELL_SHORT 1000股 @ 10"""
        pos = self.Position("000001.SZ", 0, 0.0, 0.0, 0.0, 0.0)
        trade = self._make_trade(
            "000001.SZ", self.OrderSide.SELL_SHORT, 1000, 10.0, 10000.0, 5.0
        )

        pos.execute_trade(trade)
        self.assertEqual(pos.quantity, -1000)
        self.assertEqual(pos.avg_cost, 10.0)

    def test_sell_short_add_to_position(self):
        """加空仓: 已有 -500 → 再加 -500"""
        pos = self.Position("000001.SZ", -500, 10.0, 5000.0, 0.0, 0.0)
        trade = self._make_trade(
            "000001.SZ", self.OrderSide.SELL_SHORT, 500, 11.0, 5500.0, 5.0
        )

        pos.execute_trade(trade)
        self.assertEqual(pos.quantity, -1000)
        self.assertAlmostEqual(pos.avg_cost, 10.5)  # (500*10 + 500*11) / 1000

    def test_buy_to_cover_partial(self):
        """部分平空: -1000 → 买回 400 → -600"""
        pos = self.Position("000001.SZ", -1000, 10.0, 10000.0, 0.0, 0.0)
        trade = self._make_trade(
            "000001.SZ", self.OrderSide.BUY_TO_COVER, 400, 9.0, 3600.0, 5.0
        )

        pos.execute_trade(trade)
        self.assertEqual(pos.quantity, -600)
        # 已实现盈亏: 以 9 买入平 400 股空头，每股盈利 (10-9) = 1
        expected_pnl = 400 * (10.0 - 9.0) - 5.0
        self.assertAlmostEqual(pos.realized_pnl, expected_pnl)

    def test_buy_to_cover_full(self):
        """全部平空: -1000 → 0"""
        pos = self.Position("000001.SZ", -1000, 10.0, 10000.0, 0.0, 0.0)
        trade = self._make_trade(
            "000001.SZ", self.OrderSide.BUY_TO_COVER, 1000, 9.0, 9000.0, 5.0
        )

        pos.execute_trade(trade)
        self.assertEqual(pos.quantity, 0)
        self.assertEqual(pos.avg_cost, 0)
        self.assertEqual(pos.market_value, 0.0)
        self.assertEqual(pos.unrealized_pnl, 0.0)

    def test_buy_to_cover_short_loss(self):
        """平空亏损: 空头均价 10，买回价 12"""
        pos = self.Position("000001.SZ", -1000, 10.0, 10000.0, 0.0, 0.0)
        trade = self._make_trade(
            "000001.SZ", self.OrderSide.BUY_TO_COVER, 1000, 12.0, 12000.0, 5.0
        )

        pos.execute_trade(trade)
        # 亏损: 1000 * (10 - 12) - 5 = -2005
        expected_pnl = 1000 * (10.0 - 12.0) - 5.0
        self.assertAlmostEqual(pos.realized_pnl, expected_pnl)

    def test_buy_still_works(self):
        """原有 BUY 逻辑不受影响"""
        pos = self.Position("000001.SZ", 500, 10.0, 5000.0, 0.0, 0.0)
        trade = self._make_trade(
            "000001.SZ", self.OrderSide.BUY, 500, 12.0, 6000.0, 5.0
        )

        pos.execute_trade(trade)
        self.assertEqual(pos.quantity, 1000)
        self.assertAlmostEqual(pos.avg_cost, 11.0)

    def test_sell_still_works(self):
        """原有 SELL 逻辑不受影响"""
        pos = self.Position("000001.SZ", 1000, 10.0, 10000.0, 0.0, 0.0)
        trade = self._make_trade(
            "000001.SZ", self.OrderSide.SELL, 400, 12.0, 4800.0, 5.0
        )

        pos.execute_trade(trade)
        self.assertEqual(pos.quantity, 600)
        self.assertGreater(pos.realized_pnl, 0)

    def test_to_dict_includes_margin(self):
        """to_dict 包含 margin_used"""
        pos = self.Position("IF2406", -2, 3500.0, 7000.0, 0.0, 0.0, margin_used=700.0)
        d = pos.to_dict()
        self.assertIn("margin_used", d)
        self.assertEqual(d["margin_used"], 700.0)
        self.assertIn("direction", d)
        self.assertEqual(d["direction"], -1)


# ============================================================================
# 模块 2.3: T0FuturesPolicy 测试
# ============================================================================


class TestT0FuturesPolicy(unittest.TestCase):
    """T0FuturesPolicy 期货 T+0 执行策略"""

    def setUp(self):
        from core.execution_policy import T0FuturesPolicy, OrderIntent

        self.Policy = T0FuturesPolicy
        self.OrderIntent = OrderIntent
        self.date = pd.Timestamp("2024-01-15")

    def test_timing(self):
        """期货 T+0 → IMMEDIATE_OPEN"""
        policy = self.Policy()
        from core.execution_policy import ExecutionTiming

        self.assertEqual(policy.timing, ExecutionTiming.IMMEDIATE_OPEN)

    def test_no_pending_queue(self):
        """期货不需要待执行队列"""
        policy = self.Policy()
        self.assertFalse(policy.needs_pending_queue)

    def test_supports_intraday(self):
        """期货支持日内交易"""
        policy = self.Policy()
        self.assertTrue(policy.supports_intraday)

    def test_create_orders_buy(self):
        """BUY 意图 → PendingOrder(BUY)"""
        policy = self.Policy()
        intent = self.OrderIntent("IF2406", "future", 2.0, 0.0)

        orders = policy.create_orders(intent, self.date)
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].side.name, "BUY")
        self.assertEqual(orders[0].quantity, 2)

    def test_create_orders_sell(self):
        """SELL 意图 → PendingOrder(SELL)"""
        policy = self.Policy()
        intent = self.OrderIntent("IF2406", "future", 0.0, 2.0)

        orders = policy.create_orders(intent, self.date)
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].side.name, "SELL")
        self.assertEqual(orders[0].quantity, 2)

    def test_create_orders_sell_short(self):
        """SELL_SHORT 意图 → PendingOrder(SELL_SHORT)"""
        policy = self.Policy()
        intent = self.OrderIntent("IF2406", "future", -2.0, 0.0)

        orders = policy.create_orders(intent, self.date)
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].side.name, "SELL_SHORT")
        self.assertEqual(orders[0].quantity, 2)

    def test_create_orders_buy_to_cover(self):
        """BUY_TO_COVER 意图 → PendingOrder(BUY_TO_COVER)"""
        policy = self.Policy()
        intent = self.OrderIntent("IF2406", "future", 0.0, -2.0)

        orders = policy.create_orders(intent, self.date)
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].side.name, "BUY_TO_COVER")
        self.assertEqual(orders[0].quantity, 2)

    def test_create_orders_hold(self):
        """HOLD → 空列表"""
        policy = self.Policy()
        intent = self.OrderIntent("IF2406", "future", 2.0, 2.0)

        orders = policy.create_orders(intent, self.date)
        self.assertEqual(len(orders), 0)

    def test_create_orders_add_short(self):
        """加空仓: -2 → -5"""
        policy = self.Policy()
        intent = self.OrderIntent("IF2406", "future", -5.0, -2.0)

        orders = policy.create_orders(intent, self.date)
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].side.name, "SELL_SHORT")
        self.assertEqual(orders[0].quantity, 3)

    def test_create_orders_partial_cover(self):
        """部分平空: -5 → -2"""
        policy = self.Policy()
        intent = self.OrderIntent("IF2406", "future", -2.0, -5.0)

        orders = policy.create_orders(intent, self.date)
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].side.name, "BUY_TO_COVER")
        self.assertEqual(orders[0].quantity, 3)

    def test_flip_long_to_short(self):
        """多头翻空: 3 → -2"""
        policy = self.Policy()
        intent = self.OrderIntent("IF2406", "future", -2.0, 3.0)

        orders = policy.create_orders(intent, self.date)
        # 需要两个订单: 先 SELL 平多, 再 SELL_SHORT 开空
        self.assertEqual(len(orders), 2)
        sides = [o.side.name for o in orders]
        self.assertIn("SELL", sides)
        self.assertIn("SELL_SHORT", sides)

    def test_flip_short_to_long(self):
        """空头翻多: -3 → 2"""
        policy = self.Policy()
        intent = self.OrderIntent("IF2406", "future", 2.0, -3.0)

        orders = policy.create_orders(intent, self.date)
        # 需要两个订单: 先 BUY_TO_COVER 平空, 再 BUY 开多
        self.assertEqual(len(orders), 2)
        sides = [o.side.name for o in orders]
        self.assertIn("BUY_TO_COVER", sides)
        self.assertIn("BUY", sides)

    def test_uses_existing_order_types(self):
        """生成的订单是标准 PendingOrder 类型"""
        policy = self.Policy()
        from core.pending import PendingOrder

        intent = self.OrderIntent("IF2406", "future", -2.0, 0.0)
        orders = policy.create_orders(intent, self.date)
        self.assertIsInstance(orders[0], PendingOrder)


# ============================================================================
# 模块 2.4: MarginConfig 测试
# ============================================================================


class TestMarginConfig(unittest.TestCase):
    """保证金配置"""

    def test_default_values(self):
        """默认保证金配置"""
        from core.config import MarginConfig

        cfg = MarginConfig()
        self.assertAlmostEqual(cfg.initial_margin_ratio, 0.10)
        self.assertAlmostEqual(cfg.maintenance_margin_ratio, 0.08)

    def test_custom_values(self):
        """自定义保证金配置"""
        from core.config import MarginConfig

        cfg = MarginConfig(
            initial_margin_ratio=0.15,
            maintenance_margin_ratio=0.12,
        )
        self.assertAlmostEqual(cfg.initial_margin_ratio, 0.15)
        self.assertAlmostEqual(cfg.maintenance_margin_ratio, 0.12)

    def test_calculate_initial_margin(self):
        """计算初始保证金"""
        from core.config import MarginConfig

        cfg = MarginConfig(initial_margin_ratio=0.10)
        margin = cfg.calculate_initial_margin(notional_value=100000.0)
        self.assertAlmostEqual(margin, 10000.0)

    def test_calculate_maintenance_margin(self):
        """计算维持保证金"""
        from core.config import MarginConfig

        cfg = MarginConfig(maintenance_margin_ratio=0.08)
        margin = cfg.calculate_maintenance_margin(notional_value=100000.0)
        self.assertAlmostEqual(margin, 8000.0)


# ============================================================================
# 模块 2.5: 集成测试
# ============================================================================


class TestPhase2Integration(unittest.TestCase):
    """Phase 2 集成测试"""

    def test_full_roundtrip_long_short_flat(self):
        """完整多空回环: 多→空→平"""
        from core.execution import Trade
        from core.pending import OrderSide
        from core.tracker import Position

        pos = Position("IF2406", 0, 0.0, 0.0, 0.0, 0.0)

        # Step 1: 开多 2 手 @ 3500
        pos.execute_trade(Trade(
            pd.Timestamp("2024-01-15"), "IF2406", OrderSide.BUY,
            2, 3500.0, 7000.0, 5.0, 7005.0,
        ))
        self.assertEqual(pos.quantity, 2)
        self.assertEqual(pos.direction, 1)

        # Step 2: 平多 + 开空 -2 手 @ 3600
        pos.execute_trade(Trade(
            pd.Timestamp("2024-01-16"), "IF2406", OrderSide.SELL,
            2, 3600.0, 7200.0, 5.0, 7195.0,
        ))
        self.assertEqual(pos.quantity, 0)
        self.assertEqual(pos.avg_cost, 0)

        pos.execute_trade(Trade(
            pd.Timestamp("2024-01-16"), "IF2406", OrderSide.SELL_SHORT,
            2, 3600.0, 7200.0, 5.0, 7195.0,
        ))
        self.assertEqual(pos.quantity, -2)
        self.assertEqual(pos.direction, -1)

        # Step 3: 平空 @ 3500
        pos.execute_trade(Trade(
            pd.Timestamp("2024-01-17"), "IF2406", OrderSide.BUY_TO_COVER,
            2, 3500.0, 7000.0, 5.0, 6995.0,
        ))
        self.assertEqual(pos.quantity, 0)
        self.assertEqual(pos.direction, 0)
        # 空头盈利: 2 * (3600 - 3500) - 5 = 195
        # 多头盈利: 2 * (3600 - 3500) - 5 = 195
        # 总盈利: 390
        self.assertAlmostEqual(pos.realized_pnl, 390.0)

    def test_policy_router_stock_vs_future(self):
        """策略路由: stock → T1StockPolicy, future → T0FuturesPolicy"""
        from core.execution_policy import (
            T1StockPolicy, T0FuturesPolicy, OrderIntent,
        )

        policies = {
            "stock": T1StockPolicy(),
            "future": T0FuturesPolicy(),
        }

        # Stock intent uses T1
        stock_intent = OrderIntent("000001.SZ", "stock", 1000.0, 0.0)
        stock_policy = policies[stock_intent.asset_type]
        self.assertIsInstance(stock_policy, T1StockPolicy)
        self.assertTrue(stock_policy.needs_pending_queue)

        # Future intent uses T0
        future_intent = OrderIntent("IF2406", "future", 2.0, 0.0)
        future_policy = policies[future_intent.asset_type]
        self.assertIsInstance(future_policy, T0FuturesPolicy)
        self.assertFalse(future_policy.needs_pending_queue)

    def test_t0_policy_create_orders_idempotent(self):
        """T0FuturesPolicy 对 HOLD 意图返回空列表"""
        from core.execution_policy import T0FuturesPolicy, OrderIntent

        policy = T0FuturesPolicy()
        date = pd.Timestamp("2024-01-15")

        # 仓位不变
        intent = OrderIntent("IF2406", "future", 2.0, 2.0)
        orders = policy.create_orders(intent, date)
        self.assertEqual(len(orders), 0)

        # 零仓位不变
        intent2 = OrderIntent("IF2406", "future", 0.0, 0.0)
        orders2 = policy.create_orders(intent2, date)
        self.assertEqual(len(orders2), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)