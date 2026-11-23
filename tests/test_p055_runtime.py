"""P-055 T1：运行时长跑 / 心跳值 / 停机 / relay+consumer 循环（8 例）。"""

from __future__ import annotations

import signal
import threading
import time
from types import SimpleNamespace

import services.bus as bus_mod
from live.events import OutboxEventType, order_event
from live.ledger_store import SqliteLedgerStore
from live.orders import OrderRequest, from_request
from services.trading_worker import (
    Heartbeat,
    WorkerComponents,
    assemble,
    install_stop_handlers,
    shutdown,
)


class _RecordingBus:
    def __init__(self) -> None:
        self.keys: dict[str, str] = {}
        self.pending = 0

    def set_key(self, key: str, value: str, ttl: int) -> None:
        del ttl
        self.keys[key] = value

    def get_key(self, key: str) -> str | None:
        return self.keys.get(key)

    def publish(self, channel: str, message: dict) -> None:
        del channel, message

    def read(self, *, consumer: str, count: int = 10, block_ms: int = 1000):
        del consumer, count, block_ms
        return []

    def ack(self, message_id: str) -> None:
        del message_id

    def autoclaim(self, *, consumer: str, idle_ms: int, count: int):
        del consumer, idle_ms, count
        return []

    def stream_pending(self, consumer: str) -> int:
        del consumer
        return self.pending


def _store_with_event(tmp_path) -> SqliteLedgerStore:
    store = SqliteLedgerStore(tmp_path / "ledger.db")
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


def test_install_stop_handlers_sets_event():
    old_int = signal.getsignal(signal.SIGINT)
    old_term = signal.getsignal(signal.SIGTERM)
    stop_event = threading.Event()
    try:
        install_stop_handlers(stop_event)
        handler = signal.getsignal(signal.SIGINT)
        assert callable(handler)
        handler(signal.SIGINT, None)  # 直接调用注册的 handler，不 os.kill
        assert stop_event.is_set()
    finally:
        signal.signal(signal.SIGINT, old_int)
        signal.signal(signal.SIGTERM, old_term)


def test_heartbeat_value_parseable_by_reader(monkeypatch):
    from services.api_worker import build_heartbeat_reader

    backing = _RecordingBus()
    monkeypatch.setattr(bus_mod, "SyncRedisBus", lambda _url: backing, raising=True)
    settings = SimpleNamespace(redis_url="redis://unused:6379/0", ready_staleness_seconds=3.0)
    reader = build_heartbeat_reader(settings)
    heartbeat = Heartbeat(backing, value_provider=lambda: "1700000000:3")
    heartbeat.beat_once()
    # 固定旧时间戳 → 相对 now 必 stale
    assert reader()["trading"] is False
    backing.set_key("p054:trading:heartbeat", f"{int(time.time())}:3", 10)
    assert reader()["trading"] is True


def test_shutdown_calls_heartbeat_stop():
    order: list[str] = []

    class _Heartbeat:
        def stop(self) -> None:
            order.append("heartbeat")

    class _Thread:
        def join(self, timeout=None) -> None:
            order.append(f"join:{timeout}")

    class _Gateway:
        def shutdown(self) -> None:
            order.append("gateway")

    stop_event = threading.Event()
    shutdown(
        WorkerComponents(store=object(), gateway=object(), relay=None, consumer=None, bus=None),
        stop_event=stop_event,
        heartbeat=_Heartbeat(),
        threads=[_Thread()],
        gateway=_Gateway(),
    )
    assert stop_event.is_set()
    assert order == ["heartbeat", "join:5.0", "gateway"]


def test_relay_loop_respects_stop_event(tmp_path):
    store = _store_with_event(tmp_path)

    class _Publisher:
        def add(self, message) -> str:
            return "1-0"

    from services.outbox_relay import RelayLoop

    relay = RelayLoop(store, _Publisher(), sleep=lambda _s: None)
    stop_event = threading.Event()
    thread = threading.Thread(target=relay.run, args=(stop_event,), daemon=True)
    thread.start()
    stop_event.set()
    thread.join(timeout=5.0)
    assert not thread.is_alive()


def test_consumer_run_writes_pending():
    from services.outbox_relay import ConsumerLoop

    bus = _RecordingBus()
    bus.pending = 7
    loop = ConsumerLoop(object(), bus)
    stop_event = threading.Event()
    thread = threading.Thread(target=loop.run, args=(stop_event,), daemon=True)
    thread.start()
    deadline = time.time() + 5.0
    while time.time() < deadline and "p054:consumer:heartbeat" not in bus.keys:
        time.sleep(0.01)
    stop_event.set()
    thread.join(timeout=5.0)
    assert bus.keys["p054:consumer:heartbeat"].endswith(":7")


def test_consumer_run_does_not_busy_loop():
    from services.outbox_relay import ConsumerLoop

    waits: list[float] = []

    class _Stop:
        def __init__(self) -> None:
            self._set = False

        def is_set(self) -> bool:
            return self._set

        def wait(self, timeout: float | None = None) -> bool:
            waits.append(float(timeout or 0.0))
            self._set = True  # 第一次节流后退出
            return True

    loop = ConsumerLoop(object(), _RecordingBus())
    loop.run(_Stop(), poll_interval=0.2, sleep=lambda s: waits.append(float(s)))
    assert waits and waits[0] > 0


def test_fake_bus_assembly(tmp_path):
    from services.bus import InMemoryBus, InMemoryBusAdapter

    components = assemble(gateway=object(), store=object(), bus=InMemoryBusAdapter(InMemoryBus()))
    assert isinstance(components, WorkerComponents)
    assert components.consumer is not None and components.relay is not None
    # --bus fake 不触网：装配阶段无 Redis 连接
    assert hasattr(components.bus, "stream_pending")


def test_sync_redis_bus_adapter_shape_with_real_redis(tmp_path):
    """Step 10 实跑修正回归：SyncRedisBus 必须满足 relay/consumer 的 adapter 形状。

    端到端：relay XADD → consumer XREADGROUP → Pub/Sub 扇出 → ack → 不重投。
    需真实 Redis（设 ``P054_TEST_REDIS_URL``）；CI 无该变量时跳过。
    """
    import json
    import os

    import pytest

    url = os.environ.get("P054_TEST_REDIS_URL")
    if not url:
        pytest.skip("需要 P054_TEST_REDIS_URL（真实 Redis 集成测试）")
    from services.bus import SyncRedisBus
    from services.outbox_relay import ConsumerLoop, RelayLoop

    channel = "p055:it:orders:events"
    bus = SyncRedisBus(url)
    bus.delete_key("p054:orders")  # 起跑复位：组游标残留会把旧条目当新事件（Step 10 教训）
    bus.delete_key(channel)
    store = SqliteLedgerStore(tmp_path / "it_ledger.db")
    store.set_meta("recovery_state", "complete")
    try:
        for i in range(3):
            request = OrderRequest(
                asset="600000.SH",
                side="BUY",
                quantity=100.0,
                price=10.0,
                client_order_id=f"it-{i}",
                account_id="ACC",
                strategy_id="S1",
                signal_ts=float(i),
            )
            record = from_request(request, ts=1.0)
            store.upsert_order_with_events(
                record,
                [order_event(record, OutboxEventType.ORDER_ACCEPTED, version=1, ts=1.0)],
            )
        assert RelayLoop(store, bus, batch=10).run_once() == 3

        pubsub = bus.subscribe(channel)  # 先订阅后消费（Pub/Sub 无保留）
        consumer = ConsumerLoop(store, bus, channel=channel)
        assert consumer.run_once(count=10) == 3
        seqs: list[int] = []  # 首帧为 subscribe 确认（忽略后返回 None），循环读满 3 条
        deadline = time.monotonic() + 5.0
        while len(seqs) < 3 and time.monotonic() < deadline:
            message = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message:
                seqs.append(int(json.loads(message["data"])["seq"]))
        assert sorted(seqs) == [1, 2, 3]
        assert consumer.run_once(count=10) == 0  # 已 ack，XREADGROUP ">" 不重投
        # Step 10 实跑修正回归：autoclaim 路径（Redis 7 三元素响应，空 PEL → 0）
        assert consumer.run_once(count=10, autoclaim=True) == 0
    finally:
        try:
            bus.delete_key("p054:orders")
            bus.delete_key(channel)
        finally:
            bus.close()
            store.close()
