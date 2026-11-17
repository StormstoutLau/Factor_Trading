"""P-039 adj_factor 日期覆盖缺陷回归测试（U-P038-2）。

覆盖：缺日补齐 / 无缺日等价 / 窗口首日缺口 / 不污染无前值期 / 修复范围仅 adj。
夹具复用 ``tests/_synth_fixture.write_price_fixture``（全日期覆盖），
再用局部后处理改写 ``stock_adj.pkl``——**不修改共享夹具**（DESIGN-D3）。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from core.config import BacktestConfig
from core.data import DataManager
from _synth_fixture import write_price_fixture

DATES = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08"]
CODES = ["000001", "000002"]
ADJ_BY_DATE = {
    "2024-01-02": 1.0,
    "2024-01-03": 1.1,
    "2024-01-04": 1.2,
    "2024-01-05": 1.3,
    "2024-01-08": 1.4,
}


def _prepare(tmp_path: Path, *, drop_adj=(), drop_open=(), adj_na=()) -> DataManager:
    """写完整夹具 → 后处理 → 返回已加载 basic data 的 DataManager。"""
    write_price_fixture(tmp_path, DATES, CODES, prices=10.0)

    adj_path = tmp_path / "stock_adj.pkl"
    adj = pd.read_pickle(adj_path)
    for d, v in ADJ_BY_DATE.items():
        adj.loc[pd.Timestamp(d), :] = v
    for d in adj_na:  # 该日全列置 NaN（模拟「无前值」）
        adj.loc[pd.Timestamp(d), :] = np.nan
    if drop_adj:
        adj = adj.drop(index=[pd.Timestamp(d) for d in drop_adj])
    adj.to_pickle(adj_path)

    if drop_open:
        open_path = tmp_path / "open.pkl"
        o = pd.read_pickle(open_path)
        o = o.drop(index=[pd.Timestamp(d) for d in drop_open])
        o.to_pickle(open_path)

    cfg = BacktestConfig(data_dir=tmp_path, write_manifest=False)
    dm = DataManager(cfg)
    _ = dm.trade_dates  # 触发 _load_basic_data，使 _trade_dates 非 None
    return dm


def test_v1_missing_day_ffilled(tmp_path):
    """V1：缺日补齐为前值。"""
    dm = _prepare(tmp_path, drop_adj=["2024-01-04"])
    adj = dm.adj_factor
    assert len(adj) == len(DATES)
    assert adj.loc[pd.Timestamp("2024-01-04"), "000001"] == pytest.approx(1.1)
    assert adj.loc[pd.Timestamp("2024-01-05"), "000001"] == pytest.approx(1.3)


def test_v2_no_gap_equivalence(tmp_path):
    """V2：无缺日时与直接读取逐值相等（回归保护）。"""
    dm = _prepare(tmp_path)
    adj = dm.adj_factor
    raw = pd.read_pickle(tmp_path / "stock_adj.pkl")
    raw = raw.reindex(columns=dm.stock_codes)  # F-S4-P039-2：显式列对齐
    pd.testing.assert_frame_equal(adj, raw)


def test_v3_window_first_day_gap_uses_outside_prev(tmp_path):
    """V3：窗口首日缺口 → 取窗口外前值（三段式唯一性）。"""
    write_price_fixture(tmp_path, DATES, CODES, prices=10.0)
    adj_path = tmp_path / "stock_adj.pkl"
    adj = pd.read_pickle(adj_path)
    for d, v in ADJ_BY_DATE.items():
        adj.loc[pd.Timestamp(d), :] = v
    adj = adj.drop(index=[pd.Timestamp("2024-01-04")])
    adj.to_pickle(adj_path)

    cfg = BacktestConfig(data_dir=tmp_path, start_date="2024-01-04", write_manifest=False)
    dm = DataManager(cfg)
    _ = dm.trade_dates
    got = dm.adj_factor.loc[pd.Timestamp("2024-01-04"), "000001"]
    assert got == pytest.approx(1.1)  # 2024-01-03（窗口外）的值


def test_v4_no_bfill_before_first_value(tmp_path):
    """V4：无前值时保持 NaN（禁止 bfill 污染）。"""
    dm = _prepare(tmp_path, adj_na=("2024-01-02",))
    adj = dm.adj_factor
    assert np.isnan(adj.loc[pd.Timestamp("2024-01-02"), "000001"])
    assert adj.loc[pd.Timestamp("2024-01-03"), "000001"] == pytest.approx(1.1)


def test_v5_other_kinds_still_strict(tmp_path):
    """V5：修复范围仅 adj_factor——open 缺日仍按现网 KeyError（边界保护）。"""
    dm = _prepare(tmp_path, drop_open=["2024-01-04"])
    with pytest.raises(KeyError, match="not in index"):  # F-S4-P039-3
        _ = dm.open
