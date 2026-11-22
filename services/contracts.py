"""服务层纯契约：Protocol / DTO / 错误码（零第三方运行依赖，I16）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


class ErrorCode:
    NOT_READY = "not_ready"
    AUTH_FAILED = "auth_failed"
    SLOW_CONSUMER = "slow_consumer"
    QUEUE_OVERFLOW = "queue_overflow"
    INTERNAL = "internal"


@dataclass(frozen=True)
class StreamMessage:
    seq: int
    event_id: str
    event_type: str
    payload: str
    message_id: str = ""


@dataclass(frozen=True)
class SnapshotDTO:
    seq: int
    orders: tuple[dict, ...]
    positions: tuple[dict, ...]
    account: dict
    recovery_state: str
    degraded: bool = False


class EventPublisher(Protocol):
    def publish(self, channel: str, message: dict) -> None: ...


class OrderStream(Protocol):
    def add(self, message: StreamMessage) -> str: ...

    def read(
        self, *, consumer: str, count: int = 10, block_ms: int = 1000
    ) -> list[StreamMessage]: ...

    def ack(self, message_id: str) -> None: ...

    def autoclaim(self, *, consumer: str, idle_ms: int, count: int) -> list[StreamMessage]: ...


class TicketStore(Protocol):
    def issue(self, token: str, ttl: int) -> bool: ...

    def consume(self, token: str) -> bool: ...


class ServiceError(RuntimeError):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code
        self.message = message


def orders_to_dicts(records: Sequence) -> tuple[dict, ...]:
    return tuple(
        {
            "client_order_id": r.client_order_id,
            "broker_order_id": r.broker_order_id,
            "asset": r.asset,
            "side": r.side,
            "quantity": r.quantity,
            "filled_quantity": r.filled_quantity,
            "avg_price": r.avg_price,
            "state": r.state.value,
            "updated_ts": r.updated_ts,
        }
        for r in records
    )
