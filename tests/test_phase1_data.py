"""
Phase 1 测试：数据层修复验证

验证:
1. E1: 因子缺失时用NaN而非最早数据
2. E2: 复权计算避免除零
3. E3: 因子数据缺失保持NaN
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))


def _create_minimal_data(tmpdir: Path, trade_dates: pd.DatetimeIndex, stocks=None):
    """创建最小数据集：所有DataManager需要的价格文件"""
    if stocks is None:
        stocks = ["AAPL"]
    # 交易日历
    trade_dates_df = pd.DataFrame(index=trade_dates)
    trade_dates_df.to_pickle(tmpdir / "trade_dates.pkl")

    # 价格数据
    for price_type in ["close", "open", "high", "low"]:
        df = pd.DataFrame({s: [100.0] * len(trade_dates) for s in stocks}, index=trade_dates)
        df.to_pickle(tmpdir / f"{price_type}.pkl")

    # 复权因子
    adj = pd.DataFrame({s: [1.0] * len(trade_dates) for s in stocks}, index=trade_dates)
    adj.to_pickle(tmpdir / "stock_adj.pkl")

    # 停牌数据
    suspend = pd.DataFrame({s: [False] * len(trade_dates) for s in stocks}, index=trade_dates)
    suspend.to_pickle(tmpdir / "suspend.pkl")

    # 行业数据
    industry = pd.DataFrame({s: ["Tech"] * len(trade_dates) for s in stocks}, index=trade_dates)
    industry.to_pickle(tmpdir / "industry.pkl")

    # ST数据
    st = pd.DataFrame({s: [False] * len(trade_dates) for s in stocks}, index=trade_dates)
    st.to_pickle(tmpdir / "st.pkl")


def test_e1_factor_no_future_info():
    """E1: 因子缺失时用NaN而非最早数据"""
    print("\n[Test] E1: 因子对齐避免未来信息泄露...")

    from core.data import DataManager
    from core.config import BacktestConfig

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # 创建交易日历
        trade_dates = pd.date_range("2024-01-02", "2024-01-10", freq="B")
        _create_minimal_data(tmpdir, trade_dates)

        # 创建因子数据：只有2024-01-05及之后
        factor_dates = pd.date_range("2024-01-05", "2024-01-10", freq="B")
        factor_data = pd.DataFrame(
            {"AAPL": [1.0, 2.0, 3.0, 4.0]},
            index=factor_dates,
        )
        factor_data.to_pickle(tmpdir / "factor_test.pkl")

        # 创建配置
        config = BacktestConfig(data_dir=tmpdir, factor_files=["factor_test.pkl"])

        # 创建DataManager
        dm = DataManager(config)
        dm.preload_data()

        # 加载因子
        factor = dm.load_factor("factor_test.pkl")

        # 验证：2024-01-02到2024-01-04应为NaN
        early_dates = pd.date_range("2024-01-02", "2024-01-04", freq="B")
        for d in early_dates:
            assert pd.isna(factor.loc[d, "AAPL"]), f"日期{d}不应有因子数据"

        # 验证：2024-01-05及之后应有数据
        later_dates = pd.date_range("2024-01-05", "2024-01-10", freq="B")
        for d in later_dates:
            assert pd.notna(factor.loc[d, "AAPL"]), f"日期{d}应有因子数据"

        print("  ✓ 早期日期因子为NaN，无未来信息泄露")
        print("  ✓ 后期日期因子正确填充")
        return True


def test_e2_adj_factor_no_div_zero():
    """E2: 复权计算避免除零"""
    print("\n[Test] E2: 复权计算除零保护...")

    from core.data import DataManager
    from core.config import BacktestConfig

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # 创建交易日历
        trade_dates = pd.date_range("2024-01-02", "2024-01-05", freq="B")
        _create_minimal_data(tmpdir, trade_dates, stocks=["AAPL", "TSLA"])

        # 覆盖复权因子：AAPL最新为0（除零场景）
        adj_data = pd.DataFrame(
            {"AAPL": [1.0, 1.0, 1.0, 0.0]},  # 最后一天为0
            index=trade_dates,
        )
        adj_data.to_pickle(tmpdir / "stock_adj.pkl")

        # 创建配置
        config = BacktestConfig(data_dir=tmpdir)

        # 创建DataManager
        dm = DataManager(config)
        dm.preload_data()

        # 获取后复权价格
        adj_price = dm.get_adj_price("close", adjustment_type="backward")

        # 验证：不应有inf或NaN
        assert not np.isinf(adj_price.values).any(), "后复权价格不应有inf"
        assert not pd.isna(adj_price.values).all(), "后复权价格不应全为NaN"

        print("  ✓ 复权因子为0时无除零错误")
        print(f"  ✓ 后复权价格范围: {adj_price.min().min():.2f} ~ {adj_price.max().max():.2f}")
        return True


def test_e3_factor_nan_preserved():
    """E3: 因子数据缺失保持NaN"""
    print("\n[Test] E3: 因子缺失保持NaN...")

    from core.data import DataManager
    from core.config import BacktestConfig

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # 创建交易日历
        trade_dates = pd.date_range("2024-01-02", "2024-01-05", freq="B")
        _create_minimal_data(tmpdir, trade_dates, stocks=["AAPL", "TSLA"])

        # 创建因子数据：有缺失 (使用AAPL和TSLA)
        factor_data = pd.DataFrame(
            {
                "AAPL": [1.0, np.nan, 3.0, 4.0],
                "TSLA": [np.nan, 2.0, np.nan, 4.0],
            },
            index=trade_dates,
        )
        factor_data.to_pickle(tmpdir / "factor_test.pkl")

        # 创建配置
        config = BacktestConfig(data_dir=tmpdir, factor_files=["factor_test.pkl"])

        # 创建DataManager
        dm = DataManager(config)
        dm.preload_data()

        # 加载因子
        factor = dm.load_factor("factor_test.pkl")

        # 验证：NaN保持为NaN
        assert pd.isna(factor.loc["2024-01-02", "TSLA"]), "TSLA的NaN应保持"
        assert pd.isna(factor.loc["2024-01-03", "AAPL"]), "AAPL的NaN应保持"

        # 验证：有效值保持有效
        assert factor.loc["2024-01-02", "AAPL"] == 1.0
        assert factor.loc["2024-01-03", "TSLA"] == 2.0

        print("  ✓ 因子NaN正确保持")
        print("  ✓ 因子有效值正确保留")
        return True


def run_all_tests():
    """运行所有Phase 1测试"""
    print("=" * 60)
    print("Phase 1 测试：数据层修复验证")
    print("=" * 60)

    tests = [
        ("E1 因子对齐", test_e1_factor_no_future_info),
        ("E2 复权除零", test_e2_adj_factor_no_div_zero),
        ("E3 因子NaN", test_e3_factor_nan_preserved),
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
    print(f"Phase 1 结果: {passed} 通过, {failed} 失败")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
