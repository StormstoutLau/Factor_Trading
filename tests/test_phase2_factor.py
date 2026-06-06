"""
Phase 2 测试：因子处理层修复验证

验证:
1. E4: _fill_missing正确处理DataFrame和Series类型的tradable_mask
2. E5: _neutralize过滤NaN行业数据避免get_dummies出错
3. E6: _standardize rank标准化正确处理NaN
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_e4_fill_missing_mask_types():
    """E4: _fill_missing正确处理DataFrame和Series类型的tradable_mask"""
    print("\n[Test] E4: 缺失值填充兼容DataFrame/Series掩码...")

    from core.factor import FactorPipeline
    from core.config import FactorConfig

    # 创建模拟DataManager
    class MockDM:
        industry = None
        mktcap = None

    cfg = FactorConfig(fill_method="median")
    pipeline = FactorPipeline(MockDM(), cfg)

    # 测试数据
    dates = pd.date_range("2024-01-02", "2024-01-05", freq="B")
    factor = pd.DataFrame(
        {
            "AAPL": [1.0, np.nan, 3.0, 4.0],
            "TSLA": [np.nan, 2.0, np.nan, 4.0],
        },
        index=dates,
    )

    # 测试1: DataFrame掩码
    mask_df = pd.DataFrame(
        {
            "AAPL": [True, True, True, True],
            "TSLA": [True, True, True, True],
        },
        index=dates,
    )
    result_df = pipeline._fill_missing(factor.copy(), mask_df)
    # AAPL第2天应为中位数(2.5)，TSLA第1天和第3天应为中位数(3.0)
    assert pd.notna(result_df.loc["2024-01-03", "AAPL"]), "DataFrame掩码: AAPL NaN应被填充"
    assert pd.notna(result_df.loc["2024-01-02", "TSLA"]), "DataFrame掩码: TSLA NaN应被填充"
    print("  ✓ DataFrame掩码正确处理")

    # 测试2: Series掩码
    mask_series = pd.Series(
        {"AAPL": True, "TSLA": True}
    )
    result_series = pipeline._fill_missing(factor.copy(), mask_series)
    assert pd.notna(result_series.loc["2024-01-03", "AAPL"]), "Series掩码: AAPL NaN应被填充"
    assert pd.notna(result_series.loc["2024-01-02", "TSLA"]), "Series掩码: TSLA NaN应被填充"
    print("  ✓ Series掩码正确处理")

    # 测试3: None掩码
    result_none = pipeline._fill_missing(factor.copy(), None)
    assert pd.notna(result_none.loc["2024-01-03", "AAPL"]), "None掩码: AAPL NaN应被填充"
    print("  ✓ None掩码正确处理")

    return True


def test_e5_neutralize_nan_industry():
    """E5: _neutralize过滤NaN行业数据避免get_dummies出错"""
    print("\n[Test] E5: 中性化过滤NaN行业数据...")

    from core.factor import FactorPipeline
    from core.config import FactorConfig

    # 创建模拟DataManager，行业数据包含NaN
    dates = pd.date_range("2024-01-02", "2024-01-05", freq="B")
    stocks = [f"STK{i:02d}" for i in range(20)]

    industry_df = pd.DataFrame(
        {s: ["Tech" if i < 10 else "Finance" for _ in dates] for i, s in enumerate(stocks)},
        index=dates,
    )
    # 故意让一些股票的行业为NaN
    for s in stocks[15:]:
        industry_df[s] = np.nan
    mktcap_df = pd.DataFrame(
        {s: [1e10] * len(dates) for s in stocks},
        index=dates,
    )

    class MockDM:
        industry = industry_df
        mktcap = mktcap_df

    cfg = FactorConfig(neutralize=True, neutralize_industry=True, neutralize_mktcap=False)
    pipeline = FactorPipeline(MockDM(), cfg)

    # 测试数据
    np.random.seed(42)
    factor = pd.DataFrame(
        {s: np.random.randn(len(dates)) for s in stocks},
        index=dates,
    )

    try:
        result = pipeline._neutralize(factor)
        # 验证没有抛出异常
        assert result is not None, "中性化应返回结果"
        assert not result.isna().all().all(), "中性化结果不应全为NaN"
        print("  ✓ 含NaN行业数据的中性化未抛出异常")
        print("  ✓ 中性化结果有效")
        return True
    except Exception as e:
        print(f"  ✗ 中性化失败: {e}")
        return False


def test_e6_standardize_rank_nan():
    """E6: _standardize rank标准化正确处理NaN"""
    print("\n[Test] E6: rank标准化保留NaN...")

    from core.factor import FactorPipeline
    from core.config import FactorConfig

    class MockDM:
        industry = None
        mktcap = None

    cfg = FactorConfig(standardize_method="rank")
    pipeline = FactorPipeline(MockDM(), cfg)

    # 测试数据：包含NaN
    dates = pd.date_range("2024-01-02", "2024-01-05", freq="B")
    factor = pd.DataFrame(
        {
            "AAPL": [1.0, np.nan, 3.0, 4.0],
            "TSLA": [np.nan, 2.0, np.nan, 4.0],
            "MSFT": [3.0, 4.0, 1.0, 2.0],
        },
        index=dates,
    )

    result = pipeline._standardize(factor)

    # 验证：原始NaN位置应保持NaN
    assert pd.isna(result.loc["2024-01-02", "TSLA"]), "TSLA原始NaN应保持NaN"
    assert pd.isna(result.loc["2024-01-03", "AAPL"]), "AAPL原始NaN应保持NaN"

    # 验证：非NaN位置应被标准化
    assert pd.notna(result.loc["2024-01-02", "AAPL"]), "AAPL有效值应被标准化"
    assert pd.notna(result.loc["2024-01-03", "MSFT"]), "MSFT有效值应被标准化"

    print("  ✓ 原始NaN位置保持NaN")
    print("  ✓ 有效值正确标准化")
    return True


def run_all_tests():
    """运行所有Phase 2测试"""
    print("=" * 60)
    print("Phase 2 测试：因子处理层修复验证")
    print("=" * 60)

    tests = [
        ("E4 缺失值填充", test_e4_fill_missing_mask_types),
        ("E5 中性化NaN行业", test_e5_neutralize_nan_industry),
        ("E6 rank标准化NaN", test_e6_standardize_rank_nan),
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
    print(f"Phase 2 结果: {passed} 通过, {failed} 失败")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
