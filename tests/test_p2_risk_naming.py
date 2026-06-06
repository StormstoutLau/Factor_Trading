"""
P2.2 TDD: 风险模块命名澄清测试

验证风险模块职责划分和命名：
1. risk_manager.py → 主动盯市风险管理器（个股止损、保证金检查）
2. risk_monitor.py → 多维度风险监控器（五维风控、预警）
3. 命名澄清: risk_manager.RiskAction, risk_monitor.MonitorAction
4. 无命名冲突，职责清晰
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest


class TestRiskModuleNaming(unittest.TestCase):
    """风险模块命名和职责澄清"""

    def test_risk_manager_has_RiskAction(self):
        """risk_manager.py 有 RiskAction 枚举"""
        from core.risk_manager import RiskAction

        self.assertTrue(hasattr(RiskAction, "STOP_LOSS"))
        self.assertTrue(hasattr(RiskAction, "FORCE_CLOSE"))
        self.assertTrue(hasattr(RiskAction, "MARGIN_CALL"))

    def test_risk_monitor_does_not_have_RiskAction(self):
        """risk_monitor.py 不应再有 RiskAction，应改为 MonitorAction"""
        import core.risk_monitor as rm

        self.assertFalse(
            hasattr(rm, "RiskAction"),
            "risk_monitor 应将 RiskAction 重命名为 MonitorAction"
        )
        self.assertTrue(
            hasattr(rm, "MonitorAction"),
            "risk_monitor 应有 MonitorAction"
        )

    def test_MonitorAction_has_correct_fields(self):
        """MonitorAction 应有正确的动作类型"""
        from core.risk_monitor import MonitorAction

        ma = MonitorAction(action_type='hold')
        self.assertEqual(ma.action_type, 'hold')

    def test_risk_manager_module_doc_mentions_purpose(self):
        """risk_manager 模块文档应说明盯市职责"""
        import core.risk_manager as rm

        doc = rm.__doc__
        self.assertIn("盯市", doc)
        self.assertIn("止损", doc)
        self.assertIn("保证金", doc)

    def test_risk_monitor_module_doc_mentions_purpose(self):
        """risk_monitor 模块文档应说明五维监控职责"""
        import core.risk_monitor as rm

        doc = rm.__doc__
        self.assertIn("多维度", doc)
        self.assertIn("监控", doc)
        self.assertIn("五维", doc)

    def test_risk_manager_mark_to_market_exists(self):
        """risk_manager 有 MarkToMarketPolicy"""
        from core.risk_manager import MarkToMarketPolicy

        policy = MarkToMarketPolicy()
        self.assertTrue(hasattr(policy, "check_position"))
        self.assertTrue(hasattr(policy, "check_portfolio"))

    def test_risk_monitor_base_monitor_exists(self):
        """risk_monitor 有 BaseRiskMonitor"""
        from core.risk_monitor import BaseRiskMonitor

        self.assertTrue(hasattr(BaseRiskMonitor, "monitor"))

    def test_imports_no_name_collision(self):
        """可同时导入两个模块不会冲突"""
        from core.risk_manager import RiskAction
        from core.risk_monitor import MonitorAction, RiskLevel

        # 无语法错误即可
        self.assertEqual(RiskAction.STOP_LOSS.name, "STOP_LOSS")
        self.assertEqual(RiskLevel.SAFE.value, 0)
        ma = MonitorAction(action_type='clear')
        self.assertEqual(ma.action_type, 'clear')


class TestRiskModuleResponsibilities(unittest.TestCase):
    """风险模块职责划分验证"""

    def test_risk_manager_handles_position_level_risk(self):
        """risk_manager 处理个股持仓级风险"""
        from core.config import MarginConfig
        from core.risk_manager import StopLossConfig, MarkToMarketPolicy
        from core.tracker import Position

        # 构造持仓
        pos = Position(
            stock="IF2406",
            quantity=-2,
            avg_cost=3500.0,
            market_value=7000.0,
            unrealized_pnl=-1000.0,
            realized_pnl=0.0,
            margin_used=700.0,
        )

        policy = MarkToMarketPolicy(
            stop_loss_config=StopLossConfig(stop_loss_pct=-0.10, enabled=True),
            margin_config=MarginConfig(
                initial_margin_ratio=0.10,
                maintenance_margin_ratio=0.08,
                force_liquidation_ratio=0.05,
            )
        )

        actions = policy.check_position(pos)
        # 能正常返回风险动作列表
        self.assertIsInstance(actions, list)

    def test_risk_monitor_handles_multi_dimension(self):
        """risk_monitor 处理多维度监控"""
        from core.risk_monitor import FundamentalMonitor, RiskLevel

        monitor = FundamentalMonitor()
        signal = monitor.monitor(
            symbol="TEST",
            financial_data={'debt_ratio': 0.5, 'operating_cashflow': 1000},
        )
        self.assertEqual(signal.level, RiskLevel.SAFE)


if __name__ == "__main__":
    unittest.main(verbosity=2)