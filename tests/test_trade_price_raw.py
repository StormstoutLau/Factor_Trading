"""P-012 B3b：成交/估值取价切 raw + legacy 复现旧口径（D2 / T-6）。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.config import BacktestConfig, PriceModeConfig
from core.data import DataManager
from core.engine_v2 import BacktestEngineV2


@pytest.fixture
def data_dir(tmp_path):
    dates = pd.bdate_range("2024-01-02", periods=5)
    codes = ["000001", "000002"]
    close = pd.DataFrame(
        {
            "000001": [10.0, 11.0, 12.0, 6.0, 6.5],
            "000002": [20.0, 20.5, 21.0, 21.5, 22.0],
        },
        index=dates,
    )
    adj = pd.DataFrame(
        {"000001": [1.0, 1.0, 2.0, 2.0, 2.0], "000002": [1.0] * 5},
        index=dates,
    )
    for name, frame in {
        "close.pkl": close,
        "open.pkl": close,
        "high.pkl": close,
        "low.pkl": close,
        "stock_adj.pkl": adj,
        "suspend.pkl": pd.DataFrame(0, index=dates, columns=codes),
        "industry.pkl": pd.DataFrame(1, index=dates, columns=codes),
    }.items():
        frame.to_pickle(tmp_path / name)
    return tmp_path


def test_execution_price_excludes_adj(data_dir):
    cfg = BacktestConfig(data_dir=data_dir)
    engine = BacktestEngineV2(cfg)
    dm = DataManager(cfg)
    assert cfg.price_modes.trade == "raw"
    assert cfg.price_modes.valuation == "raw"
    pd.testing.assert_frame_equal(
        engine._exec_price(dm, "close"),
        dm.get_adj_price("close", "raw"),
        check_exact=True,
    )

    legacy_cfg = BacktestConfig(
        data_dir=data_dir, legacy_adjustment=True, adjustment_type="forward"
    )
    legacy_engine = BacktestEngineV2(legacy_cfg)
    legacy_dm = DataManager(legacy_cfg)
    pd.testing.assert_frame_equal(
        legacy_engine._exec_price(legacy_dm, "close"),
        legacy_dm.get_adj_price("close", "hfq"),
        check_exact=True,
    )


def test_returns_mode_controls_calculation(data_dir):
    cfg = BacktestConfig(data_dir=data_dir, price_modes=PriceModeConfig(returns="raw"))
    dm = DataManager(cfg)
    raw = dm.get_adj_price("close", "raw")
    expected = raw.pct_change()
    expected.iloc[0] = np.nan
    pd.testing.assert_frame_equal(dm.returns, expected, check_exact=True)

    legacy_cfg = BacktestConfig(data_dir=data_dir, legacy_adjustment=True, adjustment_type="none")
    legacy_dm = DataManager(legacy_cfg)
    pd.testing.assert_frame_equal(legacy_dm.returns, expected, check_exact=True)
