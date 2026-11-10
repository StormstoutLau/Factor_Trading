"""P-014：V2 停牌路径账目性质测试（L1 判据）。

缺陷背景（RESEARCH_p014 §4）：次日开盘路径（``enable_pending_orders=False``）
在停牌期会为同一标的重复生成清仓单，恢复日一次性全部成交，导致持仓为负
（I2 违规）。本模块用**性质断言**而非逐笔快照锁定修复：

- I1：``invariant_report.ok``（I2 违规 0）
- I2：任意快照持仓 ``quantity >= 0``
- I3：任一笔 SELL 成交量 <= 执行前持仓
- I4：同一 ``(date, stock, side)`` 无 quantity 完全相同的两笔成交

夹具为**本模块自建**（不依赖 ``_golden_cases``）：golden 的 G3/G7 只锁数值，
本模块锁性质，二者互为独立观测面。
"""

from __future__ import annotations

from pathlib import Path

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
from core.engine_v2 import BacktestEngineV2
from core.execution import Trade
from core.pending import OrderSide, create_pending_order

DATES = pd.bdate_range("2024-01-02", periods=20)
CODES = ["000001", "600000", "000002"]
SUSPEND_START, SUSPEND_END = 12, 14  # 600000 于第 12/13 个交易日停牌
INITIAL_CAPITAL = 10_000_000.0


def _prices() -> tuple[np.ndarray, np.ndarray]:
    """确定性波动价（与 P-013 G2/G3 同源构造，无随机数）。"""
    i = np.arange(len(DATES), dtype=float)
    close = np.column_stack([10.0 + 5.0 * k + 0.1 * np.sin(i + k) for k in range(len(CODES))])
    open_ = close * (1.0 + 0.002 * np.cos(i))[:, None]
    return close, open_


def _write_fixture(root: Path) -> None:
    close, open_ = _prices()
    suspend = np.zeros_like(close)
    suspend[SUSPEND_START:SUSPEND_END, 1] = 1
    write_price_fixture(root, DATES, CODES, close, open_prices=open_, suspend=suspend)
    write_factor(
        root,
        "factor_value",
        np.tile(np.arange(1.0, len(CODES) + 1), (len(DATES), 1)),
        DATES,
        CODES,
    )


def _config(root: Path, *, enable_pending: bool) -> BacktestConfig:
    return BacktestConfig(
        data_dir=root,
        output_dir=root / "out",
        factor_files=["factor_value.pkl"],
        cost=CostConfig(
            commission_rate=0.0003,
            commission_min=5.0,
            stamp_tax_rate=0.001,
            slippage_pct=0.001,
        ),
        factor=FactorConfig(
            winsorize_method="none",
            standardize_method="none",
            fill_method="none",
            neutralize=False,
        ),
        optimizer=OptimizerConfig(
            method="equal_weight",
            target_count=len(CODES),
            max_weight=1.0,
            round_lot=True,
            select_top=True,
        ),
        rebalance=RebalanceConfig(method="fixed", frequency="daily"),
        universe=UniverseConfig(
            exclude_na_factors=False,
            exclude_suspended=True,
            exclude_limit_up=True,
        ),
        initial_capital=INITIAL_CAPITAL,
        enable_pending_orders=enable_pending,
    )


def _run(root: Path, *, enable_pending: bool) -> tuple[BacktestEngineV2, dict]:
    engine = BacktestEngineV2(_config(root, enable_pending=enable_pending))
    engine.setup()
    return engine, engine.run()


@pytest.mark.parametrize("enable_pending", [False, True], ids=["next_day", "queue"])
def test_accounting_properties(tmp_path: Path, enable_pending: bool) -> None:
    """I1-I4：两条执行路径在停牌场景下账目自洽。"""
    _write_fixture(tmp_path)
    engine, results = _run(tmp_path, enable_pending=enable_pending)

    report = (results.get("additional_info") or {}).get("invariant_report") or {}
    violations = [
        v for v in (report.get("violations") or []) if str(v.get("code", "")).startswith("I2")
    ]
    assert report.get("ok", True), f"I2 违规 {len(violations)} 项: {violations[:3]}"

    snapshots = engine.tracker.get_snapshots() if engine.tracker else []
    negatives = [
        (str(snap.date.date()), stock, int(pos.quantity))
        for snap in snapshots
        for stock, pos in snap.positions.items()
        if int(pos.quantity) < 0
    ]
    assert not negatives, f"出现负持仓: {negatives[:3]}"

    trades = engine.executor.trade_log.get_trades() if engine.executor else []
    holdings: dict[str, int] = {}
    for trade in trades:
        stock = str(trade.stock)
        qty = int(trade.quantity)
        if trade.side == OrderSide.BUY:
            holdings[stock] = holdings.get(stock, 0) + qty
        else:
            before = holdings.get(stock, 0)
            assert qty <= before, f"{trade.date.date()} {stock} 卖出 {qty} 超过持仓 {before}"
            holdings[stock] = before - qty

    keys = [(str(t.date.date()), str(t.stock), t.side.name, int(t.quantity)) for t in trades]
    duplicated = {key for key in keys if keys.count(key) > 1}
    assert not duplicated, f"同日同向同量重复成交: {sorted(duplicated)[:3]}"


def test_clamp_sell_quantity(tmp_path: Path) -> None:
    """D6：SELL 按可卖持仓夹紧；BUY 原样返回。"""
    _write_fixture(tmp_path)
    engine, _ = _run(tmp_path, enable_pending=False)
    assert engine.tracker is not None

    engine.tracker.execute_trade(
        Trade(
            date=DATES[0],
            stock="600000",
            side=OrderSide.BUY,
            quantity=500,
            price=15.0,
            amount=7500.0,
            cost=0.0,
            net_amount=7500.0,
        )
    )

    buy_order = create_pending_order("600000", OrderSide.BUY, 300, DATES[1])
    sell_full = create_pending_order("600000", OrderSide.SELL, 300, DATES[1])
    sell_excess = create_pending_order("600000", OrderSide.SELL, 800, DATES[1])
    sell_empty = create_pending_order("000001", OrderSide.SELL, 100, DATES[1])

    assert engine._clamp_sell_quantity(buy_order) == 300
    assert engine._clamp_sell_quantity(sell_full) == 300
    assert engine._clamp_sell_quantity(sell_excess) == 500
    assert engine._clamp_sell_quantity(sell_empty) == 0


def test_cancel_next_day_orders_scoped(tmp_path: Path) -> None:
    """D5：撤单只作用于指定标的，返回撤销数。"""
    _write_fixture(tmp_path)
    engine, _ = _run(tmp_path, enable_pending=False)

    in_scope = create_pending_order("600000", OrderSide.SELL, 100, DATES[0])
    out_scope = create_pending_order("000001", OrderSide.SELL, 100, DATES[0])
    engine._next_day_orders = [
        {"order": in_scope, "create_date": DATES[0], "create_date_index": 0},
        {"order": out_scope, "create_date": DATES[0], "create_date_index": 0},
    ]

    cancelled = engine._cancel_next_day_orders(DATES[1], {"600000"})

    assert cancelled == 1
    assert in_scope.status.name == "CANCELLED"
    assert [info["order"] for info in engine._next_day_orders] == [out_scope]


def test_expire_next_day_orders(tmp_path: Path) -> None:
    """D7：次日订单按 max_pending_days_* 过期（买 5 / 卖 10 自然日）。"""
    _write_fixture(tmp_path)
    engine, _ = _run(tmp_path, enable_pending=False)

    stale_buy = create_pending_order("000001", OrderSide.BUY, 100, DATES[0])
    fresh_buy = create_pending_order("000002", OrderSide.BUY, 100, DATES[7])
    stale_sell = create_pending_order("600000", OrderSide.SELL, 100, DATES[0])
    engine._next_day_orders = [
        {"order": stale_buy, "create_date": DATES[0], "create_date_index": 0},
        {"order": fresh_buy, "create_date": DATES[7], "create_date_index": 7},
        {"order": stale_sell, "create_date": DATES[0], "create_date_index": 0},
    ]

    expired = engine._expire_next_day_orders(DATES[9])  # 与 DATES[0] 相差 11 个自然日

    assert expired == 2, "买 5 日 / 卖 10 日：DATES[0] 的两笔均应过期"
    assert stale_buy.status.name == "EXPIRED"
    assert stale_sell.status.name == "EXPIRED"
    assert [info["order"] for info in engine._next_day_orders] == [fresh_buy]
