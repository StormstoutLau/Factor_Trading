"""P-011 B6：trace 完整性（`--trace-dir` → 六层 CSV/JSON + manifest）。

DESIGN §4.6：trace 目录必须能被 ``scripts/change_report.py`` 直接消费。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from _synth_fixture import write_factor, write_price_fixture
from core.change_report import LAYER_FILES, RESIDUAL_TOL, compare_runs
from core.config import BacktestConfig, OptimizerConfig, RebalanceConfig
from core.engine_v2 import BacktestEngineV2

DATES = pd.bdate_range("2024-01-02", periods=6)
CODES = ["000001", "600000"]
PRICES = np.array(
    [[10.0, 20.0], [10.2, 19.8], [10.1, 20.3], [10.4, 20.1], [10.3, 20.5], [10.6, 20.2]]
)


def _run(tmp_path, *, suspend: int = 0) -> tuple[BacktestEngineV2, object]:
    write_price_fixture(tmp_path, DATES, CODES, PRICES, suspend=suspend)
    write_factor(tmp_path, "factor_value", PRICES, DATES, CODES)
    trace_dir = tmp_path / "trace"
    cfg = BacktestConfig(
        data_dir=tmp_path,
        output_dir=tmp_path / "out",
        dump_layers_dir=trace_dir,
        factor_files=["factor_value.pkl"],
        optimizer=OptimizerConfig(method="equal_weight", target_count=2, max_weight=1.0),
        rebalance=RebalanceConfig(method="fixed", frequency="N_days", n_days=3),
        initial_capital=1_000_000.0,
    )
    engine = BacktestEngineV2(cfg)
    engine.setup()
    engine.run()
    return engine, trace_dir


def test_all_six_layers_present(tmp_path):
    """六层文件 + manifest.json 全部落盘。"""
    _, trace_dir = _run(tmp_path)
    for name in LAYER_FILES:
        assert (trace_dir / name).is_file(), name
    assert (trace_dir / "manifest.json").is_file()


def test_l6_rows_equal_trade_dates(tmp_path):
    """L6_nav.csv 行数 == 交易日数。"""
    engine, trace_dir = _run(tmp_path)
    nav = pd.read_csv(trace_dir / "L6_nav.csv")
    assert len(nav) == len(engine.dm.trade_dates)
    assert tuple(nav.columns) == ("date", "cash", "market_value", "total_value")


def test_l1_l2_long_format_columns(tmp_path):
    """L1/L2 均为长表，且只记录"受限"单元格：全可交易 → 0 行，全停牌 → 全行。"""
    _, clean_dir = _run(tmp_path / "clean")
    l1_empty = pd.read_csv(clean_dir / "L1_limit_mask.csv")
    l2_empty = pd.read_csv(clean_dir / "L2_tradable.csv")
    assert tuple(l1_empty.columns) == ("date", "stock", "can_buy", "can_sell")
    assert tuple(l2_empty.columns) == ("date", "stock", "buyable", "sellable")
    assert len(l1_empty) == 0 and len(l2_empty) == 0

    _, suspended_dir = _run(tmp_path / "suspended", suspend=1)
    l2 = pd.read_csv(suspended_dir / "L2_tradable.csv")
    assert len(l2) == len(DATES) * len(CODES)
    assert not l2["buyable"].any()


def test_self_diff_consumable(tmp_path):
    """``compare_runs(trace, trace)`` 可直接消费：残差在容差内、归因完整。"""
    _, trace_dir = _run(tmp_path)
    report = compare_runs(trace_dir, trace_dir)

    assert report.nav.diff == 0.0
    # 残差 = |重算 NAV - 上报 NAV|，经 CSV round-trip 后存在 1e-10 量级浮点噪声，
    # 契约以 RESIDUAL_TOL=1e-8 判定（F-S9-5），不要求位精确的 0。
    assert report.residual < RESIDUAL_TOL
    assert report.attribution_complete is True
    assert {layer.layer for layer in report.layers} == {
        name.rsplit(".", 1)[0] for name in LAYER_FILES
    }
    assert all(layer.changed == 0 for layer in report.layers)
