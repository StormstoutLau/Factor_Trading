"""P-046a 约束语义验收（AC-C / AC-B1 / AC-B2）。

口径：DESIGN §4 分支矩阵、§4.3 单点解；RESEARCH §15 验收标准。
规则：A5 禁录制——所有期望值来自闭式或运行期对拍，不硬编码实现输出。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.config import OptimizerConfig
from core.portfolio import (
    InfeasibleConstraintError,
    build_optimizer,
    estimate_cov,
)
from core.target_positions import build_target_positions

METHODS = ["equal_weight", "min_variance", "mean_variance", "risk_parity"]


def _scores(n: int = 5) -> pd.Series:
    return pd.Series(np.arange(n, 0, -1, dtype=float), index=[f"S{i}" for i in range(n)])


def _returns(n_obs: int = 60, n: int = 5, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame(rng.normal(0.0, 0.01, size=(n_obs, n)), columns=[f"S{i}" for i in range(n)])


def _opt(method: str, **kw) -> object:
    return build_optimizer(OptimizerConfig(method=method, **kw))


# ---------------------------------------------------------------------------
# AC-C-01a：约束层与旧实现逐位一致（可行域内）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("method", METHODS)
def test_ac_c_01a_sample_identical_to_legacy(method):
    """可行域内（m=1，约束不生效）约束层与旧实现逐位一致（DESIGN §2.1）。"""
    scores, rets = _scores(), _returns()
    opt = _opt(method, max_weight=1.0, target_count=5, cov_method="sample")
    raw = opt.optimize(scores, rets)
    assert float(raw.max()) <= 1.0 + 1e-8  # 运行期校验：raw 在可行域内（容差含 cvxpy 解精度）
    new = opt._apply_constraints(raw)  # type: ignore[attr-defined]
    old = opt._apply_constraints_legacy(raw)  # type: ignore[attr-defined]
    assert np.allclose(new.to_numpy(), old.to_numpy(), atol=1e-12)
    assert new.sum() == pytest.approx(1.0, abs=1e-12)


# ---------------------------------------------------------------------------
# AC-C-02 / AC-C-03：总权重与箱体约束
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("n,max_weight", [(5, 0.2), (3, 0.5), (10, 0.1)])
def test_ac_c_02_total_weight_le_one(n, max_weight):
    w = _opt("equal_weight", max_weight=max_weight, target_count=n).optimize(_scores(n))
    assert float(w.sum()) <= 1.0 + 1e-12
    assert float(w.sum()) == pytest.approx(min(1.0, n * max_weight), abs=1e-12)


@pytest.mark.parametrize(
    "n,max_weight,min_weight", [(5, 0.3, 0.05), (4, 0.5, 0.1), (6, 0.25, 0.02)]
)
def test_ac_c_03_box_bounds(n, max_weight, min_weight):
    scores, rets = _scores(n), _returns(n=n, seed=11)
    for method in METHODS:
        w = _opt(
            method,
            max_weight=max_weight,
            min_weight=min_weight,
            target_count=n,
            cov_method="sample",
        ).optimize(scores, rets)
        values = w.to_numpy()
        assert float(values.sum()) == pytest.approx(1.0, abs=1e-9)
        assert float(values.max()) <= max_weight + 1e-9
        assert float(values.min()) >= min_weight - 1e-12


# ---------------------------------------------------------------------------
# AC-C-04 / AC-C-05 / AC-C-06
# ---------------------------------------------------------------------------
def test_ac_c_04_no_nan_on_zero_raw():
    scores = _scores()
    constant = pd.DataFrame(np.zeros((60, 5)), columns=scores.index)
    w = _opt("risk_parity", max_weight=0.4, target_count=5).optimize(scores, constant)
    values = w.to_numpy()
    assert not np.isnan(values).any()
    assert not np.isinf(values).any()
    assert float(values.sum()) == pytest.approx(1.0, abs=1e-9)


def test_ac_c_05_idempotent():
    scores, rets = _scores(), _returns()
    opt = _opt("risk_parity", max_weight=0.3, target_count=5)
    once = opt.optimize(scores, rets)
    twice = opt._apply_constraints(once)  # type: ignore[attr-defined]
    assert np.allclose(once.to_numpy(), twice.to_numpy(), atol=1e-12, rtol=0.0)


def test_ac_c_06_deterministic():
    scores, rets = _scores(), _returns()
    first = _opt("mean_variance", max_weight=0.3, target_count=5).optimize(scores, rets)
    second = _opt("mean_variance", max_weight=0.3, target_count=5).optimize(scores, rets)
    assert first.to_numpy().tobytes() == second.to_numpy().tobytes()


# ---------------------------------------------------------------------------
# AC-C-07 / AC-C-09
# ---------------------------------------------------------------------------
def test_ac_c_07_diagnostics_on_infeasible():
    scores, rets = _scores(), _returns()
    opt = _opt("risk_parity", max_weight=0.1, target_count=5)
    result = opt.optimize_with_diagnostics(scores, rets)  # type: ignore[attr-defined]
    assert result.infeasible_kind == "upper"
    assert result.n_selected == 5
    assert result.max_weight == 0.1
    assert result.cash_residual == pytest.approx(1.0 - float(result.weights.sum()), abs=1e-12)
    assert result.message


def test_ac_c_09_selection_snapshot():
    scores = pd.Series([5.0, 0.0, 4.0, 3.0, 2.0], index=list("ABCDE"))
    w = _opt("equal_weight", max_weight=1.0, target_count=3).optimize(scores)
    # 零值过滤 + nlargest(3)：A(5), C(4), D(3)
    assert list(w.index) == ["A", "C", "D"]
    assert np.allclose(w.to_numpy(), [1 / 3, 1 / 3, 1 / 3], atol=1e-12)


# ---------------------------------------------------------------------------
# AC-C-08：静态配置校验（U1-D）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_weight": 0.0},
        {"min_weight": -0.1},
        {"min_weight": 0.5, "max_weight": 0.5},
        {"target_count": 0},
    ],
)
def test_ac_c_08_config_validation(kwargs):
    with pytest.raises(ValueError):
        OptimizerConfig(**kwargs)


# ---------------------------------------------------------------------------
# AC-B1：不可行分型与消息
# ---------------------------------------------------------------------------
def test_ac_b1_01_error_message_fields():
    scores = _scores()
    opt = _opt("equal_weight", min_weight=0.6, max_weight=0.7, target_count=2)
    with pytest.raises(InfeasibleConstraintError) as excinfo:
        opt.optimize(scores)
    message = str(excinfo.value)
    for token in (
        "method=equal_weight",
        "n=2",
        "max_weight=0.7",
        "min_weight=0.6",
        "required_max_weight",
        "sum_max",
        "sum_min",
    ):
        assert token in message


@pytest.mark.parametrize("method", METHODS)
def test_ac_b1_02_u1b_raises(method):
    scores, rets = _scores(), _returns()
    opt = _opt(method, min_weight=0.6, max_weight=0.7, target_count=2)
    with pytest.raises(InfeasibleConstraintError):
        opt.optimize(scores, rets)


def test_ac_b1_03_boundary_feasible():
    scores = _scores()
    max_weight = (1.0 - 1e-13) / 5.0
    result = _opt("equal_weight", max_weight=max_weight, target_count=5).optimize_with_diagnostics(  # type: ignore[attr-defined]
        scores
    )
    assert result.infeasible_kind is None
    assert float(result.weights.sum()) == pytest.approx(1.0, abs=1e-9)


def test_ac_b1_04_message_distinct():
    scores = _scores()
    upper = _opt("equal_weight", max_weight=0.1, target_count=5).optimize_with_diagnostics(scores)  # type: ignore[attr-defined]
    opt = _opt("equal_weight", min_weight=0.6, max_weight=0.7, target_count=2)
    with pytest.raises(InfeasibleConstraintError) as excinfo:
        opt.optimize(scores)
    assert "(U1-A)" in upper.message
    assert "(U1-B)" in str(excinfo.value)


# ---------------------------------------------------------------------------
# AC-B2：上限型语义（只截断、留现金、不归一）
# ---------------------------------------------------------------------------
def _erc_truncating_case():
    rng = np.random.default_rng(3)
    data = rng.normal(0.0, 0.02, size=(60, 4))
    data[:, 0] *= 0.05  # 低波动资产 → ERC 原始权重远超上限
    scores = pd.Series([4.0, 3.0, 2.0, 1.0], index=[f"S{i}" for i in range(4)])
    rets = pd.DataFrame(data, columns=scores.index)
    return scores, rets


def test_ac_b2_01_upper_residual():
    scores, rets = _erc_truncating_case()
    result = _opt("risk_parity", max_weight=0.2, target_count=4).optimize_with_diagnostics(  # type: ignore[attr-defined]
        scores, rets
    )
    values = result.weights.to_numpy()
    assert result.infeasible_kind == "upper"
    assert float(values.sum()) < 1.0
    assert float(values.max()) <= 0.2 + 1e-9
    assert result.cash_residual == pytest.approx(1.0 - float(values.sum()), abs=1e-12)


def test_ac_b2_02_equal_weight_cap():
    result = _opt("equal_weight", max_weight=0.1, target_count=3).optimize_with_diagnostics(  # type: ignore[attr-defined]
        _scores(3)
    )
    assert np.allclose(result.weights.to_numpy(), [0.1, 0.1, 0.1], atol=1e-12)
    assert float(result.weights.sum()) == pytest.approx(0.3, abs=1e-12)
    assert result.cash_residual == pytest.approx(0.7, abs=1e-12)


def test_ac_b2_03_erc_only_truncates():
    scores, rets = _erc_truncating_case()
    result = _opt("risk_parity", max_weight=0.2, target_count=4).optimize_with_diagnostics(  # type: ignore[attr-defined]
        scores, rets
    )
    values = result.weights.to_numpy()
    assert np.isclose(values.max(), 0.2, atol=1e-9)  # 确有截断发生
    assert float(values.sum()) < 1.0 - 1e-6  # 未再归一化


def test_ac_b2_04_u1b_not_b2():
    opt = _opt("equal_weight", min_weight=0.6, max_weight=0.7, target_count=2)
    with pytest.raises(InfeasibleConstraintError):
        opt.optimize_with_diagnostics(_scores())  # type: ignore[attr-defined]


def test_ac_b2_05_diag_fields():
    result = _opt("equal_weight", max_weight=0.1, target_count=4).optimize_with_diagnostics(  # type: ignore[attr-defined]
        _scores(4)
    )
    assert result.method == "equal_weight"
    assert result.n_selected == 4
    assert result.max_weight == pytest.approx(0.1)
    assert result.min_weight == pytest.approx(0.0)
    assert "U1-A" in result.message


def test_ac_b2_06_residual_synonym():
    scores, rets = _scores(), _returns()
    for method in METHODS:
        result = _opt(method, max_weight=0.15, target_count=5).optimize_with_diagnostics(  # type: ignore[attr-defined]
            scores, rets
        )
        assert result.cash_residual == pytest.approx(1.0 - float(result.weights.sum()), abs=1e-12)


def test_ac_b2_07_target_positions_cash():
    scores = _scores(5)
    weights = _opt("equal_weight", max_weight=0.1, target_count=5).optimize(scores)
    total_value = 1_000_000.0
    prices = pd.Series(10.0, index=weights.index)
    targets = build_target_positions(
        weights, current_positions={}, prices=prices, total_value=total_value, round_lot=False
    )
    invested = sum(position.target_quantity * prices[code] for code, position in targets.items())
    # 闭式：Σw × total_value × 0.985（既有 value_buffer）
    assert invested == pytest.approx(float(weights.sum()) * total_value * 0.985, rel=1e-9)
    assert total_value - invested > (1.0 - float(weights.sum())) * total_value


@pytest.mark.parametrize(
    "method,max_weight",
    [("min_variance", 0.1), ("min_variance", 0.2), ("mean_variance", 0.1), ("mean_variance", 0.2)],
)
def test_ac_b2_08_minvar_degenerates(method, max_weight):
    scores, rets = _scores(3), _returns(n=3)
    result = _opt(method, max_weight=max_weight, target_count=3, cov_method="sample").optimize_with_diagnostics(  # type: ignore[attr-defined]
        scores, rets
    )
    assert result.infeasible_kind == "upper"
    assert np.allclose(result.weights.to_numpy(), np.full(3, max_weight), atol=1e-12)
    assert result.cash_residual == pytest.approx(1.0 - 3 * max_weight, abs=1e-12)


def test_cov_entry_used_by_optimizer():
    """注入 Σ 优先于重估（F-D-8）：改 Σ 必改输出。"""
    scores, rets = _scores(3), _returns(n=3, seed=5)
    opt = _opt("min_variance", max_weight=1.0, target_count=3)
    cov = estimate_cov(rets, method="sample")
    scaled = cov * 4.0  # 同比例缩放不改变 min-var 解
    w_a = opt.optimize(scores, None, cov)
    w_b = opt.optimize(scores, None, scaled)
    assert np.allclose(w_a.to_numpy(), w_b.to_numpy(), atol=1e-9)
