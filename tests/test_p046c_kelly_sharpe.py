"""P-046c 矩阵凯利 + max_sharpe 验收（Step 9 TDD）。

口径：DESIGN §5.3/§5.4、§8.2（B1-B15）；IMPL §3.4/§3.5/§6.2；
外部锚 A29b/A29c（skfolio 效用/退化守卫）、A30（pypfopt Charnes-Cooper）、A31（δ 因子）。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.config import KellyConfig, MaxSharpeConfig, OptimizerConfig
from core.portfolio import KellyOptimizer, MaxSharpeOptimizer, build_optimizer

CODES = list("ABCDE")
MU5 = np.array([0.08, 0.06, 0.05, 0.04, 0.03])
SIGMA2 = np.linspace(0.2, 0.4, 5) ** 2
SCORES = pd.Series([5.0, 4.0, 3.0, 2.0, 1.0], index=CODES)


def _s5() -> pd.DataFrame:
    rng = np.random.default_rng(1)
    m = rng.standard_normal((5, 5))
    scale = np.diag(np.linspace(0.15, 0.35, 5))
    cov = scale @ (m @ m.T / 5.0 + 0.01 * np.eye(5)) @ scale
    return pd.DataFrame(cov, index=CODES, columns=CODES)


def _returns(mu: np.ndarray, rows: int = 30) -> pd.DataFrame:
    """常数收益率列 → ``returns[selected].mean()`` 精确等于 μ。"""
    values = np.tile(np.asarray(mu, dtype=float), (rows, 1))
    index = pd.bdate_range("2024-01-02", periods=rows)
    return pd.DataFrame(values, index=index, columns=CODES[: len(mu)])


def _kelly(**kwargs):
    params = {"method": "kelly", "target_count": 5, "max_weight": 1.0}
    params.update(kwargs)
    return build_optimizer(OptimizerConfig(**params))


def _max_sharpe(**kwargs):
    params = {"method": "max_sharpe", "target_count": 5, "max_weight": 1.0}
    params.update(kwargs)
    return build_optimizer(OptimizerConfig(**params))


def test_kelly_50a_long_only_invariants():
    """B1 / I5：E3 50A（seed=7）长多不变量。"""
    rng = np.random.default_rng(7)
    m = rng.standard_normal((50, 50))
    cov = pd.DataFrame(m @ m.T / 50.0 + 1e-4 * np.eye(50))
    mu = rng.normal(0.05, 0.02, 50)
    index = pd.bdate_range("2024-01-02", periods=30)
    codes = [f"S{i:03d}" for i in range(50)]
    returns = pd.DataFrame(np.tile(mu, (30, 1)), index=index, columns=codes)
    cov.index = codes
    cov.columns = codes
    scores = pd.Series(np.arange(50, 0, -1, dtype=float), index=codes)
    result = _kelly(target_count=50).optimize_with_diagnostics(
        scores, returns=returns, cov_matrix=cov
    )
    values = result.weights.to_numpy(dtype=float)
    assert float(values.min()) >= -1e-12
    assert float(values.sum()) == pytest.approx(1.0, abs=1e-8)
    assert not np.isnan(values).any()


def test_kelly_box_free_matches_closed_form():
    """B2 / I5：对角 Σ、f=0.5、max=1 → KKT 闭式 <1e-8。"""
    cov = pd.DataFrame(np.diag(SIGMA2), index=CODES, columns=CODES)
    lam = 1.0 / 0.5
    coef = 1.0 / (2.0 * lam * SIGMA2)
    nu = (float(coef @ MU5) - 1.0) / float(coef.sum())
    closed = (MU5 - nu) * coef
    assert np.all(closed > 0.0)
    result = _kelly().optimize_with_diagnostics(SCORES, returns=_returns(MU5), cov_matrix=cov)
    assert np.allclose(result.weights.to_numpy(), closed, atol=1e-8, rtol=0.0)


def test_kelly_fraction_maps_to_risk_aversion():
    """B3 / D8：f=1⇔δ=1、f=0.5⇔δ=2（与共享求解器逐位一致）。"""
    cov = _s5()
    returns = _returns(MU5)
    half = _kelly(max_weight=0.5, kelly=KellyConfig(fraction=1.0)).optimize_with_diagnostics(
        SCORES, returns=returns, cov_matrix=cov
    )
    mvo1 = build_optimizer(
        OptimizerConfig(method="mean_variance", target_count=5, max_weight=0.5, risk_aversion=1.0)
    ).optimize_with_diagnostics(SCORES, returns=returns, cov_matrix=cov)
    assert np.allclose(half.weights.to_numpy(), mvo1.weights.to_numpy(), atol=1e-12, rtol=0.0)

    aggressive = _kelly(max_weight=0.5, kelly=KellyConfig(fraction=0.5)).optimize_with_diagnostics(
        SCORES, returns=returns, cov_matrix=cov
    )
    mvo2 = build_optimizer(
        OptimizerConfig(method="mean_variance", target_count=5, max_weight=0.5, risk_aversion=2.0)
    ).optimize_with_diagnostics(SCORES, returns=returns, cov_matrix=cov)
    assert np.allclose(aggressive.weights.to_numpy(), mvo2.weights.to_numpy(), atol=1e-12, rtol=0.0)


def test_kelly_config_fraction_bounds():
    """B4 / D9：fraction ∈ (0,1] 否则 ``ValueError``。"""
    with pytest.raises(ValueError, match="fraction"):
        KellyConfig(fraction=0.0)
    with pytest.raises(ValueError, match="fraction"):
        KellyConfig(fraction=1.5)


def test_kelly_upper_result():
    """B5 / D21：n=5、max=0.1 → 各 0.1 + 现金 0.5 + ``upper``。"""
    result = _kelly(max_weight=0.1).optimize_with_diagnostics(
        SCORES, returns=_returns(MU5), cov_matrix=_s5()
    )
    assert result.infeasible_kind == "upper"
    assert result.method == "kelly"
    assert np.allclose(result.weights.to_numpy(), np.full(5, 0.1), atol=1e-12, rtol=0.0)
    assert float(result.cash_residual) == pytest.approx(0.5, abs=1e-12)


def test_kelly_empty_result():
    """B6 / D8：空 scores → ``empty``。"""
    result = _kelly().optimize_with_diagnostics(
        pd.Series(dtype=float), returns=_returns(MU5), cov_matrix=_s5()
    )
    assert result.infeasible_kind == "empty"
    assert result.method == "kelly"
    assert len(result.weights) == 0


def test_kelly_requires_returns():
    """B7 / D8：``returns is None`` → ``ValueError``（不静默退化）。"""
    with pytest.raises(ValueError, match="凯利"):
        _kelly().optimize_with_diagnostics(SCORES, cov_matrix=_s5())


def test_kelly_factory():
    """B8 / D18：工厂映射。"""
    assert isinstance(_kelly(), KellyOptimizer)


def test_max_sharpe_matches_pypfopt_reference():
    """B9 / I6：E4 参考解 ±1e-6、Sharpe 1.385755±1e-6（常量固化，不 import pypfopt）。"""
    cov = _s5()
    result = _max_sharpe(
        max_weight=0.6, max_sharpe=MaxSharpeConfig(risk_free_rate=0.02)
    ).optimize_with_diagnostics(SCORES, returns=_returns(MU5), cov_matrix=cov)
    expected = [0.164545, 0.478144, 0.345451, 0.0, 0.011859]
    assert np.allclose(result.weights.to_numpy(), expected, atol=1e-6, rtol=0.0)
    values = result.weights.to_numpy(dtype=float)
    sigma = cov.to_numpy(dtype=float)
    sharpe = float(MU5 @ values - 0.02) / float(np.sqrt(values @ sigma @ values))
    assert sharpe == pytest.approx(1.385755, abs=1e-6)


def test_max_sharpe_box_free_closed_form():
    """B10 / I6：对角 Σ、rf=0.02、max=1 → 闭式 ``w∝Σ⁻¹(μ−rf)`` <1e-8。"""
    cov = pd.DataFrame(np.diag(SIGMA2), index=CODES, columns=CODES)
    ratio = (MU5 - 0.02) / SIGMA2
    closed = ratio / ratio.sum()
    result = _max_sharpe(max_sharpe=MaxSharpeConfig(risk_free_rate=0.02)).optimize_with_diagnostics(
        SCORES, returns=_returns(MU5), cov_matrix=cov
    )
    assert np.allclose(result.weights.to_numpy(), closed, atol=1e-8, rtol=0.0)


def test_max_sharpe_rejects_no_excess_return():
    """B11 / D10：max(μ)≤rf → ``ValueError``。"""
    with pytest.raises(ValueError, match="无风险利率"):
        _max_sharpe(max_sharpe=MaxSharpeConfig(risk_free_rate=0.10)).optimize_with_diagnostics(
            SCORES, returns=_returns(MU5), cov_matrix=_s5()
        )


def test_max_sharpe_upper_result():
    """B12 / D21：n=5、max=0.1 → upper 语义。"""
    result = _max_sharpe(
        max_weight=0.1, max_sharpe=MaxSharpeConfig(risk_free_rate=0.02)
    ).optimize_with_diagnostics(SCORES, returns=_returns(MU5), cov_matrix=_s5())
    assert result.infeasible_kind == "upper"
    assert result.method == "max_sharpe"
    assert float(result.cash_residual) == pytest.approx(0.5, abs=1e-12)


def test_max_sharpe_requires_returns():
    """B13 / D10：``returns is None`` → ``ValueError``。"""
    with pytest.raises(ValueError, match="max_sharpe"):
        _max_sharpe().optimize_with_diagnostics(SCORES, cov_matrix=_s5())


def test_max_sharpe_config_rf_validation():
    """B14 / D11：非有限 rf → ``ValueError``。"""
    with pytest.raises(ValueError, match="risk_free_rate"):
        MaxSharpeConfig(risk_free_rate=float("nan"))


def test_max_sharpe_factory():
    """B15 / D18：工厂类名 + 未知 method 报错集含新键。"""
    assert isinstance(_max_sharpe(), MaxSharpeOptimizer)
    with pytest.raises(ValueError, match="合法值") as excinfo:
        build_optimizer(OptimizerConfig(method="bogus"))
    assert "kelly" in str(excinfo.value)
    assert "max_sharpe" in str(excinfo.value)
