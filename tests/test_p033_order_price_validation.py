"""P-033 待执行订单价格有效性测试

覆盖 DESIGN V1-V8（IMPL §5 十七实例）：执行入口解析价守卫（含 VWAP 聚合 NaN）、
两引擎 queue 前置过滤与计量、无效价零成交/零入账/订单保留、正常路径零误报。
fixture 独立（不改 test_p027 / test_p029 / test_p031）。
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import pytest

from agents.multi_strategy_engine import StrategyConfig, StrategyEngine
from core.config import (
    BacktestConfig,
    CostConfig,
    ExecutionPriceType,
    OptimizerConfig,
    RebalanceConfig,
)
from core.engine_v2 import BacktestEngineV2
from core.execution import ExecutionSimulator, Trade
from core.pending import OrderSide, PendingOrderQueue, create_pending_order
from core.tracker import PositionTracker

STOCKS = ["A"]
DATES = pd.bdate_range("2024-01-02", periods=10)
CAPITAL = 10_000_000.0
FAR_FUTURE = float("nan")


# --------------------------------------------------------------- fixtures
class _P033DM:
    """最小数据面：按字段返回常量价（可注入 NaN / 0 / 负 / inf）。"""

    def __init__(
        self,
        fields: dict[str, float] | None = None,
        n_days: int = 10,
        stocks: list[str] | None = None,
    ):
        self.stock_codes = list(stocks or STOCKS)
        self.trade_dates = DATES[:n_days]
        self.n_stocks = len(self.stock_codes)
        self.returns = pd.DataFrame(0.0, index=self.trade_dates, columns=self.stock_codes)
        self._fields = fields or {}

    def get_adj_price(self, field: str, adjustment_type: str) -> pd.DataFrame:
        value = self._fields.get(field, 10.0)
        return pd.DataFrame(
            {s: [value] * len(self.trade_dates) for s in self.stock_codes},
            index=self.trade_dates,
        )


class _P033Universe:
    """全可交易掩码（tradable / buyable / sellable 三面齐备）。"""

    def __init__(self, dates: pd.DatetimeIndex, stocks: list[str]):
        index = pd.Index(dates)
        self.tradable = pd.DataFrame(True, index=index, columns=stocks)
        self.buyable = pd.DataFrame(True, index=index, columns=stocks)
        self.sellable = pd.DataFrame(True, index=index, columns=stocks)


def _zero_cost() -> CostConfig:
    return CostConfig(commission_rate=0.0, commission_min=0.0, stamp_tax_rate=0.0, slippage_pct=0.0)


def _make_agents_engine(n_days: int = 10, fields: dict[str, float] | None = None) -> StrategyEngine:
    """F4：仅直接调被调函数，不跑全链路。"""
    dm = _P033DM(fields=fields, n_days=n_days)
    strategy_cfg = StrategyConfig(name="long", direction="long", target_count=1)
    base_cfg = BacktestConfig(
        enable_pending_orders=True,
        rebalance=RebalanceConfig(frequency="daily"),
        optimizer=OptimizerConfig(method="equal_weight", round_lot=True),
        cost=_zero_cost(),
    )
    signal = pd.DataFrame(0.0, index=dm.trade_dates, columns=dm.stock_codes)
    return StrategyEngine(
        strategy_cfg, base_cfg, dm, _P033Universe(dm.trade_dates, dm.stock_codes), signal
    )


def _make_v2_engine(n_days: int = 10, fields: dict[str, float] | None = None) -> BacktestEngineV2:
    """F5：注入组件、不调 setup()（避免因子文件依赖）。"""
    cfg = BacktestConfig(
        enable_pending_orders=True,
        rebalance=RebalanceConfig(frequency="daily"),
        optimizer=OptimizerConfig(method="equal_weight", round_lot=True),
        cost=_zero_cost(),
    )
    engine = BacktestEngineV2(cfg)
    dm = _P033DM(fields=fields, n_days=n_days)
    engine.dm = dm
    engine.universe = _P033Universe(dm.trade_dates, dm.stock_codes)
    engine.executor = ExecutionSimulator(_zero_cost())
    engine.tracker = PositionTracker(dm.n_stocks, CAPITAL)
    engine.pending_queue = PendingOrderQueue()
    return engine


def _seed_position(engine: StrategyEngine, stock: str, qty: int, price: float = 10.0) -> None:
    """F6：建仓（V4 用）。"""
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


# --------------------------------------------------------------- V1（B1t）
@pytest.mark.parametrize(
    "bad_price",
    [None, float("nan"), float("inf"), float("-inf"), 0.0, -5.0],
    ids=["none", "nan", "inf", "neg_inf", "zero", "negative"],
)
def test_v1_price_guard_matrix(bad_price):
    """V1 / I1：解析价 None / NaN / ±inf / ≤0 → (False, None)，trade_log 零入账。"""
    executor = ExecutionSimulator(_zero_cost())

    success, trade = executor.execute_order("A", OrderSide.BUY, 100, DATES[0], bad_price)

    assert (success, trade) == (False, None)
    assert executor.trade_log.get_trades() == []


# --------------------------------------------------------------- V7（B1t）
def test_v7_vwap_nan_blocked():
    """V7 / I1：VWAP 聚合 NaN（open/close 合法、high/low 缺失为 NaN）不得成交。"""
    executor = ExecutionSimulator(_zero_cost(), execution_price_type=ExecutionPriceType.VWAP)

    success, trade = executor.execute_order(
        "A", OrderSide.BUY, 100, DATES[0], 10.0, 10.0, float("nan"), float("nan")
    )

    assert (success, trade) == (False, None)
    assert executor.trade_log.get_trades() == []


# --------------------------------------------------------------- V2（B2t）
@pytest.mark.parametrize("bad_open", [float("nan"), 0.0], ids=["nan", "zero"])
def test_v2_agents_queue_invalid_open(bad_open):
    """V2 / I2 / I6：agents queue 遇 NaN / 0 开盘价 → 零成交、现金不变、订单留队、计数 1。"""
    engine = _make_agents_engine(fields={"open": bad_open})
    engine.pending_queue.add_order(create_pending_order("A", OrderSide.BUY, 100, DATES[0]))

    engine._process_pending_orders(DATES[0], 0)

    assert engine.executor.trade_log.get_trades() == []
    assert engine.tracker.get_cash() == CAPITAL
    assert len(engine.pending_queue.get_pending_orders()) == 1
    assert engine.get_failure_stats().get("pending_invalid_price") == 1


# --------------------------------------------------------------- V3（B2t）
@pytest.mark.parametrize("bad_open", [-5.0, float("-inf")], ids=["negative", "neg_inf"])
def test_v3_agents_queue_negative_open(bad_open):
    """V3 / I2：负价（-5 / -inf）同样零成交、现金不变、计数 1（覆盖 R2「现金 +500」）。"""
    engine = _make_agents_engine(fields={"open": bad_open})
    engine.pending_queue.add_order(create_pending_order("A", OrderSide.BUY, 100, DATES[0]))

    engine._process_pending_orders(DATES[0], 0)

    assert engine.executor.trade_log.get_trades() == []
    assert engine.tracker.get_cash() == CAPITAL
    assert engine.get_failure_stats().get("pending_invalid_price") == 1


# --------------------------------------------------------------- V4（B2t）
def test_v4_agents_queue_sell_nan_keeps_position():
    """V4 / I2：SELL + open=NaN → 零成交、持仓不清零、成本不变、现金不变。"""
    engine = _make_agents_engine(fields={"open": float("nan")})
    _seed_position(engine, "A", 100, price=10.0)
    cash_after_seed = engine.tracker.get_cash()
    engine.pending_queue.add_order(create_pending_order("A", OrderSide.SELL, 100, DATES[0]))

    engine._process_pending_orders(DATES[0], 0)

    position = engine.tracker.get_position("A")
    assert engine.executor.trade_log.get_trades() == []
    assert position is not None
    assert position.quantity == 100
    assert position.avg_cost == 10.0
    assert engine.tracker.get_cash() == cash_after_seed
    assert engine.get_failure_stats().get("pending_invalid_price") == 1


# --------------------------------------------------------------- V5（B2t）
def test_v5_invalid_price_retry_bounded():
    """V5 / DESIGN-D5：全程 NaN → 总成交 0，8 个交易日内队列被 mark_expired 排空。"""
    engine = _make_agents_engine(fields={"open": float("nan")}, n_days=8)
    engine.pending_queue.add_order(create_pending_order("A", OrderSide.BUY, 100, DATES[0]))

    for i in range(8):
        engine._process_pending_orders(DATES[i], i)
        engine.pending_queue.mark_expired(DATES[i])

    stats = engine.get_failure_stats()
    assert engine.executor.trade_log.get_trades() == []
    assert engine.pending_queue.get_pending_orders() == []
    assert 0 < stats.get("pending_invalid_price", 0) <= 5


# --------------------------------------------------------------- V6（B3t）
@pytest.mark.parametrize("bad_open", [float("nan"), 0.0], ids=["nan", "zero"])
def test_v6_v2_queue_invalid_open(bad_open, caplog):
    """V6 / I2 / I6：V2 queue 遇 NaN / 0 → 零成交、现金不变、汇总日志告警含该股。"""
    caplog.set_level(logging.WARNING, logger="core.engine_v2")
    engine = _make_v2_engine(fields={"open": bad_open})
    engine.pending_queue.add_order(create_pending_order("A", OrderSide.BUY, 100, DATES[0]))

    engine._process_pending_orders(DATES[0], 0)

    assert engine.executor.trade_log.get_trades() == []
    assert engine.tracker.get_cash() == CAPITAL
    messages = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("缺少价格数据订单" in msg and "A" in msg for msg in messages), messages


# --------------------------------------------------------------- V8（B2t→B3t）
@pytest.mark.parametrize("engine_kind", ["agents", "v2"])
def test_v8_normal_path_no_false_positive(engine_kind, caplog):
    """V8 / I3：合法价 10 → 正常成交 1 笔，无效价计量缺席或 0（回归保护，红态即通过）。"""
    if engine_kind == "agents":
        engine = _make_agents_engine()
        engine.pending_queue.add_order(create_pending_order("A", OrderSide.BUY, 100, DATES[0]))

        engine._process_pending_orders(DATES[0], 0)

        trades = engine.executor.trade_log.get_trades()
        assert len(trades) == 1
        assert trades[0].price == 10.0
        assert trades[0].quantity == 100
        assert engine.get_failure_stats().get("pending_invalid_price", 0) == 0
        return

    caplog.set_level(logging.WARNING, logger="core.engine_v2")
    v2 = _make_v2_engine()
    v2.pending_queue.add_order(create_pending_order("A", OrderSide.BUY, 100, DATES[0]))

    v2._process_pending_orders(DATES[0], 0)

    trades = v2.executor.trade_log.get_trades()
    assert len(trades) == 1
    assert trades[0].price == 10.0
    messages = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert not any("缺少价格数据" in msg for msg in messages), messages
