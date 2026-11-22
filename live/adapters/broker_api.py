from __future__ import annotations

from live.channel import (
    ChannelAdapter,
    ChannelCapability,
    ChannelState,
    ChannelUnavailable,
    FillReport,
    OrderReport,
    PositionReport,
    SubmitAck,
)
from live.orders import OrderRequest


class BrokerApiChannelAdapter(ChannelAdapter):
    def __init__(self, transport=None) -> None:
        self._transport = transport
        self.state = ChannelState.DISCONNECTED
        self.capability = ChannelCapability(
            channel_id="broker_api",
            venue="broker_api",
            account_level="cash",
            products=("stock",),
            supports_client_order_id=True,
            supports_cancel=True,
            supports_query_orders=True,
            supports_query_trades=True,
            supports_query_positions=True,
            autonomous=True,
            report_registered=False,
            max_submit_per_sec=20.0,
            max_submit_per_day=20000,
            max_cancel_per_sec=20.0,
            max_query_per_sec=4.0,
            notes="语义占位；准入审核归 N-3",
        )

    def _require(self):
        if self._transport is None:
            raise ChannelUnavailable("broker_api not configured")
        return self._transport

    def connect(self) -> None:
        self._require()
        self.state = ChannelState.CONNECTED

    def disconnect(self) -> None:
        self.state = ChannelState.DISCONNECTED

    def submit(self, request: OrderRequest) -> SubmitAck:
        raise ChannelUnavailable("broker_api not configured")

    def cancel(self, client_order_id: str) -> None:
        raise ChannelUnavailable("broker_api not configured")

    def query_orders(self, *, day: str) -> list[OrderReport]:
        raise ChannelUnavailable("broker_api not configured")

    def query_trades(self, *, day: str) -> list[FillReport]:
        raise ChannelUnavailable("broker_api not configured")

    def query_positions(self) -> list[PositionReport]:
        raise ChannelUnavailable("broker_api not configured")
