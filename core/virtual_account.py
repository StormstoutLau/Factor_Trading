"""多策略虚拟子账户（P-051c，DESIGN D7 / I7 / I8）。

纯记账：不接引擎、不读写文件、不 import lifecycle（D7）。变更全部返回新实例。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Mapping

__all__ = ["VirtualAccount", "BudgetCheck", "check_allocation", "check_book"]

TOL = 1e-9


def _finite(name: str, value: float) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} 必须为有限数：{value!r}")
    return number


@dataclass(frozen=True)
class VirtualAccount:
    """单策略虚拟子账户（D7）：cash + reserved + Σpositions == total（I7）。"""

    strategy_id: str
    cash: float
    reserved: float
    positions: Mapping[str, float]
    total: float

    def __post_init__(self) -> None:
        if not str(self.strategy_id).strip():
            raise ValueError("strategy_id 不能为空")
        cash = _finite("cash", self.cash)
        reserved = _finite("reserved", self.reserved)
        total = _finite("total", self.total)
        if cash < 0.0:
            raise ValueError(f"cash 不能为负：{cash}")
        if reserved < 0.0:
            raise ValueError(f"reserved 不能为负：{reserved}")
        positions = {
            str(code): _finite(f"positions[{code}]", notional)
            for code, notional in self.positions.items()
        }
        for code, notional in positions.items():
            if notional < 0.0:
                raise ValueError(f"positions[{code}] 不能为负：{notional}")
        booked = cash + reserved + math.fsum(positions.values())
        if abs(booked - total) > TOL:
            raise ValueError(f"账本不守恒：cash+reserved+positions={booked} != total={total}")
        object.__setattr__(self, "cash", cash)
        object.__setattr__(self, "reserved", reserved)
        object.__setattr__(self, "total", total)
        object.__setattr__(self, "positions", positions)

    def allocate(self, notional: float) -> "VirtualAccount":
        """额度层：注资/撤资（cash/total 同步变动，不动 positions/reserved）。"""
        amount = _finite("notional", notional)
        if amount == 0.0:
            raise ValueError("allocate 金额不得为零")
        if amount < 0.0:
            if self.cash + amount < 0.0:
                raise ValueError(f"撤资后 cash 为负：{self.cash + amount}")
            if self.total + amount < self.reserved:
                raise ValueError("撤资后 total 不足以覆盖 reserved")
        return replace(self, cash=self.cash + amount, total=self.total + amount)

    def try_reserve(self, notional: float) -> tuple["VirtualAccount", bool]:
        """订单层：cash → reserved；资金不足返回 ``(self, False)`` 不抛错。"""
        amount = _finite("notional", notional)
        if amount <= 0.0:
            raise ValueError(f"reserve 金额必须为正：{amount}")
        if amount > self.cash:
            return self, False
        updated = replace(self, cash=self.cash - amount, reserved=self.reserved + amount)
        return updated, True

    def release(self, notional: float) -> "VirtualAccount":
        """reserved → cash；超过 reserved 抛 ``ValueError``。"""
        amount = _finite("notional", notional)
        if amount <= 0.0:
            raise ValueError(f"release 金额必须为正：{amount}")
        if amount > self.reserved + TOL:
            raise ValueError(f"release 超过 reserved：{amount} > {self.reserved}")
        moved = min(amount, self.reserved)
        return replace(self, cash=self.cash + moved, reserved=self.reserved - moved)

    def fill(self, code: str, notional: float) -> "VirtualAccount":
        """以实际成交额入账：reserved -= notional，positions[code] += notional。"""
        amount = _finite("notional", notional)
        if amount <= 0.0:
            raise ValueError(f"fill 金额必须为正：{amount}")
        if amount > self.reserved + TOL:
            raise ValueError(f"fill 超过 reserved：{amount} > {self.reserved}")
        moved = min(amount, self.reserved)
        positions = dict(self.positions)
        positions[code] = positions.get(code, 0.0) + moved
        return replace(self, reserved=self.reserved - moved, positions=positions)


@dataclass(frozen=True)
class BudgetCheck:
    """预算校验结果：``ok`` 与 ``violations`` 一一对应。"""

    ok: bool
    violations: tuple[str, ...] = ()


def check_allocation(
    weights: Mapping[str, float], total: float, *, max_weight: float = 1.0
) -> BudgetCheck:
    """单策略目标权重校验：非负、≤ max_weight、Σ ≤ 1（均含 TOL）。"""
    violations: list[str] = []
    total_value = _finite("total", total)
    if total_value <= 0.0:
        violations.append("total")
    for code in sorted(weights, key=str):
        weight = float(weights[code])
        if not math.isfinite(weight):
            violations.append(f"non_finite:{code}")
        elif weight < -TOL:
            violations.append(f"negative:{code}")
        elif weight > max_weight + TOL:
            violations.append(f"max_weight:{code}")
    if math.fsum(float(value) for value in weights.values()) > 1.0 + TOL:
        violations.append("sum")
    return BudgetCheck(ok=not violations, violations=tuple(violations))


def check_book(accounts: Mapping[str, VirtualAccount], total: float) -> BudgetCheck:
    """账本校验：Σ account.total ≤ total + TOL；任一账户 I7 破缺时构造期已抛错。"""
    violations: list[str] = []
    total_value = _finite("total", total)
    if total_value <= 0.0:
        violations.append("total")
    booked = math.fsum(float(account.total) for account in accounts.values())
    if booked > total_value + TOL:
        violations.append("over_allocated")
    return BudgetCheck(ok=not violations, violations=tuple(violations))
