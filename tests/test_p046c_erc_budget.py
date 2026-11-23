"""P-046c ERC 修复 + 非等风险预算验收（Step 9 TDD）。

口径：DESIGN §5.1/§5.2、§8.1（A1-A14）；IMPL §3.2/§3.3/§6.2；
外部锚 A27/A27b（凸模型无 ``Σw=1``）、A28（riskfolio 同形状）、B13/B14。
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import pytest

from core.config import OptimizerConfig
from core.portfolio import build_optimizer, estimate_cov

CODES = list("ABCDE")
SCORES = pd.Series([5.0, 4.0, 3.0, 2.0, 1.0], index=CODES)
BUDGET = {"A": 0.4, "B": 0.3, "C": 0.15, "D": 0.1, "E": 0.05}


def _s5() -> pd.DataFrame:
    """DESIGN §8.4 共享 SPD 构型（seed=1）。"""
    rng = np.random.default_rng(1)
    m = rng.standard_normal((5, 5))
    scale = np.diag(np.linspace(0.15, 0.35, 5))
    cov = scale @ (m @ m.T / 5.0 + 0.01 * np.eye(5)) @ scale
    return pd.DataFrame(cov, index=CODES, columns=CODES)


def _rc_pct(weights: pd.Series, cov: pd.DataFrame) -> np.ndarray:
    """风险贡献占比（Σ rc_i / σ_p² = 1，无需再归一）。"""
    w = weights.to_numpy(dtype=float)
    sigma = cov.to_numpy(dtype=float)
    pvar = float(w @ sigma @ w)
    return w * (sigma @ w) / pvar


def _rp(**kwargs):
    params = {"method": "risk_parity", "target_count": 5, "max_weight": 1.0}
    params.update(kwargs)
    return build_optimizer(OptimizerConfig(**params))


def test_erc_negative_corr_two_asset_recovers_inverse_vol():
    """A1 / I2：两资产负相关 → [0.6,0.4]±1e-4，RC 各 0.5±1e-3。"""
    codes = ["A", "B"]
    cov = pd.DataFrame([[0.04, -0.054], [-0.054, 0.09]], index=codes, columns=codes)
    result = build_optimizer(
        OptimizerConfig(method="risk_parity", target_count=2, max_weight=1.0)
    ).optimize_with_diagnostics(pd.Series([2.0, 1.0], index=codes), cov_matrix=cov)
    assert np.allclose(result.weights.to_numpy(), [0.6, 0.4], atol=1e-4, rtol=0.0)
    assert np.allclose(_rc_pct(result.weights, cov), [0.5, 0.5], atol=1e-3, rtol=0.0)


def test_erc_negative_corr_emits_fallback_diagnostic():
    """A2 / D3-D5：负 RC 回退凸解并落 ``erc_fallback`` 诊断。"""
    codes = ["A", "B"]
    cov = pd.DataFrame([[0.04, -0.054], [-0.054, 0.09]], index=codes, columns=codes)
    result = build_optimizer(
        OptimizerConfig(method="risk_parity", target_count=2, max_weight=1.0)
    ).optimize_with_diagnostics(pd.Series([2.0, 1.0], index=codes), cov_matrix=cov)
    assert result.warning_kind == "erc_fallback"
    assert result.message.startswith("erc_fallback:")


def test_erc_five_asset_random_spd_rc_equal():
    """A3 / I3：S5 随机 SPD → RC 各 0.2±1e-3，且权重非等权。"""
    cov = _s5()
    result = _rp().optimize_with_diagnostics(SCORES, cov_matrix=cov)
    assert np.allclose(_rc_pct(result.weights, cov), np.full(5, 0.2), atol=1e-3, rtol=0.0)
    assert float(np.abs(result.weights.to_numpy() - 0.2).max()) > 0.1


def test_erc_equicorr_fast_path_zero_drift():
    """A4 / D2：等相关构型走快速乘性路径，权重与现状逐字一致。"""
    vols = np.linspace(0.2, 0.4, 5)
    rho = 0.3
    corr = np.full((5, 5), rho) + (1.0 - rho) * np.eye(5)
    cov = pd.DataFrame(np.outer(vols, vols) * corr, index=CODES, columns=CODES)
    result = _rp().optimize_with_diagnostics(SCORES, cov_matrix=cov)
    expected = [0.282638, 0.226110, 0.188425, 0.161507, 0.141319]
    assert np.allclose(result.weights.to_numpy(), expected, atol=1e-5, rtol=0.0)
    assert result.message == ""
    assert result.warning_kind is None


def test_erc_sample_cov_fast_path_rc_equal():
    """A5 / I12：20A 样本（seed=2026）快速路径 RC 各 0.05±1e-3、message 空。"""
    rng = np.random.default_rng(2026)
    common = 0.7 * rng.normal(0.0, 0.01, (60, 1))
    idio = rng.normal(0.0, 0.008, (60, 20))
    codes = [f"S{i:02d}" for i in range(20)]
    index = pd.bdate_range("2024-01-02", periods=60)
    returns = pd.DataFrame(common + idio, index=index, columns=codes)
    cov = estimate_cov(returns)
    scores = pd.Series(np.linspace(3.0, 1.0, 20), index=codes)
    result = _rp(target_count=20).optimize_with_diagnostics(scores, returns=returns, cov_matrix=cov)
    assert np.allclose(_rc_pct(result.weights, cov), np.full(20, 0.05), atol=1e-3, rtol=0.0)
    assert result.message == ""


def test_erc_max_iter_exhausted_falls_back():
    """A6 / D3③：max_iter=1 未收敛 → ``erc_fallback:max_iter``，RC 仍 0.2。

    F-S9-P046c-1：S5 等权起点 RC 含负分量（−0.0064），条件②先于③触发；
    改用等相关构型（等权 RC 全正、一步 max|Δw|=0.1415 ≫ tol）隔离③。
    """
    vols = np.linspace(0.2, 0.4, 5)
    rho = 0.3
    corr = np.full((5, 5), rho) + (1.0 - rho) * np.eye(5)
    cov = pd.DataFrame(np.outer(vols, vols) * corr, index=CODES, columns=CODES)
    opt = _rp(risk_parity_max_iter=1, risk_parity_tol=1e-12)
    result = opt.optimize_with_diagnostics(SCORES, cov_matrix=cov)
    assert result.message == "erc_fallback:max_iter"
    assert result.warning_kind == "erc_fallback"
    assert np.allclose(_rc_pct(result.weights, cov), np.full(5, 0.2), atol=1e-3, rtol=0.0)


def test_erc_partial_zero_variance_keeps_equal_weight_zero_vol():
    """A7 / D3：部分零方差 → 等权 [1/3]*3 + ``zero_vol``（不落入病态凸解）。"""
    codes = ["A", "B", "C"]
    cov = pd.DataFrame(np.diag([0.04, 0.09, 0.0]), index=codes, columns=codes)
    result = build_optimizer(
        OptimizerConfig(method="risk_parity", target_count=3, max_weight=1.0)
    ).optimize_with_diagnostics(pd.Series([3.0, 2.0, 1.0], index=codes), cov_matrix=cov)
    assert np.allclose(result.weights.to_numpy(), np.full(3, 1.0 / 3.0), atol=1e-12, rtol=0.0)
    assert result.message == "zero_vol"
    assert result.warning_kind == "zero_vol"


def test_erc_budget_matches_target_rc():
    """A8 / I4：非等预算 b → RC≈b±1e-3（参考 5.67e-05）。"""
    cov = _s5()
    result = _rp(risk_budget=BUDGET).optimize_with_diagnostics(SCORES, cov_matrix=cov)
    rc = _rc_pct(result.weights, cov)
    assert np.allclose(rc, [BUDGET[c] for c in CODES], atol=1e-3, rtol=0.0)


def test_erc_budget_extra_keys_dropped(caplog):
    """A9 / D7：预算含未知代码 → warning 后丢弃，结果正常。"""
    cov = _s5()
    caplog.set_level(logging.WARNING, logger="core.portfolio")
    result = _rp(risk_budget={"A": 0.5, "B": 0.3, "ZZ": 0.2}).optimize_with_diagnostics(
        SCORES, cov_matrix=cov
    )
    assert "已丢弃" in caplog.text
    assert float(result.weights.sum()) == pytest.approx(1.0, abs=1e-9)
    rc = _rc_pct(result.weights, cov)
    expected = [0.5, 0.3, (1.0 - 0.8) / 3.0, (1.0 - 0.8) / 3.0, (1.0 - 0.8) / 3.0]
    assert np.allclose(rc, expected, atol=1e-3, rtol=0.0)


def test_erc_budget_missing_filled_with_remainder():
    """A10 / D7：指定 2 只和 0.7 → 其余各 0.1；指定者 RC≈0.4/0.3。"""
    cov = _s5()
    result = _rp(risk_budget={"A": 0.4, "B": 0.3}).optimize_with_diagnostics(SCORES, cov_matrix=cov)
    rc = _rc_pct(result.weights, cov)
    assert rc[0] == pytest.approx(0.4, abs=1e-3)
    assert rc[1] == pytest.approx(0.3, abs=1e-3)
    assert np.allclose(rc[2:], np.full(3, 0.1), atol=1e-3, rtol=0.0)


def test_erc_budget_all_covered_must_sum_one():
    """A11 / D7：全覆盖且和 0.9 → ``ValueError``。"""
    cov = _s5()
    bad = {"A": 0.4, "B": 0.3, "C": 0.1, "D": 0.05, "E": 0.05}
    with pytest.raises(ValueError, match="合计为 1"):
        _rp(risk_budget=bad).optimize_with_diagnostics(SCORES, cov_matrix=cov)


def test_erc_budget_negative_rejected():
    """A12 / D7：负预算在配置期 ``ValueError``。"""
    with pytest.raises(ValueError, match="非负有限数"):
        OptimizerConfig(method="risk_parity", risk_budget={"A": -0.1, "B": 1.1})


def test_erc_budget_no_match_uniform_fallback(caplog):
    """A13 / D7：预算键全部不在选中集 → warning + 等风险。"""
    cov = _s5()
    caplog.set_level(logging.WARNING, logger="core.portfolio")
    result = _rp(risk_budget={"X": 0.5, "Y": 0.5}).optimize_with_diagnostics(SCORES, cov_matrix=cov)
    assert "无交集" in caplog.text
    assert np.allclose(_rc_pct(result.weights, cov), np.full(5, 0.2), atol=1e-3, rtol=0.0)


def test_optimizer_config_rejects_bad_industry_cap_and_budget_method():
    """A14 / D17：cap 越界与 risk_budget 错配 method 均 ``ValueError``；合法 cap 通过。"""
    with pytest.raises(ValueError, match="industry_max_weight"):
        OptimizerConfig(industry_max_weight=0.0)
    with pytest.raises(ValueError, match="industry_max_weight"):
        OptimizerConfig(industry_max_weight=1.5)
    with pytest.raises(ValueError, match="risk_parity"):
        OptimizerConfig(method="equal_weight", risk_budget={"A": 1.0})
    # D17：不采纳 config_v2 的 cap<=max_weight 反向规则
    config = OptimizerConfig(method="risk_parity", max_weight=0.1, industry_max_weight=0.3)
    assert config.industry_max_weight == pytest.approx(0.3)
