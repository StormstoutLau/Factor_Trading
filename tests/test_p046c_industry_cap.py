"""P-046c 行业上限严格投影验收（Step 9 TDD）。

口径：DESIGN §5.5、§8.3（C1-C10）；IMPL §3.6/§3.7/§6.2；
外部锚 A33/A34（组约束矩阵口径）、B11（凸集最近点投影）。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import core.engine_v2 as engine_module
from _synth_fixture import write_factor, write_price_fixture
from core.config import (
    BacktestConfig,
    CostConfig,
    FactorConfig,
    OptimizerConfig,
    RebalanceConfig,
    UniverseConfig,
)
from core.portfolio import InfeasibleConstraintError, project_industry_cap

DATES = pd.bdate_range("2024-01-02", periods=5)


def _e8(n: int, g: int, seed: int) -> tuple[pd.Series, pd.Series]:
    """E8 构型（补充调研 §4/§10）：rng 流 m(SPD) → groups → dirichlet → 55% 集中。

    行业码取 **1..G**（D14：标签 0 是 ``data.py`` 缺失填充哨兵，会被计为未分类）。
    """
    rng = np.random.default_rng(seed)
    rng.standard_normal((n, n))
    groups = np.arange(n) % g
    rng.shuffle(groups)
    w0 = rng.dirichlet(np.ones(n))
    top = groups == 0
    w0[top] = w0[top] / w0[top].sum() * 0.55
    w0[~top] = w0[~top] / w0[~top].sum() * 0.45
    codes = [f"S{i:04d}" for i in range(n)]
    return pd.Series(w0, index=codes), pd.Series(groups + 1, index=codes)


def test_projection_n100_hits_cap_exactly():
    """C1 / I7：E8 N=100/G=10/cap=0.12（seed=400）→ cap 精确、Σ=1、L2=0.1522。"""
    weights, industry = _e8(100, 10, 400)
    result = project_industry_cap(weights, industry, cap=0.12, max_weight=1.0)
    assert result.applied is True
    assert result.n_groups == 10
    values = result.weights.loc[weights.index]
    assert float(values.sum()) == pytest.approx(1.0, abs=1e-9)
    group_sums = [float(values[industry == g].sum()) for g in range(1, 11)]
    assert max(group_sums) == pytest.approx(0.12, abs=1e-9)
    deviation = float(np.linalg.norm(values.to_numpy() - weights.to_numpy()))
    assert deviation == pytest.approx(0.152239, abs=1e-3)
    assert result.l1_deviation == pytest.approx(0.86, abs=1e-3)


def test_projection_n500_hits_cap_exactly():
    """C2 / I7：E8 N=500/G=20/cap=0.08（seed=800）→ 0.08 精确、L2=0.1244。"""
    weights, industry = _e8(500, 20, 800)
    result = project_industry_cap(weights, industry, cap=0.08, max_weight=1.0)
    assert result.applied is True
    values = result.weights.loc[weights.index]
    assert float(values.sum()) == pytest.approx(1.0, abs=1e-9)
    group_sums = [float(values[industry == g].sum()) for g in range(1, 21)]
    assert max(group_sums) == pytest.approx(0.08, abs=1e-9)
    deviation = float(np.linalg.norm(values.to_numpy() - weights.to_numpy()))
    assert deviation == pytest.approx(0.124438, abs=1e-3)


def test_projection_noop_when_caps_binding_free():
    """C3 / D16：未触发 → 原 Series 逐位不变、``applied is False``。"""
    codes = [f"A{i}" for i in range(10)]
    industry = pd.Series(np.arange(10), index=codes)
    weights = pd.Series(np.full(10, 0.1), index=codes)
    result = project_industry_cap(weights, industry, cap=0.2, max_weight=1.0)
    assert result.applied is False
    assert result.l1_deviation == 0.0
    pd.testing.assert_series_equal(result.weights, weights)


def test_projection_infeasible_raises():
    """C4 / D15：组容量不足 → ``InfeasibleConstraintError``。"""
    codes = [f"A{i}" for i in range(10)]
    industry = pd.Series(np.repeat([1, 2], 5), index=codes)
    weights = pd.Series(np.full(10, 0.1), index=codes)
    with pytest.raises(InfeasibleConstraintError, match="不可行"):
        project_industry_cap(weights, industry, cap=0.2, max_weight=1.0)


def test_projection_unclassified_stocks_excluded():
    """C5 / D14：标签 0 与 NaN 为未分类（不计组约束，仍受 max_weight）。"""
    codes = ["A", "B", "C", "D", "E", "F"]
    industry = pd.Series([1.0, 1.0, 2.0, 2.0, 0.0, np.nan], index=codes)
    weights = pd.Series(np.full(6, 1.0 / 6.0), index=codes)
    result = project_industry_cap(weights, industry, cap=0.25, max_weight=0.3)
    assert result.n_unclassified == 2
    values = result.weights
    assert float(values.sum()) == pytest.approx(1.0, abs=1e-9)
    for g in (1.0, 2.0):
        assert float(values[industry == g].sum()) <= 0.25 + 1e-9
    assert float(values.max()) <= 0.3 + 1e-9


def test_projection_empty_and_zero_budget_noop():
    """C6：空权重 / 零预算 → 原样、``applied is False``。"""
    empty = project_industry_cap(
        pd.Series(dtype=float), pd.Series(dtype=float), cap=0.2, max_weight=0.5
    )
    assert empty.applied is False
    assert len(empty.weights) == 0

    codes = ["A", "B"]
    industry = pd.Series([1, 1], index=codes)
    zeros = pd.Series([0.0, 0.0], index=codes)
    result = project_industry_cap(zeros, industry, cap=0.1, max_weight=0.5)
    assert result.applied is False
    pd.testing.assert_series_equal(result.weights, zeros)


def test_projection_preserves_non_stock_columns():
    """C7 / I7：不在 industry 索引的期货列逐位不变；股票子集 Σ 保持。"""
    weights = pd.Series({"A": 0.5, "B": 0.2, "C": 0.1, "IF0001": 0.1})
    industry = pd.Series([1, 1, 2], index=["A", "B", "C"])
    result = project_industry_cap(weights, industry, cap=0.4, max_weight=0.6)
    assert result.applied is True
    assert float(result.weights["IF0001"]) == 0.1  # 逐位
    assert float(result.weights[["A", "B", "C"]].sum()) == pytest.approx(0.8, abs=1e-9)
    assert float(result.weights[["A", "B"]].sum()) <= 0.4 + 1e-9


def test_projection_enforces_max_weight():
    """C8 / D13：个股上限在投影内生效（不把单票推到 cap）。"""
    codes = ["A", "B", "C", "D"]
    industry = pd.Series([1, 1, 2, 3], index=codes)
    weights = pd.Series({"A": 0.5, "B": 0.2, "C": 0.15, "D": 0.15})
    result = project_industry_cap(weights, industry, cap=0.4, max_weight=0.3)
    assert result.applied is True
    assert float(result.weights.max()) <= 0.3 + 1e-9
    assert float(result.weights.sum()) == pytest.approx(1.0, abs=1e-9)
    for g in (1, 2, 3):
        assert float(result.weights[industry == g].sum()) <= 0.4 + 1e-9


ENGINE_CODES = ["000001", "000002", "000003", "000004"]
ENGINE_INDUSTRY = {  # A 组 2 只、B 组 1 只、C 组 1 只
    "000001": 1,
    "000002": 1,
    "000003": 2,
    "000004": 3,
}


def _run_engine(tmp_path, monkeypatch, *, industry_cap, suffix: str) -> pd.Series:
    root = tmp_path / suffix
    root.mkdir()
    write_price_fixture(root, DATES, ENGINE_CODES, 10.0)
    write_factor(
        root, "factor_value", np.ones((len(DATES), len(ENGINE_CODES))), DATES, ENGINE_CODES
    )
    industry = pd.DataFrame(
        np.tile([ENGINE_INDUSTRY[c] for c in ENGINE_CODES], (len(DATES), 1)),
        index=DATES,
        columns=ENGINE_CODES,
    )
    industry.to_pickle(root / "industry.pkl")

    cfg = BacktestConfig(
        data_dir=root,
        output_dir=root / "out",
        factor_files=["factor_value.pkl"],
        cost=CostConfig(
            commission_rate=0.0, commission_min=0.0, stamp_tax_rate=0.0, slippage_pct=0.0
        ),
        factor=FactorConfig(
            winsorize_method="none",
            standardize_method="none",
            fill_method="none",
            neutralize=False,
        ),
        optimizer=OptimizerConfig(
            method="equal_weight",
            target_count=len(ENGINE_CODES),
            max_weight=0.5,
            industry_max_weight=industry_cap,
            round_lot=True,
            select_top=True,
        ),
        rebalance=RebalanceConfig(method="fixed", frequency="daily"),
        universe=UniverseConfig(
            exclude_na_factors=False,
            exclude_suspended=False,
            exclude_limit_up=False,
            exclude_limit_down=False,
        ),
        initial_capital=1_000_000.0,
        enable_pending_orders=False,
        write_manifest=False,
        day_error_mode="raise",
    )

    captured: list[pd.Series] = []
    real = engine_module.build_target_positions

    def spy(weights, *args, **kwargs):
        captured.append(pd.Series(weights).copy())
        return real(weights, *args, **kwargs)

    monkeypatch.setattr(engine_module, "build_target_positions", spy)
    engine = engine_module.BacktestEngineV2(cfg)
    engine.setup()
    engine.run()
    assert captured, "未捕获到 build_target_positions 调用"
    return captured[0]


def test_engine_applies_industry_cap(tmp_path, monkeypatch):
    """C9 / D12/T7：4 股 3 行业、max=0.5、cap=0.4 → A 组 0.4、B/C 各 0.3。"""
    weights = _run_engine(tmp_path, monkeypatch, industry_cap=0.4, suffix="cap")
    assert float(weights[["000001", "000002"]].sum()) == pytest.approx(0.4, abs=1e-9)
    assert float(weights["000003"]) == pytest.approx(0.3, abs=1e-9)
    assert float(weights["000004"]) == pytest.approx(0.3, abs=1e-9)
    assert float(weights.sum()) == pytest.approx(1.0, abs=1e-9)


def test_engine_industry_cap_none_is_noop(tmp_path, monkeypatch):
    """C10 / I1：``industry_max_weight=None`` → 等权 [0.25]*4（零漂移）。"""
    weights = _run_engine(tmp_path, monkeypatch, industry_cap=None, suffix="none")
    assert np.allclose(
        weights[ENGINE_CODES].to_numpy(dtype=float), np.full(4, 0.25), atol=1e-12, rtol=0.0
    )
