from __future__ import annotations

from dataclasses import dataclass, field

from core.live_bridge import MockLiveBridge
from live.channel import (
    ChannelAdapter,
    ChannelCapability,
    ChannelRejected,
    ChannelState,
    FillReport,
    OrderReport,
    PositionReport,
    SubmitAck,
)
from live.orders import OrderRequest, OrderState


@dataclass(frozen=True)
class Frame:
    kind: str  # ack | reject | order | fill | disconnect
    payload: dict
    delay: float = 0.0


class FakeTransport:
    """按脚本出帧；测试注入帧序列（D1）。"""

    def __init__(self, frames: list[Frame] | None = None) -> None:
        self.frames: list[Frame] = list(frames or [])
        self.sent: list[OrderRequest] = []
        self.cancels: list[str] = []

    def next_frame(self, kind: str) -> Frame | None:
        for i, frame in enumerate(self.frames):
            if frame.kind == kind:
                return self.frames.pop(i)
        return None


class MockChannelAdapter(ChannelAdapter):
    def __init__(self, transport: FakeTransport | None = None) -> None:
        self._transport = transport or FakeTransport()
        self.bridge = MockLiveBridge()
        self.state = ChannelState.DISCONNECTED
        self.capability = ChannelCapability(
            channel_id="mock",
            venue="mock",
            account_level="cash",
            products=("stock",),
            supports_client_order_id=True,
            supports_cancel=True,
            supports_query_orders=True,
            supports_query_trades=True,
            supports_query_positions=True,
            autonomous=True,
            report_registered=True,
            max_submit_per_sec=50.0,
            max_submit_per_day=100000,
            max_cancel_per_sec=50.0,
            max_query_per_sec=10.0,
        )

    def connect(self) -> None:
        self.state = ChannelState.CONNECTED

    def disconnect(self) -> None:
        self.state = ChannelState.DISCONNECTED

    def submit(self, request: OrderRequest) -> SubmitAck:
        frame = self._transport.next_frame("reject")
        if frame is not None:
            raise ChannelRejected(
                str(frame.payload.get("code", "mock_reject")),
                str(frame.payload.get("reason", "")),
            )
        self._transport.sent.append(request)
        ack = self._transport.next_frame("ack")
        state = (
            OrderState(ack.payload.get("state", OrderState.PENDING_NEW.value))
            if ack
            else OrderState.PENDING_NEW
        )
        return SubmitAck(
            request.client_order_id,
            f"mock_{len(self._transport.sent):06d}",
            state,
            0.0,
        )  # ts=0.0：ack.ts 不被网关消费（transition 用 submit 的 ts，I1 确定性）

    def cancel(self, client_order_id: str) -> None:
        self._transport.cancels.append(client_order_id)

    def query_orders(self, *, day: str) -> list[OrderReport]:
        return []

    def query_trades(self, *, day: str) -> list[FillReport]:
        return []

    def query_positions(self) -> list[PositionReport]:
        return []

    def drain_reports(self):
        out: list[OrderReport | FillReport] = []
        while True:
            frame = self._transport.next_frame("order")
            if frame is None:
                break
            out.append(OrderReport(**frame.payload))
        while True:
            frame = self._transport.next_frame("fill")
            if frame is None:
                break
            out.append(FillReport(**frame.payload))
        return out
