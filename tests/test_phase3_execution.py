"""
Phase 3 测试：交易执行层修复验证

验证:
1. E10: calculate_liquidation_value卖出成本扣除正确
2. E16: execute_order净金额计算正确（买入含成本，卖出扣成本）
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_e10_liquidation_cost():
    """E10: 卖出清算价值应扣除成本"""
    print("\n[Test] E10: 卖出清算价值扣除成本...")

    from core.execution import ExecutionSimulator
    from core.config import CostConfig
    from core.pending import OrderSide

    cfg = CostConfig(commission_rate=0.0003, commission_min=5.0, stamp_tax_rate=0.001, slippage_pct=0.001)
    sim = ExecutionSimulator(cfg)

    # 卖出1000股，价格10元，金额10000元
    # 成本 = 佣金max(3,5)=5 + 印花税10 + 滑点10 = 25
    # 净额应为 10000 - 25 = 9975
    net = sim.calculate_liquidation_value("AAPL", 1000, pd.Timestamp("2024-01-02"), 10.0)

    expected_cost = 5.0 + 10000 * 0.001 + 10000 * 0.001  # 5 + 10 + 10 = 25
    expected_net = 10000 - expected_cost

    assert abs(net - expected_net) < 1e-6, f"清算价值应为{expected_net}, 实际为{net}"
    assert net < 10000, "清算价值应小于总金额（因为扣除了成本）"
    print(f"  ✓ 清算价值正确: {net:.2f} (成本: {expected_cost:.2f})")
    return True


def test_e16_net_amount_calculation():
    """E16: 买入净金额应含成本，卖出净金额应扣成本"""
    print("\n[Test] E16: 交易净金额计算...")

    from core.execution import ExecutionSimulator
    from core.config import CostConfig
    from core.pending import OrderSide

    cfg = CostConfig(commission_rate=0.0003, commission_min=5.0, stamp_tax_rate=0.001, slippage_pct=0.001)
    sim = ExecutionSimulator(cfg)

    date = pd.Timestamp("2024-01-02")

    # 买入1000股 @ 10元
    success_buy, trade_buy = sim.execute_order("AAPL", OrderSide.BUY, 1000, date, 10.0)
    assert success_buy, "买入应成功"

    expected_cost_buy = 5.0 + 10000 * 0.001  # 佣金5 + 滑点10 = 15（买入无印花税）
    expected_net_buy = 10000 + expected_cost_buy  # 总支出 = 金额 + 成本

    assert abs(trade_buy.net_amount - expected_net_buy) < 1e-6, \
        f"买入净金额应为{expected_net_buy}, 实际为{trade_buy.net_amount}"
    assert trade_buy.net_amount > 10000, "买入净金额应大于金额（因为包含成本）"
    print(f"  ✓ 买入净金额正确: {trade_buy.net_amount:.2f} (金额: {trade_buy.amount:.2f}, 成本: {trade_buy.cost:.2f})")

    # 卖出1000股 @ 10元
    success_sell, trade_sell = sim.execute_order("AAPL", OrderSide.SELL, 1000, date, 10.0)
    assert success_sell, "卖出应成功"

    expected_cost_sell = 5.0 + 10000 * 0.001 + 10000 * 0.001  # 佣金5 + 印花税10 + 滑点10 = 25
    expected_net_sell = 10000 - expected_cost_sell  # 净收入 = 金额 - 成本

    assert abs(trade_sell.net_amount - expected_net_sell) < 1e-6, \
        f"卖出净金额应为{expected_net_sell}, 实际为{trade_sell.net_amount}"
    assert trade_sell.net_amount < 10000, "卖出净金额应小于金额（因为扣除了成本）"
    print(f"  ✓ 卖出净金额正确: {trade_sell.net_amount:.2f} (金额: {trade_sell.amount:.2f}, 成本: {trade_sell.cost:.2f})")

    return True


def test_tracker_cash_update():
    """验证tracker现金更新与execution一致"""
    print("\n[Test] 持仓跟踪器现金更新一致性...")

    from core.execution import ExecutionSimulator
    from core.tracker import PositionTracker
    from core.config import CostConfig
    from core.pending import OrderSide

    cfg = CostConfig(commission_rate=0.0003, commission_min=5.0, stamp_tax_rate=0.001, slippage_pct=0.001)
    sim = ExecutionSimulator(cfg)
    tracker = PositionTracker(n_stocks=1, initial_capital=100000.0)

    date = pd.Timestamp("2024-01-02")

    # 买入
    success, trade = sim.execute_order("AAPL", OrderSide.BUY, 1000, date, 10.0)
    tracker.execute_trade(trade)

    expected_cash = 100000.0 - trade.net_amount
    assert abs(tracker.get_cash() - expected_cash) < 1e-6, \
        f"买入后现金应为{expected_cash}, 实际为{tracker.get_cash()}"
    print(f"  ✓ 买入后现金正确: {tracker.get_cash():.2f}")

    # 卖出
    success, trade = sim.execute_order("AAPL", OrderSide.SELL, 1000, date, 11.0)
    tracker.execute_trade(trade)

    # 卖出后现金 = 之前现金 + 卖出净收入
    expected_cash_after_sell = expected_cash + trade.net_amount
    assert abs(tracker.get_cash() - expected_cash_after_sell) < 1e-6, \
        f"卖出后现金应为{expected_cash_after_sell}, 实际为{tracker.get_cash()}"
    print(f"  ✓ 卖出后现金正确: {tracker.get_cash():.2f}")

    return True


def run_all_tests():
    """运行所有Phase 3测试"""
    print("=" * 60)
    print("Phase 3 测试：交易执行层修复验证")
    print("=" * 60)

    tests = [
        ("E10 清算成本", test_e10_liquidation_cost),
        ("E16 净金额计算", test_e16_net_amount_calculation),
        ("Tracker现金更新", test_tracker_cash_update),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            if test_fn():
                passed += 1
        except Exception as e:
            failed += 1
            print(f"  ✗ {name} 失败: {e}")
            import traceback

            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"Phase 3 结果: {passed} 通过, {failed} 失败")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
