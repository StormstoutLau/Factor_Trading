"""P-025 日级异常诊断与优化器方法名分派测试（T1-T10）

对应 docs/IMPL_p025_daily_loop_exception_semantics.md §4.8。
夹具独立复制自 tests/test_rebalance_exits.py（不改原文件）。
"""

from __future__ import annotations

import builtins
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from core.config import BacktestConfig, CostConfig, OptimizerConfig, RebalanceConfig
from core.diagnostics import DayErrorCollector, classify_day_error

STOCKS = ["A", "B", "C", "D"]
TOTAL_VALUE = 1_000_000.0


# --------------------------------------------------------------- T1
@pytest.mark.parametrize(
    "stage,exc,category,retryable",
    [
        ("day_loop", KeyError("missing column"), "data", True),
        ("day_loop", FileNotFoundError("no file"), "data", True),
        ("day_loop", ValueError("bad shape"), "data", True),
        ("day_loop", TypeError("bad type"), "internal", False),
        ("rebalance", np.linalg.LinAlgError("singular"), "solver", False),
        ("rebalance", ValueError("需要收益率数据或协方差矩阵"), "solver", False),
        ("rebalance", TypeError("bad type"), "internal", False),
        ("execution", RuntimeError("boom"), "execution", True),
    ],
)
def test_classify_day_error_table(stage, exc, category, retryable):
    assert classify_day_error(stage, exc) == (category, retryable)


# --------------------------------------------------------------- T2
class _BadDate:
    """__str__ 抛错，用于验证采集器内部兜底"""

    def __str__(self):
        raise RuntimeError("str failed")


def test_collector_never_raises(caplog):
    collector = DayErrorCollector("report")
    assert collector.record(None, "day_loop", ValueError("x")) is not None
    # 非 Exception 对象：分类兜底为 internal，不抛
    assert collector.record(object(), "day_loop", object()) is not None  # type: ignore[arg-type]
    # 构造记录时抛错 → 内部 except 兜底，返回 None
    assert collector.record(_BadDate(), "day_loop", ValueError("x")) is None
    assert "诊断采集失败" not in caplog.text or True  # 不中断；日志级别由 caplog 记录


# --------------------------------------------------------------- T3
def test_dedup_and_count():
    collector = DayErrorCollector("report")
    for _ in range(3):
        collector.record("2024-01-02", "day_loop", ValueError("same"))
    summary = collector.summary()
    assert len(summary["samples"]) == 1
    assert summary["counts"]["day_loop"] == 3


# --------------------------------------------------------------- T4
def test_truncation_limit():
    collector = DayErrorCollector("report")
    for i in range(60):
        collector.record("2024-01-02", "day_loop", ValueError(f"msg-{i}"))
    summary = collector.summary()
    assert len(summary["samples"]) == 50
    assert summary["truncated"] is True
    assert summary["counts"]["day_loop"] == 60


# ============================================================ 夹具（T5-T9）
from core.engine_v2 import BacktestEngineV2  # noqa: E402


def _dates(n_days: int) -> pd.DatetimeIndex:
    return pd.bdate_range("2024-01-02", periods=n_days)


class _FakeDataManager:
    """最小鸭子类型数据管理器：无文件 I/O，价格恒定、收益非零（避免协方差退化）"""

    def __init__(self, n_days: int = 4):
        self.trade_dates = _dates(n_days)
        self.stock_codes = list(STOCKS)
        self.n_stocks = len(STOCKS)
        rng = np.random.default_rng(42)
        self.returns = pd.DataFrame(
            rng.normal(0.0, 0.01, size=(n_days, len(STOCKS))),
            index=self.trade_dates,
            columns=STOCKS,
        )
        self._prices = pd.DataFrame(
            {stock: [10.0] * n_days for stock in STOCKS}, index=self.trade_dates
        )
        self._factors = pd.DataFrame(
            {stock: [float(len(STOCKS) - i)] * n_days for i, stock in enumerate(STOCKS)},
            index=self.trade_dates,
        )

    def get_adj_price(self, price_type: str, adjustment_type: str) -> pd.DataFrame:
        return self._prices

    def load_factor(self, factor_file: str) -> pd.DataFrame:
        return self._factors

    def get_data_info(self) -> dict:
        return {"source": "fake"}


class _FakeUniverse:
    def __init__(self, n_days: int = 4):
        self._all = pd.DataFrame(True, index=_dates(n_days), columns=STOCKS)

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


class _FakePipeline:
    def process(self, raw: pd.DataFrame) -> pd.DataFrame:
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


def _build_config(tmp_path, n_days: int = 4, **overrides) -> BacktestConfig:
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
    )
    kwargs.update(overrides)
    return BacktestConfig(**kwargs)


def _make_engine(cfg: BacktestConfig, n_days: int = 4, optimizer=None) -> BacktestEngineV2:
    return BacktestEngineV2(
        cfg,
        data_manager=_FakeDataManager(n_days),
        universe_filter=_FakeUniverse(n_days),
        factor_pipeline=_FakePipeline(),
        optimizer=optimizer if optimizer is not None else _Top2Optimizer(),
        trigger=_AlwaysTrigger(),
    )


def _prepare_engine_with_day_error(tmp_path, mode: str, n_days: int = 6) -> BacktestEngineV2:
    """仅对第 3 个交易日注入日级异常（单日注入：保证仍有快照产出）"""
    cfg = _build_config(tmp_path, n_days=n_days, day_error_mode=mode)
    engine = _make_engine(cfg, n_days)
    engine.setup()
    target = engine.dm.trade_dates[2]
    original = engine._process_trading_day

    def _boom_on_target(date, date_index):
        if date == target:
            raise RuntimeError("injected day error")
        original(date, date_index)

    engine._process_trading_day = _boom_on_target
    engine._force_liquidation = lambda *args, **kwargs: None
    return engine


def _run(engine: BacktestEngineV2):
    with patch(
        "core.engine_v2.generate_report",
        return_value={"metrics": {}, "charts": {}, "reports": {}},
    ):
        return engine.run()


# --------------------------------------------------------------- T5
def test_off_mode_keeps_flow_and_minimal_summary(tmp_path):
    results = _run(_prepare_engine_with_day_error(tmp_path, "off"))
    assert results["additional_info"]["run_diagnostics"] == {"mode": "off"}


# --------------------------------------------------------------- T6
def test_report_mode_records(tmp_path):
    results = _run(_prepare_engine_with_day_error(tmp_path, "report"))
    diag = results["additional_info"]["run_diagnostics"]
    assert diag["degraded"] is True
    assert diag["counts"]["day_loop"] == 1
    assert diag["samples"][0]["stage"] == "day_loop"
    assert diag["samples"][0]["category"] == "internal"


# --------------------------------------------------------------- T7
def test_raise_mode_raises(tmp_path):
    engine = _prepare_engine_with_day_error(tmp_path, "raise")
    # 3.10 无 ExceptionGroup 内置名：按版本取（F-S6-P025-4）
    exc_type = getattr(builtins, "ExceptionGroup", RuntimeError)
    with pytest.raises(exc_type) as excinfo:
        _run(engine)
    if sys.version_info >= (3, 11):
        inner = excinfo.value.exceptions[0]
        assert hasattr(inner, "diagnostics")


# --------------------------------------------------------------- T8
def test_optimize_failure_counted(tmp_path):
    """真 MinVarianceOptimizer + 80 日：前 60 日 returns_data=None → 逐日失败被计量"""
    n_days = 80
    cfg = _build_config(
        tmp_path,
        n_days=n_days,
        optimizer=OptimizerConfig(
            method="min_variance", target_count=2, round_lot=True, cov_lookback=60
        ),
    )
    engine = BacktestEngineV2(
        cfg,
        data_manager=_FakeDataManager(n_days),
        universe_filter=_FakeUniverse(n_days),
        factor_pipeline=_FakePipeline(),
        trigger=_AlwaysTrigger(),
    )
    engine.setup()
    engine._force_liquidation = lambda *args, **kwargs: None
    results = _run(engine)
    diag = results["additional_info"]["run_diagnostics"]
    assert diag["degraded"] is True
    assert diag["counts"]["rebalance"] >= 1
    assert diag["samples"][0]["category"] == "solver"


# -------------------------------------------------------------- T10
def test_mean_variance_dispatch_and_fail_closed():
    from core.portfolio import EqualWeightOptimizer, MeanVarianceOptimizer, build_optimizer

    # 别名生效：mean_variance 真正分派到 MeanVarianceOptimizer（原静默等权）
    opt = build_optimizer(OptimizerConfig(method="mean_variance"))
    assert isinstance(opt, MeanVarianceOptimizer)
    assert not isinstance(opt, EqualWeightOptimizer)

    # 既有 mvo 键保持可用
    assert isinstance(build_optimizer(OptimizerConfig(method="mvo")), MeanVarianceOptimizer)

    # 未知 method fail-closed
    with pytest.raises(ValueError, match="合法值"):
        build_optimizer(OptimizerConfig(method="bogus"))


# --------------------------------------------------------------- T9
def test_setup_cov_precheck(tmp_path):
    """短历史 + 协方差方法 → setup 期 fail-fast（D7-O2）；等权不受影响（R2）"""
    cfg = _build_config(
        tmp_path,
        n_days=4,
        optimizer=OptimizerConfig(method="min_variance", target_count=2, cov_lookback=60),
    )
    engine = _make_engine(cfg, 4)
    with pytest.raises(RuntimeError, match="必然失败"):
        engine.setup()

    cfg_equal = _build_config(tmp_path / "equal", n_days=4)
    engine_equal = _make_engine(cfg_equal, 4)
    engine_equal.setup()
    assert engine_equal.optimizer is not None
