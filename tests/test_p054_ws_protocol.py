"""P-054 G 组：WS snapshot/delta / seq / 背压 / 心跳 / 就绪（16 例）。"""

from __future__ import annotations

import pytest

from live.events import OutboxEvent, OutboxEventType, order_event
from live.ledger_store import SqliteLedgerStore
from live.orders import OrderRequest, from_request
from services.contracts import ErrorCode, ServiceError
from services.ws_hub import ConnectionHub


def _store(tmp_path, *, state: str = "complete") -> SqliteLedgerStore:
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    store.set_meta("recovery_state", state)
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


def test_g1_snapshot_frame_shape(tmp_path):
    store = _store(tmp_path)
    hub = ConnectionHub()
    frame = hub.snapshot(store)
    assert frame["type"] == "snapshot"
    assert {"seq", "orders", "positions", "account", "recovery_state"} <= set(frame)
    store.close()


def test_g2_snapshot_seq_is_watermark(tmp_path):
    store = _store(tmp_path)
    hub = ConnectionHub()
    assert hub.snapshot(store)["seq"] == store.max_outbox_seq()
    store.close()


def test_g3_register_returns_empty_connection():
    hub = ConnectionHub()
    conn = hub.register()
    assert list(conn.orders_q) == [] and conn.last_seq == 0
    hub.unregister(conn)
    assert hub.connections == []


def test_g4_order_delta_in_order(tmp_path):
    hub = ConnectionHub()
    conn = hub.register()
    hub.broadcast_orders(1, {"type": "order.accepted"})
    hub.broadcast_orders(2, {"type": "fill.applied"})
    assert [f["seq"] for f in conn.orders_q] == [1, 2]


def test_g5_duplicate_seq_deduped():
    hub = ConnectionHub()
    conn = hub.register()
    hub.broadcast_orders(5, {"type": "order.status"})
    hub.broadcast_orders(5, {"type": "order.status"})
    assert len(conn.orders_q) == 1


def test_g6_dedupe_is_per_connection():
    hub = ConnectionHub()
    first, second = hub.register(), hub.register()
    hub.broadcast_orders(1, {"type": "order.accepted"})
    hub.broadcast_orders(3, {"type": "fill.applied"})
    assert [f["seq"] for f in first.orders_q] == [1, 3]
    assert [f["seq"] for f in second.orders_q] == [1, 3]


def test_g7_register_snapshot_filter_no_loss(tmp_path):
    store = _store(tmp_path)
    hub = ConnectionHub()
    conn = hub.register()
    hub.broadcast_orders(store.max_outbox_seq() + 1, {"type": "fill.applied"})
    snapshot, pending = hub.snapshot_and_stream(store, conn, resume_last_seq=0)
    assert snapshot["seq"] == store.max_outbox_seq()
    assert [f["seq"] for f in pending] == [store.max_outbox_seq() + 1]
    store.close()


def test_g8_slow_consumer_closes_1013():
    hub = ConnectionHub(orders_max=1, slow_seconds=5.0, clock=lambda: 0.0)
    conn = hub.register()
    hub.broadcast_orders(1, {"type": "a"}, now=0.0)
    hub.broadcast_orders(2, {"type": "b"}, now=0.0)
    hub.broadcast_orders(3, {"type": "c"}, now=6.0)
    assert conn.closed is True
    assert conn.orders_q[-1]["code"] == ErrorCode.SLOW_CONSUMER
    assert conn.close_code == 1013


def test_g9_full_queue_does_not_drop_existing_frames():
    hub = ConnectionHub(orders_max=2, slow_seconds=5.0, clock=lambda: 0.0)
    conn = hub.register()
    hub.broadcast_orders(1, {"type": "a"}, now=0.0)
    hub.broadcast_orders(2, {"type": "b"}, now=0.0)
    delivered = hub.broadcast_orders(3, {"type": "c"}, now=1.0)
    assert delivered == 0
    assert [f["seq"] for f in conn.orders_q] == [1, 2]


def test_g10_market_drop_oldest():
    hub = ConnectionHub(market_max=2)
    conn = hub.register()
    hub.broadcast_market({"symbol": "A", "last": 1.0})
    hub.set_paused(True)  # F-I9：broadcast-pause 只停行情（F-A2）
    assert hub.broadcast_market({"symbol": "X", "last": 0.0}) == 0
    hub.set_paused(False)
    hub.broadcast_market({"symbol": "B", "last": 2.0})
    hub.broadcast_market({"symbol": "C", "last": 3.0})
    assert [t["symbol"] for t in conn.market_q] == ["B", "C"]


def test_g11_market_merge_same_symbol():
    hub = ConnectionHub(market_max=2)
    conn = hub.register()
    hub.broadcast_market({"symbol": "A", "last": 1.0})
    hub.broadcast_market({"symbol": "B", "last": 2.0})
    hub.broadcast_market({"symbol": "A", "last": 9.0})
    latest = [t for t in conn.market_q if t["symbol"] == "A"][-1]
    assert latest["last"] == 9.0


def test_g12_heartbeat_ping_then_close():
    hub = ConnectionHub(clock=lambda: 0.0)
    conn = hub.register()
    assert hub.heartbeat(conn, now=10.0) == "idle"
    assert hub.heartbeat(conn, now=16.0) == "ping"
    assert hub.heartbeat(conn, now=31.0) == "close"
    assert conn.close_code == 1011


def test_g13_resume_echo_and_stale_snapshot(tmp_path):
    store = _store(tmp_path)
    hub = ConnectionHub()
    conn = hub.register()
    snapshot, pending = hub.snapshot_and_stream(store, conn, resume_last_seq=1)
    assert snapshot["resumed_from"] == 1 and pending == []
    snapshot2, errors = hub.snapshot_and_stream(
        store, conn, resume_last_seq=store.max_outbox_seq() + 5
    )
    assert snapshot2["resumed_from"] == store.max_outbox_seq() + 5
    assert errors[0]["code"] == "stale_snapshot"
    store.close()


def test_g14_ensure_ready_rejects_incomplete(tmp_path):
    store = _store(tmp_path, state="incomplete")
    hub = ConnectionHub()
    with pytest.raises(ServiceError) as exc:
        hub.ensure_ready(store)
    assert exc.value.code == ErrorCode.NOT_READY
    store.close()


def test_g15_error_codes_constants():
    assert ErrorCode.NOT_READY == "not_ready"
    assert ErrorCode.AUTH_FAILED == "auth_failed"
    assert ErrorCode.SLOW_CONSUMER == "slow_consumer"
    assert ErrorCode.QUEUE_OVERFLOW == "queue_overflow"


def test_g16_close_frame_shape():
    hub = ConnectionHub(orders_max=1, slow_seconds=1.0, clock=lambda: 0.0)
    conn = hub.register()
    hub.broadcast_orders(1, {"type": "a"}, now=0.0)
    hub.broadcast_orders(2, {"type": "b"}, now=0.0)
    hub.broadcast_orders(3, {"type": "c"}, now=2.0)
    conn.orders_q.popleft()
    frame = conn.next_frame()
    assert frame == {"type": "error", "code": "slow_consumer", "message": "order consumer too slow"}
    close = conn.next_frame()
    assert close == {"type": "close", "code": 1013}
