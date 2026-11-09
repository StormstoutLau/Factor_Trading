"""P-012 B3a：复权三口径与旧名别名（D2 / T-5）验收测试。"""

from __future__ import annotations

import pandas as pd
import pytest

from core.config import BacktestConfig
from core.data import DataManager


@pytest.fixture
def dm(tmp_path):
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
        {"000001": [1.0, 1.0, 2.0, 2.0, 2.0], "000002": [1.0, 1.0, 1.0, 1.0, 1.0]},
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
    return DataManager(BacktestConfig(data_dir=tmp_path, adjustment_type="hfq"))


def test_hfq_formula(dm):
    close = dm.close
    adj = dm.adj_factor
    expected = close * adj
    pd.testing.assert_frame_equal(dm.get_adj_price("close", "hfq"), expected, check_exact=True)


def test_qfq_formula(dm):
    close = dm.close
    adj = dm.adj_factor
    expected = close.mul(adj).div(adj.iloc[-1], axis=1)
    pd.testing.assert_frame_equal(dm.get_adj_price("close", "qfq"), expected, check_exact=True)


def test_legacy_alias_warns(dm):
    for legacy, mode in (("forward", "hfq"), ("backward", "qfq"), ("none", "raw")):
        with pytest.warns(DeprecationWarning):
            legacy_price = dm.get_adj_price("close", legacy)
        expected = dm.get_adj_price("close", mode)
        pd.testing.assert_frame_equal(legacy_price, expected, check_exact=True)


def test_unknown_mode_raises(dm):
    with pytest.raises(ValueError, match="未知复权口径"):
        dm.get_adj_price("close", "foo")
