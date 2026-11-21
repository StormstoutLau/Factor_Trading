"""P-051b V 组：MarketView.history 与 views_from_data(history_window) 契约。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from _p051b_common import DATES
from _synth_fixture import write_factor, write_price_fixture

N = 140
CODES3 = ["000001", "600000", "000002"]


def _fixture(root):
    dates = pd.bdate_range("2024-01-02", periods=N)
    prices = np.array([[10.0 + 0.1 * i + 0.5 * j for j in range(3)] for i in range(N)])
    write_price_fixture(root, dates, CODES3, prices)
    write_factor(root, "factor_value", np.tile([1.0, 2.0, 3.0], (N, 1)), dates, CODES3)
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


def test_v1_five_positional_args_and_history_default_none():
    from core.strategy import MarketView

    idx = DATES[:1]
    view = MarketView(
        idx[0],
        pd.Series({"000001": 1.0}),
        pd.Series({"000001": True}),
        pd.Series({"000001": 10.0}),
        None,
    )
    assert view.history is None


def test_v2_unhashable_and_eq_raises():
    from core.strategy import MarketView

    def build():
        return MarketView(
            date=DATES[0],
            signal=pd.Series({"000001": 1.0}),
            tradable=pd.Series({"000001": True}),
            prices=pd.Series({"000001": 10.0}),
            returns=None,
        )

    a, b = build(), build()
    with pytest.raises(TypeError):
        hash(a)
    with pytest.raises(ValueError):
        a == b  # type: ignore[truthy-function]


def test_v3_history_keys_and_columns(tmp_path):
    from core.strategy import BacktestAdapter

    dates = _fixture(tmp_path)
    engine = _engine(tmp_path)
    engine.setup()
    views = BacktestAdapter.views_from_data(engine.dm, engine._composite_signal, history_window=60)
    view = views[80]
    assert view.history is not None
    assert set(view.history) == {"close", "high", "low"}
    assert list(view.history["close"].columns) == list(engine.dm.stock_codes)
    assert len(view.history["close"]) == 60
    assert view.history["close"].index[-1] < dates[80]


def test_v4_window_zero_keeps_history_none(tmp_path):
    from core.strategy import BacktestAdapter

    _fixture(tmp_path)
    engine = _engine(tmp_path)
    engine.setup()
    views = BacktestAdapter.views_from_data(engine.dm, engine._composite_signal, returns_window=60)
    assert all(view.history is None for view in views)
    for view in views:
        assert isinstance(view.prices, pd.Series)
        assert float(view.prices.dtype.kind == "f")
        if view.returns is not None:
            assert isinstance(view.returns, pd.DataFrame)


def test_v5_insufficient_history_becomes_none(tmp_path):
    from core.strategy import BacktestAdapter

    _fixture(tmp_path)
    engine = _engine(tmp_path)
    engine.setup()
    views = BacktestAdapter.views_from_data(engine.dm, engine._composite_signal, history_window=60)
    assert all(view.history is None for view in views[:60])
    assert all(view.history is not None for view in views[60:])
    assert all(len(view.history["close"]) == 60 for view in views[60:])


def test_v6_history_same_window_as_returns(tmp_path):
    from core.strategy import BacktestAdapter

    _fixture(tmp_path)
    engine = _engine(tmp_path)
    engine.setup()
    views = BacktestAdapter.views_from_data(
        engine.dm, engine._composite_signal, returns_window=60, history_window=60
    )
    for view in views[60:]:
        assert view.history is not None and view.returns is not None
        assert view.history["close"].index.equals(view.returns.index)


def test_v7_history_last_row_is_previous_day(tmp_path):
    from core.strategy import BacktestAdapter

    dates = _fixture(tmp_path)
    engine = _engine(tmp_path)
    engine.setup()
    views = BacktestAdapter.views_from_data(engine.dm, engine._composite_signal, history_window=60)
    raw = engine.dm.get_adj_price("close", "raw")
    for i in (60, 100, 139):
        view = views[i]
        assert view.history is not None
        expected = raw.loc[dates[i - 1]].reindex(engine.dm.stock_codes)
        pd.testing.assert_series_equal(
            view.history["close"].iloc[-1].reindex(engine.dm.stock_codes),
            expected,
        )
