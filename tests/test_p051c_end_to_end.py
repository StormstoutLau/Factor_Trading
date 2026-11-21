"""P-051c E 组：端到端（3 条）——GO 判据、四模板冒烟、golden 基线不变。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd
import pytest

from core.lifecycle import (
    GateAction,
    GateCriteria,
    GateDecision,
    LifecycleStage,
    StrategyFingerprint,
    apply,
    evaluate_gate,
    initial_record,
)
from core.oos import evaluate_strategy, to_evidence
from core.strategy import StrategyMeta

from _synth_fixture import write_factor, write_price_fixture

PERIODS = 120
MIN_HISTORY = 9
CODES12 = [f"{index:06d}" for index in range(1, 13)]
CODES2 = ["000001", "600000"]


def _dates() -> pd.DatetimeIndex:
    return pd.bdate_range("2024-01-02", periods=PERIODS)


def _write(root, codes, close: np.ndarray) -> pd.DatetimeIndex:
    dates = _dates()
    write_price_fixture(
        root, dates, codes, close, high_prices=close * 1.02, low_prices=close * 0.98
    )
    write_factor(root, "factor_value", np.ones((PERIODS, len(codes))), dates, codes)
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
        optimizer=OptimizerConfig(method="equal_weight", target_count=len(CODES12), max_weight=1.0),
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


class _FixedWeightStrategy:
    """非等权固定目标（E1 需要截面区分度以产出正 IC）。"""

    def __init__(self, weights: Mapping[str, float]) -> None:
        total = float(sum(weights.values()))
        self._weights = {str(code): float(value) / total for code, value in weights.items()}
        self._meta = StrategyMeta(
            strategy_id="p051c_rank", version="1.0.0", param_schema={}, code_hash="fake"
        )

    @property
    def meta(self) -> StrategyMeta:
        return self._meta

    def generate_signals(self, view, state) -> pd.Series:
        codes = [str(code) for code in view.signal.index if str(code) in self._weights]
        return pd.Series({code: self._weights[code] for code in codes}, dtype=float)


def _trend_close() -> np.ndarray:
    steps = np.arange(PERIODS, dtype=float)[:, None]
    rank = np.arange(len(CODES12), dtype=float)[None, :]
    drift = 0.0004 + 0.0004 * rank
    oscillation = 1.0 + 0.05 * np.sin(2.0 * np.pi * steps / 20.0)
    return (10.0 + rank) * (1.0 + drift) ** steps * oscillation


def test_e1_backtest_to_paper_go(tmp_path):
    close = _trend_close()
    dates = _write(tmp_path, CODES12, close)
    dm = _dm(tmp_path)
    raw = np.arange(1.0, len(CODES12) + 1)
    weights = {code: float(value) for code, value in zip(CODES12, raw / raw.sum())}
    report = evaluate_strategy(
        dm,
        _FixedWeightStrategy(weights),
        min_history=MIN_HISTORY,
        splitter=_splitter(dates),
    )
    assert report.aggregate is not None
    assert len(report.ic_series) > 0
    record = _record_at_backtest()
    decision = evaluate_gate(record, to_evidence(report, source="walk_forward"), GateCriteria())
    assert decision.action is GateAction.GO
    assert decision.target is LifecycleStage.PAPER
    advanced = apply(record, decision, at="2026-02-01")
    assert advanced.stage is LifecycleStage.PAPER


def test_e2_four_templates_smoke_through_oos(tmp_path):
    import strategies  # noqa: F401  # 注册四模板
    from core.registry import get_strategy_registry

    close = np.array(
        [[10.0 + 0.05 * index, 20.0 + 0.10 * index] for index in range(PERIODS)], dtype=float
    )
    dates = _write(tmp_path, CODES2, close)
    dm = _dm(tmp_path)
    record = _record_at_backtest()
    cases = [
        ("grid_atr", {"base_price": {"000001": 10.0, "600000": 20.0}, "atr_period": 5}),
        ("trend_breakout", {"entry_n": 5, "exit_n": 3, "ma_n": 6}),
        ("ts_momentum", {"lookbacks": (5,), "min_votes": 1}),
        ("mean_reversion", {"lookback": 5}),
    ]
    for name, extra in cases:
        entry = get_strategy_registry().get(name)
        assert entry is not None
        report = evaluate_strategy(
            dm, entry.factory(**extra), min_history=MIN_HISTORY, splitter=_splitter(dates)
        )
        assert report.aggregate is not None, name
        assert report.window_metrics, name
        decision = evaluate_gate(record, to_evidence(report, source="walk_forward"), GateCriteria())
        assert isinstance(decision.action, GateAction), name


def test_e3_baseline_inventory_unchanged():
    root = Path(__file__).resolve().parent / "golden"
    files = sorted(str(path.relative_to(root)).replace("\\", "/") for path in root.rglob("*.json"))
    assert files == [
        "G1.json",
        "G2.json",
        "G3.json",
        "G4.json",
        "G5.json",
        "G6.json",
        "G7.json",
        "p045/P045_S1.json",
        "p045/P045_S2.json",
        "p047/P047_S1.json",
        "p047/P047_S2.json",
        "p047/P047_S3.json",
        "p050/S1.json",
        "p050/S2.json",
        "p050/S3.json",
        "p050/S4.json",
    ]
    for name in files:
        payload = json.loads((root / name).read_text(encoding="utf-8"))
        assert payload["schema_version"] == "1.0"
