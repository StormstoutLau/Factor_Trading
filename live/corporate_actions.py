"""公司行为事件表与对账先归因（P-053 D12 / G11）。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import TYPE_CHECKING, Iterable

from live.reconcile import BreakLevel  # 运行期唯一内部依赖（attribute_break 判级，F-I4）

if TYPE_CHECKING:  # PositionLot/Break 仅注解：replace 鸭子类型，构造点在 ledger/reconcile 本域
    from live.ledger import PositionLot
    from live.reconcile import Break


class ActionType(str, Enum):
    CASH_DIVIDEND = "cash_dividend"
    STOCK_DIVIDEND = "stock_dividend"
    SPLIT = "split"
    RIGHTS_ISSUE = "rights_issue"


@dataclass(frozen=True)
class CorporateAction:
    action_id: str
    asset: str
    action_type: ActionType
    ex_date: str
    cash_per_share: float = 0.0
    share_ratio: float = 0.0
    price: float = 0.0
    note: str = ""


_COLUMNS = (
    "action_id",
    "asset",
    "action_type",
    "ex_date",
    "cash_per_share",
    "share_ratio",
    "price",
    "note",
)


def load_actions(rows: Iterable[dict[str, str]]) -> tuple[CorporateAction, ...]:
    out: list[CorporateAction] = []
    for row in rows:
        missing = [c for c in _COLUMNS if c not in row]
        if missing:
            raise ValueError(f"corporate action row missing columns: {missing}")
        out.append(
            CorporateAction(
                action_id=row["action_id"],
                asset=row["asset"],
                action_type=ActionType(row["action_type"]),
                ex_date=row["ex_date"],
                cash_per_share=float(row["cash_per_share"] or 0.0),
                share_ratio=float(row["share_ratio"] or 0.0),
                price=float(row["price"] or 0.0),
                note=row["note"],
            )
        )
    return tuple(out)


def actions_for(
    actions: Iterable[CorporateAction], *, asset: str, ex_date: str
) -> tuple[CorporateAction, ...]:
    return tuple(a for a in actions if a.asset == asset and a.ex_date == ex_date)


def adjust_position(lot: PositionLot, action: CorporateAction) -> tuple[PositionLot, float]:
    """返回（新持仓, 现金变动）。配股不自动扣款（U-P053-12）。"""
    if action.action_type is ActionType.CASH_DIVIDEND:
        return lot, action.cash_per_share * lot.quantity
    ratio = action.share_ratio
    if action.action_type is ActionType.RIGHTS_ISSUE:
        return replace(lot, quantity=lot.quantity * (1.0 + ratio)), 0.0
    if ratio <= 0.0:
        return lot, 0.0
    new_qty = lot.quantity * (1.0 + ratio)
    new_avg = lot.avg_cost / (1.0 + ratio) if new_qty else 0.0
    return replace(lot, quantity=new_qty, avg_cost=new_avg), 0.0


def attribute_break(brk: Break, *, actions: tuple[CorporateAction, ...]) -> Break:
    """差异可由同日公司行为精确解释 → MISSED 并记 action_id（先归因再判级）。"""
    for action in actions:
        if action.asset != brk.asset:
            continue
        if brk.kind == "cash" and action.action_type is ActionType.CASH_DIVIDEND:
            expected = action.cash_per_share * brk.local
            if abs(brk.delta - expected) <= max(1.0, abs(expected) * 0.01):
                return replace(brk, level=BreakLevel.MISSED, note=action.action_id)
        if brk.kind == "position" and action.action_type in (
            ActionType.STOCK_DIVIDEND,
            ActionType.SPLIT,
            ActionType.RIGHTS_ISSUE,
        ):
            expected = brk.local * action.share_ratio
            if abs(abs(brk.delta) - abs(expected)) <= max(1.0, abs(expected) * 0.01):
                return replace(brk, level=BreakLevel.MISSED, note=action.action_id)
    return brk
