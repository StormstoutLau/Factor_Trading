"""P-050 期货账目 / 股票负持仓：纯函数 + tracker 单测（F1-F5 / F8-F11 / F13）。

期望值全部闭式手算（禁止录制）；口径见 DESIGN D1-D12。
"""

from __future__ import annotations

import math
from dataclasses import replace

import pandas as pd
import pytest

from core.config import AssetCost, AssetInfo, AssetType, BacktestConfig, CostConfig
from core.execution import ExecutionSimulator, Trade
from core.futures_accounting import (
    ContractSpec,
    ExchangeMarginModel,
    LiquidationRequest,
    apply_settlement,
    compute_settlement,
    liquidation_requests,
    roll_orders,
    split_reversal,
)
from core.invariants import check_margin_identity, check_notional_identity
from core.pending import OrderSide
from core.risk_manager import RiskAction
from core.tracker import Position, PositionTracker

DATE = pd.Timestamp("2026-06-01")


def _spec(
    symbol: str = "IH2406",
    multiplier: float = 300.0,
    ratio: float = 0.1,
    expiry: str | None = "2026-06-19",
    roll_days: int | None = None,
    roll_target: str | None = None,
) -> ContractSpec:
    return ContractSpec(
        symbol=symbol,
        multiplier=multiplier,
        margin_ratio=ratio,
        expiry_date=pd.Timestamp(expiry) if expiry else None,
        roll_days_before_expiry=roll_days,
        roll_target=roll_target,
    )


def _trade(
    side: OrderSide,
    quantity: int,
    price: float,
    *,
    stock: str = "IH2406",
    multiplier: float = 300.0,
    asset_type: AssetType = AssetType.FUTURE,
    cost: float = 0.0,
) -> Trade:
    amount = quantity * price * multiplier
    net = amount + cost if side == OrderSide.BUY else amount - cost
    return Trade(
        date=DATE,
        stock=stock,
        side=side,
        quantity=quantity,
        price=price,
        amount=amount,
        cost=cost,
        net_amount=net,
        asset_type=asset_type,
        multiplier=multiplier,
    )


def _futures_tracker(capital: float = 1_000_000.0) -> PositionTracker:
    tracker = PositionTracker(1, capital)
    tracker.set_contract_specs({"IH2406": _spec()})
    return tracker


# ---------------------------------------------------------------------------
# A 组：字段默认值与开关
# ---------------------------------------------------------------------------


def test_config_defaults_preserved():
    cfg = BacktestConfig()
    assert cfg.allow_negative_stock_positions is False
    assert cfg.settlement_file is None
    assert cfg.futures_symbols == []
    assert cfg.liquidation_price_type.value == "open"
    assert cfg.allows_short(AssetType.STOCK) is False
    assert cfg.allows_short(AssetType.FUTURE) is True
    assert cfg.allows_short() is False
    assert BacktestConfig(allow_negative_stock_positions=True).allows_short() is True


def test_position_defaults():
    pos = Position("600000", 100, 10.0, 1000.0, 0.0, 0.0)
    assert pos.asset_type == AssetType.STOCK
    assert pos.multiplier == 1.0
    assert pos.notional_value == 0.0
    assert pos.mtm_pnl == 0.0
    assert pos.settle_base == 0.0


def test_trade_defaults():
    trade = Trade(DATE, "600000", OrderSide.BUY, 100, 10.0, 1000.0, 5.0, 1005.0)
    assert trade.asset_type == AssetType.STOCK
    assert trade.multiplier == 1.0
    assert trade.settlement_price is None


# ---------------------------------------------------------------------------
# F1-F5：期货账目闭式
# ---------------------------------------------------------------------------


def test_f1_open():
    """开仓：margin=105,000、cash=895,000、notional=1,050,000。"""
    tracker = _futures_tracker()
    tracker.execute_trade(_trade(OrderSide.BUY, 1, 3500.0))

    pos = tracker.get_position("IH2406")
    assert pos is not None
    assert pos.quantity == 1
    assert pos.margin_used == pytest.approx(105_000.0)
    assert pos.notional_value == pytest.approx(1_050_000.0)
    assert tracker.get_available_cash() == pytest.approx(895_000.0)
    assert tracker.get_total_value() == pytest.approx(1_000_000.0)
    # I-P050-10：未盯市也非 0
    assert pos.exposure == pytest.approx(1_050_000.0)
    assert pos.mtm_pnl == 0.0


def test_f2_settle():
    """结算 S=3480：pnl=-6,000、margin=104,400、Δ=-600、cash=889,600、NAV=994,000。"""
    tracker = _futures_tracker()
    tracker.execute_trade(_trade(OrderSide.BUY, 1, 3500.0))

    result = tracker.settle(DATE, {"IH2406": 3480.0}, {"IH2406": _spec()})
    assert result is not None
    assert result.total_pnl == pytest.approx(-6_000.0)
    assert result.margin_after["IH2406"] == pytest.approx(104_400.0)
    assert result.margin_delta == pytest.approx(-600.0)
    assert tracker.get_available_cash() == pytest.approx(889_600.0)
    assert tracker.get_total_value() == pytest.approx(994_000.0)

    pos = tracker.get_position("IH2406")
    assert pos is not None
    assert pos.settle_base == 3480.0
    assert pos.mtm_pnl == 0.0
    assert pos.margin_used == pytest.approx(104_400.0)


def test_f3_close():
    """平仓 3490：保证金全释放，累计盈亏 = 两日 pnl 之和（-3000）。"""
    tracker = _futures_tracker()
    tracker.execute_trade(_trade(OrderSide.BUY, 1, 3500.0))
    tracker.settle(DATE, {"IH2406": 3480.0}, {"IH2406": _spec()})
    tracker.execute_trade(_trade(OrderSide.SELL, 1, 3490.0))

    assert tracker.get_available_cash() == pytest.approx(997_000.0)
    pos = tracker.get_position("IH2406")
    assert pos is not None
    assert pos.quantity == 0
    assert pos.margin_used == 0.0
    # 平仓日 realized 只记结算后价差（3480→3490）；两日累计由 NAV 体现
    assert pos.realized_pnl == pytest.approx(3_000.0)
    assert tracker.get_total_value() == pytest.approx(997_000.0)


def test_f4_short():
    """空头 2 手 @3500，S=3520：pnl=-12,000、margin=211,200、NAV=988,000。"""
    tracker = _futures_tracker()
    tracker.execute_trade(_trade(OrderSide.SELL_SHORT, 2, 3500.0))
    assert tracker.get_available_cash() == pytest.approx(790_000.0)

    result = tracker.settle(DATE, {"IH2406": 3520.0}, {"IH2406": _spec()})
    assert result is not None
    assert result.total_pnl == pytest.approx(-12_000.0)
    assert result.margin_after["IH2406"] == pytest.approx(211_200.0)
    assert result.margin_delta == pytest.approx(1_200.0)
    assert tracker.get_available_cash() == pytest.approx(776_800.0)
    assert tracker.get_total_value() == pytest.approx(988_000.0)


def test_f5_liquidation():
    """cash<0 → 按 |notional| 降序裁剪；cash>=0 → []。"""
    big = Position("IF2406", 1, 3500.0, 210_000.0, 0.0, 0.0)
    big.asset_type = AssetType.FUTURE
    big.multiplier = 300.0
    big.margin_used = 210_000.0
    big.notional_value = 1_400_000.0

    small = Position("IC2406", 1, 6000.0, 100_000.0, 0.0, 0.0)
    small.asset_type = AssetType.FUTURE
    small.multiplier = 200.0
    small.margin_used = 100_000.0
    small.notional_value = 1_200_000.0

    positions = {"IF2406": big, "IC2406": small}
    specs = {
        "IF2406": _spec("IF2406", 300.0, 0.1),
        "IC2406": _spec("IC2406", 200.0, 0.1),
    }

    assert liquidation_requests(positions, cash=1.0, specs=specs) == []

    requests = liquidation_requests(positions, cash=-150_000.0, specs=specs)
    assert requests == [LiquidationRequest(symbol="IF2406", quantity=1.0)]

    # 缺口大于单合约释放 → 追加第二笔
    requests2 = liquidation_requests(positions, cash=-250_000.0, specs=specs)
    assert [r.symbol for r in requests2] == ["IF2406", "IC2406"]


# ---------------------------------------------------------------------------
# F6/F7 纯函数补测（引擎级在 test_p050_engine_integration.py）
# ---------------------------------------------------------------------------


def test_roll_due_and_missing_target():
    position = Position("IH2406", 1, 3500.0, 105_000.0, 0.0, 0.0)
    position.asset_type = AssetType.FUTURE
    position.multiplier = 300.0
    positions = {"IH2406": position}

    spec = _spec(roll_days=5, roll_target="IH2409")
    specs = {"IH2406": spec}

    assert roll_orders(positions, specs, pd.Timestamp("2026-06-10")) == []

    due = roll_orders(positions, specs, pd.Timestamp("2026-06-15"))
    assert len(due) == 1
    assert due[0].close_symbol == "IH2406"
    assert due[0].open_symbol == "IH2409"
    assert due[0].quantity == 1.0

    with pytest.raises(ValueError):
        roll_orders(positions, {"IH2406": _spec()}, pd.Timestamp("2026-06-19"))


# ---------------------------------------------------------------------------
# F8/F9：股票负持仓
# ---------------------------------------------------------------------------


def test_f8_stock_short():
    """NAV = C + q(P0-P)，exposure > 0。"""
    tracker = PositionTracker(1, 100_000.0, allow_negative_stock_positions=True)
    tracker.execute_trade(
        _trade(
            OrderSide.SELL_SHORT,
            100,
            10.0,
            stock="600000",
            multiplier=1.0,
            asset_type=AssetType.STOCK,
        )
    )
    assert tracker.get_available_cash() == pytest.approx(101_000.0)

    tracker.update_market_values(DATE, pd.Series({"600000": 9.0}))
    pos = tracker.get_position("600000")
    assert pos is not None
    assert pos.quantity == -100
    assert pos.market_value == pytest.approx(-900.0)
    assert tracker.get_total_value() == pytest.approx(100_100.0)
    assert pos.exposure == pytest.approx(900.0)
    # 双路径：cash + mv
    assert tracker.get_total_value() == pytest.approx(100_000.0 + 100 * (10.0 - 9.0))


def test_f9_disabled_identical():
    """开关关闭：3 个股票场景与改动前读数逐位一致。"""
    tracker = PositionTracker(1, 100_000.0)
    assert tracker.get_available_cash() == 100_000.0

    # 场景 1：买入
    tracker.execute_trade(
        _trade(OrderSide.BUY, 100, 10.0, stock="600000", multiplier=1.0, asset_type=AssetType.STOCK)
    )
    assert tracker.get_available_cash() == pytest.approx(99_000.0)
    tracker.update_market_values(DATE, pd.Series({"600000": 10.0}))
    assert tracker.get_total_value() == pytest.approx(100_000.0)

    # 场景 2：卖出
    tracker.execute_trade(
        _trade(
            OrderSide.SELL, 100, 11.0, stock="600000", multiplier=1.0, asset_type=AssetType.STOCK
        )
    )
    assert tracker.get_available_cash() == pytest.approx(100_100.0)
    assert tracker.get_position("600000") is not None
    assert tracker.get_position("600000").quantity == 0
    assert tracker.get_all_positions() == {}

    # 场景 3：关闭时 SELL_SHORT 不改现金、不入持仓视图
    tracker.execute_trade(
        _trade(
            OrderSide.SELL_SHORT,
            50,
            10.0,
            stock="600001",
            multiplier=1.0,
            asset_type=AssetType.STOCK,
        )
    )
    assert tracker.get_available_cash() == pytest.approx(100_100.0)
    assert tracker.get_all_positions() == {}


# ---------------------------------------------------------------------------
# F10/F11：越量与反手
# ---------------------------------------------------------------------------


def test_f10_overfill():
    tracker = PositionTracker(1, 100_000.0)
    tracker.execute_trade(
        _trade(OrderSide.BUY, 100, 10.0, stock="600000", multiplier=1.0, asset_type=AssetType.STOCK)
    )

    with pytest.raises(ValueError, match="SELL 越量"):
        tracker.execute_trade(
            _trade(
                OrderSide.SELL,
                200,
                10.0,
                stock="600000",
                multiplier=1.0,
                asset_type=AssetType.STOCK,
            )
        )

    with pytest.raises(ValueError, match="SELL_SHORT 越量"):
        tracker.execute_trade(
            _trade(
                OrderSide.SELL_SHORT,
                10,
                10.0,
                stock="600000",
                multiplier=1.0,
                asset_type=AssetType.STOCK,
            )
        )

    short_tracker = PositionTracker(1, 100_000.0)
    short_tracker.execute_trade(
        _trade(
            OrderSide.SELL_SHORT,
            100,
            10.0,
            stock="600000",
            multiplier=1.0,
            asset_type=AssetType.STOCK,
        )
    )

    with pytest.raises(ValueError, match="BUY_TO_COVER 越量"):
        short_tracker.execute_trade(
            _trade(
                OrderSide.BUY_TO_COVER,
                200,
                10.0,
                stock="600000",
                multiplier=1.0,
                asset_type=AssetType.STOCK,
            )
        )


def test_f11_reversal():
    """反手两笔：顺序、数量、中间 cash。"""
    assert split_reversal(100, -50) == [("SELL", 100.0), ("SELL_SHORT", 50.0)]
    assert split_reversal(-100, 50) == [("BUY_TO_COVER", 100.0), ("BUY", 50.0)]
    assert split_reversal(100, 30) == [("SELL", 70.0)]
    assert split_reversal(-100, -30) == [("BUY_TO_COVER", 70.0)]
    assert split_reversal(0, -10) == [("SELL_SHORT", 10.0)]
    assert split_reversal(0, 10) == [("BUY", 10.0)]
    assert split_reversal(0, 0) == []

    tracker = PositionTracker(1, 100_000.0, allow_negative_stock_positions=True)
    tracker.execute_trade(
        _trade(OrderSide.BUY, 100, 10.0, stock="600000", multiplier=1.0, asset_type=AssetType.STOCK)
    )
    assert tracker.get_available_cash() == pytest.approx(99_000.0)

    tracker.execute_trade(
        _trade(
            OrderSide.SELL, 100, 11.0, stock="600000", multiplier=1.0, asset_type=AssetType.STOCK
        )
    )
    assert tracker.get_available_cash() == pytest.approx(100_100.0)

    tracker.execute_trade(
        _trade(
            OrderSide.SELL_SHORT,
            50,
            11.0,
            stock="600000",
            multiplier=1.0,
            asset_type=AssetType.STOCK,
        )
    )
    assert tracker.get_available_cash() == pytest.approx(100_650.0)
    pos = tracker.get_position("600000")
    assert pos is not None
    assert pos.quantity == -50


# ---------------------------------------------------------------------------
# F13：成本接线
# ---------------------------------------------------------------------------


def test_f13_cost():
    """FUTURE 印花税 0、exchange_fee 生效；STOCK 三费不变。"""
    costs = CostConfig(
        commission_rate=0.0001,
        commission_min=5.0,
        stamp_tax_rate=0.001,
        slippage_pct=0.0,
        asset_costs={
            AssetType.FUTURE: AssetCost(stamp_tax_rate=0.001, exchange_fee=0.000023),
        },
    )
    futures_specs = {
        "IH2406": AssetInfo(
            asset_type=AssetType.FUTURE,
            multiplier=300.0,
            margin_ratio=0.1,
            expiry_date="2026-06-19",
        )
    }
    executor = ExecutionSimulator(costs, asset_specs=futures_specs)
    ok, trade = executor.execute_order("IH2406", OrderSide.SELL, 1, DATE, 3500.0)
    assert ok and trade is not None
    amount = 1 * 3500.0 * 300.0
    assert trade.amount == pytest.approx(amount)
    assert trade.multiplier == 300.0
    assert trade.asset_type == AssetType.FUTURE
    expected = max(amount * 0.0001, 5.0) + amount * 0.000023
    assert trade.cost == pytest.approx(expected)  # 无印花税

    stock_executor = ExecutionSimulator(costs)
    ok2, stock_trade = stock_executor.execute_order("600000", OrderSide.SELL, 1, DATE, 1000.0)
    assert ok2 and stock_trade is not None
    assert stock_trade.amount == pytest.approx(1000.0)
    expected_stock = max(1000.0 * 0.0001, 5.0) + 1000.0 * 0.001
    assert stock_trade.cost == pytest.approx(expected_stock)


# ---------------------------------------------------------------------------
# 结算纯函数 / 现金恒等 / 不变式
# ---------------------------------------------------------------------------


def test_apply_settlement_pure():
    position = Position("IH2406", 1, 3500.0, 0.0, 0.0, 0.0)
    position.asset_type = AssetType.FUTURE
    position.multiplier = 300.0
    position.settle_base = 3500.0
    position.margin_used = 105_000.0

    result = compute_settlement({"IH2406": position}, {"IH2406": 3480.0}, {"IH2406": _spec()})
    assert result.total_pnl == pytest.approx(-6_000.0)
    assert result.proxy_used is False

    cash_after, margin_after = apply_settlement(1_000_000.0 - 105_000.0, 105_000.0, result)
    assert cash_after == pytest.approx(895_000.0 - 6_000.0 + 600.0)
    assert margin_after == pytest.approx(104_400.0)
    # 入参不被修改
    assert position.margin_used == 105_000.0


def test_settlement_missing_price_skips():
    position = Position("IH2406", 1, 3500.0, 0.0, 0.0, 0.0)
    position.asset_type = AssetType.FUTURE
    position.multiplier = 300.0
    position.settle_base = 3500.0
    position.margin_used = 105_000.0

    result = compute_settlement({"IH2406": position}, {}, {"IH2406": _spec()})
    assert result.total_pnl == 0.0
    assert result.margin_delta == pytest.approx(0.0)
    assert result.proxy_used is False
    assert result.margin_after["IH2406"] == pytest.approx(105_000.0)


def test_i6_margin():
    tracker = _futures_tracker()
    tracker.execute_trade(_trade(OrderSide.BUY, 1, 3500.0))
    violations = check_margin_identity(
        list(tracker.get_all_positions().values()), {"IH2406": _spec()}
    )
    assert violations == []

    pos = tracker.get_position("IH2406")
    assert pos is not None
    bad = replace(pos, margin_used=90_000.0)
    assert check_margin_identity([bad], {"IH2406": _spec()})[0].code == "P050-I6"


def test_i7_notional():
    position = Position("IH2406", 1, 3500.0, 105_000.0, 0.0, 0.0)
    position.asset_type = AssetType.FUTURE
    position.multiplier = 300.0
    position.notional_value = 1_050_000.0
    prices = {"IH2406": 3500.0}
    assert check_notional_identity([position], prices) == []

    position.notional_value = 0.0
    assert check_notional_identity([position], prices)[0].code == "P050-I7"


def test_i8_cash_identity():
    """cash_t − cash_{t−1} == Σpnl − fee − Δmargin。"""
    tracker = _futures_tracker()
    tracker.execute_trade(_trade(OrderSide.BUY, 1, 3500.0))
    cash_open = tracker.get_available_cash()

    result = tracker.settle(DATE, {"IH2406": 3480.0}, {"IH2406": _spec()})
    assert result is not None
    delta = tracker.get_available_cash() - cash_open
    assert delta == pytest.approx(result.total_pnl - 0.0 - result.margin_delta)


# ---------------------------------------------------------------------------
# settle / validate / risk manager
# ---------------------------------------------------------------------------


def test_settle_noop_for_stocks():
    tracker = PositionTracker(1, 100_000.0)
    assert tracker.settle(DATE, {}, {}, fallback_prices={}) is None

    tracker.set_contract_specs({"IH2406": _spec()})
    tracker.execute_trade(
        _trade(OrderSide.BUY, 100, 10.0, stock="600000", multiplier=1.0, asset_type=AssetType.STOCK)
    )
    assert tracker.settle(DATE, {}, {"IH2406": _spec()}) is None


def test_settle_proxy_uses_fallback():
    tracker = _futures_tracker()
    tracker.execute_trade(_trade(OrderSide.BUY, 1, 3500.0))
    result = tracker.settle(DATE, {}, {"IH2406": _spec()}, fallback_prices={"IH2406": 3490.0})
    assert result is not None
    assert result.proxy_used is True
    assert result.total_pnl == pytest.approx(-3_000.0)


def test_validate_futures():
    tracker = _futures_tracker()
    tracker.execute_trade(_trade(OrderSide.BUY, 1, 3500.0))
    assert tracker.validate_positions(pd.Series({"IH2406": 3500.0})) == []

    pos = tracker.get_position("IH2406")
    assert pos is not None
    pos.mtm_pnl = 1.0
    assert tracker.validate_positions(pd.Series({"IH2406": 3500.0}))


def test_risk_manager_diagnostic_only():
    from core.risk_manager import MarkToMarketPolicy

    manager = MarkToMarketPolicy()
    position = Position("IF2406", -2, 3500.0, 100_000.0, 0.0, 0.0, margin_used=4000.0)
    position.notional_value = 100_000.0
    actions = manager.check_position(position)
    assert RiskAction.FORCE_CLOSE not in [item.action for item in actions]
    assert actions == []


def test_margin_model_protocol():
    model = ExchangeMarginModel()
    spec = _spec()
    assert model.initial_margin(1_050_000.0, spec) == pytest.approx(105_000.0)
    assert model.maintenance_margin(1_050_000.0, spec) == pytest.approx(105_000.0)


def test_no_nan_nav_after_full_cycle():
    tracker = _futures_tracker()
    tracker.execute_trade(_trade(OrderSide.BUY, 1, 3500.0))
    cash = [tracker.get_available_cash()]
    for price in (3500.0, 3480.0, 3490.0):
        result = tracker.settle(DATE, {"IH2406": price}, {"IH2406": _spec()})
        assert result is not None
        assert math.isfinite(tracker.get_total_value())
        cash.append(tracker.get_available_cash())
    assert all(math.isfinite(value) for value in cash)
