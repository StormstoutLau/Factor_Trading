"""P-051c O 组：OOS 绩效产出器（11 条）。

数据构造（IMPL §3.5）：PERIODS=120、WARMUP=10、splitter(40/20/2) → 3 窗，
末窗 test_end = idx101。
"""

from __future__ import annotations

from typing import Mapping

import numpy as np
import pandas as pd
import pytest

from core.lifecycle import (
    GateAction,
    GateCriteria,
    GateDecision,
    LifecycleError,
    LifecycleStage,
    StrategyFingerprint,
    apply,
    evaluate_gate,
    initial_record,
)
from core.metrics import MetricsResult
from core.oos import _cross_sectional_ic, _segment, evaluate_strategy, run_engine, to_evidence
from core.strategy import StrategyMeta

from _synth_fixture import write_factor, write_price_fixture

PERIODS = 120
MIN_HISTORY = 9
WARMUP = MIN_HISTORY + 1
CODES = [f"{index:06d}" for index in range(1, 13)]


# ---------------------------------------------------------------------------
# 测试物料
# ---------------------------------------------------------------------------


def _dates() -> pd.DatetimeIndex:
    return pd.bdate_range("2024-01-02", periods=PERIODS)


def _trend_close() -> np.ndarray:
    """截面漂移分层 + 20 日周期共同波动（波动用于产生非零夏普分母）。"""
    steps = np.arange(PERIODS, dtype=float)[:, None]
    rank = np.arange(len(CODES), dtype=float)[None, :]
    drift = 0.0004 + 0.0004 * rank
    oscillation = 1.0 + 0.05 * np.sin(2.0 * np.pi * steps / 20.0)
    return (10.0 + rank) * (1.0 + drift) ** steps * oscillation


def _write_fixture(root, close: np.ndarray) -> pd.DatetimeIndex:
    dates = _dates()
    write_price_fixture(
        root, dates, CODES, close, high_prices=close * 1.02, low_prices=close * 0.98
    )
    write_factor(root, "factor_value", np.ones((PERIODS, len(CODES))), dates, CODES)
    return dates


def _dm(root):
    from core.config import (
        BacktestConfig,
        CostConfig,
        FactorConfig,
        OptimizerConfig,
        RebalanceConfig,
        UniverseConfig,
    )
    from core.engine_v2 import BacktestEngineV2

    (root / "out").mkdir(exist_ok=True)
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
        optimizer=OptimizerConfig(method="equal_weight", target_count=len(CODES), max_weight=1.0),
        rebalance=RebalanceConfig(method="fixed", frequency="daily"),
        universe=UniverseConfig(
            exclude_na_factors=False, exclude_suspended=False, exclude_limit_up=False
        ),
        initial_capital=10_000_000.0,
        enable_pending_orders=False,
        write_manifest=False,
    )
    engine = BacktestEngineV2(cfg)
    engine.setup()
    return engine.dm


class _FixedWeightStrategy:
    """固定目标权重（等权 / 全零 / 任意非等权），不消费 history。"""

    def __init__(self, weights: Mapping[str, float]) -> None:
        total = float(sum(weights.values()))
        self._weights = (
            {str(code): float(value) / total for code, value in weights.items()} if total else {}
        )
        self._meta = StrategyMeta(
            strategy_id="p051c_fake", version="1.0.0", param_schema={}, code_hash="fake"
        )

    @property
    def meta(self) -> StrategyMeta:
        return self._meta

    def generate_signals(self, view, state) -> pd.Series:
        codes = [str(code) for code in view.signal.index if str(code) in self._weights]
        return pd.Series({code: self._weights[code] for code in codes}, dtype=float)


def _equal_weights() -> dict[str, float]:
    return {code: 1.0 / len(CODES) for code in CODES}


def _splitter(dates: pd.DatetimeIndex):
    from core.walk_forward import WalkForwardSplitter

    return WalkForwardSplitter(dates=dates, train_size=40, test_size=20, purge_gap=2)


def _record_at_backtest():
    fingerprint = StrategyFingerprint(
        strategy_id="p051c_fake", version="1.0.0", param_snapshot={}, code_hash="fake"
    )
    return apply(
        initial_record(fingerprint),
        GateDecision(GateAction.GO, (), LifecycleStage.BACKTEST),
        at="2026-01-02",
    )


def _assert_metrics_equal(first: MetricsResult, second: MetricsResult) -> None:
    assert first.n_periods == second.n_periods
    for name in (
        "total_return",
        "annual_return",
        "annual_volatility",
        "sharpe_ratio",
        "max_drawdown",
        "final_value",
        "risk_free_rate",
    ):
        assert getattr(first, name) == pytest.approx(getattr(second, name), rel=1e-12, abs=1e-15)


# ---------------------------------------------------------------------------
# O1-O11
# ---------------------------------------------------------------------------


def test_o1_segment_uses_non_trading_endpoints():
    dates = pd.bdate_range("2024-01-02", periods=20)
    pv = pd.Series(np.arange(20, dtype=float), index=dates)
    seg = _segment(pv, pd.Timestamp("2024-01-06"), pd.Timestamp("2024-01-14"), 0)
    assert len(seg) == 6
    assert seg.index[0] == pd.Timestamp("2024-01-05")
    assert seg.index[-1] == pd.Timestamp("2024-01-12")


def test_o2_left_anchor_clamped_to_warmup():
    dates = pd.bdate_range("2024-01-02", periods=20)
    pv = pd.Series(np.arange(20, dtype=float), index=dates)
    assert _segment(pv, dates[0], dates[2], 5).empty
    seg = _segment(pv, dates[0], dates[8], 5)
    assert len(seg) == 4
    assert seg.index[0] == dates[5]


def test_o3_short_window_skipped_and_gate_holds(tmp_path):
    close = _trend_close()
    _write_fixture(tmp_path, close)
    dm = _dm(tmp_path)
    from core.walk_forward import WalkForwardSplitter

    short = WalkForwardSplitter(dates=dm.trade_dates[:11], train_size=1, test_size=1, purge_gap=0)
    report = evaluate_strategy(
        dm, _FixedWeightStrategy(_equal_weights()), min_history=MIN_HISTORY, splitter=short
    )
    assert report.aggregate is None
    assert "w0_test" in report.skipped_windows
    assert report.decay_reason == "insufficient_warmup"
    decision = evaluate_gate(
        _record_at_backtest(), to_evidence(report, source="walk_forward"), GateCriteria()
    )
    assert decision.action is GateAction.HOLD


def test_o4_aggregate_chains_window_returns(tmp_path):
    close = _trend_close()
    dates = _write_fixture(tmp_path, close)
    dm = _dm(tmp_path)
    report = evaluate_strategy(
        dm,
        _FixedWeightStrategy(_equal_weights()),
        min_history=MIN_HISTORY,
        splitter=_splitter(dates),
    )
    assert report.aggregate is not None
    test_returns = [
        metrics.total_return for label, metrics in report.window_metrics if label.endswith("_test")
    ]
    expected = float(np.prod([1.0 + value for value in test_returns]) - 1.0)
    assert report.aggregate.total_return == pytest.approx(expected, rel=1e-12, abs=1e-15)


def test_o5_decay_none_when_signal_too_weak(tmp_path):
    close = np.full((PERIODS, len(CODES)), 10.0)
    _write_fixture(tmp_path, close)
    dm = _dm(tmp_path)
    # 从 idx20 起切窗：避开预热段结束后的建仓成本一次性冲击，隔离衰减判据本身
    from core.walk_forward import WalkForwardSplitter

    splitter = WalkForwardSplitter(
        dates=dm.trade_dates[20:], train_size=40, test_size=20, purge_gap=2
    )
    report = evaluate_strategy(
        dm, _FixedWeightStrategy(_equal_weights()), min_history=MIN_HISTORY, splitter=splitter
    )
    assert report.aggregate is not None
    assert report.aggregate.sharpe_ratio == pytest.approx(0.0)
    assert report.decay is None
    assert report.decay_reason == "insufficient_signal"


def test_o6_ic_skips_all_zero_weight_days(tmp_path):
    close = _trend_close()
    dates = _write_fixture(tmp_path, close)
    dm = _dm(tmp_path)
    report = evaluate_strategy(
        dm, _FixedWeightStrategy({}), min_history=MIN_HISTORY, splitter=_splitter(dates)
    )
    assert report.ic_series.empty
    assert report.aggregate is not None


def test_o7_ic_requires_ten_effective_pairs():
    dates = pd.bdate_range("2024-01-02", periods=3)
    weights = np.arange(1.0, len(CODES) + 1) / float(np.arange(1.0, len(CODES) + 1).sum())
    frame = pd.DataFrame(np.tile(weights, (3, 1)), index=dates, columns=CODES)
    next_returns = pd.DataFrame(
        np.tile(np.arange(1.0, len(CODES) + 1), (3, 1)), index=dates, columns=CODES
    )
    next_returns.iloc[1, [0, 1]] = np.nan  # 10 个有效对 → 保留
    next_returns.iloc[2, [0, 1, 2]] = np.nan  # 9 个有效对 → 剔除
    ic = _cross_sectional_ic(frame, next_returns, dates)
    assert list(ic.index) == [dates[0], dates[1]]
    assert float(ic.iloc[0]) == pytest.approx(1.0)
    assert float(ic.iloc[1]) == pytest.approx(1.0)


def test_o8_min_history_validation(tmp_path):
    close = _trend_close()
    _write_fixture(tmp_path, close)
    dm = _dm(tmp_path)
    strategy = _FixedWeightStrategy(_equal_weights())
    with pytest.raises(LifecycleError, match="min_history"):
        evaluate_strategy(dm, strategy, min_history=0)
    with pytest.raises(LifecycleError, match="样本不足"):
        evaluate_strategy(dm, strategy, min_history=PERIODS)


def test_o9_capital_floor_enforced(tmp_path):
    close = _trend_close()
    _write_fixture(tmp_path, close)
    dm = _dm(tmp_path)
    weights = pd.DataFrame(0.0, index=dm.trade_dates, columns=dm.stock_codes)
    with pytest.raises(LifecycleError, match="资金过小"):
        run_engine(dm, weights, initial_capital=999_999.0)
    with pytest.raises(LifecycleError, match="资金过小"):
        evaluate_strategy(
            dm, _FixedWeightStrategy(_equal_weights()), min_history=MIN_HISTORY, initial_capital=1.0
        )


def test_o10_warmup_excluded_from_aggregate(tmp_path):
    close = _trend_close()
    dates = _write_fixture(tmp_path, close)
    dm = _dm(tmp_path)
    report = evaluate_strategy(
        dm,
        _FixedWeightStrategy(_equal_weights()),
        min_history=MIN_HISTORY,
        splitter=_splitter(dates),
    )
    assert report.warmup_days == WARMUP
    assert report.aggregate is not None
    assert report.aggregate.n_periods == 61  # 1 + 3×20（预热段与各段锚点均不计入）
    assert len(report.oos_dates) == 60
    assert report.oos_dates[0] == dates[42]
    assert report.oos_dates[-1] == dates[101]


def test_o11_no_lookahead_on_future_prices(tmp_path):
    close = _trend_close()
    dates = _write_fixture(tmp_path, close)
    dm = _dm(tmp_path)
    snapshot = dm.get_adj_price("close", "raw").to_numpy().copy()
    report = evaluate_strategy(
        dm,
        _FixedWeightStrategy(_equal_weights()),
        min_history=MIN_HISTORY,
        splitter=_splitter(dates),
    )
    np.testing.assert_array_equal(dm.get_adj_price("close", "raw").to_numpy(), snapshot)

    tampered = close.copy()
    tampered[102:] *= 1.5
    _write_fixture(tmp_path, tampered)
    dm_future = _dm(tmp_path)
    report_future = evaluate_strategy(
        dm_future,
        _FixedWeightStrategy(_equal_weights()),
        min_history=MIN_HISTORY,
        splitter=_splitter(dates),
    )
    assert [label for label, _ in report.window_metrics] == [
        label for label, _ in report_future.window_metrics
    ]
    for (_, before), (_, after) in zip(report.window_metrics, report_future.window_metrics):
        _assert_metrics_equal(before, after)
    assert report.aggregate is not None and report_future.aggregate is not None
    _assert_metrics_equal(report.aggregate, report_future.aggregate)
