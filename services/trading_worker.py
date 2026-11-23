"""交易进程装配：writer store + gateway + relay/consumer/heartbeat 三守护线程（D20）。"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
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


def install_stop_handlers(stop_event: threading.Event) -> None:
    """主线程注册停止信号：handler **只置位**，清理统一在 ``finally``（C-2/A11）。"""
    import signal

    def _handle(signum, frame):  # noqa: ANN001
        stop_event.set()

    for name in ("SIGINT", "SIGTERM"):
        sig = getattr(signal, name, None)
        if sig is not None:
            signal.signal(sig, _handle)
    sigbreak = getattr(signal, "SIGBREAK", None)  # 仅 Windows 存在
    if sigbreak is not None:
        signal.signal(sigbreak, _handle)


def start_threads(
    components: WorkerComponents,
    *,
    stop_event: threading.Event | None = None,
    heartbeat=None,
) -> list[threading.Thread]:
    """relay + consumer + heartbeat 三守护线程（G1）；heartbeat 缺省不启。"""
    threads = [
        threading.Thread(
            target=components.relay.run, args=(stop_event,), name="p054-relay", daemon=True
        ),
        threading.Thread(
            target=components.consumer.run, args=(stop_event,), name="p054-consumer", daemon=True
        ),
    ]
    if heartbeat is not None:
        threads.append(threading.Thread(target=heartbeat.run, name="p054-heartbeat", daemon=True))
    for thread in threads:
        thread.start()
    return threads


def _env_f(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


def _env_i(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _parse_args(argv=None):
    import argparse

    parser = argparse.ArgumentParser(prog="trading_worker")
    parser.add_argument("--bus", choices=("redis", "fake"), default="redis")
    parser.add_argument("--with-market", action="store_true", dest="with_market")
    parser.add_argument("--once", action="store_true")
    return parser.parse_args(argv)


def _log(event: str, **fields) -> None:
    print(
        json.dumps(
            {"ts": time.time(), "event": event, **fields}, ensure_ascii=False, sort_keys=True
        ),
        file=sys.stderr,
        flush=True,
    )


def _safe_patrol(gateway) -> None:  # pragma: no cover - 需真实 gateway
    try:
        gateway.reconcile(ts=time.time(), nav=0.0)
    except Exception as exc:  # 巡检失败不得杀主循环（DESIGN §2.6.1 要点 3）
        _log("patrol_failed", error=repr(exc))


def run_main_loop(
    gateway,
    *,
    stop_event: threading.Event,
    once: bool = False,
    poll_seconds: float = 0.2,
    patrol_seconds: float = 6.0,
) -> None:
    """主循环：``stop_event.wait`` 非忙等（G4/D11）+ 周期巡检。"""
    next_patrol = time.monotonic() + patrol_seconds
    while not stop_event.is_set():
        gateway.poll()
        if time.monotonic() >= next_patrol:
            _safe_patrol(gateway)
            next_patrol = time.monotonic() + patrol_seconds
        if once:
            return
        stop_event.wait(poll_seconds)


def shutdown(
    components: WorkerComponents,
    *,
    stop_event: threading.Event,
    heartbeat,
    threads,
    gateway,
) -> None:
    """固定收尾顺序（C-4/F-D6）：置位 → 停心跳 → join → gateway.shutdown。"""
    stop_event.set()
    heartbeat.stop()
    for thread in threads:
        thread.join(timeout=5.0)
    gateway.shutdown()


def main(argv=None) -> None:  # pragma: no cover - 进程入口（env 直读，无 api_key 依赖，F-A3）
    from core.event_log import EventLog
    from live.adapters.terminal import TerminalChannelAdapter
    from live.gateway import TradingGateway
    from live.ledger import Ledger
    from live.ledger_store import SqliteLedgerStore
    from live.query_scheduler import QueryScheduler

    args = _parse_args(argv)
    stop_event = threading.Event()
    install_stop_handlers(stop_event)

    sqlite_path = os.environ.get("P054_SQLITE_PATH", "live_ledger.db")
    store = SqliteLedgerStore(sqlite_path)
    event_log = EventLog(log_path="events.jsonl")
    adapter = TerminalChannelAdapter(
        os.environ.get("P054_ORDER_CSV", "orders.csv"),
        event_log=event_log,
        ts_provider=time.time,
    )
    gateway = TradingGateway(
        adapter=adapter,
        gate=_build_gate(event_log),
        ledger=Ledger(store=store, initial_cash=100_000.0),
        store=store,
        event_log=event_log,
        scheduler=QueryScheduler(),  # 巡检与启动恢复共用（DESIGN §2.6.1 要点 3）
    )
    gateway.start()
    bus = (
        InMemoryBusAdapter(InMemoryBus())
        if args.bus == "fake"
        else SyncRedisBus(os.environ.get("P054_REDIS_URL", "redis://127.0.0.1:6379/0"))
    )
    components = assemble(
        gateway=gateway,
        store=store,
        bus=bus,
        batch=_env_i("P054_OUTBOX_BATCH_SIZE", 100),
        poll_interval=_env_f("P054_OUTBOX_POLL_INTERVAL_SECONDS", 0.2),
    )
    heartbeat = Heartbeat(
        bus,
        interval=_env_f("P054_HEARTBEAT_INTERVAL_SECONDS", 1.0),
        ttl=_env_i("P054_HEARTBEAT_TTL_SECONDS", 10),
        value_provider=lambda: f"{int(time.time())}:{components.relay.last_unsent}",
    )
    threads = start_threads(components, stop_event=stop_event, heartbeat=heartbeat)
    if args.with_market:
        from services.market_gateway import run_embedded

        market_thread = threading.Thread(
            target=run_embedded, args=(stop_event,), name="p054-market", daemon=True
        )
        market_thread.start()
        threads.append(market_thread)
    try:
        run_main_loop(
            gateway,
            stop_event=stop_event,
            once=args.once,
            poll_seconds=_env_f("P054_POLL_SECONDS", 0.2),
            patrol_seconds=_env_f("P054_PATROL_SECONDS", 6.0),
        )
    finally:
        shutdown(
            components,
            stop_event=stop_event,
            heartbeat=heartbeat,
            threads=threads,
            gateway=gateway,
        )


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
    def __init__(self, bus, *, interval: float = 1.0, ttl: int = 10, value_provider=None) -> None:
        self._bus = bus
        self._interval = interval
        self._ttl = ttl
        self._value_provider = value_provider
        self._stop = threading.Event()

    def beat_once(self, *, key: str = "p054:trading:heartbeat", value: str | None = None) -> None:
        if value is None:
            value = (
                self._value_provider()
                if self._value_provider is not None
                else f"{int(time.time())}:0"
            )
        self._bus.set_key(key, value, self._ttl)

    def run(self) -> None:  # pragma: no cover - 线程循环
        while not self._stop.wait(self._interval):
            self.beat_once()

    def stop(self) -> None:
        self._stop.set()


if __name__ == "__main__":  # pragma: no cover
    main()
