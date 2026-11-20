"""P-050 期货账目纯函数层。

不 import tracker/engine；只依赖 numpy/pandas/dataclasses/typing。
所有函数无副作用，输入不可变视图，输出新对象。

账目口径（DESIGN D1/D3）：
- ``cash`` 为可用资金（已扣保证金）；
- ``margin_used`` 为占用保证金；
- 逐日结算把盈亏净额入现金并重算保证金，``market_value = margin + mtm``。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Protocol, runtime_checkable

import pandas as pd

from core.config import AssetType

__all__ = [
    "ContractSpec",
    "LiquidationRequest",
    "RollInstruction",
    "SettlementResult",
    "MarginModel",
    "ExchangeMarginModel",
    "compute_settlement",
    "apply_settlement",
    "liquidation_requests",
    "roll_orders",
    "split_reversal",
]

DEFAULT_ROLL_DAYS = 5


@dataclass(frozen=True)
class ContractSpec:
    """期货合约规格（元数据驱动，不内置品种表）。"""

    symbol: str
    multiplier: float = 1.0
    margin_ratio: float = 0.0
    expiry_date: Optional[pd.Timestamp] = None
    roll_days_before_expiry: Optional[int] = None
    roll_target: Optional[str] = None
    asset_type: AssetType = AssetType.FUTURE


@dataclass(frozen=True)
class LiquidationRequest:
    """强平请求：``quantity`` 与持仓同号（正=平多，负=平空）。"""

    symbol: str
    quantity: float
    reason: str = "margin_call"
    deferred_days: int = 0


@dataclass(frozen=True)
class RollInstruction:
    """换月指令：平旧合约 ``quantity`` 手，等量开新合约。"""

    close_symbol: str
    open_symbol: str
    quantity: float
    reason: str = "expiry_roll"


@dataclass(frozen=True)
class SettlementResult:
    """单日结算结果。"""

    date: pd.Timestamp
    pnl_by_symbol: dict[str, float]
    total_pnl: float
    margin_after: dict[str, float]
    margin_delta: float
    settlements_used: dict[str, float]
    proxy_used: bool


@runtime_checkable
class MarginModel(Protocol):
    """保证金模型协议。"""

    def initial_margin(self, notional: float, spec: ContractSpec) -> float: ...

    def maintenance_margin(self, notional: float, spec: ContractSpec) -> float: ...


class ExchangeMarginModel:
    """默认模型：按 ``spec.margin_ratio``（交易所最低保证金率）计提。"""

    def initial_margin(self, notional: float, spec: ContractSpec) -> float:
        return notional * spec.margin_ratio

    def maintenance_margin(self, notional: float, spec: ContractSpec) -> float:
        return notional * spec.margin_ratio


def _is_futures(position: Any) -> bool:
    asset_type = getattr(position, "asset_type", None)
    return getattr(asset_type, "name", asset_type) == "FUTURE"


def compute_settlement(
    positions: Mapping[str, Any],
    settlements: Mapping[str, float],
    specs: Mapping[str, ContractSpec],
    margin_model: Optional[MarginModel] = None,
) -> SettlementResult:
    """逐合约结算：``pnl = q × (S_t − settle_base) × m``，并按 ``S_t`` 重建保证金。

    仅处理 ``asset_type == FUTURE`` 且有持仓的标的；缺结算价的标的不产生盈亏、
    保证金沿用原值（``proxy_used`` 保持 False）。
    """
    model: MarginModel = margin_model or ExchangeMarginModel()
    pnl_by_symbol: dict[str, float] = {}
    margin_after: dict[str, float] = {}
    settlements_used: dict[str, float] = {}
    margin_prev = 0.0
    total_pnl = 0.0

    for symbol, position in positions.items():
        if not _is_futures(position):
            continue
        qty = float(getattr(position, "quantity", 0.0) or 0.0)
        margin_prev += float(getattr(position, "margin_used", 0.0) or 0.0)
        if abs(qty) < 1e-12:
            margin_after[symbol] = 0.0
            continue
        spec = specs.get(symbol)
        if spec is None:
            raise ValueError(f"{symbol} 是期货持仓但缺少合约规格（specs）")
        settlement = settlements.get(symbol)
        if settlement is None or not pd.notna(settlement) or float(settlement) <= 0:
            margin_after[symbol] = float(getattr(position, "margin_used", 0.0) or 0.0)
            continue
        price = float(settlement)
        mult = float(getattr(position, "multiplier", 1.0) or 1.0)
        base = float(getattr(position, "settle_base", 0.0) or 0.0)
        pnl = qty * (price - base) * mult if base else 0.0
        pnl_by_symbol[symbol] = pnl
        total_pnl += pnl
        settlements_used[symbol] = price
        margin_after[symbol] = model.initial_margin(abs(qty) * price * mult, spec)

    margin_total_after = sum(margin_after.values())
    return SettlementResult(
        date=pd.Timestamp.min,
        pnl_by_symbol=pnl_by_symbol,
        total_pnl=total_pnl,
        margin_after=margin_after,
        margin_delta=margin_total_after - margin_prev,
        settlements_used=settlements_used,
        proxy_used=False,
    )


def apply_settlement(
    cash: float,
    margin_prev: float,
    result: SettlementResult,
) -> tuple[float, float]:
    """``cash += total_pnl − margin_delta``；返回 ``(cash_after, margin_after)``。"""
    cash_after = float(cash) + float(result.total_pnl) - float(result.margin_delta)
    margin_after = float(margin_prev) + float(result.margin_delta)
    return cash_after, margin_after


def liquidation_requests(
    positions: Mapping[str, Any],
    cash: float,
    specs: Mapping[str, ContractSpec],
) -> list[LiquidationRequest]:
    """``cash >= 0`` → ``[]``；否则按 ``|notional|`` 降序裁剪出最小平仓集合。

    生成时即完成裁剪（执行循环无法中途停止）：累计"预计释放保证金"覆盖缺口即停。
    """
    if cash >= 0:
        return []

    deficit = -float(cash)
    candidates = []
    for symbol, position in positions.items():
        if not _is_futures(position):
            continue
        qty = float(getattr(position, "quantity", 0.0) or 0.0)
        if abs(qty) < 1e-12:
            continue
        notional = float(getattr(position, "notional_value", 0.0) or 0.0)
        if notional <= 0:
            notional = (
                abs(qty)
                * float(getattr(position, "settle_base", 0.0) or 0.0)
                * float(getattr(position, "multiplier", 1.0) or 1.0)
            )
        released = float(getattr(position, "margin_used", 0.0) or 0.0)
        candidates.append((abs(notional), symbol, qty, released))

    candidates.sort(key=lambda item: item[0], reverse=True)

    requests: list[LiquidationRequest] = []
    covered = 0.0
    for _, symbol, qty, released in candidates:
        requests.append(LiquidationRequest(symbol=symbol, quantity=qty))
        covered += released
        if covered >= deficit:
            break
    return requests


def roll_orders(
    positions: Mapping[str, Any],
    specs: Mapping[str, ContractSpec],
    date: pd.Timestamp,
    default_roll_days: int = DEFAULT_ROLL_DAYS,
) -> list[RollInstruction]:
    """到期前 ``roll_days`` 触发换月；同合约每次调用只生成一条。"""
    instructions: list[RollInstruction] = []
    today = pd.Timestamp(date)
    seen: set[str] = set()

    for symbol, position in positions.items():
        if not _is_futures(position):
            continue
        qty = float(getattr(position, "quantity", 0.0) or 0.0)
        if abs(qty) < 1e-12 or symbol in seen:
            continue
        spec = specs.get(symbol)
        if spec is None or spec.expiry_date is None:
            continue
        roll_days = spec.roll_days_before_expiry or default_roll_days
        trigger_date = pd.Timestamp(spec.expiry_date) - pd.Timedelta(days=roll_days)
        if today < trigger_date:
            continue
        if not spec.roll_target:
            raise ValueError(f"{symbol} 已到换月窗口但缺少 roll_target（无远月合约）")
        seen.add(symbol)
        instructions.append(
            RollInstruction(
                close_symbol=symbol,
                open_symbol=spec.roll_target,
                quantity=abs(qty),
            )
        )
    return instructions


def split_reversal(current_qty: float, target_qty: float) -> list[tuple[str, float]]:
    """反手拆单：同号单笔差额；异号 ``[(平仓侧, |current|), (开仓侧, |target|)]``。

    侧别返回字符串（``"BUY"`` / ``"SELL"`` / ``"SELL_SHORT"`` / ``"BUY_TO_COVER"``），
    与 ``OrderSide`` 成员名对齐；模块层不 import ``core.pending``。
    """
    current = float(current_qty)
    target = float(target_qty)
    if abs(target - current) < 1e-12:
        return []

    if current > 0:
        if target >= 0:
            return [("BUY", target - current)] if target > current else [("SELL", current - target)]
        return [("SELL", current), ("SELL_SHORT", -target)]

    if current < 0:
        if target <= 0:
            return (
                [("SELL_SHORT", abs(target) - abs(current))]
                if abs(target) > abs(current)
                else [("BUY_TO_COVER", abs(current) - abs(target))]
            )
        return [("BUY_TO_COVER", abs(current)), ("BUY", target)]

    return [("BUY", target)] if target > 0 else [("SELL_SHORT", -target)]
