"""
Phase 3 TDD: 主动盯市 + 风险监控测试

测试范围:
1. RiskAction / RiskActionItem - 风险动作数据结构
2. MarkToMarketPolicy - 主动盯市策略
3. StopLoss - 止损检查
4. MarginRisk - 保证金风险检查
5. 集成 - 多空组合的完整风险检查
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest

import pandas as pd


# ============================================================================
# 模块 3.1: RiskAction / RiskActionItem
# ============================================================================


class TestRiskAction(unittest.TestCase):
    """风险动作枚举和数据结构"""

    def test_risk_action_enum_values(self):
        """RiskAction 枚举值"""
        from core.risk_manager import RiskAction

        self.assertIn("MARGIN_CALL", RiskAction.__members__)
        self.assertIn("FORCE_CLOSE", RiskAction.__members__)
        self.assertIn("STOP_LOSS", RiskAction.__members__)
        self.assertIn("NONE", RiskAction.__members__)

    def test_risk_action_item_create(self):
        """RiskActionItem 创建"""
        from core.risk_manager import RiskAction, RiskActionItem

        item = RiskActionItem(
            action=RiskAction.STOP_LOSS,
            asset="000001.SZ",
            reason="亏损超过 10%",
            severity=0.8,
        )

        self.assertEqual(item.action, RiskAction.STOP_LOSS)
        self.assertEqual(item.asset, "000001.SZ")
        self.assertEqual(item.reason, "亏损超过 10%")
        self.assertAlmostEqual(item.severity, 0.8)

    def test_risk_action_item_defaults(self):
        """RiskActionItem 默认值"""
        from core.risk_manager import RiskAction, RiskActionItem

        item = RiskActionItem(
            action=RiskAction.NONE,
            asset="",
            reason="",
        )

        self.assertEqual(item.severity, 0.0)
        self.assertFalse(item.requires_immediate_action)


# ============================================================================
# 模块 3.2: StopLossConfig
# ============================================================================


class TestStopLossConfig(unittest.TestCase):
    """止损配置"""

    def test_default_values(self):
        """默认止损配置"""
        from core.risk_manager import StopLossConfig

        cfg = StopLossConfig()
        self.assertAlmostEqual(cfg.stop_loss_pct, -0.10)
        self.assertAlmostEqual(cfg.trailing_stop_pct, -0.05)
        self.assertTrue(cfg.enabled)

    def test_custom_values(self):
        """自定义止损配置"""
        from core.risk_manager import StopLossConfig

        cfg = StopLossConfig(stop_loss_pct=-0.15, enabled=False)
        self.assertAlmostEqual(cfg.stop_loss_pct, -0.15)
        self.assertFalse(cfg.enabled)

    def test_disabled_stop_loss(self):
        """禁用止损时返回 None"""
        from core.risk_manager import StopLossConfig

        cfg = StopLossConfig(enabled=False)
        result = cfg.check_stop_loss(unrealized_pnl_pct=-0.20)
        self.assertIsNone(result)


# ============================================================================
# 模块 3.3: MarkToMarketPolicy - 主动盯市
# ============================================================================


class TestMarkToMarketPolicy(unittest.TestCase):
    """主动盯市策略"""

    def setUp(self):
        from core.risk_manager import MarkToMarketPolicy, StopLossConfig
        from core.config import MarginConfig

        self.stop_loss = StopLossConfig(stop_loss_pct=-0.10)
        self.margin = MarginConfig(
            initial_margin_ratio=0.10,
            maintenance_margin_ratio=0.08,
            force_liquidation_ratio=0.05,
        )
        self.mtm = MarkToMarketPolicy(
            stop_loss_config=self.stop_loss,
            margin_config=self.margin,
        )

    def test_no_risk_for_healthy_position(self):
        """健康持仓无风险动作"""
        from core.tracker import Position

        pos = Position("000001.SZ", 1000, 10.0, 10500.0, 500.0, 0.0)
        results = self.mtm.check_position(pos)

        self.assertEqual(len(results), 0)

    def test_not_applicable_for_cash_only(self):
        """现金资产不适用盯市检查"""
        from core.tracker import Position

        pos = Position("000001.SZ", 0, 0.0, 0.0, 0.0, 0.0)
        results = self.mtm.check_position(pos)
        self.assertEqual(len(results), 0)

    def test_stop_loss_triggered(self):
        """止损触发: 亏损超过 10%"""
        from core.tracker import Position
        from core.risk_manager import RiskAction

        # 成本 10000，市值 8500，亏损 15%
        pos = Position("000001.SZ", 1000, 10.0, 8500.0, -1500.0, 0.0)
        results = self.mtm.check_position(pos)

        self.assertGreaterEqual(len(results), 1)
        action = results[0]
        self.assertEqual(action.action, RiskAction.STOP_LOSS)

    def test_stop_loss_not_triggered(self):
        """止损未触发: 亏损 5%"""
        from core.tracker import Position

        pos = Position("000001.SZ", 1000, 10.0, 9500.0, -500.0, 0.0)
        results = self.mtm.check_position(pos)

        self.assertEqual(len(results), 0)

    def test_profit_no_stop_loss(self):
        """盈利时不触发止损"""
        from core.tracker import Position

        pos = Position("000001.SZ", 1000, 10.0, 12000.0, 2000.0, 0.0)
        results = self.mtm.check_position(pos)

        self.assertEqual(len(results), 0)


# ============================================================================
# 模块 3.4: 保证金风险检查 (期货)
# ============================================================================


class TestMarginRiskCheck(unittest.TestCase):
    """保证金风险检查"""

    def setUp(self):
        from core.risk_manager import MarkToMarketPolicy, StopLossConfig
        from core.config import MarginConfig

        self.stop_loss = StopLossConfig(enabled=False)
        self.margin = MarginConfig(
            initial_margin_ratio=0.10,
            maintenance_margin_ratio=0.08,
            force_liquidation_ratio=0.05,
        )
        self.mtm = MarkToMarketPolicy(
            stop_loss_config=self.stop_loss,
            margin_config=self.margin,
        )

    def test_margin_call_triggered(self):
        """保证金不足 → MARGIN_CALL"""
        from core.tracker import Position
        from core.risk_manager import RiskAction

        # 名义价值 100000，保证金 7000（7% < 8% 维持保证金）
        pos = Position("IF2406", -2, 3500.0, 7000.0, 0.0, 0.0, margin_used=7000.0)
        pos.update_market_value(3500.0)  # 名义价值 = 2*3500 = 7000
        # 保证金比例 = 7000 / 7000 = 100%... wait that's not right

        # Let me reconsider. 名义价值 = abs(quantity) * price = 2 * 3500 = 7000
        # Actually for futures, 1 contract = 300 multiplier. Let me use simpler numbers.
        # 名义价值 = 100000, margin_used = 7000, margin_ratio = 7000/100000 = 7% < 8% → MARGIN_CALL

        # Actually, let me adjust: the market_value in Position is abs(quantity)*price
        # But for futures, the notional_value = contract_multiplier * abs(quantity) * price
        # Let me just use the market_value directly for now

        # Actually, margin_ratio = margin_used / (abs(quantity) * price) = margin_used / market_value
        # If margin_used = 7000 and market_value = 100000 → ratio = 7% < 8% → MARGIN_CALL

        pos = Position("IF2406", -2, 3500.0, 100000.0, 0.0, 0.0, margin_used=7000.0)
        results = self.mtm.check_position(pos)

        self.assertGreaterEqual(len(results), 1)
        action = results[0]
        self.assertEqual(action.action, RiskAction.MARGIN_CALL)

    def test_force_close_triggered(self):
        """保证金严重不足 → FORCE_CLOSE"""
        from core.tracker import Position
        from core.risk_manager import RiskAction

        # 名义价值 100000，保证金 4000（4% < 5% 强平线）
        pos = Position("IF2406", -2, 3500.0, 100000.0, 0.0, 0.0, margin_used=4000.0)
        results = self.mtm.check_position(pos)

        self.assertGreaterEqual(len(results), 1)
        actions = [r.action for r in results]
        self.assertIn(RiskAction.FORCE_CLOSE, actions)

    def test_margin_sufficient(self):
        """保证金充足 → 无风险动作"""
        from core.tracker import Position

        # 名义价值 100000，保证金 12000（12% > 10% 初始保证金）
        pos = Position("IF2406", -2, 3500.0, 100000.0, 0.0, 0.0, margin_used=12000.0)
        results = self.mtm.check_position(pos)

        self.assertEqual(len(results), 0)

    def test_short_position_stop_loss(self):
        """空头止损: 价格上涨致亏损"""
        from core.tracker import Position
        from core.risk_manager import (
            MarkToMarketPolicy, StopLossConfig, RiskAction,
        )
        from core.config import MarginConfig

        stop_loss = StopLossConfig(stop_loss_pct=-0.10)
        mtm = MarkToMarketPolicy(stop_loss_config=stop_loss, margin_config=MarginConfig())

        # 空头: 均价 100，现价 115，亏损 15%
        pos = Position("IF2406", -2, 100.0, 230.0, -30.0, 0.0)
        results = mtm.check_position(pos)

        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].action, RiskAction.STOP_LOSS)


# ============================================================================
# 模块 3.5: 多持仓组合风险检查
# ============================================================================


class TestPortfolioRiskCheck(unittest.TestCase):
    """组合级别风险检查"""

    def test_check_multiple_positions(self):
        """多持仓批量检查"""
        from core.tracker import Position
        from core.risk_manager import (
            MarkToMarketPolicy, StopLossConfig, RiskAction,
        )
        from core.config import MarginConfig

        mtm = MarkToMarketPolicy(
            stop_loss_config=StopLossConfig(stop_loss_pct=-0.10),
            margin_config=MarginConfig(),
        )

        positions = {
            "000001.SZ": Position("000001.SZ", 1000, 10.0, 8500.0, -1500.0, 0.0),  # 亏损 15% → 止损
            "000002.SZ": Position("000002.SZ", 500, 20.0, 11000.0, 1000.0, 0.0),   # 盈利 → 无风险
            "IF2406": Position("IF2406", -2, 3500.0, 100000.0, 0.0, 0.0, margin_used=4000.0),  # 保证金不足 → 强平
        }

        all_results = mtm.check_portfolio(positions)

        # 应该有来自 000001 的止损 和 IF2406 的追保/强平
        self.assertGreaterEqual(len(all_results), 2)

        assets_with_actions = {r.asset for r in all_results}
        self.assertIn("000001.SZ", assets_with_actions)
        self.assertIn("IF2406", assets_with_actions)
        self.assertNotIn("000002.SZ", assets_with_actions)

    def test_empty_portfolio(self):
        """空持仓组合"""
        from core.risk_manager import MarkToMarketPolicy

        mtm = MarkToMarketPolicy()
        results = mtm.check_portfolio({})
        self.assertEqual(len(results), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)