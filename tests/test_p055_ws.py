"""P-055 T2：WS 挂载协议（snapshot / 4401 / 4503 / 1013 / market 包装，5 例）。"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from starlette.websockets import WebSocketDisconnect

from live.events import OutboxEventType, order_event
from live.ledger_store import SqliteLedgerStore
from live.orders import OrderRequest, from_request
from services.api import create_app
from services.auth import InMemoryTicketStore
from services.config import ServiceSettings
from services.ws_hub import ConnectionHub

READER = "reader-key-1234567890"


class _FakePubSub:
    async def listen(self):
        while True:
            await asyncio.sleep(0.05)
            if False:  # pragma: no cover - 保持 async generator 语义
                yield {}

    async def aclose(self) -> None:
        return None


class FakeAsyncBus:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict]] = []
        self.closed = False

    async def subscribe(self, channel: str):
        del channel
        return _FakePubSub()

    async def publish(self, channel: str, message: dict) -> None:
        self.published.append((channel, message))

    async def close(self) -> None:
        self.closed = True


def _seed(tmp_path, *, complete: bool = True) -> SqliteLedgerStore:
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    if complete:
        store.set_meta("recovery_state", "complete")
        request = OrderRequest(
            asset="AAA",
            side="BUY",
            quantity=100.0,
            price=10.0,
            client_order_id="co1",
            account_id="ACC",
            strategy_id="S1",
            signal_ts=1.0,
        )
        record = from_request(request, ts=1.0)
        store.upsert_order_with_events(
            record, [order_event(record, OutboxEventType.ORDER_ACCEPTED, version=1, ts=1.0)]
        )
    return store


def _app(tmp_path, *, store=None, orders_max: int = 1000, slow_seconds: float = 5.0):
    store = store or _seed(tmp_path)
    settings = ServiceSettings(sqlite_path=tmp_path / "ledger.db", api_key=SecretStr(READER))
    tickets = InMemoryTicketStore()
    bus = FakeAsyncBus()
    app = create_app(
        settings=settings,
        store=store,
        ticket_store=tickets,
        orders_hub=ConnectionHub(orders_max=orders_max, slow_seconds=slow_seconds),
        market_hub=ConnectionHub(orders_max=orders_max, slow_seconds=slow_seconds),
        bus=bus,
    )
    return app, tickets, bus


def test_snapshot_first_frame(tmp_path):
    app, tickets, _ = _app(tmp_path)
    tickets.issue("t1", 60)
    with TestClient(app) as client:
        with client.websocket_connect("/ws/orders?ticket=t1&resume_last_seq=0") as ws:
            frame = ws.receive_json()
            assert frame["type"] == "snapshot"
            assert frame["seq"] >= 0
            assert frame["recovery_state"] == "complete"


def test_missing_ticket_4401(tmp_path):
    app, _, _ = _app(tmp_path)
    with TestClient(app) as client:
        with client.websocket_connect("/ws/orders") as ws:
            error = ws.receive_json()
            assert error["type"] == "error"
            assert error["code"] == "auth_failed"
            with pytest.raises(WebSocketDisconnect) as exc:
                ws.receive_json()
            assert exc.value.code == 4401


def test_not_ready_4503(tmp_path):
    store = _seed(tmp_path, complete=False)
    app, tickets, _ = _app(tmp_path, store=store)
    tickets.issue("t2", 60)
    with TestClient(app) as client:
        with client.websocket_connect("/ws/orders?ticket=t2") as ws:
            error = ws.receive_json()
            assert error["code"] == "not_ready"
            with pytest.raises(WebSocketDisconnect) as exc:
                ws.receive_json()
            assert exc.value.code == 4503


def test_slow_consumer_1013(tmp_path):
    app, tickets, _ = _app(tmp_path, orders_max=1, slow_seconds=0.0)
    tickets.issue("t3", 60)
    hub = app.state.orders_hub
    with TestClient(app) as client:
        with client.websocket_connect("/ws/orders?ticket=t3") as ws:
            assert ws.receive_json()["type"] == "snapshot"
            hub.broadcast_orders(1, {"event_id": "e1"})
            hub.broadcast_orders(2, {"event_id": "e2"})
            frames = []
            with pytest.raises(WebSocketDisconnect) as exc:
                while True:
                    frames.append(ws.receive_json())
            assert exc.value.code == 1013
            assert any(f.get("code") == "slow_consumer" for f in frames)


def test_market_frame_wrapped(tmp_path):
    app, tickets, _ = _app(tmp_path)
    tickets.issue("t4", 60)
    hub = app.state.market_hub
    with TestClient(app) as client:
        with client.websocket_connect("/ws/market?ticket=t4") as ws:
            hub.broadcast_market({"symbol": "600000.SH", "last": 10.5, "ts": 1.0})
            frame = ws.receive_json()
            assert frame["type"] == "market"
            assert frame["tick"]["symbol"] == "600000.SH"
