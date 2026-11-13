"""P-026 静默失败治理第二批测试（T1-T12）

对应 docs/DESIGN_p026_silent_exception_governance.md §4.2（含 §11 复审订正）。
夹具风格沿用 tests/test_p025_day_error_diagnostics.py（独立复制，不改原文件）。
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from core.config import (
    BacktestConfig,
    CostConfig,
    FactorConfig,
    OptimizerConfig,
    RebalanceConfig,
)
from core.diagnostics import classify_day_error

STOCKS = [f"S{i:02d}" for i in range(12)]
TOTAL_VALUE = 1_000_000.0


# --------------------------------------------------------------- T1
@pytest.mark.parametrize(
    "exc,category,retryable",
    [
        (np.linalg.LinAlgError("singular"), "solver", False),
        (ValueError("bad shape"), "data", False),
        (KeyError("missing"), "data", False),
        (FileNotFoundError("no file"), "data", False),
        (TypeError("bad type"), "internal", False),
    ],
)
def test_t1_classify_factor_stage(exc, category, retryable):
    assert classify_day_error("factor", exc) == (category, retryable)


# ------------------------------------------------------------ T2-T4 夹具
class _FakeNeutralizeDM:
    """仅提供中性化所需的最小数据面（industry / mktcap）"""

    def __init__(self, n_days: int = 2):
        dates = pd.bdate_range("2024-01-02", periods=n_days)
        rng = np.random.default_rng(7)
        self.mktcap = pd.DataFrame(
            1e9 * (1.0 + rng.random((n_days, len(STOCKS)))),
            index=dates,
            columns=STOCKS,
        )
        self.industry = None


def _factor_frame(n_days: int = 2) -> pd.DataFrame:
    rng = np.random.default_rng(11)
    return pd.DataFrame(
        rng.normal(0.0, 1.0, size=(n_days, len(STOCKS))),
        index=pd.bdate_range("2024-01-02", periods=n_days),
        columns=STOCKS,
    )


def _neutralize_cfg() -> FactorConfig:
    return FactorConfig(
        winsorize_method="none",
        fill_method="none",
        standardize_method="none",
        neutralize=True,
        neutralize_industry=False,
        neutralize_mktcap=True,
    )


def _make_pipeline() -> "object":
    from core.factor import FactorPipeline

    return FactorPipeline(_FakeNeutralizeDM(), _neutralize_cfg())


# --------------------------------------------------------------- T2
def test_t2_no_sink_keeps_flow():
    pipeline = _make_pipeline()
    raw = _factor_frame()
    out = pipeline.process(raw)
    assert out.shape == raw.shape
    assert pipeline.neutralize_skip_counts == {"degenerate_columns": 0, "regression": 0}


# --------------------------------------------------------------- T3
def test_t3_degenerate_columns_counted(monkeypatch):
    pipeline = _make_pipeline()
    seen: list[tuple] = []
    pipeline.set_error_sink(lambda date, stage, exc: seen.append((date, stage, exc)))

    def _boom(*args, **kwargs):
        raise RuntimeError("std failed")

    monkeypatch.setattr("core.factor.np.std", _boom)
    pipeline.process(_factor_frame())

    assert pipeline.neutralize_skip_counts["degenerate_columns"] >= 1
    assert seen and seen[0][1] == "factor"


# --------------------------------------------------------------- T4
def test_t4_regression_failure_counted(monkeypatch):
    pipeline = _make_pipeline()
    seen: list[tuple] = []
    pipeline.set_error_sink(lambda date, stage, exc: seen.append((date, stage, exc)))
    raw = _factor_frame()

    def _boom(*args, **kwargs):
        raise np.linalg.LinAlgError("lstsq failed")

    monkeypatch.setattr("core.factor.np.linalg.lstsq", _boom)
    out = pipeline.process(raw)

    assert pipeline.neutralize_skip_counts["regression"] >= 1
    assert seen and seen[0][1] == "factor"
    pd.testing.assert_frame_equal(out, raw)  # 该日整体跳过，结果保持输入副本


# ============================================================ 引擎夹具（T5-T6）
from core.engine_v2 import BacktestEngineV2  # noqa: E402


class _FakeDM:
    def __init__(self, n_days: int = 4):
        dates = pd.bdate_range("2024-01-02", periods=n_days)
        self.trade_dates = dates
        self.stock_codes = ["A", "B", "C", "D"]
        self.n_stocks = 4
        rng = np.random.default_rng(42)
        self.returns = pd.DataFrame(
            rng.normal(0.0, 0.01, size=(n_days, 4)), index=dates, columns=self.stock_codes
        )
        self._prices = pd.DataFrame({s: [10.0] * n_days for s in self.stock_codes}, index=dates)
        self._factors = pd.DataFrame(
            {s: [float(4 - i)] * n_days for i, s in enumerate(self.stock_codes)}, index=dates
        )

    def get_adj_price(self, price_type: str, adjustment_type: str) -> pd.DataFrame:
        return self._prices

    def load_factor(self, factor_file: str) -> pd.DataFrame:
        return self._factors

    def get_data_info(self) -> dict:
        return {"source": "fake"}


class _FakeUniverse:
    def __init__(self, n_days: int = 4):
        dates = pd.bdate_range("2024-01-02", periods=n_days)
        self._all = pd.DataFrame(True, index=dates, columns=["A", "B", "C", "D"])

    def build_masks(self) -> None:
        return None

    @property
    def buyable(self) -> pd.DataFrame:
        return self._all

    @property
    def sellable(self) -> pd.DataFrame:
        return self._all

    @property
    def tradable(self) -> pd.DataFrame:
        return self._all

    def get_mask_summary(self) -> dict:
        return {"source": "fake"}


class _SinkPipeline:
    """带 sink 的假管道：process 首行确认 sink 已注入后上报一次"""

    def __init__(self, raise_error: bool = True):
        self._error_sink = None
        self.sink_was_set = False
        self.raise_error = raise_error

    def set_error_sink(self, sink) -> None:
        self._error_sink = sink

    def process(self, raw: pd.DataFrame) -> pd.DataFrame:
        self.sink_was_set = self._error_sink is not None
        if self.raise_error and self._error_sink is not None:
            self._error_sink("2024-01-02", "factor", ValueError("injected factor error"))
        return raw


class _Top2Optimizer:
    def optimize(self, factor_scores, returns=None, cov_matrix=None) -> pd.Series:
        scores = factor_scores.dropna()
        scores = scores[scores != 0]
        if scores.empty:
            return pd.Series(dtype=float)
        top = scores.nlargest(2)
        return pd.Series(1.0 / len(top), index=top.index)


class _AlwaysTrigger:
    def should_trigger(self, date, **kwargs) -> bool:
        return True


def _build_config(tmp_path, **overrides) -> BacktestConfig:
    zero_cost = CostConfig(
        commission_rate=0.0,
        commission_min=0.0,
        stamp_tax_rate=0.0,
        slippage_pct=0.0,
    )
    kwargs = dict(
        data_dir=Path(tmp_path),
        output_dir=Path(tmp_path) / "output",
        factor_files=["dummy.pkl"],
        factor_weights={},
        cost=zero_cost,
        rebalance=RebalanceConfig(method="fixed", frequency="daily"),
        optimizer=OptimizerConfig(target_count=2, round_lot=True),
        enable_pending_orders=True,
        enable_fallback=False,
        initial_capital=TOTAL_VALUE,
        day_error_mode="report",
    )
    kwargs.update(overrides)
    return BacktestConfig(**kwargs)


def _make_engine(cfg: BacktestConfig, pipeline) -> BacktestEngineV2:
    return BacktestEngineV2(
        cfg,
        data_manager=_FakeDM(),
        universe_filter=_FakeUniverse(),
        factor_pipeline=pipeline,
        optimizer=_Top2Optimizer(),
        trigger=_AlwaysTrigger(),
    )


# --------------------------------------------------------------- T5
def test_t5_factor_error_reaches_run_diagnostics(tmp_path):
    pipeline = _SinkPipeline(raise_error=True)
    engine = _make_engine(_build_config(tmp_path), pipeline)
    engine.setup()

    assert pipeline.sink_was_set is True  # D1.4：注入早于 _precompute_factors()
    summary = engine._diagnostics.summary()
    assert summary["counts"]["factor"] >= 1
    assert summary["degraded"] is True

    # 正常路径：不产生 factor 计数键
    ok_engine = _make_engine(_build_config(tmp_path), _SinkPipeline(raise_error=False))
    ok_engine.setup()
    assert "factor" not in ok_engine._diagnostics.summary()["counts"]


# --------------------------------------------------------------- T6
class _PlainPipeline:
    def process(self, raw: pd.DataFrame) -> pd.DataFrame:
        return raw


def test_t6_fake_pipeline_without_sink(tmp_path):
    engine = _make_engine(_build_config(tmp_path), _PlainPipeline())
    engine.setup()  # getattr 探测生效：无 set_error_sink 也不抛错
    assert "factor" not in engine._diagnostics.summary()["counts"]


# --------------------------------------------------------------- T7
def test_t7_event_log_plugin_counts_and_warns(caplog):
    from core.engine_plugins import EventLogPlugin

    class _BadLog:
        def append(self, *args, **kwargs):
            raise OSError("disk full")

    plugin = EventLogPlugin(engine=object(), event_log=_BadLog())
    with caplog.at_level(logging.WARNING, logger="core.engine_plugins"):
        plugin._log("engine.day_end", {"date": "2024-01-02"})

    assert plugin.get_stats()["error_count"] == 1
    assert any(r.levelno == logging.WARNING for r in caplog.records)
    assert "EventLog 记录失败" in caplog.text


# --------------------------------------------------------------- T8
def test_t8_guard_plugin_fail_open_and_counted():
    from core.engine_plugins import GuardPlugin

    plugin = GuardPlugin(engine=object())
    plugin.enable()

    with patch(
        "core.engine_plugins.create_guard_context_from_engine",
        side_effect=RuntimeError("ctx failed"),
    ):
        allowed, reasons = plugin.check_trade("BUY", "A", 100, 10.0)

    assert (allowed, reasons) == (True, [])  # 保持 fail-open
    stats = plugin.get_stats()
    assert stats["error_count"] == 1
    assert stats["blocked_count"] == 0
    assert stats["warning_count"] == 0


# --------------------------------------------------------------- T9
def _corr(n: int = 3) -> pd.DataFrame:
    names = [f"M{i}" for i in range(n)]
    return pd.DataFrame(np.eye(n), index=names, columns=names)


def _vols(n: int = 3) -> dict[str, float]:
    return {f"M{i}": 0.01 * (i + 1) for i in range(n)}


def test_t9_contagion_degraded_components(monkeypatch):
    from core.global_contagion import GlobalContagionMonitor

    monitor = GlobalContagionMonitor()

    normal = monitor._build_contagion_network(_corr(), _vols())
    assert normal.degraded_components == []

    empty = monitor._build_contagion_network(pd.DataFrame(), {})
    assert empty.degraded_components == []

    def _boom(*args, **kwargs):
        raise RuntimeError("calc failed")

    monkeypatch.setattr(np.linalg, "eigh", _boom)
    monkeypatch.setattr("core.global_contagion.minimum_spanning_tree", _boom)
    degraded = monitor._build_contagion_network(_corr(), _vols())
    assert degraded.degraded_components == ["centrality", "mst"]


# --------------------------------------------------------------- T10
def test_t10_granger_failed_flag(monkeypatch):
    from core.global_contagion import compute_granger_causality

    rng = np.random.default_rng(3)
    y = pd.Series(rng.normal(size=40))
    x = pd.Series(rng.normal(size=40))

    normal = compute_granger_causality(x, y)
    assert normal["failed"] is False

    short = compute_granger_causality(pd.Series([0.1] * 5), pd.Series([0.2] * 5))
    assert short["failed"] is False
    assert short["causal"] is False

    with patch(
        "statsmodels.tsa.stattools.grangercausalitytests",
        side_effect=RuntimeError("granger failed"),
    ):
        failed = compute_granger_causality(x, y)
    assert failed["failed"] is True


# --------------------------------------------------------------- T11
def test_t11_event_log_stats(tmp_path):
    from core.event_log import EventLog

    # 写盘失败：log_path 指向目录
    dir_log = EventLog(log_path=tmp_path)
    dir_log.append("t", {"v": 1})
    assert dir_log.stats()["write_failures"] >= 1

    # 坏行：1 有效 + 1 截断 JSON；read 仍返回有效条目
    bad = tmp_path / "bad.jsonl"
    good_line = '{"seq": 1, "ts": 1.0, "type": "a", "payload": {}, "source": ""}'
    bad.write_text(good_line + "\n" + '{"seq": 2, "ts": 2.0, "type": "b"', encoding="utf-8")
    log = EventLog(log_path=bad)
    entries = log.read()
    assert len(entries) == 1
    assert entries[0].seq == 1
    assert log.stats()["skipped_lines"] >= 1


# --------------------------------------------------------------- T12
class _RaisingAgent:
    def set_period(self, period: str) -> None:
        raise RuntimeError("set_period failed")


class _NoPeriodAgent:
    """无 set_period 也无 distillation_config：两条路径均跳过"""


class _EmptySplitter:
    def get_n_splits(self) -> int:
        return 0

    def split(self):
        return []


def test_t12_agent_period_failures():
    from core.walk_forward import PeriodType
    from core.walk_forward_engine import WalkForwardEngine

    engine = WalkForwardEngine(base_engine_class=object, splitter=_EmptySplitter(), config=object())

    engine._set_agent_period(_RaisingAgent(), PeriodType.TEST)
    assert engine._agent_period_failures == 1

    engine._set_agent_period(_NoPeriodAgent(), PeriodType.TEST)
    assert engine._agent_period_failures == 1  # 无 set_period 不计

    # run() 开头重置：预置 5 次脏计数，空窗口 run 后归零
    engine._agent_period_failures = 5
    result = engine.run()
    assert result.agent_period_failures == 0
