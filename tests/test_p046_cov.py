"""P-046a 协方差单一入口验收（AC-C-01c / I8 / 退化输入）。

口径：DESIGN §5.2（C1 = sklearn ``LedoitWolf``，identity 目标）；
RESEARCH §14 E1b/E2（LW 2004 Eq.(5)/(14)）与 §12 Step 6 版本核验表。
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import pytest
from sklearn.covariance import LedoitWolf

from core.config import OptimizerConfig
from core.portfolio import COV_ESTIMATORS, _psd_project, build_optimizer, estimate_cov


def _returns(n_obs: int = 60, n: int = 5, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame(rng.normal(0.0, 0.01, size=(n_obs, n)), columns=[f"S{i}" for i in range(n)])


def test_ac_c_01c_matches_sklearn_ledoitwolf():
    rets = _returns()
    got = estimate_cov(rets, method="ledoit_wolf").to_numpy()
    expected = LedoitWolf().fit(rets.to_numpy()).covariance_
    assert np.abs(got - expected).max() < 1e-15


def test_lw_2x2_closed_form():
    """LW 2004 Eq.(5)：Σ̂ = α·μI + (1−α)S，μ = tr(S)/p（结构对拍，非录制）。"""
    rets = _returns(n_obs=6, n=2, seed=13)
    x = rets.to_numpy()
    got = estimate_cov(rets, method="ledoit_wolf").to_numpy()
    # sklearn 的 S 为有偏经验协方差（除以 n，非 n-1）
    sample = np.cov(x, rowvar=False, ddof=0)
    alpha = float(LedoitWolf().fit(x).shrinkage_)
    mu = float(np.trace(sample)) / 2.0
    rebuilt = alpha * mu * np.eye(2) + (1.0 - alpha) * sample
    assert np.abs(got - rebuilt).max() < 1e-15


def test_psd_projection_non_psd_input():
    bad = np.array([[1.0, 2.0], [2.0, 1.0]])  # 特征值 {3, -1}
    projected = _psd_project(bad)
    assert np.abs(projected - projected.T).max() == 0.0
    assert np.linalg.eigvalsh(projected).min() >= -1e-15


def test_nan_listwise():
    rets = _returns(n_obs=20, n=3, seed=17)
    with_nan = rets.copy()
    with_nan.iloc[3, 1] = np.nan
    with_nan.iloc[9, 2] = np.nan
    got = estimate_cov(with_nan, method="sample", psd_fix=False)
    expected = estimate_cov(with_nan.dropna(how="any"), method="sample", psd_fix=False)
    assert np.abs(got.to_numpy() - expected.to_numpy()).max() < 1e-15


def test_unknown_method_raises():
    rets = _returns()
    with pytest.raises(ValueError) as excinfo:
        estimate_cov(rets, method="shrunk")
    message = str(excinfo.value)
    for key in COV_ESTIMATORS:
        assert key in message


def test_ewma_symmetric_psd():
    rets = _returns(seed=19)
    got = estimate_cov(rets, method="ewma", psd_fix=False).to_numpy()
    sample = estimate_cov(rets, method="sample", psd_fix=False).to_numpy()
    assert np.abs(got - got.T).max() == 0.0
    assert np.linalg.eigvalsh(got).min() >= -1e-15
    assert np.abs(got - sample).max() > 0.0  # 非 sample 的退化复用


@pytest.mark.parametrize("method", ["sample", "ledoit_wolf", "ewma"])
def test_all_methods_symmetric_psd(method):
    """I8：三条估计路径的输出均为对称 PSD（AC-C-01c 覆盖口径）。"""
    got = estimate_cov(_returns(seed=29), method=method).to_numpy()
    assert np.abs(got - got.T).max() == 0.0
    assert np.linalg.eigvalsh(got).min() >= -1e-15


def test_near_singular_cov_solver_bounds():
    rng = np.random.default_rng(23)
    base = rng.normal(0.0, 0.01, size=(60, 1))
    rets = pd.DataFrame(
        np.hstack([base, base * (1.0 + 1e-12), rng.normal(0.0, 0.01, size=(60, 1))]),
        columns=["A", "B", "C"],
    )
    cov = estimate_cov(rets, method="sample")
    scores = pd.Series([3.0, 2.0, 1.0], index=["A", "B", "C"])
    opt = build_optimizer(OptimizerConfig(method="min_variance", max_weight=0.9, target_count=3))
    w = opt.optimize(scores, None, cov)
    values = w.to_numpy()
    assert np.isfinite(values).all()
    assert float(values.sum()) == pytest.approx(1.0, abs=1e-9)
    assert float(values.max()) <= 0.9 + 1e-9


# ---------------------------------------------------------------------------
# P-046b：estimate_cov 诊断语义（F-S10-P046-2/3）
# ---------------------------------------------------------------------------
def test_estimate_cov_degenerate_warns(caplog):
    """有效行 < 2 → warning；输出仍无 NaN（数值语义不变）。"""
    rets = _returns(n_obs=4, n=3, seed=31)
    rets.iloc[[0, 1, 2], 0] = np.nan  # 仅剩 1 个有效行 → 退化
    with caplog.at_level(logging.WARNING):
        got = estimate_cov(rets, method="sample")
    assert "有效行 < 2" in caplog.text
    assert not np.isnan(got.to_numpy()).any()


def test_estimate_cov_codes_missing_warns(caplog):
    """codes 缺失列 warning 后丢弃（交集），不再静默。"""
    rets = _returns(seed=37)
    with caplog.at_level(logging.WARNING):
        got = estimate_cov(rets, method="sample", codes=["S0", "NOPE"])
    assert "缺失列已丢弃" in caplog.text
    assert list(got.columns) == ["S0"]
    assert list(got.index) == ["S0"]
