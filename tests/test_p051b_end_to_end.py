"""P-051b E 组：端到端（registry → adapter → set_signal → run）。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from _synth_fixture import write_factor, write_price_fixture

PERIODS = 30
WINDOW = 15
CODES2 = ["000001", "600000"]


def _fixture(root):
    dates = pd.bdate_range("2024-01-02", periods=PERIODS)
    close = np.array([[10.0 + 0.1 * i, 20.0 + 0.1 * i] for i in range(PERIODS)])
    write_price_fixture(
        root,
        dates,
        CODES2,
        close,
        high_prices=close * 1.02,
        low_prices=close * 0.98,
    )
    write_factor(root, "factor_value", np.tile([1.0, 2.0], (PERIODS, 1)), dates, CODES2)
    return dates


def _engine(root):
    from core.config import (
        BacktestConfig,
        CostConfig,
        FactorConfig,
        OptimizerConfig,
        RebalanceConfig,
        UniverseConfig,
    )
    from core.engine_v2 import BacktestEngineV2

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
            target_count=2,
            max_weight=1.0,
            round_lot=True,
            select_top=True,
        ),
        rebalance=RebalanceConfig(method="fixed", frequency="daily"),
        universe=UniverseConfig(
            exclude_na_factors=False, exclude_suspended=False, exclude_limit_up=False
        ),
        initial_capital=10_000_000.0,
        enable_pending_orders=False,
        write_manifest=False,
    )
    return BacktestEngineV2(cfg)


def _adapter(strategy, engine):
    from core.strategy import BacktestAdapter

    adapter = BacktestAdapter(strategy)
    views = adapter.views_from_data(
        engine.dm,
        engine._composite_signal,
        tradable=engine.universe.tradable,
        returns_window=0,
        history_window=WINDOW,
    )
    return adapter, views


def _full_frame(adapter, views, dates):
    frame = adapter.signals_frame(views[WINDOW:])
    head = pd.DataFrame(0.0, index=dates[:WINDOW], columns=frame.columns)
    full = pd.concat([head, frame])
    assert list(full.index) == list(dates)
    return full


@pytest.mark.parametrize(
    "name,extra",
    [
        ("grid_atr", {"base_price": {"000001": 10.0, "600000": 20.0}}),
        ("trend_breakout", {"entry_n": 5, "exit_n": 3, "ma_n": 10}),
        ("ts_momentum", {"lookbacks": (5,), "min_votes": 1}),
        ("mean_reversion", {"lookback": 5}),
    ],
)
def test_e1_four_templates_end_to_end(tmp_path, name, extra):
    import strategies  # noqa: F401
    from core.registry import get_strategy_registry

    dates = _fixture(tmp_path)
    engine = _engine(tmp_path)
    engine.setup()
    entry = get_strategy_registry().get(name)
    assert entry is not None
    adapter, views = _adapter(entry.factory(**extra), engine)
    full = _full_frame(adapter, views, dates)

    engine.set_signal(full, mode="weights")
    assert engine._signal_mode == "weights"
    results = engine.run()
    assert np.isfinite(results["portfolio_value"]).all()


def test_e3_row_sums_bounded(tmp_path):
    import strategies  # noqa: F401
    from core.registry import get_strategy_registry

    dates = _fixture(tmp_path)
    engine = _engine(tmp_path)
    engine.setup()
    entry = get_strategy_registry().get("ts_momentum")
    assert entry is not None
    adapter, views = _adapter(entry.factory(lookbacks=(5,), min_votes=1), engine)
    frame = adapter.signals_frame(views[WINDOW:])
    assert list(frame.index) == list(dates[WINDOW:])
    assert bool((frame.sum(axis=1) <= 1.0 + 1e-9).all())
    assert bool((frame.to_numpy() >= 0).all())


def test_e4_deterministic(tmp_path):
    import strategies  # noqa: F401
    from core.registry import get_strategy_registry

    _fixture(tmp_path)
    engine = _engine(tmp_path)
    engine.setup()
    entry = get_strategy_registry().get("mean_reversion")
    assert entry is not None
    adapter, views = _adapter(entry.factory(lookback=5), engine)
    pd.testing.assert_frame_equal(
        adapter.signals_frame(views[WINDOW:]),
        adapter.signals_frame(views[WINDOW:]),
    )


def test_e2_stop_loss_zeroes_position(tmp_path):
    from core.stops import StopConfig, apply_stops, ohlc_from_data

    dates = pd.bdate_range("2024-01-02", periods=20)
    close = np.full((20, 1), 10.0)
    close[-1, 0] = 7.5  # 第 20 日 −25%
    write_price_fixture(tmp_path, dates, ["000001"], close)
    write_factor(tmp_path, "factor_value", np.ones((20, 1)), dates, ["000001"])
    engine = _engine(tmp_path)
    engine.setup()

    targets = pd.DataFrame(1.0, index=engine.dm.trade_dates, columns=["000001"])
    result = apply_stops(targets, ohlc_from_data(engine.dm), StopConfig(stop_loss_pct=0.2))
    weights = result.weights
    assert float(weights.iloc[0, 0]) == 1.0
    assert float(weights.iloc[-1, 0]) == 0.0
