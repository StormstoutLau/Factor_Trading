"""P-052 G 组：5 类新增 Guard + live_safe 预设（G1-G15）。"""

from __future__ import annotations

from core.guard_pipeline import (
    GuardContext,
    GuardPipeline,
    IndustryExposureGuard,
    MaxOrderValueGuard,
    OrderRateGuard,
    PriceBandGuard,
    SelfTradeGuard,
)


def _ctx(**overrides) -> GuardContext:
    base = dict(
        action="BUY",
        symbol="AAA",
        quantity=100.0,
        price=10.0,
        order_value=1000.0,
        current_positions={},
        current_weights={},
        portfolio_value=100_000.0,
        cash=100_000.0,
    )
    base.update(overrides)
    return GuardContext(**base)


def test_g1_max_order_value_blocked():
    """G1：超单笔金额上限阻断。"""
    result = MaxOrderValueGuard(max_order_value=1000.0).check(_ctx(order_value=1000.5))
    assert result.passed is False
    assert result.severity == "error"


def test_g2_max_order_value_equality_passes():
    """G2：等号放行。"""
    result = MaxOrderValueGuard(max_order_value=1000.0).check(_ctx(order_value=1000.0))
    assert result.passed is True


def test_g3_price_band_buy_above_upper():
    """G3：BUY 高于涨停价阻断。"""
    ctx = _ctx(price=11.0, limit_up=10.5, limit_down=8.5)
    assert PriceBandGuard().check(ctx).passed is False


def test_g4_price_band_sell_below_lower():
    """G4：SELL 低于跌停价阻断。"""
    ctx = _ctx(action="SELL", price=8.0, limit_up=10.5, limit_down=8.5)
    assert PriceBandGuard().check(ctx).passed is False


def test_g5_price_band_none_warns_and_passes():
    """G5：价格带缺失 → warning 放行。"""
    result = PriceBandGuard().check(_ctx(limit_up=None, limit_down=None))
    assert result.passed is True
    assert result.severity == "warning"


def test_g6_industry_exposure_blocked():
    """G6：行业暴露超限阻断。"""
    ctx = _ctx(
        industry="银行",
        industry_exposure={"银行": 0.28},
        industry_limits={"银行": 0.30},
        order_value=5000.0,
        portfolio_value=100_000.0,
    )
    assert IndustryExposureGuard().check(ctx).passed is False


def test_g7_industry_exposure_within_limit():
    """G7：行业暴露未超限放行。"""
    ctx = _ctx(
        industry="银行",
        industry_exposure={"银行": 0.10},
        industry_limits={"银行": 0.30},
        order_value=5000.0,
        portfolio_value=100_000.0,
    )
    assert IndustryExposureGuard().check(ctx).passed is True


def test_g8_industry_exposure_skips_nonpositive_pv():
    """G8：portfolio_value<=0 跳过。"""
    ctx = _ctx(industry="银行", portfolio_value=0.0, industry_exposure={"银行": 0.9})
    assert IndustryExposureGuard().check(ctx).passed is True


def test_g9_order_rate_daily_limit():
    """G9：日笔数达上限阻断。"""
    ctx = _ctx(daily_order_count=1000)
    assert OrderRateGuard(max_daily_orders=1000).check(ctx).passed is False


def test_g10_order_rate_cancel_ratio():
    """G10：撤单率超限阻断。"""
    ctx = _ctx(daily_order_count=20, daily_cancel_count=15)
    guard = OrderRateGuard(max_daily_orders=1000, max_cancel_ratio=0.5, min_cancel_samples=20)
    assert guard.check(ctx).passed is False


def test_g11_order_rate_insufficient_samples():
    """G11：样本不足不判撤单率。"""
    ctx = _ctx(daily_order_count=5, daily_cancel_count=5)
    guard = OrderRateGuard(max_daily_orders=1000, max_cancel_ratio=0.5, min_cancel_samples=20)
    assert guard.check(ctx).passed is True


def test_g12_self_trade_buy_blocked():
    """G12：BUY 遇同价 SELL 挂单阻断。"""
    ctx = _ctx(action="BUY", price=10.0, counterparty_open_orders=[{"side": "SELL", "price": 9.9}])
    assert SelfTradeGuard().check(ctx).passed is False


def test_g13_self_trade_sell_blocked():
    """G13：SELL 遇同价 BUY 挂单阻断。"""
    ctx = _ctx(action="SELL", price=10.0, counterparty_open_orders=[{"side": "BUY", "price": 10.1}])
    assert SelfTradeGuard().check(ctx).passed is False


def test_g14_self_trade_empty_list_passes():
    """G14：空列表放行。"""
    assert SelfTradeGuard().check(_ctx(counterparty_open_orders=[])).passed is True


def test_g15_live_safe_components_and_order():
    """G15：live_safe() 八件套组件与顺序。"""
    pipeline = GuardPipeline.live_safe()
    names = [guard.name for guard in pipeline.guards]
    assert names == [
        "MaxPositionGuard",
        "PriceBandGuard",
        "MaxOrderValueGuard",
        "IndustryExposureGuard",
        "OrderRateGuard",
        "SelfTradeGuard",
        "MinCashGuard",
        "DrawdownGuard",
    ]
    assert len(names) == 8
