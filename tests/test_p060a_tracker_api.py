"""P-060a 持仓跟踪器公共 API 单元测试（T-A16..A19）。

对应 [IMPL_p060a §4.4](../../docs/IMPL_p060a_implementation.md)：零生产改动；
绩效指标按本仓 ddof=0 口径锁定（D-04，与 empyrical 的 ddof=1 不同）。
外部对照：X24 pyfolio 行业暴露、X25 empyrical 峰值回撤、X26 年化因子 252。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.config import AssetType
from core.futures_accounting import ContractSpec
from core.tracker import PortfolioSnapshot, Position, PositionTracker

DAY1 = pd.Timestamp("2024-01-02")
DAY2 = pd.Timestamp("2024-01-03")
DATE = pd.Timestamp("2024-01-04")


def stock_position(
    stock: str,
    quantity: float,
    avg_cost: float,
    market_value: float,
    unrealized_pnl: float = 0.0,
) -> Position:
    return Position(
        stock=stock,
        quantity=quantity,
        avg_cost=avg_cost,
        market_value=market_value,
        unrealized_pnl=unrealized_pnl,
        realized_pnl=0.0,
    )


def future_position(
    stock: str,
    quantity: float,
    notional_value: float,
    market_value: float,
    margin_used: float = 0.0,
    settle_base: float = 0.0,
    multiplier: float = 300.0,
) -> Position:
    return Position(
        stock=stock,
        quantity=quantity,
        avg_cost=settle_base,
        market_value=market_value,
        unrealized_pnl=0.0,
        realized_pnl=0.0,
        margin_used=margin_used,
        asset_type=AssetType.FUTURE,
        multiplier=multiplier,
        notional_value=notional_value,
        settle_base=settle_base,
    )


# ---------------------------------------------------------------------------
# T-A16 持仓权重
# ---------------------------------------------------------------------------


def test_p060a_a16a_empty_book_and_nonpositive_total_return_empty_series():
    """T-A16a | oracle=boundary：空仓 / total<=0 → 空 Series"""
    empty = PositionTracker(2, 1_000.0)
    assert empty.get_position_weights(pd.Series({"A": 10.0})).empty

    broke = PositionTracker(1, 1_000.0)
    broke._cash = -100.0
    assert broke.get_position_weights(pd.Series({"A": 10.0})).empty


def test_p060a_a16b_stock_and_future_weights():
    """T-A16b | oracle=closed-form：股票用 market_value、期货用 notional_value，分母为总价值"""
    tracker = PositionTracker(3, 1_000.0)
    tracker._positions["A"] = stock_position("A", 10, 10.0, 100.0)
    tracker._positions["B"] = stock_position("B", 20, 10.0, 200.0)
    tracker._positions["C"] = future_position("C", 1, 500.0, 50.0)

    weights = tracker.get_position_weights(pd.Series({"A": 100.0, "B": 200.0, "C": 500.0}))

    total = 1_000.0 + 100.0 + 200.0 + 50.0
    assert weights["A"] == pytest.approx(100.0 / total)
    assert weights["B"] == pytest.approx(200.0 / total)
    assert weights["C"] == pytest.approx(500.0 / total)
    assert weights.sum() < 1.0


def test_p060a_a16c_negative_stock_only_with_allow_flag():
    """T-A16c | oracle=state：负股仅在 allow_negative_stock 下计入（负权重）"""
    trader = PositionTracker(1, 1_000.0, allow_negative_stock_positions=True)
    trader._positions["A"] = stock_position("A", -10, 10.0, -100.0)

    allowed = trader.get_position_weights(pd.Series({"A": 10.0}))
    blocked = PositionTracker(1, 1_000.0)
    blocked._positions["A"] = stock_position("A", -10, 10.0, -100.0)

    assert allowed["A"] == pytest.approx(-100.0 / 900.0)
    assert blocked.get_position_weights(pd.Series({"A": 10.0})).empty


# ---------------------------------------------------------------------------
# T-A17 行业暴露
# ---------------------------------------------------------------------------


def test_p060a_a17_sector_exposure_aggregates_and_skips():
    """T-A17 | oracle=closed-form：同行业相加、缺映射/零持仓期货跳过"""
    tracker = PositionTracker(5, 1_000.0)
    tracker._positions["A"] = stock_position("A", 10, 10.0, 100.0)
    tracker._positions["B"] = stock_position("B", 20, 10.0, 200.0)
    tracker._positions["C"] = stock_position("C", 30, 10.0, 300.0)
    tracker._positions["D"] = future_position("D", 0, 999.0, 0.0)
    tracker._positions["E"] = future_position("E", 1, 300.0, 50.0)

    industry = pd.Series({"A": "IND1", "B": "IND1", "E": "IND2"})
    exposure = tracker.get_sector_exposure(industry)

    total = 1_000.0 + 100.0 + 200.0 + 300.0 + 0.0 + 50.0
    assert set(exposure) == {"IND1", "IND2"}
    assert exposure["IND1"] == pytest.approx(300.0 / total)
    assert exposure["IND2"] == pytest.approx(300.0 / total)

    broke = PositionTracker(1, 1_000.0)
    broke._cash = -100.0
    assert broke.get_sector_exposure(pd.Series({"A": "IND1"})) == {}

    skip = PositionTracker(2, 1_000.0)
    skip._positions["N"] = stock_position("N", -5, 10.0, -50.0)
    skip._positions["Z"] = future_position("Z", 0, 0.0, 0.0)
    assert skip.get_sector_exposure(pd.Series({"N": "IND1", "Z": "IND2"})) == {}


# ---------------------------------------------------------------------------
# T-A18 期货结算
# ---------------------------------------------------------------------------


def test_p060a_a18_settle_three_branches():
    """T-A18 | oracle=contract：无 specs/无期货→None；有持仓→盈亏与保证金重算"""
    no_specs = PositionTracker(1, 1_000_000.0)
    no_specs._positions["IF"] = future_position("IF", 2, 2_280_000.0, 228_000.0, 228_000.0)
    assert no_specs.settle(DATE, {"IF": 3_900.0}) is None

    stock_only = PositionTracker(1, 1_000_000.0)
    stock_only.set_contract_specs(
        {"IF": ContractSpec(symbol="IF", multiplier=300.0, margin_ratio=0.1)}
    )
    stock_only._positions["A"] = stock_position("A", 10, 10.0, 100.0)
    assert stock_only.settle(DATE, {"IF": 3_900.0}) is None

    tracker = PositionTracker(1, 1_000_000.0)
    tracker.set_contract_specs(
        {"IF": ContractSpec(symbol="IF", multiplier=300.0, margin_ratio=0.1)}
    )
    tracker._positions["IF"] = future_position(
        "IF", 2, 2_280_000.0, 228_000.0, margin_used=228_000.0, settle_base=3_800.0
    )
    tracker._positions["A"] = stock_position("A", 10, 10.0, 100.0)

    result = tracker.settle(DATE, {"IF": 3_900.0})

    assert result is not None
    assert result.total_pnl == pytest.approx(60_000.0)  # 2 × 100 × 300
    assert result.margin_after["IF"] == pytest.approx(234_000.0)  # 2×3900×300×0.1
    assert result.margin_delta == pytest.approx(6_000.0)
    assert tracker.get_cash() == pytest.approx(1_054_000.0)  # +60,000 − 6,000
    assert tracker.get_available_cash() == pytest.approx(1_054_000.0)
    assert tracker.get_total_cash() == pytest.approx(1_288_000.0)  # 现金 + 保证金
    pos = tracker.get_position("IF")
    assert pos is not None
    assert pos.settle_base == pytest.approx(3_900.0)
    assert pos.avg_cost == pytest.approx(3_900.0)
    assert pos.margin_used == pytest.approx(234_000.0)
    assert pos.mtm_pnl == 0.0

    proxy = PositionTracker(1, 1_000_000.0)
    proxy.set_contract_specs({"IF": ContractSpec(symbol="IF", multiplier=300.0, margin_ratio=0.1)})
    proxy._positions["IF"] = future_position(
        "IF", 2, 2_280_000.0, 228_000.0, margin_used=228_000.0, settle_base=3_800.0
    )
    proxy_result = proxy.settle(DATE, {}, fallback_prices={"IF": 3_850.0})
    assert proxy_result is not None and proxy_result.proxy_used is True
    assert proxy_result.total_pnl == pytest.approx(30_000.0)  # 2 × 50 × 300

    invalid = PositionTracker(1, 1_000_000.0)
    invalid.set_contract_specs(
        {"IF": ContractSpec(symbol="IF", multiplier=300.0, margin_ratio=0.1)}
    )
    invalid._positions["IF"] = future_position(
        "IF", 2, 2_280_000.0, 228_000.0, margin_used=228_000.0, settle_base=3_800.0
    )
    invalid_result = invalid.settle(DATE, {}, fallback_prices={"IF": 0.0})
    assert invalid_result is not None
    assert invalid_result.proxy_used is False
    assert invalid_result.total_pnl == 0.0


# ---------------------------------------------------------------------------
# T-A19 持仓校验 / 绩效指标 / 重置
# ---------------------------------------------------------------------------


def test_p060a_a19a_validate_positions_reports_all_error_classes():
    """T-A19a | oracle=contract：现金负/期货权益/负持仓/均价/市值 五类错误均出现"""
    tracker = PositionTracker(4, 1_000.0)
    tracker._cash = -1.0
    tracker._positions["F"] = future_position("F", 1, 300.0, 999.0, margin_used=100.0)
    tracker._positions["N"] = stock_position("N", -5, 10.0, -50.0)
    tracker._positions["P"] = stock_position("P", 10, 0.0, 100.0)
    tracker._positions["Q"] = stock_position("Q", 10, 10.0, 50.0)
    tracker._positions["Z"] = future_position("Z", 0, 0.0, 0.0)

    errors = tracker.validate_positions(pd.Series({"Q": 10.0}))
    text = " | ".join(errors)

    assert "现金余额为负" in text
    assert "期货权益错误" in text
    assert "持仓数量为负" in text
    assert "平均成本异常" in text
    assert "市值计算错误" in text


def test_p060a_a19b_metrics_follow_ddof_zero_and_reset_clears():
    """T-A19b | oracle=closed-form：年化/波动(ddof=0)/夏普/回撤；reset 清空并置初始资金"""
    assert PositionTracker(1, 1_000.0).get_performance_metrics() == {}

    tracker = PositionTracker(1, 1_000.0)
    tracker._cash = 900.0
    tracker._positions["A"] = stock_position("A", 10, 10.0, 100.0)

    tracker.update_market_values(DAY1, pd.Series({"A": 11.0}))
    tracker.update_market_values(DAY2, pd.Series({"A": 12.0}))

    metrics = tracker.get_performance_metrics()
    daily = [0.01, 10.0 / 1_010.0]
    total_return = 0.02
    annual_return = (1.0 + total_return) ** (252.0 / len(daily)) - 1.0
    annual_vol = np.std(daily) * np.sqrt(252.0)

    assert metrics["total_return"] == pytest.approx(total_return)
    assert metrics["annual_return"] == pytest.approx(annual_return)
    assert metrics["annual_volatility"] == pytest.approx(annual_vol)
    assert metrics["sharpe_ratio"] == pytest.approx(annual_return / annual_vol)
    assert metrics["max_drawdown"] == pytest.approx(0.0)
    assert metrics["trading_days"] == 2
    assert metrics["position_count"] == 1
    assert metrics["current_value"] == pytest.approx(1_020.0)

    tracker._positions["Z"] = future_position("Z", 0, 0.0, 0.0)
    tracker._positions["F"] = future_position(
        "F", 1, 300.0, 30.0, margin_used=30.0, settle_base=10.0
    )
    tracker.update_market_values(DAY2, pd.Series({"A": 0.0, "Z": 10.0, "F": 11.0}))
    tracker.update_market_values(DAY2, pd.Series(dtype=float))  # 缺价跳过

    nan_tracker = PositionTracker(1, 1_000.0)
    nan_tracker._snapshots.append(
        PortfolioSnapshot(
            date=DAY1,
            cash=1_000.0,
            total_value=1_000.0,
            positions={},
            daily_return=np.nan,
            cumulative_return=0.0,
        )
    )
    assert nan_tracker.get_performance_metrics() == {}

    tracker.reset(5_000.0)

    assert tracker.get_total_value() == pytest.approx(5_000.0)
    assert tracker.get_all_positions() == {}
    assert tracker.get_snapshots() == []
    assert tracker.get_performance_metrics() == {}
