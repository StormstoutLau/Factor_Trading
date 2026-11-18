"""P-059 G4 回归锁：队列路径 / 次日路径现金闸门口径对拍（DESIGN §9.4）。

唯一生产改动（``core/engine_v2.py`` L1273-1284）把次日路径的
``quantity * open_price * 1.002`` 换成与队列路径同源的 ``estimate_buy_cash``。

手算边界（默认成本 0.0003 / 5.0 / 0.001，A = 100 × 10.00 = 1000.00）：
- ``required = 1000 + max(0.3, 5) + 1.0 = 1006.00``
- 现金 1004.00 < 1006.00 → 两条路径都拒单（旧口径 1002.00 会放行次日路径）
- 现金 1010.00 ≥ 1006.00 → 两条路径都成交；成交成本 5 + 0 + 1 = 6.00，
  买入后现金 = 1010 − 1000 − 6 = 4.00；末日强平卖出（成本 7）后 final_cash = 997.00
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
import pytest

from _scenarios_builder import build_scenario
from _scenarios_spec import ExpectedBlock, ScenarioSpec

A = "000001"
PRICE = 10.0
QUANTITY = 100
AMOUNT = QUANTITY * PRICE  # 1000.00
REQUIRED_CASH = AMOUNT + max(AMOUNT * 0.0003, 5.0) + AMOUNT * 0.001  # 1006.00
TOTAL_COST = max(AMOUNT * 0.0003, 5.0) + AMOUNT * 0.001  # 6.00
PATHS = ("queue", "next_day")
CASH_LEVELS = (1004.0, 1010.0)


def _spec(path: str, cash: float) -> ScenarioSpec:
    dates = pd.bdate_range("2024-01-02", periods=5)
    return ScenarioSpec(
        scenario_id=f"G4-{path}-{cash:.0f}",
        title="G4 两路径现金闸门对拍",
        layer="L5",
        gaps=("G4",),
        dates=dates,
        codes=(A,),
        close=np.full((5, 1), PRICE),
        factors={"factor_alpha": np.ones((5, 1))},
        config={
            "initial_capital": cash,
            "no_rebalance": True,
            "enable_pending_orders": path == "queue",
            "inject_orders": [{"code": A, "side": "BUY", "quantity": QUANTITY, "path": path}],
        },
        expected=ExpectedBlock(fills=()),
    )


def _run(path: str, cash: float, tmp_path: Any) -> Any:
    return build_scenario(_spec(path, cash), tmp_path / f"{path}-{cash:.0f}")


def test_g4_hand_computed_boundary() -> None:
    """RULE-2：边界与成本均为手算值，不取自运行结果。"""
    assert math.isclose(REQUIRED_CASH, 1006.0, abs_tol=1e-9)
    assert math.isclose(TOTAL_COST, 6.0, abs_tol=1e-9)
    assert 1004.0 < REQUIRED_CASH <= 1010.0


@pytest.mark.parametrize("cash", CASH_LEVELS)
def test_g4_paths_are_symmetric(cash: float, tmp_path: Any) -> None:
    """同一现金档位下，两条路径的成交与期末现金必须完全一致。"""
    queue_run = _run("queue", cash, tmp_path)
    next_day_run = _run("next_day", cash, tmp_path)

    assert len(queue_run.trace.fills) == len(next_day_run.trace.fills), (
        f"现金 {cash}: 成交笔数不对称 "
        f"(queue={queue_run.trace.fills}, next_day={next_day_run.trace.fills})"
    )
    assert math.isclose(
        queue_run.final_cash, next_day_run.final_cash, abs_tol=1e-6
    ), f"现金 {cash}: 期末现金不对称 queue={queue_run.final_cash} next_day={next_day_run.final_cash}"

    for left, right in zip(queue_run.trace.fills, next_day_run.trace.fills):
        assert (left["code"], left["side"], left["quantity"]) == (
            right["code"],
            right["side"],
            right["quantity"],
        ), f"现金 {cash}: 成交要素不对称 {left} vs {right}"
        assert math.isclose(left["price"], right["price"], abs_tol=1e-9)


def test_g4_1004_rejects_on_both_paths(tmp_path: Any) -> None:
    """现金 1004 < 1006：两条路径都整单拒绝（旧口径次日路径会成交 → 红）。"""
    for path in PATHS:
        run = _run(path, 1004.0, tmp_path)
        assert run.trace.fills == [], f"{path}: 1004 不应成交（实际 {run.trace.fills}）"
        assert math.isclose(run.final_cash, 1004.0, abs_tol=1e-6)
        assert run.final_positions == {}

    queue_run = _run("queue", 1004.0, tmp_path)
    retry_dates = {
        event["date"] for event in queue_run.trace.state_events if event["state"] == "retry"
    }
    assert retry_dates, "1004: 被拒订单必须保留挂单（retry），而非直接丢弃"


def test_g4_1010_fills_on_both_paths(tmp_path: Any) -> None:
    """现金 1010 ≥ 1006：两条路径都成交 100 股 @10。

    买入后现金 = 1010 − 1000 − (5 + 0 + 1) = 4.00；
    末日强平按收盘价卖出，成本 = 5 + 1（印花）+ 1（滑点）= 7 → 期末现金 = 4 + 993 = 997.00。
    """
    for path in PATHS:
        run = _run(path, 1010.0, tmp_path)
        buy_fills = [fill for fill in run.trace.fills if fill["side"] == "BUY"]
        sell_fills = [fill for fill in run.trace.fills if fill["side"] == "SELL"]
        assert len(buy_fills) == 1, f"{path}: 1010 应恰好成交 1 笔买入（实际 {run.trace.fills}）"
        assert len(sell_fills) == 1, f"{path}: 末日强平应有 1 笔卖出"

        fill = buy_fills[0]
        assert (fill["code"], fill["quantity"]) == (A, QUANTITY)
        assert math.isclose(fill["price"], PRICE, abs_tol=1e-9)
        assert math.isclose(fill["cost"], TOTAL_COST, abs_tol=1e-9)

        first_day = min(run.trace.buckets)
        assert math.isclose(
            run.trace.buckets[first_day]["cash"], 4.0, abs_tol=1e-6
        ), f"{path}: 买入后现金期望 4.00 实际 {run.trace.buckets[first_day]['cash']}"

        assert math.isclose(sell_fills[0]["cost"], 7.0, abs_tol=1e-9)
        assert math.isclose(
            run.final_cash, 997.0, abs_tol=1e-6
        ), f"{path}: 期末现金期望 997.00 实际 {run.final_cash}"
