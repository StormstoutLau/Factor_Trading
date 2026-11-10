"""回测不变量校验（P-011 D2）。

设计依据：DESIGN_backtest_validation.md §4.1 / §6（I1-I7）。
本模块只做纯函数校验，不修改引擎状态；引擎在结果中以
``additional_info["invariant_report"]`` 暴露报告（``invariant_mode="report"``）。
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, Sequence

import numpy as np
import pandas as pd

if TYPE_CHECKING:  # 仅类型检查，避免运行时循环导入
    from core.execution import Trade
    from core.tracker import PortfolioSnapshot

logger = logging.getLogger(__name__)

InvariantMode = Literal["off", "report", "raise"]

_BUY_SIDES = {"BUY", "BUY_TO_COVER"}
_SELL_SIDES = {"SELL", "SELL_SHORT"}


class InvariantViolationError(RuntimeError):
    """``raise`` 模式下的首个不变量违规。"""


@dataclass
class Violation:
    """单条不变量违规。"""

    code: str
    date: str | None = None
    detail: str = ""
    value: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "date": self.date,
            "detail": self.detail,
            "value": self.value,
        }


@dataclass
class InvariantReport:
    """一组不变量校验结果。"""

    mode: str
    checked: int
    violations: list[Violation] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "checked": self.checked,
            "ok": self.ok,
            "violations": [v.to_dict() for v in self.violations],
        }


def _fmt_date(value: Any) -> str:
    try:
        return str(pd.Timestamp(value).strftime("%Y-%m-%d"))
    except (TypeError, ValueError):
        return str(value)


def _side_name(side: Any) -> str:
    return str(getattr(side, "name", side)).upper()


def _close_enough(actual: float, expected: float, *, rtol: float, atol: float) -> bool:
    return abs(actual - expected) <= atol + rtol * abs(expected)


def check_nav_identity(
    snapshots: Sequence[PortfolioSnapshot],
    *,
    rtol: float = 1e-9,
    atol: float = 1e-6,
) -> list[Violation]:
    """I1: ``total_value == cash + Σ position.market_value``（逐快照）。"""
    violations: list[Violation] = []
    for snapshot in snapshots:
        expected = float(snapshot.cash) + float(
            sum(position.market_value for position in snapshot.positions.values())
        )
        actual = float(snapshot.total_value)
        if not _close_enough(actual, expected, rtol=rtol, atol=atol):
            violations.append(
                Violation(
                    code="I1",
                    date=_fmt_date(snapshot.date),
                    detail=f"total_value={actual:.10f} != cash+Σmv={expected:.10f}",
                    value=actual - expected,
                )
            )
    return violations


def check_position_identity(
    snapshots: Sequence[PortfolioSnapshot],
    trades: Sequence[Trade],
    *,
    atol: float = 1e-6,
) -> list[Violation]:
    """I2: 快照日持仓数量 == 截至该日成交累计（买 +，卖 −）。

    边界说明（DESIGN §6 I2）：同一天出现多次快照时该日期不参与校验。末日的
    强制平仓（``engine_v2._force_liquidation``）在收盘快照**之后**成交，并再次
    调用 ``update_market_values`` 追加同日第二次快照；仅凭成交日期无法还原
    "快照之前/之后"的成交边界，故该日期 I2 无定义。退市结算与盘中强平经
    ``execute_order`` 落真实 ``trade``，在唯一快照的日期仍被计入。
    """
    violations: list[Violation] = []
    if not snapshots:
        return violations
    date_counts = Counter(_fmt_date(snapshot.date) for snapshot in snapshots)
    for snapshot in snapshots:
        if date_counts[_fmt_date(snapshot.date)] > 1:
            continue
        day = pd.Timestamp(snapshot.date)
        cumulative: dict[str, float] = {}
        for trade in trades:
            if pd.Timestamp(trade.date) > day:
                continue
            side = _side_name(trade.side)
            if side in _BUY_SIDES:
                sign = 1.0
            elif side in _SELL_SIDES:
                sign = -1.0
            else:
                continue
            stock = str(trade.stock)
            cumulative[stock] = cumulative.get(stock, 0.0) + sign * float(trade.quantity)

        actual = {
            str(stock): float(position.quantity)
            for stock, position in snapshot.positions.items()
            if abs(float(position.quantity)) > atol
        }
        expected_keys = {k for k, v in cumulative.items() if abs(v) > atol}
        for stock in sorted(set(actual) | expected_keys):
            exp = cumulative.get(stock, 0.0)
            act = actual.get(stock, 0.0)
            if abs(exp - act) > atol:
                violations.append(
                    Violation(
                        code="I2",
                        date=_fmt_date(snapshot.date),
                        detail=f"{stock}: 持仓={act} != 成交累计={exp}",
                        value=act - exp,
                    )
                )
    return violations


def check_cost_identity(
    trades: Sequence[Trade],
    stats: dict[str, Any],
    *,
    atol: float = 1e-6,
) -> list[Violation]:
    """I3: ``Σ trade.cost == stats["total_cost"]``；``cost >= 0``；净额符号正确。"""
    violations: list[Violation] = []
    total_cost = 0.0
    for trade in trades:
        cost = float(trade.cost)
        total_cost += cost
        if cost < -atol:
            violations.append(
                Violation(
                    code="I3",
                    date=_fmt_date(trade.date),
                    detail=f"{trade.stock}: cost={cost} < 0",
                    value=cost,
                )
            )
        side = _side_name(trade.side)
        amount = float(trade.amount)
        expected_net = amount + cost if side in _BUY_SIDES else amount - cost
        net = float(trade.net_amount)
        if not _close_enough(net, expected_net, rtol=1e-12, atol=atol):
            violations.append(
                Violation(
                    code="I3",
                    date=_fmt_date(trade.date),
                    detail=f"{trade.stock}: net_amount={net} != expected={expected_net}",
                    value=net - expected_net,
                )
            )
    reported = float(stats.get("total_cost", 0.0))
    if not _close_enough(total_cost, reported, rtol=1e-12, atol=atol):
        violations.append(
            Violation(
                code="I3",
                detail=f"Σcost={total_cost:.10f} != stats.total_cost={reported:.10f}",
                value=total_cost - reported,
            )
        )
    return violations


def check_return_identity(
    snapshots: Sequence[PortfolioSnapshot],
    initial_capital: float,
    *,
    rtol: float = 1e-9,
    atol: float = 1e-9,
) -> list[Violation]:
    """I4: 日收益/累计收益与 NAV 序列递推一致（首日基准 = 初始资金）。"""
    violations: list[Violation] = []
    prev_value = float(initial_capital)
    for snapshot in snapshots:
        total_value = float(snapshot.total_value)
        expected_daily = (total_value - prev_value) / prev_value if prev_value else 0.0
        expected_cum = (total_value - initial_capital) / initial_capital if initial_capital else 0.0
        daily = float(snapshot.daily_return)
        cum = float(snapshot.cumulative_return)
        if not _close_enough(daily, expected_daily, rtol=rtol, atol=atol):
            violations.append(
                Violation(
                    code="I4",
                    date=_fmt_date(snapshot.date),
                    detail=f"daily_return={daily} != {expected_daily}",
                    value=daily - expected_daily,
                )
            )
        if not _close_enough(cum, expected_cum, rtol=rtol, atol=atol):
            violations.append(
                Violation(
                    code="I4",
                    date=_fmt_date(snapshot.date),
                    detail=f"cumulative_return={cum} != {expected_cum}",
                    value=cum - expected_cum,
                )
            )
        prev_value = total_value
    return violations


def check_v3_nav_identity(
    portfolio_value: np.ndarray,
    cash: np.ndarray,
    positions: np.ndarray,
    prices: np.ndarray,
    *,
    rtol: float = 1e-9,
    atol: float = 1e-6,
) -> list[Violation]:
    """I5: ``pv[t] == cash[t] + Σ positions[t] * prices[t]``。"""
    violations: list[Violation] = []
    n_dates = len(portfolio_value)
    for t in range(n_dates):
        expected = float(cash[t]) + float(np.sum(positions[t] * prices[t]))
        actual = float(portfolio_value[t])
        if not _close_enough(actual, expected, rtol=rtol, atol=atol):
            violations.append(
                Violation(
                    code="I5",
                    date=str(t),
                    detail=f"pv={actual} != {expected}",
                    value=actual - expected,
                )
            )
    return violations


def check_v3_static_positions(
    positions: np.ndarray,
    rebalance_indices: set[int],
    *,
    atol: float = 1e-12,
) -> list[Violation]:
    """I6: 非调仓日 ``positions[t] == positions[t-1]``。"""
    violations: list[Violation] = []
    for t in range(1, len(positions)):
        if t in rebalance_indices:
            continue
        delta = positions[t] - positions[t - 1]
        if float(np.max(np.abs(delta))) > atol:
            violations.append(
                Violation(
                    code="I6",
                    date=str(t),
                    detail="非调仓日仓位发生变化",
                    value=float(np.max(np.abs(delta))),
                )
            )
    return violations


def check_v3_cost_identity(
    positions: np.ndarray,
    prices: np.ndarray,
    cash: np.ndarray,
    cost_rate: float,
    *,
    rtol: float = 1e-9,
    atol: float = 1e-6,
) -> list[Violation]:
    """I7: ``cash[t]-cash[t-1] == -ΣΔqty*price - Σ|Δqty|*price*rate``。"""
    violations: list[Violation] = []
    for t in range(1, len(cash)):
        delta_qty = positions[t] - positions[t - 1]
        expected = (
            float(cash[t - 1])
            - float(np.sum(delta_qty * prices[t]))
            - float(np.sum(np.abs(delta_qty) * prices[t])) * float(cost_rate)
        )
        actual = float(cash[t])
        if not _close_enough(actual, expected, rtol=rtol, atol=atol):
            violations.append(
                Violation(
                    code="I7",
                    date=str(t),
                    detail=f"cash={actual} != {expected}",
                    value=actual - expected,
                )
            )
    return violations


def check_all(
    snapshots: Sequence[PortfolioSnapshot],
    trades: Sequence[Trade],
    stats: dict[str, Any],
    initial_capital: float,
    mode: InvariantMode = "report",
) -> InvariantReport:
    """执行 V2 引擎上下文的不变量 I1-I4。"""
    if mode not in ("off", "report", "raise"):
        raise ValueError(f"未知 invariant_mode: {mode!r}")
    violations: list[Violation] = []
    violations.extend(check_nav_identity(snapshots))
    violations.extend(check_position_identity(snapshots, trades))
    violations.extend(check_cost_identity(trades, stats))
    violations.extend(check_return_identity(snapshots, initial_capital))
    report = InvariantReport(mode=mode, checked=len(snapshots), violations=violations)
    if violations:
        logger.error("不变量校验发现 %d 项违规（mode=%s）", len(violations), mode)
    return report
