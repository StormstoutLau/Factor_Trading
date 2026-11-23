"""P-046a 引擎接线验收（AC-C-10 单次 Σ / AC-B1-05 分类 / U1-A 落账 / 退化窗口）。

口径：DESIGN §5.1（选项 i）与 §6.2（engine 分流）；CHECKLIST B12 七项。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from _synth_fixture import write_factor, write_price_fixture
from core.config import (
    BacktestConfig,
    CostConfig,
    FactorConfig,
    OptimizerConfig,
    RebalanceConfig,
    UniverseConfig,
)
from core.diagnostics import DayErrorCollector
from core.engine_v2 import BacktestEngineV2
from core.portfolio import InfeasibleConstraintError, OptimizationResult, build_optimizer

DATES = pd.bdate_range("2024-01-02", periods=5)
CODES = ["000001", "000002"]
RISING = np.array([[10.0, 20.0], [10.5, 20.4], [10.6, 20.8], [11.2, 21.0], [11.3, 21.2]])


def _fixture(root, prices: np.ndarray = RISING) -> None:
    write_price_fixture(root, DATES, CODES, prices)
    write_factor(root, "factor_value", np.ones((len(DATES), len(CODES))), DATES, CODES)


def _make_engine(
    root,
    *,
    optimizer: OptimizerConfig,
    risk_overlay=None,
    day_error_mode="record",
    event_bus=None,
    optimizer_instance=None,
):
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
        optimizer=optimizer,
        rebalance=RebalanceConfig(method="fixed", frequency="daily"),
        universe=UniverseConfig(
            exclude_na_factors=False,
            exclude_suspended=False,
            exclude_limit_up=False,
            exclude_limit_down=False,
        ),
        initial_capital=100_000.0,
        enable_pending_orders=False,
        write_manifest=False,
        day_error_mode=day_error_mode,
        risk_overlay=risk_overlay,
    )
    engine = BacktestEngineV2(cfg, optimizer=optimizer_instance, event_bus=event_bus)
    engine.setup()
    return engine


def test_cov_computed_once(tmp_path, monkeypatch):
    """AC-C-10：同日 optimizer 与 overlay 共用一份 Σ（每日 1 次，非 2 次）。"""
    import core.engine_v2 as engine_module
    from core.portfolio import estimate_cov as real_estimate

    calls = {"n": 0}

    def _counting(*args, **kwargs):
        calls["n"] += 1
        return real_estimate(*args, **kwargs)

    monkeypatch.setattr(engine_module, "estimate_cov", _counting)

    from core.risk_overlay import RiskOverlayConfig

    root = tmp_path / "once"
    root.mkdir()
    _fixture(root)
    engine = _make_engine(
        root,
        optimizer=OptimizerConfig(
            method="equal_weight", target_count=2, max_weight=1.0, cov_lookback=2
        ),
        risk_overlay=RiskOverlayConfig(enabled=True, target_vol=0.01, defensive_policy="none"),
    )
    engine.run()
    # 5 个交易日、lookback=2 → 3 个可调仓日；每日恰 1 次（旧实现 overlay 另算 np.cov）
    assert calls["n"] == 3


def test_engine_u1b_config_category(tmp_path):
    """AC-B1-05：U1-B 经引擎落账为 config 类别（不降级为 solver）。"""
    root = tmp_path / "u1b"
    root.mkdir()
    _fixture(root)
    engine = _make_engine(
        root,
        optimizer=OptimizerConfig(
            method="equal_weight", target_count=2, min_weight=0.6, max_weight=0.7
        ),
    )
    engine.run()
    summary = engine._diagnostics.summary()
    samples = [s for s in summary["samples"] if s["stage"] == "rebalance"]
    assert samples, "U1-B 必须产生 rebalance 诊断"
    assert all(s["category"] == "config" for s in samples)
    assert all(s["retryable"] is False for s in samples)


def test_engine_u1a_diag_recorded(tmp_path):
    """F-S7-P046-1：U1-A 经引擎落账为 optimizer 类别，detail 携带结构化字段。"""
    root = tmp_path / "u1a"
    root.mkdir()
    _fixture(root)
    engine = _make_engine(
        root, optimizer=OptimizerConfig(method="equal_weight", target_count=2, max_weight=0.1)
    )
    engine.run()
    summary = engine._diagnostics.summary()
    samples = [s for s in summary["samples"] if s["stage"] == "rebalance"]
    assert samples
    sample = samples[0]
    assert sample["category"] == "optimizer"
    detail = sample["detail"]
    assert detail["infeasible_kind"] == "upper"
    assert detail["n_selected"] == 2
    assert detail["max_weight"] == pytest.approx(0.1)
    assert detail["cash_residual"] == pytest.approx(0.8, abs=1e-12)


def test_strategy_path_u1b_propagates():
    """F-D-1：strategy 路径的 2 参调用必须让 U1-B 冒泡（不静默）。"""
    scores = pd.Series([3.0, 2.0, 1.0], index=["A", "B", "C"])
    opt = build_optimizer(
        OptimizerConfig(method="equal_weight", target_count=2, min_weight=0.6, max_weight=0.7)
    )
    with pytest.raises(InfeasibleConstraintError):
        opt.optimize(scores)


def test_zero_variance_window(tmp_path):
    """退化窗口（零波动）：协方差为零时引擎不崩、无 NaN、无内部错误。"""
    root = tmp_path / "flat"
    root.mkdir()
    flat = np.full((len(DATES), 2), 10.0)
    _fixture(root, prices=flat)
    engine = _make_engine(
        root,
        optimizer=OptimizerConfig(
            method="risk_parity", target_count=2, max_weight=1.0, cov_lookback=2
        ),
    )
    engine.run()
    summary = engine._diagnostics.summary()
    assert summary["counts"].get("internal", 0) == 0


def test_error_event_emitted_on_u1b(tmp_path):
    """U1-B 同时产生 ERROR 事件（AC-B1-05 的 emit 半句）。"""
    from core.event_log import EventType

    class _RecordingBus:
        def __init__(self) -> None:
            self.events: list[tuple[str, dict]] = []

        def append(self, event_type, payload, source: str = "") -> None:
            self.events.append((event_type, payload))

        def last_seq(self) -> int:
            return len(self.events)

    root = tmp_path / "emit"
    root.mkdir()
    _fixture(root)
    bus = _RecordingBus()
    engine = _make_engine(
        root,
        optimizer=OptimizerConfig(
            method="equal_weight", target_count=2, min_weight=0.6, max_weight=0.7
        ),
        event_bus=bus,
    )
    engine.run()
    assert any(event_type == EventType.ERROR for event_type, _ in bus.events)


def test_p026_record_compat():
    """F-D-7：旧 record 路径不受新增 detail 字段影响（默认为 None）。"""
    collector = DayErrorCollector("record")
    collector.record("2024-01-02", "rebalance", ValueError("boom"))
    summary = collector.summary()
    sample = summary["samples"][0]
    assert sample["detail"] is None
    for key in ("date", "stage", "category", "error_type", "message", "retryable"):
        assert key in sample


def test_zero_vol_records_zero_variance(tmp_path):
    """P-046b F-S10-P046-1：warning_kind="zero_vol" → 诊断 error_type="ZeroVariance"。"""
    root = tmp_path / "zerovol"
    root.mkdir()
    _fixture(root)

    class _FakeZeroVol:
        cfg = OptimizerConfig(method="equal_weight", target_count=2, max_weight=1.0)

        def optimize_with_diagnostics(self, factor_scores, returns=None, cov_matrix=None):
            weights = pd.Series(0.5, index=factor_scores.index[:2])
            return OptimizationResult(
                weights, "fake", 2, 1.0, 0.0, message="zero_vol", warning_kind="zero_vol"
            )

    engine = _make_engine(
        root,
        optimizer=OptimizerConfig(method="equal_weight", target_count=2, max_weight=1.0),
        optimizer_instance=_FakeZeroVol(),
    )
    engine.run()
    summary = engine._diagnostics.summary()
    samples = [s for s in summary["samples"] if s["stage"] == "rebalance"]
    assert samples
    assert all(s["error_type"] == "ZeroVariance" for s in samples)
    assert all(s["category"] == "optimizer" for s in samples)
