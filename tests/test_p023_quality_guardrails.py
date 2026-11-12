"""P-023 质量护栏：F-A1 静默空回测的两项守卫（RED 于实现前）

RED 阶段（本文件首次落盘）：
- test_run_without_signal_raises        → 期望抛 RuntimeError，实现前 DID NOT RAISE
- test_run_after_manual_signal_injection → 对照绿（防守卫误伤 13 个既有注入式用例）
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from core.config import (
    BacktestConfig,
    CostConfig,
    OptimizerConfig,
    RebalanceConfig,
)
from core.engine_v2 import BacktestEngineV2

DATES = pd.date_range("2024-01-02", periods=4, freq="B")
STOCKS = ["A", "B", "C", "D"]
PRICES = {"A": 10.0, "B": 20.0, "C": 30.0, "D": 40.0}


def _factor_frame() -> pd.DataFrame:
    """d0/d1 由 A、B 领先；d2/d3 切换为 C、D 领先（与 test_rebalance_exits 同构）"""
    return pd.DataFrame(
        {
            "A": [4.0, 4.0, 1.0, 1.0],
            "B": [3.0, 3.0, 2.0, 2.0],
            "C": [1.0, 1.0, 4.0, 4.0],
            "D": [2.0, 2.0, 3.0, 3.0],
        },
        index=DATES,
    )


class _FakeDataManager:
    """最小鸭子类型数据管理器：无文件 I/O，价格恒定"""

    def __init__(self):
        self.trade_dates = DATES
        self.stock_codes = list(STOCKS)
        self.n_stocks = len(STOCKS)
        self.returns = pd.DataFrame(0.0, index=DATES, columns=STOCKS)
        self._prices = pd.DataFrame(
            {stock: [price] * len(DATES) for stock, price in PRICES.items()},
            index=DATES,
        )
        self._factors = _factor_frame()

    def get_adj_price(self, price_type: str, adjustment_type: str) -> pd.DataFrame:
        return self._prices

    def load_factor(self, factor_file: str) -> pd.DataFrame:
        return self._factors

    def get_data_info(self) -> dict:
        return {"source": "fake"}


class _FakeUniverse:
    def __init__(self):
        self._all = pd.DataFrame(True, index=DATES, columns=STOCKS)

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


class _FakeCombiner:
    def combine(self, factors: list[pd.DataFrame]) -> pd.DataFrame:
        return factors[0] if factors else pd.DataFrame()


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


def _build_config(tmpdir: Path, factor_files: list[str]) -> BacktestConfig:
    zero_cost = CostConfig(
        commission_rate=0.0,
        commission_min=0.0,
        stamp_tax_rate=0.0,
        slippage_pct=0.0,
    )
    return BacktestConfig(
        data_dir=tmpdir,
        output_dir=tmpdir / "output",
        factor_files=factor_files,
        factor_weights={},
        cost=zero_cost,
        rebalance=RebalanceConfig(method="fixed", frequency="daily"),
        optimizer=OptimizerConfig(target_count=2, round_lot=True),
        enable_pending_orders=False,
        enable_fallback=False,
        initial_capital=1_000_000.0,
    )


def _injected_engine(tmpdir: Path, factor_files: list[str]) -> BacktestEngineV2:
    """注入式装配：不读文件、不创建默认流水线（复现 F-A1 豁免路径）"""
    return BacktestEngineV2(
        _build_config(tmpdir, factor_files),
        data_manager=_FakeDataManager(),
        universe_filter=_FakeUniverse(),
        factor_pipeline=_FakePipeline(),
        factor_combiner=_FakeCombiner(),
        optimizer=_Top2Optimizer(),
        trigger=_AlwaysTrigger(),
    )


def _run_with_report_patch(engine: BacktestEngineV2) -> dict:
    with patch(
        "core.engine_v2.generate_report",
        return_value={"metrics": {}, "charts": {}, "reports": {}},
    ):
        return engine.run()


# ---------------------------------------------------------------- B1（D1）


def test_run_without_signal_raises(tmp_path):
    """D1：注入工作流未就绪信号时 run() 必须 fail-fast，而非静默空回测"""
    engine = _injected_engine(tmp_path, factor_files=[])
    engine.setup()  # 注入路径豁免 setup 守卫（P-007 语义，不改）
    assert engine._composite_signal is None

    with pytest.raises(RuntimeError, match="信号未就绪"):
        engine.run()


def test_run_after_manual_signal_injection(tmp_path):
    """D1 对照：setup 后手工注入信号（13 个既有用例形态）不受守卫影响"""
    engine = _injected_engine(tmp_path, factor_files=[])
    engine.setup()
    engine._composite_signal = _factor_frame()

    results = _run_with_report_patch(engine)

    assert isinstance(results, dict)
    assert "portfolio_value" in results
    assert len(engine.tracker.get_snapshots()) > 0


# ---------------------------------------------------------------- B2（D2）


def test_generate_results_empty_snapshots_raises(tmp_path):
    """D2：零快照时拒绝生成结果，而非返回空结果字典"""
    engine = _injected_engine(tmp_path, factor_files=[])
    engine.setup()

    with pytest.raises(RuntimeError, match="快照"):
        engine._generate_results()


def test_normal_injected_backtest_still_works(tmp_path):
    """D2 对照：正规注入（非空 factor_files）回测结果结构不变"""
    engine = _injected_engine(tmp_path, factor_files=["dummy.pkl"])
    engine.setup()

    results = _run_with_report_patch(engine)

    assert isinstance(results, dict)
    assert len(results["portfolio_value"]) > 0
    assert len(engine.tracker.get_snapshots()) > 0
