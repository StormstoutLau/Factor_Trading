"""P-011 B2/D4：V2↔V3 事件级等价（残差恒等式 + 阴性对照）。

构造：常量价 ``[[10, 25]]×3``、常量因子 ``[[1, 2]]×3``、全可交易、零费用、
``stock_adj=1.0``（raw == hfq）。两引擎在同一经济事件（同一目标组合）上应给出
**可解释的**差异，且差异精确等于声明的口径常数（DESIGN §4.5）：

    V2 = floor(0.985 × w × TV / P / lot) × lot   （T+1 开盘成交、整数股、0.985 缓冲）
    V3 = w × TV / P                              （同日收盘成交、无缓冲）

故 ``V3_qty − V2_qty == 0.015 × w × TV / P``，``V2_cash − V3_cash == 0.015 × TV``，
而常量价 + 零费用下两者 NAV 每一日都精确相等。
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
from core.data_v3 import DataLoaderV3
from core.engine_v2 import BacktestEngineV2
from core.engine_v3_vector import VectorBacktestEngine

DATES = pd.bdate_range("2024-01-02", periods=3)
CODES = ["000001", "600000"]
PRICES = np.array([[10.0, 25.0]] * len(DATES))
FACTORS = np.array([[1.0, 2.0]] * len(DATES))
INITIAL_CAPITAL = 10_000_000.0
VALUE_BUFFER = 0.985


def _build_v2(tmp_path) -> BacktestEngineV2:
    write_price_fixture(tmp_path, DATES, CODES, PRICES)
    write_factor(tmp_path, "factor_value", FACTORS, DATES, CODES)
    cfg = BacktestConfig(
        data_dir=tmp_path,
        output_dir=tmp_path / "out",
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
            target_count=2,
            max_weight=1.0,
            round_lot=True,
            select_top=True,
        ),
        rebalance=RebalanceConfig(method="fixed", frequency="daily"),
        universe=UniverseConfig(exclude_na_factors=False),
        initial_capital=INITIAL_CAPITAL,
        enable_pending_orders=False,
    )
    engine = BacktestEngineV2(cfg)
    engine.setup()
    engine.run()
    return engine


def _build_v3() -> tuple[VectorBacktestEngine, dict]:
    shape = {"index": DATES, "columns": CODES}
    close = pd.DataFrame(PRICES, **shape)
    dl = DataLoaderV3.from_pandas_dataframes(
        close=close,
        open=close,
        high=close,
        low=close,
        factor_dict={"factor": pd.DataFrame(FACTORS, **shape)},
    )
    engine = VectorBacktestEngine(
        {
            "initial_capital": INITIAL_CAPITAL,
            "top_n": 2,
            "rebalance_freq": 1,
            "cost_rate": 0.0,
        }
    )
    engine.setup(dl)
    return engine, engine.run()


@pytest.fixture(scope="module")
def both_engines(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("p011_equiv")
    v2 = _build_v2(tmp_path)
    v3, v3_results = _build_v3()
    return v2, v3, v3_results


def test_v2_target_quantities_match_declared_buffer(both_engines):
    """V2 日 1 持仓 = floor(0.985×w×TV/P/100)×100（`value_buffer` + 整手）。"""
    v2, _, _ = both_engines
    snapshot = v2.tracker.get_snapshots()[1]
    quantities = [int(snapshot.positions[code].quantity) for code in CODES]
    assert quantities == [492_500, 197_000]
    assert snapshot.cash == pytest.approx(150_000.0)


def test_v3_target_quantities_match_full_weight(both_engines):
    """V3 日 1 持仓 = w×TV/P（无缓冲、无整手约束）。"""
    _, v3, _ = both_engines
    positions = v3.get_positions()
    assert positions is not None
    assert [int(q) for q in positions[1]] == [500_000, 200_000]


def test_portfolio_value_equivalence(both_engines):
    """常量价 + 零费用 → 两引擎 NAV 每日精确相等。"""
    v2, v3, v3_results = both_engines
    v2_pv = [snapshot.total_value for snapshot in v2.tracker.get_snapshots()[: len(DATES)]]
    v3_pv = list(v3_results["portfolio_value"])
    assert v2_pv == [INITIAL_CAPITAL] * len(DATES)
    assert v3_pv == [INITIAL_CAPITAL] * len(DATES)
    assert np.array_equal(v2_pv, v3_pv)


def test_cash_residual_equals_declared_buffer(both_engines):
    """``V2_cash − V3_cash == (1 − 0.985) × TV``，且残差不是浮点噪声。"""
    v2, v3, v3_results = both_engines
    positions = v3.get_positions()
    assert positions is not None
    close = PRICES[1]
    v3_cash = float(v3_results["portfolio_value"][1]) - float(np.sum(positions[1] * close))
    v2_cash = float(v2.tracker.get_snapshots()[1].cash)

    residual = v2_cash - v3_cash
    assert residual == pytest.approx((1.0 - VALUE_BUFFER) * INITIAL_CAPITAL)
    assert residual == 150_000.0


def test_negative_control_residual_matches_no_buffer_hypothesis(both_engines):
    """阴性对照：持仓差精确等于 0.015×w×TV/P，逐股可核（非"同向"式的弱断言）。"""
    v2, v3, _ = both_engines
    positions = v3.get_positions()
    assert positions is not None
    v2_qty = [v2.tracker.get_snapshots()[1].positions[code].quantity for code in CODES]
    v3_qty = positions[1]

    weight = 1.0 / len(CODES)
    expected = [(1.0 - VALUE_BUFFER) * weight * INITIAL_CAPITAL / price for price in PRICES[1]]
    diff = [float(v3_qty[i] - v2_qty[i]) for i in range(len(CODES))]
    assert diff == pytest.approx(expected)
    assert diff == [7_500.0, 3_000.0]
