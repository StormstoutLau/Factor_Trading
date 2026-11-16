"""P-034 价格差异校验守卫测试

覆盖 DESIGN V1-V5（IMPL §5 十二实例）：close_price 无效（None / 0 / NaN / ±inf / 负）
时差异校验跳过——消除 ZeroDivisionError 吞单（Python float 形态）、inf% 告警噪声
（numpy 形态）与 NaN/负值下校验静默失效；合法 close 的 10% 差异告警逐字不变。
fixture 独立（不改 test_p029 / test_p031 / test_p033）。
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import pytest

from core.config import CostConfig, ExecutionPriceType
from core.execution import ExecutionSimulator
from core.pending import OrderSide

DATES = pd.bdate_range("2024-01-02", periods=3)
STOCK = "A"
OPEN = 10.0
LOGGER = "core.execution"


# --------------------------------------------------------------- fixtures
def _zero_cost() -> CostConfig:
    return CostConfig(commission_rate=0.0, commission_min=0.0, stamp_tax_rate=0.0, slippage_pct=0.0)


def _sim() -> ExecutionSimulator:
    """F2：每例新建（隔离 trade_log）。"""
    return ExecutionSimulator(_zero_cost(), execution_price_type=ExecutionPriceType.OPEN)


def _run(sim: ExecutionSimulator, close_price, open_price: float = OPEN):
    """F3：统一调用形态（BUY 100 股 @ OPEN）。"""
    return sim.execute_order(STOCK, OrderSide.BUY, 100, DATES[0], open_price, close_price)


def _msgs(caplog, keyword: str):
    """F4：按关键字分离三类告警。"""
    return [r for r in caplog.records if keyword in r.getMessage()]


# --------------------------------------------------------------- V1
@pytest.mark.parametrize(
    "close_price",
    [
        pytest.param(0.0, id="python-0"),
        pytest.param(np.float64(0.0), id="numpy-0"),
        pytest.param(float("nan"), id="nan"),
        pytest.param(-5.0, id="negative"),
        pytest.param(float("inf"), id="inf"),
        pytest.param(float("-inf"), id="neg-inf"),
    ],
)
def test_v1_invalid_close_skips_diff_check(caplog, close_price):
    """V1：无效 close 六形态 → 成交正常、零差异告警、零执行失败。"""
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    sim = _sim()

    success, trade = _run(sim, close_price)

    assert success is True
    assert trade is not None
    assert trade.price == OPEN
    assert len(sim.trade_log.get_trades()) == 1
    assert _msgs(caplog, "差异过大") == []
    assert _msgs(caplog, "交易执行失败") == []


# --------------------------------------------------------------- V2
@pytest.mark.parametrize(
    ("close_price", "expect_count", "expect_text"),
    [
        pytest.param(8.0, 1, "25.00%", id="gap-25pct"),
        pytest.param(7.0, 1, "42.86%", id="gap-43pct"),
        pytest.param(10.5, 0, None, id="gap-5pct-below-threshold"),
    ],
)
def test_v2_valid_close_keeps_warning(caplog, close_price, expect_count, expect_text):
    """V2：合法 close 的 10% 差异告警逐字保留（回归保护）。"""
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    sim = _sim()

    success, _ = _run(sim, close_price)

    assert success is True
    hits = _msgs(caplog, "差异过大")
    assert len(hits) == expect_count
    if expect_text is not None:
        assert expect_text in hits[0].getMessage()


# --------------------------------------------------------------- V3
def test_v3_none_close_unchanged(caplog):
    """V3：close=None 原行为不变（跳过、零告警）。"""
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    sim = _sim()

    success, trade = _run(sim, None)

    assert success is True
    assert trade is not None
    assert trade.price == OPEN
    assert _msgs(caplog, "差异过大") == []


# --------------------------------------------------------------- V4
def test_v4_zero_close_not_swallowed(caplog):
    """V4：R1 吞单——close=0.0（Python float）不再抛 ZeroDivisionError。"""
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    sim = _sim()

    success, trade = _run(sim, 0.0)

    assert success is True
    assert trade is not None
    assert len(sim.trade_log.get_trades()) == 1
    assert _msgs(caplog, "交易执行失败") == []


# --------------------------------------------------------------- V5
def test_v5_guard_interaction(caplog):
    """V5：P-033 守卫先行——open=NaN 时不进入差异校验。"""
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    sim = _sim()

    success, trade = _run(sim, 0.0, open_price=float("nan"))

    assert success is False
    assert trade is None
    assert len(_msgs(caplog, "执行价格无效")) == 1
    assert _msgs(caplog, "差异过大") == []
