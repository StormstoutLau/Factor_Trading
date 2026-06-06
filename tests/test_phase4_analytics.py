"""
Phase 4 测试：绩效计算层修复验证

验证:
1. E13: 年化收益率负收益保护
2. E14: 回撤持续期计算兼容各种输入类型
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_e13_negative_return_protection():
    """E13: 年化收益率负收益保护"""
    print("\n[Test] E13: 年化收益率负收益保护...")

    from core.analytics import PerformanceAnalyzer
    from core.tracker import PortfolioSnapshot

    analyzer = PerformanceAnalyzer()

    # 创建负收益快照 (-90%)
    snapshots = []
    for i in range(10):
        cr = -0.9 * (i / 9)  # 从0到-90%
        snapshots.append(PortfolioSnapshot(
            date=pd.Timestamp(f"2024-01-{i+2:02d}"),
            cash=100000 * (1 + cr),
            total_value=100000 * (1 + cr),
            positions={},
            daily_return=cr / 10 if i > 0 else 0,
            cumulative_return=cr
        ))

    analyzer.set_data(snapshots, pd.DataFrame())
    metrics = analyzer.calculate_performance_metrics()

    # 验证：total_return为-0.9，annual_return不应为NaN或异常值
    assert not np.isnan(metrics['annual_return']), "年化收益率不应为NaN"
    assert metrics['annual_return'] == -1.0, f"全部亏损时年化收益率应为-1.0, 实际为{metrics['annual_return']}"
    print(f"  ✓ 负收益保护正确: total_return={metrics['total_return']:.2%}, annual_return={metrics['annual_return']:.2%}")

    # 测试正常正收益
    snapshots2 = []
    for i in range(10):
        cr = 0.5 * (i / 9)  # 从0到50%
        snapshots2.append(PortfolioSnapshot(
            date=pd.Timestamp(f"2024-01-{i+2:02d}"),
            cash=100000 * (1 + cr),
            total_value=100000 * (1 + cr),
            positions={},
            daily_return=cr / 10 if i > 0 else 0,
            cumulative_return=cr
        ))

    analyzer.set_data(snapshots2, pd.DataFrame())
    metrics2 = analyzer.calculate_performance_metrics()

    assert metrics2['annual_return'] > 0, "正收益时年化收益率应大于0"
    print(f"  ✓ 正收益计算正确: annual_return={metrics2['annual_return']:.2%}")

    return True


def test_e14_drawdown_periods_types():
    """E14: 回撤持续期计算兼容各种输入类型"""
    print("\n[Test] E14: 回撤持续期兼容各种输入...")

    from core.analytics import PerformanceAnalyzer

    analyzer = PerformanceAnalyzer()

    # 测试1: numpy数组
    dd_np = np.array([0.0, 0.01, 0.02, 0.0, 0.03, 0.0])
    periods = analyzer._calculate_drawdown_periods(dd_np)
    assert periods.size > 0, "numpy数组输入应返回有效结果"
    print(f"  ✓ numpy数组输入正确: {periods}")

    # 测试2: Python列表
    dd_list = [0.0, 0.01, 0.02, 0.0, 0.03, 0.0]
    periods = analyzer._calculate_drawdown_periods(dd_list)
    assert periods.size > 0, "列表输入应返回有效结果"
    print(f"  ✓ 列表输入正确: {periods}")

    # 测试3: pandas Series
    dd_series = pd.Series([0.0, 0.01, 0.02, 0.0, 0.03, 0.0])
    periods = analyzer._calculate_drawdown_periods(dd_series)
    assert periods.size > 0, "Series输入应返回有效结果"
    print(f"  ✓ Series输入正确: {periods}")

    # 测试4: 全零输入（无回撤）
    dd_zero = [0.0, 0.0, 0.0]
    periods = analyzer._calculate_drawdown_periods(dd_zero)
    assert periods.size > 0, "全零输入应返回非空数组"
    assert periods[0] == 0, "无回撤时持续期应为0"
    print(f"  ✓ 全零输入正确: {periods}")

    return True


def run_all_tests():
    """运行所有Phase 4测试"""
    print("=" * 60)
    print("Phase 4 测试：绩效计算层修复验证")
    print("=" * 60)

    tests = [
        ("E13 负收益保护", test_e13_negative_return_protection),
        ("E14 回撤持续期", test_e14_drawdown_periods_types),
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
    print(f"Phase 4 结果: {passed} 通过, {failed} 失败")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
