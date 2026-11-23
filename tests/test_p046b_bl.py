"""P-046b BL 优化器验收（Step 9 TDD）。

口径：DESIGN §5（先验/观点/Woodbury/退化）、§10.1（11 例）、§3.1 I1-I5；
IMPL §3.3/§3.5/§6.2；外部锚 A20（pypfopt 1.5.5 black_litterman.py）。
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import pytest

from core.config import BLConfig, OptimizerConfig
from core.portfolio import (
    BaseOptimizer,
    BlackLittermanOptimizer,
    MeanVarianceOptimizer,
    _bl_prior,
    black_litterman_posterior,
    build_optimizer,
)

CODES = ["A", "B", "C"]
COV = pd.DataFrame(
    [[0.04, 0.01, 0.02], [0.01, 0.09, 0.03], [0.02, 0.03, 0.16]],
    index=CODES,
    columns=CODES,
)
PRIOR = pd.Series([0.081, 0.114, 0.153], index=CODES)  # δ=3, w_eq=(1/3,1/3,1/3)


def _optimizer(method: str = "black_litterman", **kwargs) -> BaseOptimizer:
    return build_optimizer(OptimizerConfig(method=method, **kwargs))


def test_bl_no_views_equals_prior():
    """I1：K=0 时后验逐位等于先验（不进入矩阵求解）。"""
    post = black_litterman_posterior(COV, PRIOR, {})
    assert np.allclose(post.to_numpy(), PRIOR.to_numpy(), atol=1e-12, rtol=0.0)


def test_bl_single_view_closed_form():
    """默认 Ω=τPΣPᵀ 下单观点闭式：π + Σe_i (Q−π_i) / (2Σ_ii)。"""
    q = 0.10
    post = black_litterman_posterior(COV, PRIOR, {"A": q}, tau=0.05)
    expected = PRIOR + (q - PRIOR["A"]) / (2.0 * COV.loc["A", "A"]) * COV["A"]
    assert np.allclose(post.to_numpy(), expected.to_numpy(), atol=1e-12, rtol=0.0)


def test_bl_single_view_implied_weights_only_view_asset():
    """F-R2 一般性：隐含权重 (δΣ)⁻¹post 仅观点资产变化（随机 5×5，seed=42）。"""
    rng = np.random.default_rng(42)
    m = rng.normal(size=(5, 8))
    sigma = m @ m.T / 8.0 + np.eye(5) * 0.05
    idx = [f"S{i}" for i in range(5)]
    delta = 3.0
    pi = delta * sigma @ np.full(5, 0.2)
    post = black_litterman_posterior(
        pd.DataFrame(sigma, index=idx, columns=idx),
        pd.Series(pi, index=idx),
        {"S2": 0.12},
    )
    diff = np.abs(
        np.linalg.solve(delta * sigma, post.to_numpy()) - np.linalg.solve(delta * sigma, pi)
    )
    assert diff[2] > 1e-8
    assert all(diff[j] < 1e-10 for j in range(5) if j != 2)


def test_bl_tau_cancels_with_default_omega():
    """I3：默认 Ω 下 τ 消去（0.05 与 0.5 后验一致）。"""
    a = black_litterman_posterior(COV, PRIOR, {"A": 0.10}, tau=0.05)
    b = black_litterman_posterior(COV, PRIOR, {"A": 0.10}, tau=0.5)
    assert np.allclose(a.to_numpy(), b.to_numpy(), atol=1e-12, rtol=0.0)


def test_bl_omega_limits():
    """I4：Ω→0 观点资产→Q；Ω→∞→先验。"""
    low = black_litterman_posterior(COV, PRIOR, {"A": 0.10}, omega=[1e-14])
    high = black_litterman_posterior(COV, PRIOR, {"A": 0.10}, omega=[1e14])
    assert abs(float(low["A"]) - 0.10) < 1e-8
    assert np.allclose(high.to_numpy(), PRIOR.to_numpy(), atol=1e-8, rtol=0.0)


def test_bl_zero_view_variance_raises():
    """I5/D8：零观点组合方差 fail-loud。"""
    zero = pd.DataFrame(np.zeros((3, 3)), index=CODES, columns=CODES)
    with pytest.raises(ValueError, match="零/非有限"):
        black_litterman_posterior(zero, pd.Series(0.0, index=CODES), {"A": 0.1})


def test_bl_explicit_prior_missing_asset_raises():
    """D4：显式先验缺选中资产 → ValueError。"""
    cfg = OptimizerConfig(bl=BLConfig(prior="explicit", prior_returns={"A": 0.081}))
    with pytest.raises(ValueError, match="缺少资产"):
        _bl_prior(COV, cfg)


def test_bl_views_missing_asset_filtered(caplog):
    """D5：未入选观点 warning 后丢弃，不崩；结果仍为合法权重。"""
    scores = pd.Series([3.0, 2.0, 1.0], index=CODES)
    opt = _optimizer(target_count=2, max_weight=1.0, bl=BLConfig(views={"C": 0.2}))
    with caplog.at_level(logging.WARNING):
        result = opt.optimize_with_diagnostics(scores, cov_matrix=COV)
    assert "已丢弃" in caplog.text
    assert "C" not in result.weights.index
    assert float(result.weights.sum()) == pytest.approx(1.0, abs=1e-9)


def test_bl_optimizer_not_mean_variance_subclass():
    """D3：组合而非继承。"""
    opt = _optimizer()
    assert isinstance(opt, BaseOptimizer)
    assert not isinstance(opt, MeanVarianceOptimizer)


def test_bl_upper_infeasible_passthrough():
    """F-4-2：上限型透传 infeasible_kind/cash_residual，method 正确。"""
    scores = pd.Series([3.0, 2.0, 1.0], index=CODES)
    opt = _optimizer(target_count=3, max_weight=0.2)
    result = opt.optimize_with_diagnostics(scores, cov_matrix=COV)
    assert result.method == "black_litterman"
    assert result.infeasible_kind == "upper"
    assert result.warning_kind is None
    assert float(result.cash_residual) == pytest.approx(0.4, abs=1e-12)
    assert np.allclose(result.weights.to_numpy(), np.full(3, 0.2), atol=1e-12)


def test_build_optimizer_bl_aliases():
    """D14：black_litterman / bl 同义；未知 method 行为不变。"""
    assert isinstance(_optimizer("black_litterman"), BlackLittermanOptimizer)
    assert isinstance(_optimizer("bl"), BlackLittermanOptimizer)
    with pytest.raises(ValueError, match="合法值"):
        build_optimizer(OptimizerConfig(method="bogus"))
