"""P-060a 因子处理分支单元测试（T-A06..A10）。

对应 [IMPL_p060a §4.2](../../docs/IMPL_p060a_implementation.md)：零生产改动；
去极值只断言「界 + 单调」（D-01 软截断非社区主流，但不改实现）。
外部对照：X9 scipy winsorize（硬截断）、X11 jqfactor MAD、X14 中性化 OLS 残差。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import pytest
from scipy.stats import spearmanr

from core.config import FactorConfig
from core.factor import FactorPipeline

_DATE = pd.Timestamp("2024-01-02")


@dataclass
class FakeDM:
    """仅提供 `_neutralize` 所需的 industry / mktcap 两个属性。"""

    industry: pd.DataFrame | None = None
    mktcap: pd.DataFrame | None = None


def make_pipeline(dm: FakeDM | None = None, **overrides) -> FactorPipeline:
    cfg = FactorConfig(**overrides)
    return FactorPipeline(dm or FakeDM(), cfg)


def one_row(values: list[float], columns: list[str] | None = None) -> pd.DataFrame:
    cols = columns or [f"S{i:02d}" for i in range(len(values))]
    return pd.DataFrame([values], index=[_DATE], columns=cols)


def neutral_dm(n: int, groups: int = 3) -> FakeDM:
    """构造 n 只股票、groups 个行业、市值递增的确定性数据。"""
    cols = [f"S{i:02d}" for i in range(n)]
    industry = pd.DataFrame([[f"IND{i % groups}" for i in range(n)]], index=[_DATE], columns=cols)
    mktcap = pd.DataFrame([[1e9 * (1.0 + i) for i in range(n)]], index=[_DATE], columns=cols)
    return FakeDM(industry=industry, mktcap=mktcap)


def neutral_values(n: int) -> list[float]:
    return [0.1 * i + (0.3 if i % 2 else -0.2) for i in range(n)]


# ---------------------------------------------------------------------------
# T-A06 MAD 去极值（软截断：只断言界与单调）
# ---------------------------------------------------------------------------


def test_p060a_a06a_mad_bounds_hold():
    """T-A06a | oracle=cross-check：[1,2,3,100] n=3 → median 2.5 / MAD 1 / 界 [-0.5,5.5]"""
    pipe = make_pipeline(winsorize_method="mad", winsorize_n=3.0)
    out = pipe._winsorize_mad(one_row([1.0, 2.0, 3.0, 100.0]))

    assert out.iloc[0].min() >= -0.5 - 1e-9
    assert out.iloc[0].max() <= 5.5 + 1e-9


def test_p060a_a06b_mad_output_is_monotonic():
    """T-A06b | oracle=invariant：软截断保持单调，且 100 被压到上界附近"""
    pipe = make_pipeline(winsorize_method="mad", winsorize_n=3.0)
    out = pipe._winsorize_mad(one_row([1.0, 2.0, 3.0, 100.0])).iloc[0].to_numpy()

    assert np.all(np.diff(out) >= -1e-12)
    assert 4.5 < out[-1] <= 5.5 + 1e-12


# ---------------------------------------------------------------------------
# T-A07 百分位去极值
# ---------------------------------------------------------------------------


def test_p060a_a07_percentile_bounds_hold():
    """T-A07 | oracle=cross-check：0..9、pct=(0.05,0.95) → 界 [0.45,8.55]"""
    pipe = make_pipeline(winsorize_method="percentile", winsorize_pct=(0.05, 0.95))
    out = pipe._winsorize_percentile(one_row([float(i) for i in range(10)])).iloc[0]

    assert out.min() >= 0.45 - 1e-9
    assert out.max() <= 8.55 + 1e-9


# ---------------------------------------------------------------------------
# T-A08 sigma 去极值
# ---------------------------------------------------------------------------


def test_p060a_a08a_sigma_zero_std_row_unchanged():
    """T-A08a | oracle=boundary：std=0 行原样返回"""
    pipe = make_pipeline(winsorize_method="sigma", winsorize_n=2.0)
    out = pipe._winsorize_sigma(one_row([5.0, 5.0, 5.0]))

    assert out.iloc[0].tolist() == [5.0, 5.0, 5.0]


def test_p060a_a08b_sigma_bounds_hold():
    """T-A08b | oracle=cross-check：界 mean±n·std（pandas std, ddof=1）"""
    pipe = make_pipeline(winsorize_method="sigma", winsorize_n=2.0)
    row = pd.Series([1.0, 2.0, 3.0, 4.0])
    out = pipe._winsorize_sigma(one_row(row.tolist())).iloc[0]

    lower = row.mean() - 2.0 * row.std()
    upper = row.mean() + 2.0 * row.std()
    assert out.min() >= lower - 1e-9
    assert out.max() <= upper + 1e-9


# ---------------------------------------------------------------------------
# T-A09 缺失填充（3×3 矩阵）
# ---------------------------------------------------------------------------


def test_p060a_a09a_median_fill_with_dataframe_mask():
    """T-A09a | oracle=closed-form：仅可交易 NaN 被填为当日可交易中位数 2.0"""
    pipe = make_pipeline(fill_method="median")
    factor = pd.DataFrame([[1.0, np.nan, 3.0, np.nan]], index=[_DATE], columns=list("ABCD"))
    mask = pd.DataFrame([[True, True, True, False]], index=[_DATE], columns=list("ABCD"))

    out = pipe._fill_missing(factor, mask)

    assert out.loc[_DATE, "B"] == pytest.approx(2.0)
    assert pd.isna(out.loc[_DATE, "D"])


def test_p060a_a09b_series_mask_broadcasts_like_dataframe():
    """T-A09b | oracle=cross-check：Series 掩码按列广播，结果与 DataFrame 掩码一致"""
    pipe = make_pipeline(fill_method="mean")
    factor = pd.DataFrame([[1.0, np.nan, 3.0, np.nan]], index=[_DATE], columns=list("ABCD"))
    mask_series = pd.Series([True, True, True, False], index=list("ABCD"))
    mask_df = pd.DataFrame([mask_series.to_numpy()], index=[_DATE], columns=list("ABCD"))

    out_series = pipe._fill_missing(factor, mask_series)
    out_df = pipe._fill_missing(factor, mask_df)

    pd.testing.assert_frame_equal(out_series, out_df)
    assert out_series.loc[_DATE, "B"] == pytest.approx(2.0)


def test_p060a_a09c_no_mask_fills_by_row_statistic():
    """T-A09c | oracle=closed-form：无掩码时 median/mean→2.0、zero→0.0"""
    factor = pd.DataFrame([[1.0, np.nan, 3.0]], index=[_DATE], columns=list("ABC"))

    med = make_pipeline(fill_method="median")._fill_missing(factor)
    mean = make_pipeline(fill_method="mean")._fill_missing(factor)
    zero = make_pipeline(fill_method="zero")._fill_missing(factor)

    assert med.loc[_DATE, "B"] == pytest.approx(2.0)
    assert mean.loc[_DATE, "B"] == pytest.approx(2.0)
    assert zero.loc[_DATE, "B"] == pytest.approx(0.0)


def test_p060a_a09d_untradable_nan_survives_zero_fill():
    """T-A09d | oracle=invariant：zero 填充也不得填不可交易位置的 NaN"""
    pipe = make_pipeline(fill_method="zero")
    factor = pd.DataFrame([[np.nan, np.nan]], index=[_DATE], columns=list("AB"))
    mask = pd.DataFrame([[True, False]], index=[_DATE], columns=list("AB"))

    out = pipe._fill_missing(factor, mask)

    assert out.loc[_DATE, "A"] == pytest.approx(0.0)
    assert pd.isna(out.loc[_DATE, "B"])


# ---------------------------------------------------------------------------
# T-A10 中性化 / 反转 / 标准化
# ---------------------------------------------------------------------------


def test_p060a_a10a_neutralize_skips_under_ten_stocks():
    """T-A10a | oracle=boundary：可中性化样本 <10 → 原值返回"""
    pipe = make_pipeline(neutralize=True, neutralize_industry=True, neutralize_mktcap=True)
    pipe.dm = neutral_dm(9)
    factor = one_row(neutral_values(9))

    out = pipe._neutralize(factor)

    pd.testing.assert_frame_equal(out, factor)
    assert pipe.neutralize_skip_counts == {"degenerate_columns": 0, "regression": 0}


def test_p060a_a10b_neutralize_residuals_orthogonal_to_industry():
    """T-A10b | oracle=invariant：残差均值≈0、行业组均值≈0、两桶计数为 0"""
    pipe = make_pipeline(neutralize=True, neutralize_industry=True, neutralize_mktcap=True)
    dm = neutral_dm(12, groups=3)
    pipe.dm = dm
    factor = one_row(neutral_values(12))

    out = pipe._neutralize(factor)
    residuals = out.iloc[0].to_numpy()

    assert residuals.mean() == pytest.approx(0.0, abs=1e-9)
    for group in dm.industry.iloc[0].unique():
        cols = dm.industry.iloc[0][dm.industry.iloc[0] == group].index
        assert residuals[[factor.columns.get_loc(c) for c in cols]].mean() == pytest.approx(
            0.0, abs=1e-9
        )
    assert pipe.neutralize_skip_counts == {"degenerate_columns": 0, "regression": 0}


def test_p060a_a10c_lstsq_failure_keeps_values(monkeypatch):
    """T-A10c | oracle=contract：回归异常 → regression 桶 +1、sink 收到、原值保留"""
    pipe = make_pipeline(neutralize=True, neutralize_industry=True, neutralize_mktcap=True)
    pipe.dm = neutral_dm(12)
    factor = one_row(neutral_values(12))
    errors: list[tuple[object, str, BaseException]] = []
    pipe.set_error_sink(lambda d, k, e: errors.append((d, k, e)))

    def boom(*args, **kwargs):
        raise np.linalg.LinAlgError("singular")

    monkeypatch.setattr(np.linalg, "lstsq", boom)
    out = pipe._neutralize(factor)

    assert pipe.neutralize_skip_counts["regression"] == 1
    assert errors and errors[0][1] == "factor"
    pd.testing.assert_frame_equal(out, factor)


def test_p060a_a10d_std_failure_counts_degenerate_bucket(monkeypatch):
    """T-A10d | oracle=contract：去常数列异常 → degenerate_columns 桶 +1 且原值保留"""
    pipe = make_pipeline(neutralize=True, neutralize_industry=True, neutralize_mktcap=True)
    pipe.dm = neutral_dm(12)
    factor = one_row(neutral_values(12))
    errors: list[tuple[object, str, BaseException]] = []
    pipe.set_error_sink(lambda d, k, e: errors.append((d, k, e)))

    def boom(*args, **kwargs):
        raise ValueError("std failure")

    monkeypatch.setattr(np, "std", boom)
    out = pipe._neutralize(factor)

    assert pipe.neutralize_skip_counts["degenerate_columns"] == 1
    assert errors and errors[0][1] == "factor"
    pd.testing.assert_frame_equal(out, factor)


def test_p060a_a10e_reverse_is_negation():
    """T-A10e | oracle=closed-form：reverse = -factor；秩相关系数 = -1"""
    pipe = make_pipeline()
    factor = one_row([1.0, 2.0, 3.0, 10.0])

    out = pipe._reverse(factor)

    pd.testing.assert_frame_equal(out, -factor)
    rho, _ = spearmanr(factor.iloc[0].to_numpy(), out.iloc[0].to_numpy())
    assert rho == pytest.approx(-1.0)


def test_p060a_a10f_standardize_three_methods():
    """T-A10f | oracle=invariant：zscore/rank 均值≈0、std≈1；minmax∈[0,1]；rank 保持 NaN"""
    factor = pd.DataFrame([[1.0, 2.0, 3.0]], index=[_DATE], columns=list("ABC"))

    z = make_pipeline(standardize_method="zscore")._standardize(factor).iloc[0]
    r = make_pipeline(standardize_method="rank")._standardize(factor).iloc[0]
    m = make_pipeline(standardize_method="minmax")._standardize(factor).iloc[0]

    assert z.mean() == pytest.approx(0.0, abs=1e-12)
    assert z.std() == pytest.approx(1.0, abs=1e-12)
    assert r.mean() == pytest.approx(0.0, abs=1e-12)
    assert r.std() == pytest.approx(1.0, abs=1e-12)
    assert m.min() == pytest.approx(0.0)
    assert m.max() == pytest.approx(1.0)

    factor_nan = pd.DataFrame([[1.0, np.nan, 3.0]], index=[_DATE], columns=list("ABC"))
    r_nan = make_pipeline(standardize_method="rank")._standardize(factor_nan).iloc[0]
    assert r_nan["A"] == pytest.approx(-0.70710678, rel=1e-6)
    assert pd.isna(r_nan["B"])
    assert r_nan["C"] == pytest.approx(0.70710678, rel=1e-6)


def test_p060a_a10g_constant_rows_collapse_to_zero():
    """T-A10g | oracle=boundary：全零/常数列 → std=0 → zscore/minmax 归 0"""
    factor = pd.DataFrame([[7.0, 7.0, 7.0]], index=[_DATE], columns=list("ABC"))

    z = make_pipeline(standardize_method="zscore")._standardize(factor)
    m = make_pipeline(standardize_method="minmax")._standardize(factor)

    assert z.iloc[0].tolist() == [0.0, 0.0, 0.0]
    assert m.iloc[0].tolist() == [0.0, 0.0, 0.0]
