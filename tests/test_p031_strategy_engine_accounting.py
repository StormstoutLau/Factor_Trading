"""P-031 账目时序回归测试

覆盖 DESIGN V1-V6 + V2b（IMPL §5）：目标持仓并集、NAV 价格重算、双路径卖量夹紧、
双载体撤销/过期、中性空头腿显式禁用。fixture 独立（不改 test_p027 / test_p029）。
"""

from __future__ import annotations

import logging

import pandas as pd
import pytest

from agents.multi_strategy_engine import StrategyConfig, StrategyEngine
from core.config import BacktestConfig, CostConfig, OptimizerConfig, RebalanceConfig
from core.execution import Trade
from core.pending import OrderSide, PendingOrderQueue, create_pending_order

STOCKS = ["A", "B"]
DATES = pd.bdate_range("2024-01-02", periods=10)


# --------------------------------------------------------------- fixtures
class _P031DM:
    """最小数据面：全常量价格，可按日期切片。"""

    def __init__(
        self,
        prices: dict[str, float] | None = None,
        n_days: int = 10,
        stocks: list[str] | None = None,
    ):
        self.stock_codes = list(stocks or STOCKS)
        self.trade_dates = DATES[:n_days]
        self.n_stocks = len(self.stock_codes)
        self.returns = pd.DataFrame(0.0, index=self.trade_dates, columns=self.stock_codes)
        self._prices = prices or {s: 10.0 for s in self.stock_codes}

    def get_adj_price(self, field: str, adjustment_type: str) -> pd.DataFrame:
        return pd.DataFrame(
            {s: [self._prices[s]] * len(self.trade_dates) for s in self.stock_codes},
            index=self.trade_dates,
        )


class _P031Universe:
    """全可交易掩码（tradable / buyable / sellable 三面齐备）。"""

    def __init__(self, dates: pd.DatetimeIndex, stocks: list[str]):
        index = pd.Index(dates)
        self.tradable = pd.DataFrame(True, index=index, columns=stocks)
        self.buyable = pd.DataFrame(True, index=index, columns=stocks)
        self.sellable = pd.DataFrame(True, index=index, columns=stocks)


def _zero_cost() -> CostConfig:
    return CostConfig(commission_rate=0.0, commission_min=0.0, stamp_tax_rate=0.0, slippage_pct=0.0)


def _make_engine(
    direction: str = "long",
    enable_pending: bool = False,
    zero_cost: bool = True,
    n_days: int = 10,
    stocks: list[str] | None = None,
    signal: pd.DataFrame | None = None,
) -> StrategyEngine:
    universe_stocks = list(stocks or STOCKS)
    strategy_cfg = StrategyConfig(name=direction, direction=direction, target_count=2)
    base_cfg = BacktestConfig(
        enable_pending_orders=enable_pending,
        rebalance=RebalanceConfig(frequency="daily"),
        optimizer=OptimizerConfig(method="equal_weight", round_lot=True, max_weight=1.0),
        cost=_zero_cost() if zero_cost else CostConfig(),
    )
    dm = _P031DM(n_days=n_days, stocks=universe_stocks)
    sig = (
        signal
        if signal is not None
        else pd.DataFrame(0.0, index=dm.trade_dates, columns=universe_stocks)
    )
    return StrategyEngine(
        strategy_cfg, base_cfg, dm, _P031Universe(dm.trade_dates, universe_stocks), sig
    )


def _seed_position(engine: StrategyEngine, stock: str, qty: int, price: float = 10.0) -> None:
    trade = Trade(
        date=DATES[0],
        stock=stock,
        side=OrderSide.BUY,
        quantity=qty,
        price=price,
        amount=qty * price,
        cost=0.0,
        net_amount=qty * price,
    )
    engine.tracker.execute_trade(trade)
    engine.tracker.update_market_values(DATES[0], pd.Series({stock: price}))


# --------------------------------------------------------------- V5（B1）
def test_neutral_short_leg_unsupported(caplog):
    """V5 / I7：both → 仅多头腿、显式计数与标记、构造期 1 条 WARNING、半仓部署。"""
    caplog.set_level(logging.WARNING, logger="agents.multi_strategy_engine")
    engine = _make_engine(direction="both")

    warns = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warns) == 1
    assert "unsupported" in warns[0].getMessage()

    caplog.clear()
    engine._execute_neutral_rebalance(DATES[0], 0, pd.Series({"A": 1.0, "B": 0.5}))

    assert engine.get_failure_stats() == {"neutral_short_leg_skipped": 1}
    orders = [item["order"] for item in engine._next_day_orders]
    assert orders, "多头腿应产生买入订单"
    assert all(order.side == OrderSide.BUY for order in orders)

    engine._execute_next_day_orders(DATES[1], 1)
    trades = engine.executor.trade_log.get_trades()
    assert trades and all(trade.side == OrderSide.BUY for trade in trades)

    notional = sum(trade.amount for trade in trades)
    capital = engine.tracker.initial_capital
    assert notional == pytest.approx(capital * 0.5 * 0.985, rel=0.02), "半仓且不重归一化"

    result = engine._generate_results()
    assert result["additional_info"]["neutral_short_leg"] == "unsupported"

    # long 分支：构造期零新增 WARNING，结果标记不适用
    caplog.clear()
    long_engine = _make_engine(direction="long")
    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []
    assert (
        long_engine._generate_results()["additional_info"]["neutral_short_leg"] == "not_applicable"
    )


# --------------------------------------------------------------- V1（B2）
def test_exit_order_for_dropped_holding():
    """V1 / I1：目标外持仓必产生清仓单（旧实现只遍历 target_weights，永不卖出）。"""
    engine = _make_engine()
    _seed_position(engine, "A", 1000)

    engine._generate_orders(DATES[0], 0, pd.Series({"B": 0.5}))

    sells = [
        item["order"] for item in engine._next_day_orders if item["order"].side == OrderSide.SELL
    ]
    assert len(sells) == 1
    assert sells[0].stock == "A"
    assert sells[0].quantity == 1000

    engine._execute_next_day_orders(DATES[1], 1)

    assert engine.tracker.get_position("A").quantity == 0
    assert engine.tracker.get_position("B").quantity > 0


# --------------------------------------------------------------- V2（B2）
def test_nav_timing_single_trade():
    """V2 / I3：NAV 以价格重算——daily + 恒定 100% 只成交 1 笔（旧实现 9 笔）。"""
    signal = pd.DataFrame({"A": 1.0}, index=DATES)
    engine = _make_engine(stocks=["A"], signal=signal)  # target_count=2 → 单股权重归一为 1.0

    for index, date in enumerate(engine.dm.trade_dates):
        engine._process_trading_day(date, index)

    trades = engine.executor.trade_log.get_trades()
    assert len(trades) == 1, f"应仅在首日建仓一次，实际 {len(trades)} 笔"

    position = engine.tracker.get_position("A")
    assert position is not None
    nav = engine.tracker.get_cash() + position.quantity * 10.0
    assert nav == pytest.approx(engine.tracker.initial_capital, rel=1e-12)


# --------------------------------------------------------------- V2b（B2）
def test_nav_guard_on_zero_equity():
    """V2b / F-S4-P031-2：nav≤0 不抛 ValueError（多策略循环无 try），显式计数并早退。"""
    engine = _make_engine()
    engine.tracker._cash = 0.0

    engine._generate_orders(DATES[0], 0, pd.Series({"A": 1.0}))

    assert engine.get_failure_stats() == {"rebalance_nav_invalid": 1}
    assert engine._next_day_orders == []


# --------------------------------------------------------------- V3（B3）
@pytest.mark.parametrize("path", ["next_day", "queue"])
def test_oversell_clamped(path):
    """V3 / I2：3 张 SELL×100 对 100 股持仓 → 只成交 1 笔 100 股，现金恰 +1,000。"""
    engine = _make_engine(enable_pending=(path == "queue"))
    _seed_position(engine, "A", 100)
    cash_before = engine.tracker.get_cash()

    if path == "next_day":
        for _ in range(3):
            order = create_pending_order("A", OrderSide.SELL, 100, DATES[0])
            engine._next_day_orders.append({"order": order, "create_date": DATES[0]})
        engine._execute_next_day_orders(DATES[1], 1)
    else:
        for _ in range(3):
            engine.pending_queue.add_order(create_pending_order("A", OrderSide.SELL, 100, DATES[0]))
        engine._process_pending_orders(DATES[1], 1)
        assert engine.pending_queue.get_pending_orders() == []

    trades = engine.executor.trade_log.get_trades()
    assert len(trades) == 1
    assert trades[0].quantity == 100
    assert engine.tracker.get_cash() == pytest.approx(cash_before + 1_000)
    assert engine.get_failure_stats().get("oversell_blocked") == 2
    assert engine.tracker.get_position("A").quantity == 0


# --------------------------------------------------------------- V4（B4）
def test_stale_orders_cancelled_on_rebalance():
    """V4① / I4：再平衡撤销信号域内在途单，域外保留。"""
    signal = pd.DataFrame({"A": 1.0, "B": 1.0}, index=DATES)
    engine = _make_engine(signal=signal)

    stale_in_domain = create_pending_order("A", OrderSide.BUY, 100, DATES[0])
    stale_out_domain = create_pending_order("Z", OrderSide.BUY, 100, DATES[0])
    engine._next_day_orders = [
        {"order": stale_in_domain, "create_date": DATES[0]},
        {"order": stale_out_domain, "create_date": DATES[0]},
    ]

    engine._execute_rebalance(DATES[1], 1)

    live = [item["order"] for item in engine._next_day_orders]
    assert stale_in_domain not in live, "信号域内陈旧单应被撤销"
    assert stale_out_domain in live, "域外在途单应保留"
    assert engine.get_failure_stats()["next_day_orders_cancelled"] == 1


def test_stale_orders_expired():
    """V4② / I6：BUY 单超过 5 自然日上限后过期，不再执行（F-S6-P031-1）。"""
    engine = _make_engine()
    stale = create_pending_order("A", OrderSide.BUY, 100, DATES[0])
    engine._next_day_orders = [{"order": stale, "create_date": DATES[0]}]

    engine._execute_next_day_orders(DATES[5], 5)  # 7 自然日 ≥ max_pending_days_buy=5

    assert engine.get_failure_stats()["next_day_orders_expired"] == 1
    assert engine._next_day_orders == []
    assert engine.executor.trade_log.get_trades() == []


# --------------------------------------------------------------- V6（B4）
def test_normal_path_zero_new_counters():
    """V6 / 回归保护：常规多头全链路 → 6 个新计数键全 0，既有键零误报。"""
    signal = pd.DataFrame({"A": 1.0, "B": 1.0}, index=DATES)
    engine = _make_engine(signal=signal)

    result = engine.run()
    stats = result["failure_counts"]

    for key in (
        "oversell_blocked",
        "oversell_trimmed",
        "next_day_orders_cancelled",
        "next_day_orders_expired",
        "neutral_short_leg_skipped",
        "rebalance_nav_invalid",
    ):
        assert stats.get(key, 0) == 0, f"{key} 不应在正常路径触发"
    assert "orders_missing_price" not in stats
    assert "next_day_open_price" not in stats
    assert result["additional_info"]["neutral_short_leg"] == "not_applicable"
