"""P-053 T 组：回报流、恢复与流控（T6，8 例）。"""

from __future__ import annotations

import pandas as pd
import pytest

from core.circuit_breaker import CircuitConfig
from core.compliance import RateLedger, RateLimitConfig
from core.event_log import EventLog
from core.execution_policy import OrderIntent
from core.guard_pipeline import GuardContext, GuardPipeline
from core.safety import KillLevel, default_fault_policy
from live.adapters.mock import FakeTransport, Frame, MockChannelAdapter
from live.channel import ChannelState, ChannelUnavailable
from live.gateway import TradingGateway
from live.ledger import Ledger
from live.ledger_store import SqliteLedgerStore
from live.orders import OrderRequest
from live.safety_gate import SafetyGate
from live.safety_store import SafetyStateStore

DAY = 1_700_000_000.0


class _ProbeAdapter(MockChannelAdapter):
    """记录恢复调用次序（T6 ①）。"""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    def connect(self) -> None:
        self.calls.append("connect")
        super().connect()

    def query_trades(self, *, day: str):
        self.calls.append("query_trades")
        return []

    def query_orders(self, *, day: str):
        self.calls.append("query_orders")
        return []

    def query_positions(self):
        self.calls.append("query_positions")
        return []


def _make_gate(log: EventLog, tmp_path, name: str = "state.json") -> SafetyGate:
    return SafetyGate(
        event_log=log,
        store=SafetyStateStore(tmp_path / name),
        rate_config=RateLimitConfig(max_per_second=0, max_per_day=0),
        circuit_config=CircuitConfig(),
        fault_policy=default_fault_policy(),
        pipeline=GuardPipeline([]),
    )


def _make_gateway(tmp_path, *, adapter=None, clock=lambda: DAY):
    log = EventLog(log_path=tmp_path / "events.jsonl")
    gate = _make_gate(log, tmp_path)
    ledger = Ledger(initial_cash=100_000.0)
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    gateway = TradingGateway(
        adapter=adapter or MockChannelAdapter(),
        gate=gate,
        ledger=ledger,
        store=store,
        event_log=log,
        clock=clock,
    )
    return gateway, gate, ledger, store


def _intent() -> OrderIntent:
    return OrderIntent(asset="AAA", asset_type="stock", target_quantity=100, current_quantity=0)


def _request() -> OrderRequest:
    return OrderRequest(
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


def _ctx() -> GuardContext:
    return GuardContext(
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


def _submit(gateway, *, ts: float = DAY):
    return gateway.submit(_intent(), _request(), _ctx(), account_id="ACC", strategy_id="S1", ts=ts)


def test_t6_recovery_order_trades_before_orders(tmp_path):
    probe = _ProbeAdapter()
    gateway, _gate, _ledger, store = _make_gateway(tmp_path, adapter=probe)
    gateway.start()
    assert probe.calls.index("query_trades") < probe.calls.index("query_orders")
    store.close()


def test_t6_reconnect_does_not_resend(tmp_path):
    transport = FakeTransport()
    adapter = MockChannelAdapter(transport)
    gateway, _gate, _ledger, store = _make_gateway(tmp_path, adapter=adapter)
    gateway.start()
    assert transport.sent == []
    _submit(gateway)
    assert len(transport.sent) == 1
    gateway.start()
    assert len(transport.sent) == 1
    store.close()


def test_t6_pending_unconfirmed_grace_window(tmp_path):
    now = {"t": DAY}
    gateway, _gate, _ledger, store = _make_gateway(tmp_path, clock=lambda: now["t"])
    gateway.start()
    _submit(gateway, ts=DAY)
    assert gateway.pending_unconfirmed() == []
    now["t"] = DAY + 61.0
    assert len(gateway.pending_unconfirmed()) == 1
    store.close()


def test_t6_query_bucket_one_per_second(tmp_path):
    gateway, _gate, _ledger, store = _make_gateway(tmp_path)
    gateway.start()
    gateway._query_config = RateLimitConfig(max_per_second=1, max_per_day=1000)
    gateway._query_ledger = RateLedger()
    gateway._throttle_query(1000.0)
    with pytest.raises(ChannelUnavailable, match="rate limited"):
        gateway._throttle_query(1000.0)
    gateway._throttle_query(1001.0)
    store.close()


def test_t6_rejected_updates_gate(tmp_path):
    transport = FakeTransport([Frame("reject", {"code": "E1", "reason": "bad"})])
    adapter = MockChannelAdapter(transport)
    gateway, gate, _ledger, store = _make_gateway(tmp_path, adapter=adapter)
    calls: list[bool] = []
    original = gate.on_order_result

    def spy(*, rejected: bool, ts: float):
        calls.append(rejected)
        return original(rejected=rejected, ts=ts)

    gate.on_order_result = spy
    gate_calls: list[int] = []  # F-R5-8：I5 直接断言「拒单前已过 pre_trade_check」
    original_gate = gate.pre_trade_check

    def gate_spy(*args, **kwargs):
        gate_calls.append(1)
        return original_gate(*args, **kwargs)

    gate.pre_trade_check = gate_spy
    result = _submit(gateway)
    assert result.accepted is False
    assert calls == [True]
    assert gate_calls == [1]
    assert transport.sent == []
    store.close()


def test_t6_kill_blocks_before_adapter(tmp_path):
    transport = FakeTransport()
    adapter = MockChannelAdapter(transport)
    gateway, gate, _ledger, store = _make_gateway(tmp_path, adapter=adapter)
    gateway.start()
    gate.gate_kill(KillLevel.GLOBAL, "", True, "test", ts=DAY)
    result = _submit(gateway)
    assert result.accepted is False
    assert any("kill" in reason for reason in result.reasons)
    assert transport.sent == []
    store.close()


def test_t6_cancel_all_uses_bridge(tmp_path):
    adapter = MockChannelAdapter()
    gateway, _gate, _ledger, store = _make_gateway(tmp_path, adapter=adapter)
    adapter.bridge.place_intents([_intent()], pd.Timestamp("2026-01-05"))
    assert gateway.cancel_all(ts=DAY) == 1
    store.close()


def test_t6_halted_rejects_new_order(tmp_path):
    transport = FakeTransport()
    adapter = MockChannelAdapter(transport)
    gateway, _gate, _ledger, store = _make_gateway(tmp_path, adapter=adapter)
    adapter.state = ChannelState.HALTED
    result = _submit(gateway)
    assert result.accepted is False
    assert result.reasons == ("channel_halted",)
    assert transport.sent == []
    store.close()
