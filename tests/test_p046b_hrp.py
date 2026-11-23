"""P-046b HRP 优化器验收（Step 9 TDD）。

口径：DESIGN §6（两级距离/叶序/递归二分/退化）、§10.2（9 例）、§3.1 I6-I8；
IMPL §3.6/§3.7/§6.2；外部锚 A4/A5/A17/A21。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy.cluster.hierarchy import leaves_list, linkage
from scipy.spatial.distance import pdist

from core.config import HRPConfig, OptimizerConfig
from core.portfolio import (
    BaseOptimizer,
    HRPOptimizer,
    InfeasibleConstraintError,
    build_optimizer,
    correlation_distance,
    quasi_diagonal_order,
    recursive_bisection,
)

CODES = ["A", "B", "C"]
RHO = np.array([[1.0, 0.7, 0.2], [0.7, 1.0, -0.2], [0.2, -0.2, 1.0]])
VOLS = np.array([0.2, 0.3, 0.4])
COV = pd.DataFrame(np.outer(VOLS, VOLS) * RHO, index=CODES, columns=CODES)
SCORES = pd.Series([3.0, 2.0, 1.0], index=CODES)


def _optimizer(**kwargs) -> BaseOptimizer:
    return build_optimizer(OptimizerConfig(method="hrp", **kwargs))


def test_hrp_distance_matches_paper_example():
    """I6：第一级 d 与第二级 d̃ 与论文 Example 1-2 逐位（atol=1e-4）。"""
    dist = correlation_distance(COV)
    expected_d = np.sqrt(0.5 * (1.0 - RHO))
    assert np.allclose(dist.to_numpy(), expected_d, atol=1e-4, rtol=0.0)
    d_tilde = pdist(dist.to_numpy(), metric="euclidean")
    assert np.allclose(d_tilde, [0.5659, 0.9747, 1.1225], atol=1e-4, rtol=0.0)


def test_hrp_single_linkage_leaves_order():
    """I6：single linkage 合并距离与叶序 [2,0,1]。"""
    dist = correlation_distance(COV)
    order = quasi_diagonal_order(dist)
    assert order == [2, 0, 1]
    z = linkage(pdist(dist.to_numpy(), metric="euclidean"), method="single")
    assert np.allclose(z[:, 2], [0.5659, 0.9747], atol=1e-4, rtol=0.0)
    assert [int(i) for i in leaves_list(z)] == [2, 0, 1]


def test_hrp_recursive_bisection_closed_form():
    """I7：测试内独立复算 α（不硬编码权重）；Σw=1。"""
    order = [2, 0, 1]
    w = recursive_bisection(COV, order)
    sigma = COV.to_numpy()[np.ix_(order, order)]
    v1 = float(sigma[0, 0])
    sub = sigma[1:, 1:]
    inv = 1.0 / np.diag(sub)
    inner = inv / inv.sum()
    v2 = float(inner @ sub @ inner)
    alpha1 = 1.0 - v1 / (v1 + v2)
    v1b, v2b = float(sigma[1, 1]), float(sigma[2, 2])
    alpha2 = 1.0 - v1b / (v1b + v2b)
    expected_ordered = np.array([alpha1, (1 - alpha1) * alpha2, (1 - alpha1) * (1 - alpha2)])
    assert np.allclose(w.to_numpy()[order], expected_ordered, atol=1e-12, rtol=0.0)
    assert float(w.sum()) == pytest.approx(1.0, abs=1e-12)


def test_hrp_single_asset():
    """I8：N=1 → 权重 1.0；叶序 [0]。"""
    cov1 = pd.DataFrame([[0.04]], index=["A"], columns=["A"])
    assert quasi_diagonal_order(correlation_distance(cov1)) == [0]
    result = _optimizer(target_count=1, max_weight=1.0).optimize_with_diagnostics(
        pd.Series([1.0], index=["A"]), cov_matrix=cov1
    )
    assert float(result.weights["A"]) == pytest.approx(1.0, abs=1e-12)


def test_hrp_zero_variance_no_nan():
    """F-4-1：全零 → 等权 1/N + zero_vol；部分零 → 零权资产、无 NaN、Σw=1。"""
    zero = pd.DataFrame(np.zeros((3, 3)), index=CODES, columns=CODES)
    opt = _optimizer(target_count=3, max_weight=1.0)
    result = opt.optimize_with_diagnostics(SCORES, cov_matrix=zero)
    assert result.warning_kind == "zero_vol"
    assert result.message == "zero_vol"
    assert np.allclose(result.weights.to_numpy(), np.full(3, 1.0 / 3.0), atol=1e-12)

    partial = pd.DataFrame(np.diag([0.0, 0.09, 0.16]), index=CODES, columns=CODES)
    part = opt.optimize_with_diagnostics(SCORES, cov_matrix=partial)
    values = part.weights.to_numpy()
    assert not np.isnan(values).any()
    assert float(part.weights["A"]) == pytest.approx(0.0, abs=1e-12)
    assert float(part.weights.sum()) == pytest.approx(1.0, abs=1e-12)
    assert part.warning_kind is None


def test_hrp_max_assets_guard():
    """D18/F-5-2：n > max_assets → InfeasibleConstraintError（ValueError 子类）。"""
    opt = _optimizer(target_count=3, max_weight=1.0, hrp=HRPConfig(max_assets=2))
    with pytest.raises(ValueError, match="max_assets"):
        opt.optimize_with_diagnostics(SCORES, cov_matrix=COV)


def test_hrp_box_constraints():
    """F-4-2：upper 字段/message；lower 抛；可行域箱体生效。"""
    upper = _optimizer(target_count=3, max_weight=0.2).optimize_with_diagnostics(
        SCORES, cov_matrix=COV
    )
    assert upper.infeasible_kind == "upper"
    assert upper.method == "hrp"
    assert upper.message
    assert float(upper.cash_residual) == pytest.approx(0.4, abs=1e-12)

    lower = _optimizer(target_count=3, min_weight=0.4, max_weight=0.5)
    with pytest.raises(InfeasibleConstraintError):
        lower.optimize_with_diagnostics(SCORES, cov_matrix=COV)

    bounded = _optimizer(target_count=3, max_weight=0.5).optimize_with_diagnostics(
        SCORES, cov_matrix=COV
    )
    values = bounded.weights.to_numpy()
    assert float(values.max()) <= 0.5 + 1e-9
    assert float(values.sum()) == pytest.approx(1.0, abs=1e-9)


def test_hrp_method_name():
    """D14：结果 method 标识。"""
    result = _optimizer(target_count=3, max_weight=1.0).optimize_with_diagnostics(
        SCORES, cov_matrix=COV
    )
    assert result.method == "hrp"


def test_build_optimizer_hrp():
    """D14：工厂分支 + 未知 method 行为不变。"""
    assert isinstance(_optimizer(), HRPOptimizer)
    with pytest.raises(ValueError, match="合法值"):
        build_optimizer(OptimizerConfig(method="bogus"))
