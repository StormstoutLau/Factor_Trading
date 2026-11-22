"""outbox 事件目录、构造器与 canonical JSON（P-054 D5/D6）。

事件集固定 **6 类**（F-I6）：对账结果只写 ``AUDIT_RECONCILE``，不入 outbox。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:  # 运行期零依赖（I16 精神）
    from live.orders import FillRecord, OrderRecord


class OutboxEventType:
    ORDER_ACCEPTED = "order.accepted"
    ORDER_REJECTED = "order.rejected"
    ORDER_CANCELED = "order.canceled"
    ORDER_CANCEL_REJECTED = "order.cancel_rejected"
    ORDER_STATUS = "order.status"
    FILL_APPLIED = "fill.applied"


@dataclass(frozen=True)
class OutboxEvent:
    event_id: str
    aggregate_type: str  # "order" | "fill"（reconcile 不入 outbox）
    aggregate_id: str  # coid | fill_key
    event_type: str
    payload: str  # canonical JSON
    created_ts: float


def canonical_json(obj: object) -> str:
    """统一序列化口径（DESIGN §3.4）：键排序、紧凑分隔、不转义中文。"""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _record_payload(
    record: OrderRecord, *, event_id: str, event_type: str, ts: float, reason: str
) -> dict:
    return {
        "schema": 1,
        "event_id": event_id,
        "type": event_type,
        "ts": ts,
        "coid": record.client_order_id,
        "broker_order_id": record.broker_order_id,
        "asset": record.asset,
        "side": record.side,
        "status": record.state.value,
        "filled_quantity": record.filled_quantity,
        "avg_price": record.avg_price,
        "reason": reason,
    }


def order_event(
    record: OrderRecord,
    event_type: str,
    *,
    version: int | None = None,
    ts: float | None = None,
    reason: str = "",
) -> OutboxEvent:
    """构造订单事件；``accepted`` 调用方必须显式传 ``version=1``（D-19）。"""
    v = record.event_version if version is None else version
    if event_type == OutboxEventType.ORDER_ACCEPTED:
        event_id = f"order:{record.client_order_id}:accepted:v{v}"
    elif event_type == OutboxEventType.ORDER_REJECTED:
        event_id = f"order:{record.client_order_id}:rejected:v{v}"
    elif event_type == OutboxEventType.ORDER_CANCELED:
        event_id = f"order:{record.client_order_id}:canceled:v{v}"
    elif event_type == OutboxEventType.ORDER_CANCEL_REJECTED:
        event_id = f"order:{record.client_order_id}:cancel_rejected:v{v}"
    else:
        event_id = f"order:{record.client_order_id}:status:{record.state.value}:v{v}"
    created = record.updated_ts if ts is None else ts
    payload = _record_payload(
        record, event_id=event_id, event_type=event_type, ts=created, reason=reason
    )
    return OutboxEvent(
        event_id=event_id,
        aggregate_type="order",
        aggregate_id=record.client_order_id,
        event_type=event_type,
        payload=canonical_json(payload),
        created_ts=created,
    )


def fill_event(
    fill: FillRecord, *, ts: float | None = None, entry_ids: Sequence[str] = ()
) -> OutboxEvent:
    """成交事件固定 ``v1``（``fill_key`` 本身唯一）。"""
    event_id = f"fill:{fill.fill_key}:v1"
    created = fill.ts if ts is None else ts
    payload = {
        "schema": 1,
        "event_id": event_id,
        "type": OutboxEventType.FILL_APPLIED,
        "ts": created,
        "fill_key": fill.fill_key,
        "coid": fill.client_order_id,
        "asset": fill.asset,
        "side": fill.side,
        "quantity": fill.quantity,
        "price": fill.price,
        "fee": fill.fee,
        "entry_ids": list(entry_ids),
    }
    return OutboxEvent(
        event_id=event_id,
        aggregate_type="fill",
        aggregate_id=fill.fill_key,
        event_type=OutboxEventType.FILL_APPLIED,
        payload=canonical_json(payload),
        created_ts=created,
    )
