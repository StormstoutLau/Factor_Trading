from __future__ import annotations

import csv
from pathlib import Path

from core.event_log import EventType, IEventBus
from live.channel import (
    CapabilityError,
    ChannelAdapter,
    ChannelCapability,
    ChannelState,
    FillReport,
    OrderReport,
    PositionReport,
    SubmitAck,
)
from live.orders import OrderRequest, OrderState

_ORDER_COLUMNS = (
    "ts",
    "client_order_id",
    "asset",
    "side",
    "quantity",
    "price",
    "order_type",
    "strategy_id",
    "account_id",
    "remark",
)
_FILL_COLUMNS = (
    "fill_key",
    "client_order_id",
    "asset",
    "side",
    "quantity",
    "price",
    "fee",
    "ts",
)


class TerminalChannelAdapter(ChannelAdapter):
    def __init__(self, path: str | Path, *, event_log: IEventBus, ts_provider) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._event_log = event_log
        self._ts = ts_provider
        self.state = ChannelState.DISCONNECTED
        self.capability = ChannelCapability(
            channel_id="terminal",
            venue="terminal",
            account_level="cash",
            products=("stock",),
            supports_client_order_id=True,
            supports_cancel=False,
            supports_query_orders=False,
            supports_query_trades=False,
            supports_query_positions=False,
            autonomous=False,
            report_registered=False,
            max_submit_per_sec=1.0,
            max_submit_per_day=1000,
            max_cancel_per_sec=0.0,
            max_query_per_sec=0.0,
        )

    def connect(self) -> None:
        self.state = ChannelState.CONNECTED

    def disconnect(self) -> None:
        self.state = ChannelState.DISCONNECTED

    def submit(self, request: OrderRequest) -> SubmitAck:
        write_header = not self._path.exists() or self._path.stat().st_size == 0
        with self._path.open("a", newline="", encoding="utf-8-sig") as fp:
            writer = csv.writer(fp)
            if write_header:
                writer.writerow(_ORDER_COLUMNS)
            writer.writerow(
                [
                    f"{self._ts():.6f}",
                    request.client_order_id,
                    request.asset,
                    request.side,
                    f"{request.quantity:.6f}",
                    "" if request.price is None else f"{request.price:.6f}",
                    request.order_type,
                    request.strategy_id,
                    request.account_id,
                    request.remark,
                ]
            )
        self._event_log.append(
            EventType.AUDIT_ORDER,
            {
                "client_order_id": request.client_order_id,
                "action": "listed",
                "path": str(self._path),
            },
            source="live.adapters.terminal",
        )
        return SubmitAck(request.client_order_id, "", OrderState.PENDING_NEW, self._ts())

    def cancel(self, client_order_id: str) -> None:
        raise CapabilityError("missing: cancel")

    def query_orders(self, *, day: str) -> list[OrderReport]:
        raise CapabilityError("missing: query_orders")

    def query_trades(self, *, day: str) -> list[FillReport]:
        raise CapabilityError("missing: query_trades")

    def query_positions(self) -> list[PositionReport]:
        raise CapabilityError("missing: query_positions")

    def import_fills(self, path: str | Path) -> list[FillReport]:
        with Path(path).open(newline="", encoding="utf-8-sig") as fp:
            rows = list(csv.DictReader(fp))
        missing = [c for c in _FILL_COLUMNS if rows and c not in rows[0]]
        if missing:
            raise ValueError(f"fill csv missing columns: {missing}")
        return [
            FillReport(
                fill_key=row["fill_key"],
                client_order_id=row["client_order_id"],
                asset=row["asset"],
                side=row["side"],
                quantity=float(row["quantity"]),
                price=float(row["price"]),
                fee=float(row["fee"] or 0.0),
                ts=float(row["ts"]),
            )
            for row in rows
        ]
