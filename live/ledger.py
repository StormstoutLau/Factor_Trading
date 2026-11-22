"""双分录账本：加权成本 + `entry_id` 幂等 + 预留结算（P-053 D5）。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from live.corporate_actions import CorporateAction, adjust_position
from live.orders import FillRecord

_EPS = 1e-9


class LedgerError(RuntimeError):
    """fail-closed：预留超现金 / 结算无预留 / 回填现金不足。"""


@dataclass(frozen=True)
class PositionLot:
    asset: str
    quantity: float
    avg_cost: float
    realized_pnl: float = 0.0


@dataclass(frozen=True)
class LedgerEntry:
    entry_id: str
    kind: str  # fill | fee | corporate_action | cash_adjust
    ts: float
    asset: str
    quantity: float  # 买正卖负（C-2）
    price: float
    amount: float  # = quantity * price（有符号，不含费）
    fee: float
    ref: str


@dataclass(frozen=True)
class LedgerSnapshot:
    cash: float
    reserved_cash: float
    positions: tuple[PositionLot, ...]
    as_of: float

    @property
    def equity(self) -> float:
        return self.cash + self.reserved_cash + sum(p.quantity * p.avg_cost for p in self.positions)


class Ledger:
    def __init__(self, store=None, *, initial_cash: float = 0.0) -> None:
        self._store = store
        self._initial_cash = float(initial_cash)
        self._cash = float(initial_cash)
        self._reserves: dict[str, float] = {}
        self._positions: dict[str, PositionLot] = {}
        self._entries: list[LedgerEntry] = []
        self._seen: set[str] = set()

    # ---------- 预留 ----------

    def reserve(self, *, ref: str, amount: float, ts: float) -> None:
        if amount < 0:
            raise ValueError(f"reserve amount must be >= 0: {amount}")
        if amount > self._cash + _EPS:
            raise LedgerError(f"insufficient cash for reserve {ref}: need {amount:.2f}")
        self._cash -= amount
        self._reserves[ref] = self._reserves.get(ref, 0.0) + amount

    def release(self, *, ref: str, ts: float) -> None:
        amount = self._reserves.pop(ref, 0.0)  # 缺失即 no-op（C-3）
        if amount:
            self._cash += amount

    def settle_reserve(self, *, ref: str, actual: float, ts: float) -> float:
        reserved = self._reserves.pop(ref, None)
        if reserved is None:
            raise LedgerError(f"no reserve for {ref}")
        returned = reserved - actual
        self._cash += returned
        if self._cash < -_EPS:
            raise LedgerError(f"cash negative after settle {ref}: {self._cash:.4f}")
        return returned

    @property
    def cash(self) -> float:
        return self._cash

    @property
    def reserved(self) -> float:
        return sum(self._reserves.values())

    # ---------- 入账 ----------

    def apply_fill(self, fill: FillRecord, *, ts: float | None = None) -> bool:
        if fill.fill_key in self._seen:
            return False
        t = fill.ts if ts is None else ts
        signed = fill.quantity if fill.side == "BUY" else -fill.quantity
        if fill.side not in ("BUY", "SELL"):
            raise ValueError(f"unsupported side for cash ledger: {fill.side}")  # D15
        amount = signed * fill.price
        if fill.side == "BUY":
            actual = fill.quantity * fill.price + fill.fee
            if fill.client_order_id in self._reserves:
                self.settle_reserve(ref=fill.client_order_id, actual=actual, ts=t)
            else:
                if actual > self._cash + _EPS:
                    raise LedgerError(f"insufficient cash for fill {fill.fill_key}")
                self._cash -= actual
        else:
            self._cash += fill.quantity * fill.price  # 现金变动 = −amount（卖出 amount<0，F-I3）
            self._cash -= fill.fee  # fee 单列 entry，replay 逐项对应

        self._seen.add(fill.fill_key)
        self._append(
            LedgerEntry(
                entry_id=f"fill:{fill.fill_key}",
                kind="fill",
                ts=t,
                asset=fill.asset,
                quantity=signed,
                price=fill.price,
                amount=amount,
                fee=0.0,
                ref=fill.client_order_id,
            )
        )
        if fill.fee:
            self._append(
                LedgerEntry(
                    entry_id=f"fee:{fill.fill_key}",
                    kind="fee",
                    ts=t,
                    asset=fill.asset,
                    quantity=0.0,
                    price=0.0,
                    amount=0.0,
                    fee=fill.fee,
                    ref=fill.client_order_id,
                )
            )
        self._update_position(fill.asset, signed, fill.price)
        return True

    def apply_corporate_action(self, action: CorporateAction, *, ts: float) -> list[LedgerEntry]:
        lot = self._positions.get(action.asset, PositionLot(action.asset, 0.0, 0.0))
        new_lot, cash_delta = adjust_position(lot, action)
        key = f"ca:{action.action_id}:{action.asset}"
        if key in self._seen:
            return []
        entries = [
            LedgerEntry(
                entry_id=key,
                kind="corporate_action",
                ts=ts,
                asset=action.asset,
                quantity=new_lot.quantity - lot.quantity,
                price=0.0,
                amount=-cash_delta,  # 统一口径：现金变动 = −amount（F-I3；分红流入 → amount<0）
                fee=0.0,
                ref=action.action_id,
            )
        ]
        self._cash += cash_delta
        self._positions[action.asset] = new_lot
        for entry in entries:
            self._append(entry)
        return entries

    def cash_adjust(self, *, asset: str, delta: float, ref: str, ts: float) -> LedgerEntry:
        """显式现金调整（入金/费退/配股缴款）：``delta`` = 现金变动；entry.amount = −delta（F-I3）。"""
        key = f"cash_adjust:{ref}"
        if key in self._seen:
            raise LedgerError(f"duplicate cash_adjust: {ref}")
        entry = LedgerEntry(
            entry_id=key,
            kind="cash_adjust",
            ts=ts,
            asset=asset,
            quantity=0.0,
            price=0.0,
            amount=-delta,
            fee=0.0,
            ref=ref,
        )
        self._cash += delta
        self._append(entry)
        return entry

    # ---------- 读 ----------

    def snapshot(self) -> LedgerSnapshot:
        return LedgerSnapshot(
            cash=self._cash,
            reserved_cash=self.reserved,
            positions=tuple(sorted(self._positions.values(), key=lambda p: p.asset)),
            as_of=self._entries[-1].ts if self._entries else 0.0,
        )

    def entries(self) -> list[LedgerEntry]:
        return list(self._entries)

    @property
    def initial_cash(self) -> float:
        return self._initial_cash

    def attach_store(self, store) -> None:  # store: LedgerStore；F-I10 网关接线
        self._store = store

    @classmethod
    def resume(cls, entries: Iterable[LedgerEntry], *, initial_cash: float) -> "Ledger":
        """从已持久化分录重建运行账本（崩溃恢复 E⑤ / F-I10；开放预留不参与，I10）。"""
        snap = cls.replay(entries, initial_cash=initial_cash)
        ledger = cls(initial_cash=initial_cash)
        ledger._cash = snap.cash
        ledger._positions = {p.asset: p for p in snap.positions}
        ledger._entries = list(entries)
        ledger._seen = {e.entry_id for e in entries}
        return ledger

    @staticmethod
    def replay(entries: Iterable[LedgerEntry], *, initial_cash: float) -> LedgerSnapshot:
        """只重建 cash/positions（开放中的预留不参与，I10 测试限定为已结算账本，C-2）。

        ``corporate_action`` 的 avg_cost 反推 ratio=(q+Δq)/q 对 STOCK_DIVIDEND/SPLIT 与
        ``adjust_position`` 等价（Step 6 §4-5）；RIGHTS_ISSUE（apply 不摊薄）不在 replay
        等价范围（F-I17④，test_ledger ⑭ 范围确认）。
        """
        cash = float(initial_cash)
        lots: dict[str, PositionLot] = {}
        last_ts = 0.0
        for e in entries:
            last_ts = e.ts
            if e.kind in ("fill", "corporate_action", "cash_adjust"):
                cash -= e.amount
                if e.kind == "fill":
                    lot = lots.get(e.asset, PositionLot(e.asset, 0.0, 0.0))
                    lots[e.asset] = _apply_lot(lot, e.quantity, e.price, None)
                elif e.kind == "corporate_action" and e.quantity:
                    lot = lots.get(e.asset, PositionLot(e.asset, 0.0, 0.0))
                    ratio = (lot.quantity + e.quantity) / lot.quantity if lot.quantity else 1.0
                    lots[e.asset] = replace(
                        lot,
                        quantity=lot.quantity + e.quantity,
                        avg_cost=lot.avg_cost / ratio if ratio else 0.0,
                    )
            if e.kind == "fee":
                cash -= e.fee
        return LedgerSnapshot(
            cash=cash,
            reserved_cash=0.0,
            positions=tuple(sorted(lots.values(), key=lambda p: p.asset)),
            as_of=last_ts,
        )

    # ---------- 内部 ----------

    def _append(self, entry: LedgerEntry) -> None:
        if self._store is not None:
            self._store.append_entry(entry)
        self._entries.append(entry)

    def _update_position(self, asset: str, signed_qty: float, price: float) -> None:
        lot = self._positions.get(asset, PositionLot(asset, 0.0, 0.0))
        self._positions[asset] = _apply_lot(lot, signed_qty, price, None)


def _apply_lot(lot: PositionLot, signed_qty: float, price: float, _unused) -> PositionLot:
    """买加仓改加权成本；卖减仓结算 realized_pnl；清零时 avg_cost=0（D5）。"""
    if signed_qty > 0:
        new_qty = lot.quantity + signed_qty
        avg = (lot.quantity * lot.avg_cost + signed_qty * price) / new_qty if new_qty else 0.0
        return PositionLot(lot.asset, new_qty, avg, lot.realized_pnl)
    qty = lot.quantity + signed_qty
    realized = lot.realized_pnl + (price - lot.avg_cost) * (-signed_qty)
    if abs(qty) <= _EPS:
        return PositionLot(lot.asset, 0.0, 0.0, realized)
    return PositionLot(lot.asset, qty, lot.avg_cost, realized)
