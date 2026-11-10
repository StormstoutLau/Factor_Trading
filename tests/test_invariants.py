"""P-011 B1：不变量 I1-I4 + 引擎接入验收。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.config import BacktestConfig, OptimizerConfig, RebalanceConfig
from core.engine_v2 import BacktestEngineV2
from core.invariants import (
    check_all,
    check_cost_identity,
    check_nav_identity,
    check_position_identity,
    check_return_identity,
)
from core.pending import OrderSide
from core.tracker import PortfolioSnapshot, Position
from _synth_fixture import write_factor, write_price_fixture


def _position(stock: str, quantity: float, market_value: float) -> Position:
    return Position(
        stock=stock,
        quantity=quantity,
        avg_cost=10.0,
        market_value=market_value,
        unrealized_pnl=0.0,
        realized_pnl=0.0,
    )


def _snapshot(
    day: str,
    cash: float,
    total_value: float,
    positions: dict[str, Position] | None = None,
    *,
    initial_capital: float = 1000.0,
    daily_return: float | None = None,
    cumulative_return: float | None = None,
    prev_value: float | None = None,
) -> PortfolioSnapshot:
    positions = positions or {}
    if daily_return is None:
        base = initial_capital if prev_value is None else prev_value
        daily_return = (total_value - base) / base if base else 0.0
    if cumulative_return is None:
        cumulative_return = (total_value - initial_capital) / initial_capital
    return PortfolioSnapshot(
        date=pd.Timestamp(day),
        cash=cash,
        total_value=total_value,
        positions=positions,
        daily_return=daily_return,
        cumulative_return=cumulative_return,
    )


def _trade(
    day: str,
    stock: str,
    side: OrderSide,
    quantity: int,
    price: float = 10.0,
    cost: float = 0.0,
):
    from core.execution import Trade

    amount = quantity * price
    net_amount = amount + cost if side == OrderSide.BUY else amount - cost
    return Trade(
        date=pd.Timestamp(day),
        stock=stock,
        side=side,
        quantity=quantity,
        price=price,
        amount=amount,
        cost=cost,
        net_amount=net_amount,
    )


def test_nav_identity_ok():
    snaps = [
        _snapshot("2024-01-02", 400.0, 1000.0, {"A": _position("A", 60, 600)}),
        _snapshot("2024-01-03", 500.0, 1100.0, {"A": _position("A", 60, 600)}),
    ]
    assert check_nav_identity(snaps) == []


def test_nav_identity_detects_mismatch():
    snaps = [_snapshot("2024-01-02", 400.0, 1001.0, {"A": _position("A", 60, 600)})]
    violations = check_nav_identity(snaps)
    assert len(violations) == 1
    assert violations[0].code == "I1"
    assert violations[0].date == "2024-01-02"


def test_position_identity_ok():
    snaps = [
        _snapshot("2024-01-02", 0.0, 1000.0, {"A": _position("A", 100, 1000)}),
        _snapshot("2024-01-03", 0.0, 600.0, {"A": _position("A", 60, 600)}),
        _snapshot("2024-01-04", 0.0, 600.0, {"A": _position("A", 60, 600)}),
    ]
    trades = [
        _trade("2024-01-02", "A", OrderSide.BUY, 100),
        _trade("2024-01-03", "A", OrderSide.SELL, 40),
    ]
    assert check_position_identity(snaps, trades) == []


def test_position_identity_detects_untracked_change():
    snaps = [
        _snapshot("2024-01-02", 0.0, 1000.0, {"A": _position("A", 100, 1000)}),
        _snapshot("2024-01-03", 0.0, 800.0, {"A": _position("A", 80, 800)}),
        _snapshot("2024-01-04", 0.0, 1000.0, {"A": _position("A", 100, 1000)}),
    ]
    trades = [_trade("2024-01-02", "A", OrderSide.BUY, 100)]
    violations = check_position_identity(snaps, trades)
    assert len(violations) == 1
    assert violations[0].code == "I2"
    assert violations[0].date == "2024-01-03"
    assert "A" in violations[0].detail


def test_position_identity_skips_ambiguous_same_day_snapshots():
    """同日多次快照（末日强平追加）无法还原成交边界 → 该日期跳过。"""
    snaps = [
        _snapshot("2024-01-02", 0.0, 1000.0, {"A": _position("A", 100, 1000)}),
        _snapshot("2024-01-03", 0.0, 1000.0, {"A": _position("A", 100, 1000)}),
        _snapshot("2024-01-03", 1000.0, 1000.0, {}),
    ]
    trades = [
        _trade("2024-01-02", "A", OrderSide.BUY, 100),
        _trade("2024-01-03", "A", OrderSide.SELL, 100),
    ]
    assert check_position_identity(snaps, trades) == []


def test_cost_identity_ok():
    trades = [
        _trade("2024-01-02", "A", OrderSide.BUY, 100, cost=5.0),
        _trade("2024-01-03", "A", OrderSide.SELL, 100, cost=7.0),
    ]
    stats = {"total_cost": 12.0}
    assert check_cost_identity(trades, stats) == []


def test_cost_identity_detects_negative_cost():
    trades = [_trade("2024-01-02", "A", OrderSide.BUY, 100, cost=-1.0)]
    violations = check_cost_identity(trades, {"total_cost": -1.0})
    assert any(v.code == "I3" and "cost" in v.detail for v in violations)


def test_return_identity_ok():
    snaps = [
        _snapshot("2024-01-02", 0.0, 1000.0, initial_capital=1000.0),
        _snapshot(
            "2024-01-03",
            0.0,
            1100.0,
            initial_capital=1000.0,
            prev_value=1000.0,
        ),
    ]
    assert check_return_identity(snaps, initial_capital=1000.0) == []


def test_return_identity_detects_drift():
    snaps = [
        _snapshot(
            "2024-01-02",
            0.0,
            1000.0,
            initial_capital=1000.0,
            daily_return=0.01,
            cumulative_return=0.0,
        )
    ]
    violations = check_return_identity(snaps, initial_capital=1000.0)
    assert len(violations) == 1
    assert violations[0].code == "I4"


def test_check_all_report_mode():
    snaps = [_snapshot("2024-01-02", 0.0, 1001.0, {"A": _position("A", 100, 1000)})]
    report = check_all(snaps, [], {"total_cost": 0.0}, initial_capital=1000.0, mode="report")
    assert report.ok is False
    assert report.mode == "report"
    assert report.checked == 1
    assert any(v.code == "I1" for v in report.violations)
    with pytest.raises(ValueError):
        check_all(snaps, [], {"total_cost": 0.0}, initial_capital=1000.0, mode="bogus")  # type: ignore[arg-type]


def test_engine_emits_invariant_report(tmp_path):
    rng = np.random.default_rng(20261110)
    dates = pd.bdate_range("2024-01-02", periods=20)
    codes = [f"00000{i}" for i in range(1, 6)]
    prices = 10.0 * np.cumprod(1.0 + rng.normal(0.0, 0.01, (len(dates), len(codes))), axis=0)
    write_price_fixture(tmp_path, dates, codes, prices)
    close = pd.DataFrame(prices, index=dates, columns=codes)
    write_factor(tmp_path, "factor_value", close.pct_change(5).fillna(0.0), dates, codes)

    cfg = BacktestConfig(
        data_dir=tmp_path,
        output_dir=tmp_path / "out",
        factor_files=["factor_value.pkl"],
        optimizer=OptimizerConfig(method="equal_weight", target_count=3, max_weight=1.0),
        rebalance=RebalanceConfig(method="fixed", frequency="N_days", n_days=5),
        initial_capital=1_000_000.0,
    )
    engine = BacktestEngineV2(cfg)
    engine.setup()
    results = engine.run()

    report = results["additional_info"]["invariant_report"]
    assert report["ok"] is True, report["violations"]
    assert report["mode"] == "report"
    assert report["checked"] == len(engine.tracker.get_snapshots())
