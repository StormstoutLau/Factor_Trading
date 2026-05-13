"""
最终集成测试：运行所有Phase测试并验证整体一致性
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def run_phase_tests():
    """运行所有Phase测试"""
    print("=" * 70)
    print("最终集成测试：运行所有Phase测试")
    print("=" * 70)

    phases = [
        ("Phase 1: 数据层修复", "tests.test_phase1_data"),
        ("Phase 2: 因子处理层修复", "tests.test_phase2_factor"),
        ("Phase 3: 交易执行层修复", "tests.test_phase3_execution"),
        ("Phase 4: 绩效计算层修复", "tests.test_phase4_analytics"),
        ("Phase 5: 业务逻辑层修复", "tests.test_phase5_business"),
    ]

    all_passed = True
    results = []

    for phase_name, module_name in phases:
        print(f"\n{'='*70}")
        print(f"运行 {phase_name}")
        print(f"{'='*70}")

        try:
            module = __import__(module_name, fromlist=["run_all_tests"])
            success = module.run_all_tests()
            results.append((phase_name, success))
            if not success:
                all_passed = False
        except Exception as e:
            print(f"  ✗ {phase_name} 执行失败: {e}")
            results.append((phase_name, False))
            all_passed = False

    # 汇总结果
    print(f"\n{'='*70}")
    print("集成测试汇总")
    print(f"{'='*70}")

    for phase_name, success in results:
        status = "✓ 通过" if success else "✗ 失败"
        print(f"  {status}: {phase_name}")

    total = len(results)
    passed = sum(1 for _, s in results if s)

    print(f"\n总计: {passed}/{total} 通过")
    print(f"{'='*70}")

    return all_passed


def test_cross_layer_consistency():
    """测试跨层一致性"""
    print(f"\n{'='*70}")
    print("跨层一致性测试")
    print(f"{'='*70}")

    import numpy as np
    import pandas as pd
    from core.execution import ExecutionSimulator, Trade
    from core.tracker import PositionTracker
    from core.config import CostConfig
    from core.pending import OrderSide

    # 创建完整链路：Execution -> Tracker -> Analytics
    cfg = CostConfig(commission_rate=0.0003, commission_min=5.0, stamp_tax_rate=0.001, slippage_pct=0.001)
    executor = ExecutionSimulator(cfg)
    tracker = PositionTracker(n_stocks=2, initial_capital=100000.0)

    date = pd.Timestamp("2024-01-02")

    # 买入
    success, trade = executor.execute_order("AAPL", OrderSide.BUY, 1000, date, 10.0)
    tracker.execute_trade(trade)

    # 验证：买入后现金减少
    assert tracker.get_cash() < 100000.0, "买入后现金应减少"
    print(f"  ✓ 买入后现金正确: {tracker.get_cash():.2f}")

    # 更新市值
    prices = pd.Series({"AAPL": 11.0})
    tracker.update_market_values(date, prices)

    # 验证：市值更新后总价值增加
    total_value = tracker.get_total_value()
    assert total_value > tracker.get_cash(), "总市值应大于现金"
    print(f"  ✓ 市值更新后总价值: {total_value:.2f}")

    # 卖出
    success, trade = executor.execute_order("AAPL", OrderSide.SELL, 1000, date, 11.0)
    tracker.execute_trade(trade)

    # 验证：卖出后现金增加
    final_cash = tracker.get_cash()
    assert final_cash > 90000.0, "卖出后现金应接近初始资金"
    print(f"  ✓ 卖出后现金: {final_cash:.2f}")

    # 验证无持仓
    positions = tracker.get_all_positions()
    assert len(positions) == 0, "清仓后应无持仓"
    print(f"  ✓ 清仓后无持仓")

    return True


def test_data_factor_pipeline():
    """测试数据层到因子处理层的数据流"""
    print(f"\n{'='*70}")
    print("数据流一致性测试")
    print(f"{'='*70}")

    import tempfile
    import numpy as np
    import pandas as pd
    from core.data import DataManager
    from core.factor import FactorPipeline
    from core.config import BacktestConfig, FactorConfig

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # 创建测试数据
        trade_dates = pd.date_range("2024-01-02", "2024-01-10", freq="B")
        stocks = ["AAPL", "TSLA"]

        trade_dates_df = pd.DataFrame(index=trade_dates)
        trade_dates_df.to_pickle(tmpdir / "trade_dates.pkl")

        for price_type in ["close", "open", "high", "low"]:
            df = pd.DataFrame({s: [100.0] * len(trade_dates) for s in stocks}, index=trade_dates)
            df.to_pickle(tmpdir / f"{price_type}.pkl")

        adj = pd.DataFrame({s: [1.0] * len(trade_dates) for s in stocks}, index=trade_dates)
        adj.to_pickle(tmpdir / "stock_adj.pkl")

        for fname in ["suspend.pkl", "industry.pkl", "st.pkl"]:
            if "industry" in fname:
                df = pd.DataFrame({s: ["Tech"] * len(trade_dates) for s in stocks}, index=trade_dates)
            else:
                df = pd.DataFrame({s: [False] * len(trade_dates) for s in stocks}, index=trade_dates)
            df.to_pickle(tmpdir / fname)

        # 创建因子数据（含NaN）
        factor_data = pd.DataFrame(
            {"AAPL": [1.0, np.nan, 3.0, 4.0, 5.0], "TSLA": [np.nan, 2.0, np.nan, 4.0, 5.0]},
            index=trade_dates[:5],
        )
        factor_data.to_pickle(tmpdir / "factor_test.pkl")

        # 加载数据
        config = BacktestConfig(data_dir=tmpdir, factor_files=["factor_test.pkl"])
        dm = DataManager(config)
        dm.preload_data()

        # 验证数据层修复
        factor = dm.load_factor("factor_test.pkl")
        assert pd.isna(factor.loc["2024-01-02", "TSLA"]), "TSLA NaN应保持"
        print(f"  ✓ 数据层NaN保持正确")

        # 因子处理
        pipeline = FactorPipeline(dm, FactorConfig(standardize_method="zscore", fill_method="median"))
        processed = pipeline.process(factor)

        # 验证因子层修复
        assert not processed.isna().all().all(), "处理后不应全为NaN"
        print(f"  ✓ 因子处理正确: shape={processed.shape}")

    return True


def run_all_tests():
    """运行最终集成测试"""
    print("=" * 70)
    print("最终集成测试")
    print("=" * 70)

    # 1. 运行所有Phase测试
    phase_passed = run_phase_tests()

    # 2. 跨层一致性测试
    consistency_passed = True
    try:
        consistency_passed = test_cross_layer_consistency()
    except Exception as e:
        print(f"  ✗ 跨层一致性测试失败: {e}")
        consistency_passed = False

    # 3. 数据流测试
    dataflow_passed = True
    try:
        dataflow_passed = test_data_factor_pipeline()
    except Exception as e:
        print(f"  ✗ 数据流测试失败: {e}")
        dataflow_passed = False

    # 最终汇总
    print(f"\n{'='*70}")
    print("最终集成测试汇总")
    print(f"{'='*70}")
    print(f"  Phase测试: {'✓ 通过' if phase_passed else '✗ 失败'}")
    print(f"  跨层一致性: {'✓ 通过' if consistency_passed else '✗ 失败'}")
    print(f"  数据流一致性: {'✓ 通过' if dataflow_passed else '✗ 失败'}")

    all_passed = phase_passed and consistency_passed and dataflow_passed
    print(f"\n  最终结果: {'✓ 全部通过' if all_passed else '✗ 存在失败'}")
    print(f"{'='*70}")

    return all_passed


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
