"""P-054 H 组：relay 顺序 / mark_sent / 重投 / inbox / XACK / 扇出 / 退避（12 例）。"""

from __future__ import annotations

import pytest

from live.events import OutboxEvent
from live.ledger_store import SqliteLedgerStore
from services.bus import InMemoryBus, InMemoryBusAdapter
from services.contracts import StreamMessage
from services.metrics import get_metrics
from services.outbox_relay import ConsumerLoop, PublisherFailure, RelayLoop


def _event(eid: str = "ev1") -> OutboxEvent:
    return OutboxEvent(
        event_id=eid,
        aggregate_type="order",
        aggregate_id="co1",
        event_type="order.accepted",
        payload='{"a":1}',
        created_ts=1.0,
    )


class RecordingPublisher:
    def __init__(self) -> None:
        self.added: list[StreamMessage] = []

    def add(self, message: StreamMessage) -> str:
        self.added.append(message)
        return f"{message.seq}-0"


class FailingPublisher:
    def __init__(self, failures: int = 1) -> None:
        self.failures = failures
        self.added: list[StreamMessage] = []

    def add(self, message: StreamMessage) -> str:
        if self.failures > 0:
            self.failures -= 1
            raise RuntimeError("redis down")
        self.added.append(message)
        return f"{message.seq}-0"


def _store(tmp_path) -> SqliteLedgerStore:
    return SqliteLedgerStore(tmp_path / "ledger.db")


def test_h1_relay_preserves_seq_order(tmp_path):
    store = _store(tmp_path)
    store.append_outbox([_event("ev1"), _event("ev2"), _event("ev3")])
    publisher = RecordingPublisher()
    relay = RelayLoop(store, publisher, sleep=lambda _s: None)
    assert relay.run_once() == 3
    assert [m.seq for m in publisher.added] == [1, 2, 3]
    store.close()


def test_h2_failure_keeps_sent_zero(tmp_path):
    store = _store(tmp_path)
    store.append_outbox([_event("ev1")])
    relay = RelayLoop(store, FailingPublisher(1), sleep=lambda _s: None)
    with pytest.raises(PublisherFailure):
        relay.run_once()
    assert len(store.pending_outbox()) == 1
    store.close()


def test_h3_crash_redelivery(tmp_path):
    store = _store(tmp_path)
    store.append_outbox([_event("ev1")])
    relay = RelayLoop(store, FailingPublisher(1), sleep=lambda _s: None)
    with pytest.raises(PublisherFailure):
        relay.run_once()
    good = RecordingPublisher()
    assert RelayLoop(store, good, sleep=lambda _s: None).run_once() == 1
    assert [m.event_id for m in good.added] == ["ev1"]
    assert store.pending_outbox() == []
    store.close()


def test_h4_inbox_dedup(tmp_path):
    store = _store(tmp_path)
    bus = InMemoryBus()
    adapter = InMemoryBusAdapter(bus)
    adapter.add(
        StreamMessage(seq=1, event_id="ev1", event_type="order.accepted", payload='{"a":1}')
    )
    store.mark_inbox("ev1", 1.0)
    consumer = ConsumerLoop(store, adapter)
    assert consumer.run_once() == 0
    assert bus.stream_pending("trading-1") == 0
    store.close()


def test_h5_ack_after_publish(tmp_path):
    store = _store(tmp_path)
    bus = InMemoryBus()
    adapter = InMemoryBusAdapter(bus)
    adapter.add(
        StreamMessage(seq=1, event_id="ev1", event_type="order.accepted", payload='{"a":1}')
    )
    queue = bus.subscribe("p054:orders:events")
    assert ConsumerLoop(store, adapter).run_once() == 1
    assert len(queue) == 1 and queue[0]["seq"] == 1
    assert bus.stream_pending("trading-1") == 0
    store.close()


def test_h6_autoclaim_pending(tmp_path):
    store = _store(tmp_path)
    bus = InMemoryBus()
    adapter = InMemoryBusAdapter(bus)
    adapter.add(
        StreamMessage(seq=1, event_id="ev1", event_type="order.accepted", payload='{"a":1}')
    )
    messages = adapter.read(consumer="trading-1")
    assert len(messages) == 1
    claimed = adapter.autoclaim(consumer="trading-1", idle_ms=0, count=10)
    assert [m.event_id for m in claimed] == ["ev1"]
    store.close()


def test_h7_pubsub_fanout_all_workers():
    bus = InMemoryBus()
    first, second = bus.subscribe("p054:orders:events"), bus.subscribe("p054:orders:events")
    bus.publish("p054:orders:events", {"seq": 1})
    assert len(first) == 1 and len(second) == 1


def test_h8_redis_failure_backoff(tmp_path):
    store = _store(tmp_path)
    store.append_outbox([_event("ev1")])
    sleeps: list[float] = []
    relay = RelayLoop(store, FailingPublisher(2), sleep=sleeps.append)
    with pytest.raises(PublisherFailure):
        relay.run_once()
    with pytest.raises(PublisherFailure):
        relay.run_once()
    assert sleeps == [1.0, 2.0]
    store.close()


def test_h9_outbox_pending_metric(tmp_path):
    store = _store(tmp_path)
    store.append_outbox([_event("ev1")])
    metrics = get_metrics()
    RelayLoop(store, RecordingPublisher(), sleep=lambda _s: None, metrics=metrics).run_once()
    assert metrics.outbox_pending._value.get() == 0
    store.close()


def test_h10_empty_batch_sleeps_poll_interval(tmp_path):
    store = _store(tmp_path)
    sleeps: list[float] = []
    relay = RelayLoop(store, RecordingPublisher(), poll_interval=0.25, sleep=sleeps.append)

    def sleep_and_stop(seconds: float) -> None:
        sleeps.append(seconds)
        relay.stop = True

    relay._sleep = sleep_and_stop
    relay.run()
    assert sleeps == [0.25]
    store.close()


def test_h11_purge_once_retention(tmp_path):
    store = _store(tmp_path)
    old = OutboxEvent(
        event_id="old",
        aggregate_type="order",
        aggregate_id="co1",
        event_type="order.accepted",
        payload="p",
        created_ts=0.0,
    )
    store.append_outbox([old])
    seq = store.pending_outbox()[0].seq
    store.mark_sent(seq, 0.0)
    store.append_outbox([_event("new")])
    relay = RelayLoop(store, RecordingPublisher(), clock=lambda: 8 * 86_400, sleep=lambda _s: None)
    assert relay.purge_once(retention_days=7) == 1
    store.close()


def test_h12_consumer_pending_metric(tmp_path):
    store = _store(tmp_path)
    bus = InMemoryBus()
    adapter = InMemoryBusAdapter(bus)
    adapter.add(
        StreamMessage(seq=1, event_id="ev1", event_type="order.accepted", payload='{"a":1}')
    )
    metrics = get_metrics()
    ConsumerLoop(store, adapter, metrics=metrics).run_once()
    assert metrics.consumer_pending._value.get() == 0
    store.close()
