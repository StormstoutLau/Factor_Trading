"""订单号、FIX 对齐状态机与订单/成交记录（P-053 D3/D4）。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from enum import Enum


@dataclass(frozen=True)
class OrderRequest:
    """统一订单请求（D3/D9；channel 与适配器经 TYPE_CHECKING 引用——Step 6 F-I2 落本文件）。"""

    asset: str
    side: str  # 与 OrderIntent.action 同域（BUY/SELL/SELL_SHORT/BUY_TO_COVER）
    quantity: float
    asset_type: str = "stock"
    price: float | None = None  # 市价单 None（预留基准价取 ctx.price，C-6）
    order_type: str = "limit"
    client_order_id: str = ""  # 空则由网关步⑤生成一次（D3）
    account_id: str = ""
    strategy_id: str = ""
    signal_ts: float = 0.0
    remark: str = ""


class OrderState(str, Enum):
    PENDING_NEW = "A"
    NEW = "0"
    PARTIALLY_FILLED = "1"
    FILLED = "2"
    CANCELED = "4"
    REJECTED = "8"
    EXPIRED = "C"
    PENDING_CANCEL = "6"
    UNKNOWN = "?"


TERMINAL_STATES = frozenset(
    {OrderState.FILLED, OrderState.CANCELED, OrderState.REJECTED, OrderState.EXPIRED}
)

LEGAL: dict[OrderState, frozenset[OrderState]] = {
    OrderState.PENDING_NEW: frozenset(
        {
            OrderState.NEW,
            OrderState.PARTIALLY_FILLED,
            OrderState.FILLED,
            OrderState.REJECTED,
            OrderState.EXPIRED,
            OrderState.UNKNOWN,
        }
    ),
    OrderState.NEW: frozenset(
        {
            OrderState.PARTIALLY_FILLED,
            OrderState.FILLED,
            OrderState.PENDING_CANCEL,
            OrderState.CANCELED,
            OrderState.EXPIRED,
            OrderState.UNKNOWN,
        }
    ),
    OrderState.PARTIALLY_FILLED: frozenset(
        {
            OrderState.PARTIALLY_FILLED,  # 自环：多次部成回报，filled_quantity 递增（F-I5；校验③保单调）
            OrderState.FILLED,
            OrderState.PENDING_CANCEL,
            OrderState.CANCELED,
            OrderState.EXPIRED,
            OrderState.UNKNOWN,
        }
    ),
    OrderState.PENDING_CANCEL: frozenset(
        {
            OrderState.PENDING_CANCEL,  # 自环：复合态重报（CTP 52 部成待撤多次推送，F-I5）
            OrderState.PARTIALLY_FILLED,
            OrderState.FILLED,
            OrderState.CANCELED,
            OrderState.EXPIRED,
            OrderState.UNKNOWN,
        }
    ),
    OrderState.UNKNOWN: frozenset({s for s in OrderState if s is not OrderState.UNKNOWN}),
    OrderState.FILLED: frozenset(),
    OrderState.CANCELED: frozenset(),
    OrderState.REJECTED: frozenset(),
    OrderState.EXPIRED: frozenset(),
}

_SOURCE = "live.orders"


def make_client_order_id(
    *,
    strategy_id: str,
    account_id: str,
    asset: str,
    side: str,
    quantity: float,
    price: float | None,
    signal_ts: float,
) -> str:
    """确定性 16 hex（D3）：同输入同输出；网关只在首次 submit 调用一次。"""
    raw = "|".join(
        [
            strategy_id,
            account_id,
            asset,
            side,
            f"{quantity:.6f}",
            f"{(price if price is not None else 0.0):.6f}",
            f"{signal_ts:.6f}",
        ]
    )
    return "co_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class OrderRecord:
    client_order_id: str
    broker_order_id: str
    asset: str
    side: str
    quantity: float
    filled_quantity: float
    avg_price: float
    state: OrderState
    created_ts: float
    updated_ts: float
    reject_code: str = ""
    reject_reason: str = ""
    event_version: int = 0  # 每次真实迁移 +1；同态回报不变（P-054 D6/D-19）

    @property
    def remaining_quantity(self) -> float:
        return max(0.0, self.quantity - self.filled_quantity)

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES


@dataclass(frozen=True)
class FillRecord:
    fill_key: str
    client_order_id: str
    asset: str
    side: str
    quantity: float
    price: float
    fee: float
    ts: float


class OrderTransitionError(RuntimeError):
    """非法迁移 / 终态回退 / 成交量回退。"""


def transition(
    record: OrderRecord,
    *,
    state: OrderState,
    ts: float,
    broker_order_id: str | None = None,
    filled_quantity: float | None = None,
    avg_price: float | None = None,
    reject_code: str = "",
    reject_reason: str = "",
) -> OrderRecord:
    """按 §3.2 迁移表推进；同态同步回报幂等返回原对象（C-8）。"""
    if record.state is state and filled_quantity is None:
        # 同态回报（F-I5）：纯重放幂等返回原对象；携带新 broker_order_id（ack 回填）只补该字段
        if broker_order_id and not record.broker_order_id:
            return replace(record, broker_order_id=broker_order_id, updated_ts=ts)
        return record
    if record.is_terminal:
        raise OrderTransitionError(
            f"{record.client_order_id}: terminal {record.state} is irreversible"
        )
    if state not in LEGAL[record.state]:
        raise OrderTransitionError(f"{record.client_order_id}: illegal {record.state} -> {state}")
    fq = record.filled_quantity if filled_quantity is None else filled_quantity
    if fq < record.filled_quantity - 1e-12:
        raise OrderTransitionError(f"{record.client_order_id}: filled_quantity regressed")
    if fq > record.quantity + 1e-12:
        raise OrderTransitionError(f"{record.client_order_id}: filled_quantity > quantity")
    return replace(
        record,
        state=state,
        updated_ts=ts,
        broker_order_id=broker_order_id or record.broker_order_id,
        filled_quantity=fq,
        avg_price=record.avg_price if avg_price is None else avg_price,
        reject_code=reject_code or record.reject_code,
        reject_reason=reject_reason or record.reject_reason,
        event_version=record.event_version + 1,
    )


def from_request(request: OrderRequest, *, ts: float) -> OrderRecord:
    """首次提交的 PENDING_NEW 记录（F-D2：以 request 构造）。"""
    return OrderRecord(
        client_order_id=request.client_order_id,
        broker_order_id="",
        asset=request.asset,
        side=request.side,
        quantity=request.quantity,
        filled_quantity=0.0,
        avg_price=0.0,
        state=OrderState.PENDING_NEW,
        created_ts=ts,
        updated_ts=ts,
    )
