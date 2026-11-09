"""P-012 B5：动态股票池与退市结算（D5 / T-8~T-10）验收测试。"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd
import pytest

from core.config import BacktestConfig, CostConfig
from core.data import DataManager
from core.engine_v2 import BacktestEngineV2
from core.execution import ExecutionSimulator
from core.pending import OrderSide
from core.tracker import PositionTracker
from filter.universe_filter_clean import UniverseFilter, UniverseFilterConfig

DATES = pd.bdate_range("2024-01-02", periods=10)
STOCKS = ["000001", "430001", "600001"]


def _write_market(root: Path) -> None:
    close = pd.DataFrame(10.0, index=DATES, columns=STOCKS)
    close.to_pickle(root / "close.pkl")
    close.to_pickle(root / "open.pkl")
    pd.DataFrame(1.0, index=DATES, columns=STOCKS).to_pickle(root / "stock_adj.pkl")
    pd.DataFrame(0, index=DATES, columns=STOCKS).to_pickle(root / "suspend.pkl")
    pd.DataFrame(0, index=DATES, columns=STOCKS).to_pickle(root / "st.pkl")


def _write_universe(
    root: Path,
    list_rows: list[dict],
    delist_rows: list[dict],
    manifest: bool = True,
) -> None:
    universe_dir = root / "universe"
    universe_dir.mkdir(exist_ok=True)
    pd.DataFrame(list_rows, columns=["stock", "list_date"]).to_csv(
        universe_dir / "list_date.csv", index=False
    )
    pd.DataFrame(delist_rows, columns=["stock", "delist_date", "delist_return"]).to_csv(
        universe_dir / "delist.csv", index=False
    )
    if manifest:
        payload = {
            "source": "fixture",
            "fetched_at": "2026-11-10T00:00:00",
            "rows": len(list_rows) + len(delist_rows),
            "sha256": "abc123",
            "schema_version": "1.0",
        }
        (universe_dir / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")


def _dm(root: Path) -> DataManager:
    cfg = BacktestConfig(
        data_dir=root, start_date=str(DATES[0].date()), end_date=str(DATES[-1].date())
    )
    return DataManager(cfg)


def _filter(root: Path) -> UniverseFilter:
    filt = UniverseFilter(_dm(root), UniverseFilterConfig())
    filt.build_masks()
    return filt


def test_list_date_masks_before_listing(tmp_path):
    """上市前不可买/不可卖；上市日起恢复（E1/E2）。"""
    _write_market(tmp_path)
    _write_universe(
        tmp_path,
        [{"stock": "430001", "list_date": DATES[3].strftime("%Y-%m-%d")}],
        [],
    )
    filt = _filter(tmp_path)

    assert not filt.buyable.loc[DATES[2], "430001"]
    assert not filt.sellable.loc[DATES[2], "430001"]
    assert filt.buyable.loc[DATES[3], "430001"]
    assert filt.sellable.loc[DATES[3], "430001"]
    assert filt.buyable.loc[DATES[0], "600001"]


def test_delisted_stock_not_tradable_after_delist(tmp_path):
    """退市后不可买/不可卖；退市前正常（E2/V10）。"""
    _write_market(tmp_path)
    _write_universe(
        tmp_path,
        [],
        [{"stock": "000001", "delist_date": DATES[5].strftime("%Y-%m-%d"), "delist_return": -0.10}],
    )
    filt = _filter(tmp_path)

    assert filt.buyable.loc[DATES[4], "000001"]
    assert not filt.buyable.loc[DATES[5], "000001"]
    assert not filt.sellable.loc[DATES[-1], "000001"]
    assert filt.buyable.loc[DATES[-1], "600001"]


def test_missing_universe_degrades_with_single_warning(tmp_path, caplog):
    """快照缺失 → uncorrected + warning 恰一次 + 不限制（E1/INV-4）。"""
    _write_market(tmp_path)
    dm = _dm(tmp_path)

    with caplog.at_level(logging.WARNING):
        snap = dm.universe
        dm.universe  # 幂等，不应重复告警
    assert snap.status == "uncorrected"
    assert snap.manifest is None
    assert snap.list_date.empty
    warnings = [r for r in caplog.records if "universe" in r.getMessage().lower()]
    assert len(warnings) == 1

    filt = UniverseFilter(dm, UniverseFilterConfig())
    filt.build_masks()
    assert bool(filt.buyable.loc[DATES[0], "430001"])


def test_delist_settlement_uses_delist_return(tmp_path):
    """结算价 = last_close × (1 + delist_return)；不重复盯市（E3/F-I9）。"""
    _write_market(tmp_path)
    _write_universe(
        tmp_path,
        [],
        [{"stock": "000001", "delist_date": DATES[5].strftime("%Y-%m-%d"), "delist_return": -0.10}],
    )
    engine = _engine(tmp_path)
    _buy(engine, "000001", 100, DATES[0], 10.0)

    snapshots_before = len(engine.tracker.get_snapshots())
    engine._settle_delisted(DATES[5])

    sells = [t for t in engine.executor.trade_log.get_trades() if t.side == OrderSide.SELL]
    assert len(sells) == 1
    assert sells[0].price == pytest.approx(9.0)
    assert "000001" not in engine.tracker.get_all_positions()
    assert len(engine.tracker.get_snapshots()) == snapshots_before
    assert engine._delist_return_source["000001"] == "delist_return"
    assert engine._n_delisted_closed == 1


def test_delist_settlement_without_return_uses_last_close(tmp_path):
    """无 delist_return → last_close 兜底并标记来源（E3）。"""
    _write_market(tmp_path)
    _write_universe(
        tmp_path,
        [],
        [{"stock": "000001", "delist_date": DATES[5].strftime("%Y-%m-%d")}],
    )
    engine = _engine(tmp_path)
    _buy(engine, "000001", 100, DATES[0], 10.0)

    engine._settle_delisted(DATES[5])

    sells = [t for t in engine.executor.trade_log.get_trades() if t.side == OrderSide.SELL]
    assert sells[0].price == pytest.approx(10.0)
    assert engine._delist_return_source["000001"] == "last_close"
    assert engine._n_delisted_closed == 1


def test_report_includes_survivorship_and_delist_fields(tmp_path):
    """报告透传 survivorship/n_unknown_* 与退市结算字段（E4/V11/V18）。"""
    _write_market(tmp_path)
    _write_universe(
        tmp_path,
        [{"stock": "430001", "list_date": DATES[3].strftime("%Y-%m-%d")}],
        [{"stock": "000001", "delist_date": DATES[5].strftime("%Y-%m-%d"), "delist_return": -0.10}],
    )
    engine = _engine(tmp_path)
    report = engine._universe_report()

    assert report["survivorship"] == "corrected"
    assert report["data_version"] == "abc123"
    assert report["n_unknown_list"] == 2  # 000001 / 600001 无上市日
    assert report["n_unknown_delist"] == 2  # 430001 / 600001 无退市日
    assert report["n_delisted_closed"] == 0
    assert report["delist_return_source"] is None


def _engine(root: Path) -> BacktestEngineV2:
    cfg = BacktestConfig(
        data_dir=root, start_date=str(DATES[0].date()), end_date=str(DATES[-1].date())
    )
    engine = BacktestEngineV2(cfg)
    engine.dm = DataManager(cfg)
    engine.tracker = PositionTracker(len(STOCKS), 1_000_000.0)
    engine.executor = ExecutionSimulator(
        CostConfig(commission_rate=0.0, commission_min=0.0, stamp_tax_rate=0.0, slippage_pct=0.0)
    )
    return engine


def _buy(engine: BacktestEngineV2, stock: str, qty: int, date: pd.Timestamp, price: float) -> None:
    ok, trade = engine.executor.execute_order(stock, OrderSide.BUY, qty, date, price)
    assert ok and trade is not None
    engine.tracker.execute_trade(trade)
