"""P-011 B3：三口径一致（``core.metrics`` / analytics / V3 kernel）。

DESIGN §4.2 要求"同名指标同一公式"：Sharpe 的无风险利率、最大回撤的符号与
锚点、年化分母（252/N）必须完全一致，否则报告层的差异无法归因。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.analytics import PerformanceAnalyzer
from core.data_v3 import DataLoaderV3
from core.engine_v3_vector import VectorBacktestEngine, _metrics_kernel
from core.metrics import DEFAULT_RISK_FREE_RATE, compute_metrics
from core.tracker import PortfolioSnapshot

PV = [1_000_000.0, 1_012_000.0, 998_000.0, 1_030_000.0, 1_025_000.0]


def _snapshots(portfolio_value: list[float]) -> list[PortfolioSnapshot]:
    initial = portfolio_value[0]
    previous = initial
    snapshots = []
    for index, value in enumerate(portfolio_value):
        snapshots.append(
            PortfolioSnapshot(
                date=pd.Timestamp("2024-01-02") + pd.Timedelta(days=index),
                cash=0.0,
                total_value=value,
                positions={},
                daily_return=(value - previous) / previous,
                cumulative_return=(value - initial) / initial,
            )
        )
        previous = value
    return snapshots


def _v3_engine(close: np.ndarray, *, risk_free_rate: float | None = None):
    dates = pd.bdate_range("2024-01-02", periods=len(close))
    columns = [f"S{i}" for i in range(close.shape[1])]
    frame = pd.DataFrame(close, index=dates, columns=columns)
    loader = DataLoaderV3.from_pandas_dataframes(
        close=frame,
        open=frame,
        high=frame,
        low=frame,
        factor_dict={"factor": frame * 0.0 + 1.0},
    )
    config = {
        "initial_capital": 1_000_000.0,
        "top_n": close.shape[1],
        "rebalance_freq": 1,
        "cost_rate": 0.0,
    }
    if risk_free_rate is not None:
        config["risk_free_rate"] = risk_free_rate
    engine = VectorBacktestEngine(config)
    engine.setup(loader)
    return engine.run()


def test_compute_metrics_matches_analytics():
    """analytics 的五个口径字段必须与 compute_metrics 一致（同源委托）。"""
    snapshots = _snapshots(PV)
    analyzer = PerformanceAnalyzer()
    analyzer.set_data(snapshots, pd.DataFrame())
    metrics = analyzer.calculate_performance_metrics()
    expected = compute_metrics(PV)

    assert metrics["total_return"] == pytest.approx(expected.total_return, rel=1e-12)
    assert metrics["annual_return"] == pytest.approx(expected.annual_return, rel=1e-12)
    assert metrics["annual_volatility"] == pytest.approx(expected.annual_volatility, rel=1e-12)
    assert metrics["sharpe_ratio"] == pytest.approx(expected.sharpe_ratio, rel=1e-12)
    assert metrics["max_drawdown"] == pytest.approx(expected.max_drawdown, rel=1e-12)
    assert metrics["risk_free_rate"] == DEFAULT_RISK_FREE_RATE


def test_v3_kernel_matches_compute_metrics():
    """V3 kernel（负值原语）与 compute_metrics（非负量级）只差一个符号。"""
    values = np.asarray(PV, dtype=float)
    total_return, annual_return, volatility, sharpe, max_drawdown, final_value = _metrics_kernel(
        values, DEFAULT_RISK_FREE_RATE
    )
    expected = compute_metrics(values, risk_free_rate=DEFAULT_RISK_FREE_RATE)

    assert total_return == pytest.approx(expected.total_return, rel=1e-12)
    assert annual_return == pytest.approx(expected.annual_return, rel=1e-12)
    assert volatility == pytest.approx(expected.annual_volatility, rel=1e-12)
    assert sharpe == pytest.approx(expected.sharpe_ratio, rel=1e-12)
    assert -float(max_drawdown) == pytest.approx(expected.max_drawdown, rel=1e-12)
    assert float(final_value) == expected.final_value


def test_v3_results_use_config_rf():
    """V3 结果层 rf 来自 cfg；Sharpe 差 == rf/vol。"""
    close = np.array([[10.0], [10.5], [10.2]])
    with_rf = _v3_engine(close, risk_free_rate=0.03)
    without_rf = _v3_engine(close, risk_free_rate=0.0)

    assert with_rf["risk_free_rate"] == pytest.approx(0.03)
    assert without_rf["risk_free_rate"] == pytest.approx(0.0)
    delta = without_rf["sharpe_ratio"] - with_rf["sharpe_ratio"]
    assert delta == pytest.approx(0.03 / with_rf["volatility"])


def test_v3_drawdown_includes_initial_anchor():
    """pv=[100,90,81] → 19%（原实现只从第 1 个收益起算，误报 10%）。"""
    values = np.array([100.0, 90.0, 81.0])
    assert compute_metrics(values).max_drawdown == pytest.approx(0.19)
    assert -float(_metrics_kernel(values)[4]) == pytest.approx(0.19)


def test_v2_volatility_uses_diff_returns():
    """波动按 N−1 个差分收益计算（原实现把首日 0 收益计入，低估波动）。"""
    snapshots = _snapshots(PV)
    analyzer = PerformanceAnalyzer()
    analyzer.set_data(snapshots, pd.DataFrame())
    metrics = analyzer.calculate_performance_metrics()

    diff_returns = np.diff(PV) / np.asarray(PV[:-1], dtype=float)
    expected_new = np.std(diff_returns) * np.sqrt(252)
    legacy_returns = [snapshot.daily_return for snapshot in snapshots]
    legacy = np.std(legacy_returns) * np.sqrt(252)

    assert metrics["annual_volatility"] == pytest.approx(expected_new, rel=1e-12)
    assert metrics["annual_volatility"] != pytest.approx(legacy, rel=1e-6)


@pytest.mark.parametrize("portfolio_value", [[], [1_000.0]])
def test_compute_metrics_empty_and_single(portfolio_value):
    """长度 < 2 是 compute_metrics 的唯一抛出条件。"""
    with pytest.raises(ValueError):
        compute_metrics(portfolio_value)


def test_kernel_single_point_returns_zeros():
    """kernel 对单点保留历史行为（返回零值 + 终值），不抛异常。"""
    assert _metrics_kernel(np.array([5.0])) == (0.0, 0.0, 0.0, 0.0, 0.0, 5.0)


def test_trading_days_equals_snapshot_count():
    """``trading_days`` 与快照数一致（I9 指标-快照对账前提）。"""
    snapshots = _snapshots(PV)
    analyzer = PerformanceAnalyzer()
    analyzer.set_data(snapshots, pd.DataFrame())
    metrics = analyzer.calculate_performance_metrics()

    assert metrics["trading_days"] == len(PV) == len(snapshots)
    assert compute_metrics(PV).n_periods == len(PV)
