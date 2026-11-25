"""P-060a 交易执行成本单元测试（T-A01..A05）。

对应 [IMPL_p060a §4.1](../../docs/IMPL_p060a_implementation.md)：零生产改动，
全部闭式/契约 oracle；外部对照见 X4（zipline 最低佣金）、X6（qlib 分侧费率）。
"""

from __future__ import annotations

import pandas as pd
import pytest

from core.config import AssetCost, AssetType, CostConfig, ExecutionPriceType
from core.execution import ExecutionSimulator
from core.pending import OrderSide, PendingOrder

_DATE = pd.Timestamp("2024-01-02")


def make_simulator(**overrides) -> ExecutionSimulator:
    """构造默认成本口径（万三 / 最低 5 / 印花税 0.1% / 滑点 0.1%）的执行模拟器。"""
    params = {
        "commission_rate": 0.0003,
        "commission_min": 5.0,
        "stamp_tax_rate": 0.001,
        "slippage_pct": 0.001,
    }
    params.update(overrides)
    return ExecutionSimulator(CostConfig(**params))


# ---------------------------------------------------------------------------
# T-A01 佣金下限
# ---------------------------------------------------------------------------


def test_p060a_a01a_commission_floor_applies():
    """T-A01a | oracle=closed-form：1000×0.0003=0.3 → 下限 5 + 滑点 1 = 6.0"""
    sim = make_simulator()
    assert sim._calculate_cost(1_000.0, OrderSide.BUY) == pytest.approx(6.0)


def test_p060a_a01b_rate_wins_above_floor():
    """T-A01b | oracle=closed-form：1e6×0.0003=300（下限失效）+ 滑点 1000 = 1300"""
    sim = make_simulator()
    assert sim._calculate_cost(1_000_000.0, OrderSide.BUY) == pytest.approx(1_300.0)


# ---------------------------------------------------------------------------
# T-A02 印花税单边 / 期货成本口径
# ---------------------------------------------------------------------------


def test_p060a_a02a_buy_has_no_stamp_tax():
    """T-A02a | oracle=closed-form：佣金 5 + 滑点 10（买入无印花税）= 15"""
    sim = make_simulator()
    assert sim._calculate_cost(10_000.0, OrderSide.BUY) == pytest.approx(15.0)


def test_p060a_a02b_sell_adds_stamp_tax():
    """T-A02b | oracle=cross-check：卖出 5+10+10=25；买卖差 = 印花税 10"""
    sim = make_simulator()
    buy = sim._calculate_cost(10_000.0, OrderSide.BUY)
    sell = sim._calculate_cost(10_000.0, OrderSide.SELL)
    assert sell == pytest.approx(25.0)
    assert sell - buy == pytest.approx(10.0)


def test_p060a_a02c_future_skips_stamp_tax_but_pays_exchange_fee():
    """T-A02c | oracle=closed-form：期货 SELL 不收印花税；300+100+1000=1400"""
    cfg = CostConfig(
        commission_rate=0.0003,
        commission_min=5.0,
        stamp_tax_rate=0.001,
        slippage_pct=0.001,
        asset_costs={AssetType.FUTURE: AssetCost(stamp_tax_rate=0.001, exchange_fee=0.0001)},
    )
    sim = ExecutionSimulator(cfg)
    cost = sim._calculate_cost(1_000_000.0, OrderSide.SELL, AssetType.FUTURE)
    assert cost == pytest.approx(1_400.0)


# ---------------------------------------------------------------------------
# T-A03 异常旁路 / 价格回退 / 待执行单委托
# ---------------------------------------------------------------------------


def test_p060a_a03a_execute_reports_to_sink_and_returns_false(monkeypatch):
    """T-A03a | oracle=contract：执行异常 → (False, None) 且 sink 收到 execution"""
    sim = make_simulator()
    errors: list[tuple[pd.Timestamp, str, BaseException]] = []
    sim.set_error_sink(lambda d, k, e: errors.append((d, k, e)))

    def boom(*args, **kwargs):
        raise RuntimeError("forced cost failure")

    monkeypatch.setattr(sim, "_calculate_cost", boom)
    ok, trade = sim.execute_order("600000.SH", OrderSide.BUY, 100, _DATE, 10.0)

    assert ok is False
    assert trade is None
    assert errors and errors[0][1] == "execution"
    assert isinstance(errors[0][2], RuntimeError)


def test_p060a_a03b_price_fallbacks_and_pending_delegate():
    """T-A03b | oracle=contract：无效/异常/未知价格类型回退开盘价；待执行单委托成交"""
    # 自定义价无效（0）→ 回退开盘价
    sim_invalid = ExecutionSimulator(
        CostConfig(),
        ExecutionPriceType.CUSTOM,
        custom_price_callback=lambda d, s, side: 0.0,
    )
    ok, trade = sim_invalid.execute_order("600000.SH", OrderSide.BUY, 100, _DATE, 10.0)
    assert ok and trade is not None and trade.price == pytest.approx(10.0)

    # 回调抛错 → 回退开盘价
    def boom_callback(*args):
        raise ValueError("custom price boom")

    sim_raise = ExecutionSimulator(CostConfig(), ExecutionPriceType.CUSTOM, boom_callback)
    ok2, trade2 = sim_raise.execute_order("600000.SH", OrderSide.BUY, 100, _DATE, 10.0)
    assert ok2 and trade2 is not None and trade2.price == pytest.approx(10.0)

    # 未知执行价格类型 → 回退开盘价（L277-278），**并实走成功路径**
    # （U-P060-10 已修：此前成功日志读 .value 抛 AttributeError 致订单失败）
    sim_unknown = make_simulator()
    sim_unknown.execution_price_type = "unknown"  # type: ignore[assignment]
    assert sim_unknown._get_execution_price(
        _DATE, "600000.SH", OrderSide.BUY, 10.0, None
    ) == pytest.approx(10.0)
    ok3, trade3 = sim_unknown.execute_order("600000.SH", OrderSide.BUY, 100, _DATE, 10.0)
    assert ok3 and trade3 is not None and trade3.price == pytest.approx(10.0)

    # 待执行单委托（L443）
    order = PendingOrder("600000.SH", OrderSide.BUY, 100, _DATE)
    ok4, trade4 = make_simulator().execute_pending_order(order, _DATE, 10.0)
    assert ok4 and trade4 is not None and trade4.stock == "600000.SH"


# ---------------------------------------------------------------------------
# T-A04 零金额语义（仅公式一致性，pending-semantics）
# ---------------------------------------------------------------------------


def test_p060a_a04_zero_amount_charges_commission_floor():
    """T-A04 | oracle=closed-form(pending-semantics)：max(0,5)=5，不认定业务期望"""
    sim = make_simulator()
    assert sim._calculate_cost(0.0, OrderSide.BUY) == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# T-A05 价格校验 / 市场冲击
# ---------------------------------------------------------------------------


def test_p060a_a05a_price_validation_boundaries():
    """T-A05a | oracle=boundary：ref<=0→False；偏差 0.20 通过、0.21 拒绝"""
    sim = make_simulator()
    assert sim.validate_execution_price("X", _DATE, 10.0, 0.0) is False
    assert sim.validate_execution_price("X", _DATE, 10.0, -1.0) is False
    assert sim.validate_execution_price("X", _DATE, 119.0, 100.0) is True
    assert sim.validate_execution_price("X", _DATE, 120.0, 100.0) is True
    assert sim.validate_execution_price("X", _DATE, 121.0, 100.0) is False


def test_p060a_a05b_market_impact_closed_form():
    """T-A05b | oracle=closed-form：adv<=0→0；ratio×0.01；上限 0.05"""
    sim = make_simulator()
    assert sim.simulate_market_impact("X", 1_000, 0.0, 10.0) == 0.0
    assert sim.simulate_market_impact("X", 1_000, 10_000.0, 10.0) == pytest.approx(0.001)
    assert sim.simulate_market_impact("X", 1_000_000, 10_000.0, 10.0) == pytest.approx(0.05)
