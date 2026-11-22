"""交易进程装配：writer store + gateway + relay/consumer/heartbeat 三守护线程（D20）。"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path

from services.bus import InMemoryBus, InMemoryBusAdapter, SyncRedisBus
from services.outbox_relay import ConsumerLoop, RelayLoop


@dataclass
class WorkerComponents:
    store: object
    gateway: object
    relay: RelayLoop
    consumer: ConsumerLoop
    bus: object


def write_heartbeat(bus, key: str, value: str, ttl: int) -> None:
    """心跳走 Redis TTL，不落 SQLite（D20/F-D2）。"""
    bus.set_key(key, value, ttl)


def assemble(
    *,
    gateway,
    store,
    bus=None,
    metrics=None,
    batch: int = 100,
    poll_interval: float = 0.2,
) -> WorkerComponents:
    """装配 relay/consumer（F-A4）：gateway.start() 由调用方先执行（写 recovery/initial_cash meta）。"""
    if bus is None:
        bus = InMemoryBusAdapter(InMemoryBus())
    relay = RelayLoop(store, bus, batch=batch, poll_interval=poll_interval, metrics=metrics)
    consumer = ConsumerLoop(store, bus, metrics=metrics)
    return WorkerComponents(store=store, gateway=gateway, relay=relay, consumer=consumer, bus=bus)


def start_threads(components: WorkerComponents) -> list[threading.Thread]:
    threads = [
        threading.Thread(target=components.relay.run, name="p054-relay", daemon=True),
    ]
    for thread in threads:
        thread.start()
    return threads


def main() -> None:  # pragma: no cover - 进程入口（env 直读，无 api_key 依赖，F-A3）
    import time as _time

    from core.event_log import EventLog
    from live.adapters.terminal import TerminalChannelAdapter
    from live.gateway import TradingGateway
    from live.ledger import Ledger
    from live.ledger_store import SqliteLedgerStore

    sqlite_path = os.environ.get("P054_SQLITE_PATH", "live_ledger.db")
    store = SqliteLedgerStore(sqlite_path)
    event_log = EventLog(log_path="events.jsonl")
    adapter = TerminalChannelAdapter(
        os.environ.get("P054_ORDER_CSV", "orders.csv"),
        event_log=event_log,
        ts_provider=_time.time,
    )
    gateway = TradingGateway(
        adapter=adapter,
        gate=_build_gate(event_log),
        ledger=Ledger(store=store, initial_cash=100_000.0),
        store=store,
        event_log=event_log,
    )
    gateway.start()
    components = assemble(
        gateway=gateway,
        store=store,
        bus=SyncRedisBus(os.environ.get("P054_REDIS_URL", "redis://127.0.0.1:6379/0")),
    )
    start_threads(components)
    try:
        while True:
            gateway.poll()
    finally:
        gateway.shutdown()


def _build_gate(event_log):  # pragma: no cover - 进程装配辅助
    from core.circuit_breaker import CircuitConfig
    from core.compliance import RateLimitConfig
    from core.guard_pipeline import GuardPipeline
    from core.safety import default_fault_policy
    from live.safety_gate import SafetyGate
    from live.safety_store import SafetyStateStore

    return SafetyGate(
        event_log=event_log,
        store=SafetyStateStore(Path("safety_state.json")),
        rate_config=RateLimitConfig(max_per_second=0, max_per_day=0),
        circuit_config=CircuitConfig(),
        fault_policy=default_fault_policy(),
        pipeline=GuardPipeline([]),
    )


class Heartbeat:
    def __init__(self, bus, *, interval: float = 1.0, ttl: int = 10) -> None:
        self._bus = bus
        self._interval = interval
        self._ttl = ttl
        self._stop = threading.Event()

    def beat_once(self, *, key: str = "p054:trading:heartbeat", value: str = "ok") -> None:
        self._bus.set_key(key, value, self._ttl)

    def run(self) -> None:  # pragma: no cover - 线程循环
        while not self._stop.wait(self._interval):
            self.beat_once()

    def stop(self) -> None:
        self._stop.set()
