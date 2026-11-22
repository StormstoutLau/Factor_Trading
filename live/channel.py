"""通道能力门、通道状态、限额合成与适配器 ABC（P-053 D2/D9）。

本模块零 I/O、零系统时钟（I1/I11）；`live.orders` 仅 TYPE_CHECKING 引用。
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # 仅类型：运行期不产生 orders ↔ channel 循环依赖（C-1）
    from live.orders import OrderRequest, OrderState


class ChannelState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DEGRADED = "degraded"  # 可撤单/可查询，禁止新开
    HALTED = "halted"  # 全停（对账 unresolved / 人工）


@dataclass(frozen=True)
class ChannelCapability:
    channel_id: str
    venue: str  # "ctp" | "broker_api" | "terminal" | "mock"
    account_level: str  # 本批仅 "cash"（D15）；margin/short 归 P-056
    products: tuple[str, ...]  # ("stock",) / ("future","option")
    supports_client_order_id: bool
    supports_cancel: bool
    supports_query_orders: bool
    supports_query_trades: bool
    supports_query_positions: bool
    autonomous: bool
    report_registered: bool
    max_submit_per_sec: float
    max_submit_per_day: int
    max_cancel_per_sec: float
    max_query_per_sec: float
    notes: str = ""


class CapabilityError(RuntimeError):
    """能力不满足（消息含缺失项清单）。"""


class ChannelUnavailable(RuntimeError):
    """未配置 / 未连通 / 未注入 transport。"""


class ChannelRejected(RuntimeError):
    """柜台明确拒单（code/reason 原样落 audit.order）。"""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(f"{code}: {reason}")
        self.code = code
        self.reason = reason


@dataclass(frozen=True)
class ChannelLimits:
    submit_per_sec: float
    submit_per_day: int
    cancel_per_sec: float
    query_per_sec: float


@dataclass(frozen=True)
class SubmitAck:
    client_order_id: str
    broker_order_id: str
    state: OrderState
    ts: float


@dataclass(frozen=True)
class OrderReport:
    client_order_id: str
    broker_order_id: str
    state: OrderState
    filled_quantity: float
    avg_price: float
    ts: float
    code: str = ""
    reason: str = ""


@dataclass(frozen=True)
class FillReport:
    fill_key: str
    client_order_id: str
    asset: str
    side: str
    quantity: float
    price: float
    fee: float
    ts: float


@dataclass(frozen=True)
class PositionReport:
    asset: str
    quantity: float
    available: float | None = None


_SWITCHES = {
    "client_order_id": "supports_client_order_id",
    "cancel": "supports_cancel",
    "query_orders": "supports_query_orders",
    "query_trades": "supports_query_trades",
    "query_positions": "supports_query_positions",
    "autonomous": "autonomous",
    "report_registered": "report_registered",
}


def require_capability(cap: ChannelCapability, *, need: frozenset[str]) -> None:
    """缺项即 ``CapabilityError("missing: a, b")``；未知键按品种名处理（D2）。"""
    missing: list[str] = []
    for key in sorted(need):
        attr = _SWITCHES.get(key)
        if attr is not None:
            if not getattr(cap, attr):
                missing.append(key)
        elif key not in cap.products:
            missing.append(key)
    if missing:
        raise CapabilityError("missing: " + ", ".join(missing))


def resolve_limits(
    cap: ChannelCapability,
    *,
    internal_per_sec: float,
    internal_per_day: int,
    regulator_per_sec: float = 300.0,
    regulator_per_day: int = 20000,
) -> ChannelLimits:
    """三方最小（内部 / 通道 / 监管，D2）：任一维取 min，监管优先。"""
    return ChannelLimits(
        submit_per_sec=min(internal_per_sec, cap.max_submit_per_sec, regulator_per_sec),
        submit_per_day=min(internal_per_day, cap.max_submit_per_day, regulator_per_day),
        cancel_per_sec=min(cap.max_cancel_per_sec, cap.max_submit_per_sec),
        query_per_sec=min(cap.max_query_per_sec, cap.max_submit_per_sec),
    )


class ChannelAdapter(ABC):
    """四通道统一语义（D9）：7 方法 + 2 属性。"""

    capability: ChannelCapability
    state: ChannelState

    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def submit(self, request: OrderRequest) -> SubmitAck: ...

    @abstractmethod
    def cancel(self, client_order_id: str) -> None: ...

    @abstractmethod
    def query_orders(self, *, day: str) -> list[OrderReport]: ...

    @abstractmethod
    def query_trades(self, *, day: str) -> list[FillReport]: ...

    @abstractmethod
    def query_positions(self) -> list[PositionReport]: ...

    def drain_reports(self) -> list[OrderReport | FillReport]:
        """非阻塞清空回报队列；无队列通道（poll 型）返回 []。"""
        return []


def _ceil_positive(value: float) -> float:
    return float(math.ceil(value)) if value > 0 else 0.0
