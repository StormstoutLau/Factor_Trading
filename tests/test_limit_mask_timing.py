"""P-012 B4：涨跌停价格法与时点（D4 / T-7）验收测试。"""

from __future__ import annotations

import pandas as pd
import pytest

from core.config import BacktestConfig
from core.data import DataManager
from filter.universe_filter_clean import UniverseFilter, UniverseFilterConfig

DATES = pd.bdate_range("2024-01-02", periods=30)
STOCKS = ["000001", "600001", "300001"]


def _write_market(
    root,
    close: pd.DataFrame,
    open_: pd.DataFrame,
    adj: pd.DataFrame,
    suspend: pd.DataFrame,
    st: pd.DataFrame,
) -> None:
    close.to_pickle(root / "close.pkl")
    open_.to_pickle(root / "open.pkl")
    adj.to_pickle(root / "stock_adj.pkl")
    suspend.to_pickle(root / "suspend.pkl")
    st.to_pickle(root / "st.pkl")


def _flat_market(price: float = 10.0) -> tuple[pd.DataFrame, ...]:
    close = pd.DataFrame(price, index=DATES, columns=STOCKS)
    open_ = close.copy()
    adj = pd.DataFrame(1.0, index=DATES, columns=STOCKS)
    suspend = pd.DataFrame(0, index=DATES, columns=STOCKS)
    st = pd.DataFrame(0, index=DATES, columns=STOCKS)
    return close, open_, adj, suspend, st


def _build(root, filter_cfg: UniverseFilterConfig | None = None) -> UniverseFilter:
    cfg = BacktestConfig(
        data_dir=root, start_date=str(DATES[0].date()), end_date=str(DATES[-1].date())
    )
    dm = DataManager(cfg)
    filt = UniverseFilter(dm, filter_cfg or UniverseFilterConfig())
    filt.build_masks()
    return filt


def test_mask_ignores_future_perturbation(tmp_path):
    """t 行掩码只依赖 ≤t 的可得输入（V9 / INV-2）。"""
    close, open_, adj, suspend, st = _flat_market()
    open_ = close * 1.01
    _write_market(tmp_path, close, open_, adj, suspend, st)
    base = _build(tmp_path)

    cut = 10
    close2, open2, adj2, suspend2, st2 = _flat_market()
    open2 = close2 * 1.01
    # 扰动 t>cut 的全部未来输入
    close2.iloc[cut + 1 :] *= 3.0
    open2.iloc[cut + 1 :] *= 5.0
    adj2.iloc[cut + 1 :] *= 2.0
    suspend2.iloc[cut + 1 :] = 1
    st2.iloc[cut + 1 :] = 1
    _write_market(tmp_path, close2, open2, adj2, suspend2, st2)
    after = _build(tmp_path)

    window = DATES[: cut + 1]
    pd.testing.assert_frame_equal(base.buyable.loc[window], after.buyable.loc[window])
    pd.testing.assert_frame_equal(base.sellable.loc[window], after.sellable.loc[window])


def test_open_at_limit_up_not_buyable(tmp_path):
    """开盘价达到涨停价 → 当日不可买；未达到（超出 EPS）→ 可买。"""
    close, open_, adj, suspend, st = _flat_market()
    day = DATES[5]
    open_.loc[day, "000001"] = 11.0  # prev_close 10.0 × 1.10
    open_.loc[day, "600001"] = 10.993  # 距涨停 0.007 > EPS
    _write_market(tmp_path, close, open_, adj, suspend, st)
    filt = _build(tmp_path)

    assert not filt.buyable.loc[day, "000001"]
    assert filt.buyable.loc[day, "600001"]
    assert filt.sellable.loc[day, "000001"]


def test_open_at_limit_down_not_sellable(tmp_path):
    """开盘价达到跌停价 → 当日不可卖；未达到（超出 EPS）→ 可卖。"""
    close, open_, adj, suspend, st = _flat_market()
    day = DATES[5]
    open_.loc[day, "000001"] = 9.0  # prev_close 10.0 × 0.90
    open_.loc[day, "600001"] = 9.007  # 距跌停 0.007 > EPS
    _write_market(tmp_path, close, open_, adj, suspend, st)
    filt = _build(tmp_path)

    assert not filt.sellable.loc[day, "000001"]
    assert filt.sellable.loc[day, "600001"]
    assert filt.buyable.loc[day, "000001"]
