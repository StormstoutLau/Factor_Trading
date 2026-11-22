"""P-054 J 组：FakeBus 单进程全链 / 快照重放 / 双 worker / 重连（6 例）。"""

from __future__ import annotations

import pytest

from core.circuit_breaker import CircuitConfig
from core.compliance import RateLimitConfig
from core.event_log import EventLog
from core.execution_policy import OrderIntent
from core.guard_pipeline import GuardContext, GuardPipeline
from core.safety import default_fault_policy
from live.adapters.mock import FakeTransport, MockChannelAdapter
from live.events import OutboxEventType
from live.gateway import TradingGateway
from live.ledger import Ledger
from live.ledger_store import SqliteLedgerStore
from live.orders import OrderRequest
from live.safety_gate import SafetyGate
from live.safety_store import SafetyStateStore
from scripts.p054_bench_ws import sample_segments
from services.bus import InMemoryBus, InMemoryBusAdapter
from services.contracts import ServiceError
from services.outbox_relay import ConsumerLoop, RelayLoop
from services.ws_hub import ConnectionHub

DAY = 1_700_000_000.0


def _build(tmp_path):
    log = EventLog(log_path=tmp_path / "events.jsonl")
    gate = SafetyGate(
        event_log=log,
        store=SafetyStateStore(tmp_path / "state.json"),
        rate_config=RateLimitConfig(max_per_second=0, max_per_day=0),
        circuit_config=CircuitConfig(),
        fault_policy=default_fault_policy(),
        pipeline=GuardPipeline([]),
    )
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    ledger = Ledger(initial_cash=100_000.0)
    ledger.attach_store(store)
    adapter = MockChannelAdapter(FakeTransport())
    gateway = TradingGateway(
        adapter=adapter,
        gate=gate,
        ledger=ledger,
        store=store,
        event_log=log,
        clock=lambda: DAY,
        rate_config=RateLimitConfig(max_per_second=0, max_per_day=0),
    )
    bus = InMemoryBus()
    stream = InMemoryBusAdapter(bus)
    relay = RelayLoop(store, stream, sleep=lambda _s: None)
    consumer = ConsumerLoop(store, stream)
    hub = ConnectionHub()
    return gateway, store, bus, relay, consumer, hub


def _submit(gateway, *, ts: float = DAY):
    intent = OrderIntent(asset="AAA", asset_type="stock", target_quantity=100, current_quantity=0)
    request = OrderRequest(
        asset="AAA",
        side="BUY",
        quantity=100.0,
        asset_type="stock",
        price=10.0,
        order_type="limit",
        account_id="ACC",
        strategy_id="S1",
        signal_ts=DAY,
    )
    ctx = GuardContext(
        action="BUY",
        symbol="AAA",
        quantity=100.0,
        price=10.0,
        order_value=1000.0,
        current_positions={},
        current_weights={},
        portfolio_value=100_000.0,
        cash=100_000.0,
    )
    return gateway.submit(intent, request, ctx, account_id="ACC", strategy_id="S1", ts=ts)


def test_j1_fakebus_full_chain(tmp_path):
    gateway, store, bus, relay, consumer, hub = _build(tmp_path)
    store.set_meta("recovery_state", "complete")
    conn = hub.register()
    queue = bus.subscribe("p054:orders:events")
    _submit(gateway)
    assert relay.run_once() == 1
    assert consumer.run_once() == 1
    frame = queue.popleft()
    hub.broadcast_orders(frame["seq"], frame["event"])
    delta = conn.next_frame()
    assert delta["type"] == "delta" and delta["seq"] == 1
    assert delta["events"][0]["type"] == OutboxEventType.ORDER_ACCEPTED
    store.close()


def test_j2_snapshot_plus_delta_replay_equivalent(tmp_path):
    gateway, store, bus, relay, consumer, hub = _build(tmp_path)
    store.set_meta("recovery_state", "complete")
    _submit(gateway)
    snapshot = hub.snapshot(store)
    assert snapshot["seq"] == store.max_outbox_seq()
    events = store.outbox_after(0, 10)
    assert [e.seq for e in events] == list(range(1, snapshot["seq"] + 1))
    store.close()


def test_j3_dual_workers_receive_same_seq(tmp_path):
    gateway, store, bus, relay, consumer, hub = _build(tmp_path)
    store.set_meta("recovery_state", "complete")
    first, second = hub.register(), hub.register()
    hub.broadcast_orders(7, {"type": "order.status"})
    assert first.next_frame()["seq"] == second.next_frame()["seq"] == 7
    store.close()


def test_j4_reconnect_gets_fresh_snapshot(tmp_path):
    gateway, store, bus, relay, consumer, hub = _build(tmp_path)
    store.set_meta("recovery_state", "complete")
    store.set_meta("initial_cash", "100000.0")  # F-A1：writer 侧落 meta（gateway.start 同款）
    _submit(gateway)
    conn = hub.register()
    snapshot, _pending = hub.snapshot_and_stream(store, conn)
    assert len(snapshot["orders"]) == 1
    assert snapshot["orders"][0]["client_order_id"].startswith("co_")
    # 快照现金 = initial − Σ(amount+fee)：买入预留未结算 → cash 不变（reserve 不入 entries）
    assert snapshot["account"]["cash"] == pytest.approx(100_000.0)
    store.close()


def test_j5_not_ready_path(tmp_path):
    gateway, store, bus, relay, consumer, hub = _build(tmp_path)
    with pytest.raises(ServiceError):
        hub.ensure_ready(store)
    store.close()


def test_j6_latency_segments_sample(tmp_path):
    result = sample_segments(20)
    assert result["n"] == 20
    for key in ("append_to_enqueue", "enqueue_to_send", "end_to_end"):
        assert set(result[key]) == {"p50", "p95", "p99"}
