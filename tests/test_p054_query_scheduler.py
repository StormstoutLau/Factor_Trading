"""P-054 E 组：查询调度器（最小间隔 / 单在途 / Full Jitter / 降级）（12 例）。"""

from __future__ import annotations

import random
import threading

import pytest

from core.circuit_breaker import CircuitConfig
from core.compliance import RateLimitConfig
from core.event_log import EventLog
from core.guard_pipeline import GuardPipeline
from core.safety import default_fault_policy
from live.adapters.mock import MockChannelAdapter
from live.channel import ChannelUnavailable
from live.gateway import TradingGateway
from live.ledger import Ledger
from live.ledger_store import SqliteLedgerStore
from live.query_scheduler import BackoffPolicy, QueryScheduler
from live.safety_gate import SafetyGate
from live.safety_store import SafetyStateStore

DAY = 1_700_000_000.0


class FakeTime:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def test_e1_minimum_interval():
    fake = FakeTime()
    scheduler = QueryScheduler(
        query_per_sec=1.0, clock=fake.clock, sleep=fake.sleep, backoff=BackoffPolicy()
    )
    scheduler.run(lambda: 1)
    scheduler.run(lambda: 2)
    assert sum(fake.sleeps) >= 1.0


def test_e2_single_in_flight():
    scheduler = QueryScheduler(query_per_sec=100.0)
    active = 0
    peak = 0
    lock = threading.Lock()

    def fn():
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        threading.Event().wait(0.01)
        with lock:
            active -= 1

    threads = [threading.Thread(target=scheduler.run, args=(fn,)) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert peak == 1


def test_e3_full_jitter_range():
    policy = BackoffPolicy(initial=1.0, factor=2.0, cap=5.0)
    rng = random.Random(7)
    samples = [policy.delay(1, rng) for _ in range(20)]
    assert all(0.0 <= s <= 1.0 for s in samples)
    assert min(samples) < 1.0


def test_e4_backoff_cap():
    assert BackoffPolicy(initial=1.0, factor=2.0, cap=5.0).high(10) == 5.0


def test_e5_max_attempts_then_raise():
    fake = FakeTime()
    scheduler = QueryScheduler(
        query_per_sec=1000.0,
        clock=fake.clock,
        sleep=fake.sleep,
        backoff=BackoffPolicy(max_attempts=5),
    )

    def fn():
        raise ChannelUnavailable("flow control")

    with pytest.raises(ChannelUnavailable):
        scheduler.run(fn)
    assert scheduler.attempts == 5
    assert len(fake.sleeps) == 4


def test_e6_startup_three_queries_serial():
    fake = FakeTime()
    scheduler = QueryScheduler(query_per_sec=1.0, clock=fake.clock, sleep=fake.sleep)
    calls: list[int] = []
    for i in range(3):
        scheduler.run(lambda i=i: calls.append(i))
    assert calls == [0, 1, 2]
    assert sum(fake.sleeps) >= 2.0


def test_e7_retry_then_success():
    fake = FakeTime()
    scheduler = QueryScheduler(
        query_per_sec=1000.0, clock=fake.clock, sleep=fake.sleep, backoff=BackoffPolicy()
    )
    attempts = {"n": 0}

    def fn():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise ChannelUnavailable("-3")
        return "ok"

    assert scheduler.run(fn) == "ok"
    assert scheduler.attempts == 3


def _make_gateway(tmp_path, adapter, *, scheduler=None):
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
    gateway = TradingGateway(
        adapter=adapter,
        gate=gate,
        ledger=Ledger(initial_cash=100_000.0),
        store=store,
        event_log=log,
        clock=lambda: DAY,
        scheduler=scheduler,
    )
    return gateway, store


def test_e8_trades_failure_fail_closed(tmp_path):
    class TradesDown(MockChannelAdapter):
        def query_trades(self, *, day):
            raise ChannelUnavailable("query_trades down")

    gateway, store = _make_gateway(tmp_path, TradesDown())
    with pytest.raises(ChannelUnavailable):
        gateway.start()
    assert store.get_meta("recovery_state") == "failed"
    store.close()


def test_e9_positions_failure_degrades(tmp_path):
    class PositionsDown(MockChannelAdapter):
        def query_positions(self):
            raise ChannelUnavailable("query_positions down")

    gateway, store = _make_gateway(tmp_path, PositionsDown())
    gateway.start()  # 不抛
    assert store.get_meta("recovery_state") == "degraded_positions"
    store.close()


def test_e10_orders_failure_fail_closed(tmp_path):
    class OrdersDown(MockChannelAdapter):
        def query_orders(self, *, day):
            raise ChannelUnavailable("query_orders down")

    gateway, store = _make_gateway(tmp_path, OrdersDown())
    with pytest.raises(ChannelUnavailable):
        gateway.start()
    store.close()


def test_e11_patrol_shares_scheduler(tmp_path):
    fake = FakeTime()
    scheduler = QueryScheduler(
        query_per_sec=1000.0, clock=fake.clock, sleep=fake.sleep, backoff=BackoffPolicy()
    )
    gateway, store = _make_gateway(tmp_path, MockChannelAdapter(), scheduler=scheduler)
    gateway.start()
    before = scheduler.calls
    gateway.reconcile(ts=DAY)
    assert scheduler.calls == before + 1
    store.close()


def test_e12_fake_clock_records_all_sleeps(tmp_path):
    fake = FakeTime()
    scheduler = QueryScheduler(query_per_sec=1.0, clock=fake.clock, sleep=fake.sleep)
    scheduler.run(lambda: None)
    scheduler.run(lambda: None)
    assert fake.sleeps and fake.now >= 1.0
